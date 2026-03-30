from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from pathlib import Path
from threading import Lock, Thread
from typing import Any, Callable
from urllib.parse import parse_qs, quote_plus, urlparse
from uuid import uuid4

from sirius_toolbox.core.exceptions import LoginRequiredError, UserCancelledError
from sirius_toolbox.core.types import SourceProvider
from sirius_toolbox.settings import Settings
from sirius_toolbox.storage.jsonl_store import JsonlStore
from sirius_toolbox.tasks.handlers import handle_poi_task, handle_social_task
from sirius_toolbox.tasks.models import PoiCollectTask, SocialCollectTask


WEBUI_VERSION = "2026.03.30.22"


@dataclass(slots=True)
class AsyncTaskState:
    task_id: str
    task_type: str
    status: str
    progress: int
    message: str
    created_at: str
    started_at: str | None = None
    ended_at: str | None = None
    params: dict[str, Any] | None = None
    result_count: int | None = None
    error: str | None = None
    operation_logs: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "params": self.params or {},
            "result_count": self.result_count,
            "error": self.error,
            "operation_logs": list(self.operation_logs),
        }


class AsyncTaskManager:
    def __init__(self, max_tasks: int = 120) -> None:
        self._max_tasks = max_tasks
        self._tasks: dict[str, AsyncTaskState] = {}
        self._order: list[str] = []
        self._lock = Lock()

    def submit(
        self,
        task_type: str,
        params: dict[str, Any],
        runner: Callable[[Callable[[int, str], None]], int],
        task_id: str | None = None,
    ) -> str:
        task_id = task_id or uuid4().hex
        now = datetime.now().isoformat(timespec="seconds")
        state = AsyncTaskState(
            task_id=task_id,
            task_type=task_type,
            status="queued",
            progress=5,
            message="Task queued",
            created_at=now,
            params=params,
        )
        with self._lock:
            if task_id in self._tasks:
                task_id = uuid4().hex
            self._tasks[task_id] = state
            self._order.append(task_id)
            while len(self._order) > self._max_tasks:
                expired = self._order.pop(0)
                self._tasks.pop(expired, None)
        self._log_event(task_id, status="queued", progress=5, message="Task queued")

        worker = Thread(target=self._run_task, args=(task_id, runner), daemon=True)
        worker.start()
        return task_id

    def get(self, task_id: str) -> AsyncTaskState | None:
        with self._lock:
            return self._tasks.get(task_id)

    def recent(self, limit: int = 20) -> list[AsyncTaskState]:
        with self._lock:
            ids = list(reversed(self._order[-limit:]))
            return [self._tasks[i] for i in ids if i in self._tasks]

    def _update(
        self,
        task_id: str,
        *,
        status: str | None = None,
        progress: int | None = None,
        message: str | None = None,
        result_count: int | None = None,
        error: str | None = None,
        started_at: str | None = None,
        ended_at: str | None = None,
    ) -> None:
        with self._lock:
            state = self._tasks.get(task_id)
            if not state:
                return
            if status is not None:
                state.status = status
            if progress is not None:
                state.progress = max(0, min(100, progress))
            if message is not None:
                state.message = message
            if result_count is not None:
                state.result_count = result_count
            if error is not None:
                state.error = error
            if started_at is not None:
                state.started_at = started_at
            if ended_at is not None:
                state.ended_at = ended_at

    def _log_event(self, task_id: str, *, status: str, progress: int, message: str) -> None:
        with self._lock:
            state = self._tasks.get(task_id)
            if not state:
                return
            state.operation_logs.append(
                {
                    "time": datetime.now().isoformat(timespec="seconds"),
                    "status": status,
                    "progress": max(0, min(100, int(progress))),
                    "message": message,
                }
            )
            if len(state.operation_logs) > 240:
                state.operation_logs = state.operation_logs[-240:]

    def _run_task(
        self,
        task_id: str,
        runner: Callable[[Callable[[int, str], None]], int],
    ) -> None:
        self._update(
            task_id,
            status="running",
            progress=15,
            message="Task started",
            started_at=datetime.now().isoformat(timespec="seconds"),
        )
        self._log_event(task_id, status="running", progress=15, message="Task started")

        def report(progress: int, message: str) -> None:
            self._update(task_id, status="running", progress=progress, message=message)
            self._log_event(task_id, status="running", progress=progress, message=message)

        try:
            result_count = runner(report)
            self._update(
                task_id,
                status="succeeded",
                progress=100,
                message="Task completed",
                result_count=result_count,
                ended_at=datetime.now().isoformat(timespec="seconds"),
            )
            self._log_event(task_id, status="succeeded", progress=100, message="Task completed")
        except UserCancelledError as exc:
            self._update(
                task_id,
                status="cancelled",
                progress=100,
                message="Task cancelled by user action",
                error=str(exc),
                ended_at=datetime.now().isoformat(timespec="seconds"),
            )
            self._log_event(task_id, status="cancelled", progress=100, message=str(exc))
        except LoginRequiredError as exc:
            self._update(
                task_id,
                status="failed",
                progress=100,
                message="Login is required to continue",
                error=str(exc),
                ended_at=datetime.now().isoformat(timespec="seconds"),
            )
            self._log_event(task_id, status="failed", progress=100, message=str(exc))
        except Exception as exc:  # noqa: BLE001
            self._update(
                task_id,
                status="failed",
                progress=100,
                message="Task failed",
                error=str(exc),
                ended_at=datetime.now().isoformat(timespec="seconds"),
            )
            self._log_event(task_id, status="failed", progress=100, message=str(exc))


def _read_task_records(data_dir: Path, task_id: str, stream: str, limit: int = 30) -> list[dict[str, Any]]:
    target = data_dir / "curated" / "tasks" / task_id / f"{stream}.jsonl"
    if not target.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return list(reversed(rows))


def _read_recent_records(file_path: Path, limit: int = 30) -> list[dict]:
    if not file_path.exists():
        return []

    lines = file_path.read_text(encoding="utf-8").splitlines()
    records: list[dict] = []
    for line in lines[-limit:]:
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(records))


def _read_recent_records_from_tasks(data_dir: Path, stream: str, limit: int = 30) -> list[dict]:
    task_root = data_dir / "curated" / "tasks"
    if not task_root.exists():
        return []

    files = sorted(
        task_root.glob(f"*/{stream}.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    records: list[dict] = []
    for file_path in files:
        lines = file_path.read_text(encoding="utf-8").splitlines()
        for line in reversed(lines):
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(records) >= limit:
                return records
    return records


def read_recent_poi_records(data_dir: Path, limit: int = 30) -> list[dict]:
    task_records = _read_recent_records_from_tasks(data_dir, "poi", limit=limit)
    if task_records:
        return task_records
    return _read_recent_records(data_dir / "curated" / "poi.jsonl", limit=limit)


def read_recent_social_records(data_dir: Path, limit: int = 30) -> list[dict]:
    task_records = _read_recent_records_from_tasks(data_dir, "social_post", limit=limit)
    if task_records:
        return task_records
    return _read_recent_records(data_dir / "curated" / "social_post.jsonl", limit=limit)


class SiriusWebUIHandler(BaseHTTPRequestHandler):
    settings: Settings
    logger: logging.Logger
    data_dir: Path
    task_manager: AsyncTaskManager

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        message = params.get("message", [""])[0]
        status = params.get("status", ["info"])[0]

        if parsed.path.startswith("/data/"):
            self._write_static_file(parsed.path)
            return

        if parsed.path == "/":
            self._write_html(self._render_index(message=message, status=status))
            return

        if parsed.path == "/poi":
            self._write_html(self._render_poi_page(message=message, status=status))
            return

        if parsed.path == "/xhs":
            self._write_html(self._render_xhs_page(message=message, status=status))
            return

        if parsed.path == "/tasks":
            task_id = params.get("task_id", [""])[0].strip()
            self._write_html(self._render_tasks_page(task_id=task_id, message=message, status=status))
            return

        if parsed.path.startswith("/api/tasks/"):
            task_id = parsed.path.removeprefix("/api/tasks/").strip()
            self._write_task_detail_json(task_id)
            return

        if parsed.path.startswith("/api/task-results/"):
            task_id = parsed.path.removeprefix("/api/task-results/").strip()
            self._write_task_result_json(task_id)
            return

        if parsed.path == "/api/tasks":
            self._write_task_list_json(limit=20)
            return

        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"Not Found")

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/collect-poi":
            self._handle_collect_poi()
            return

        if self.path == "/collect-xhs":
            self._handle_collect_xhs()
            return

        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"Not Found")

    def _handle_collect_poi(self) -> None:
        try:
            form = self._read_post_form()
            provider = form.get("provider", [""])[0]
            keyword = form.get("keyword", [""])[0].strip()
            city = form.get("city", [""])[0].strip()
            page_size = self._safe_int(form.get("page_size", ["20"])[0], default=20)
            max_pages = self._safe_int(form.get("max_pages", ["2"])[0], default=2)

            if provider not in {"gaode", "baidu"}:
                raise ValueError("provider must be gaode or baidu")
            if not keyword:
                raise ValueError("keyword is required")
            if not city:
                raise ValueError("city is required")

            task = PoiCollectTask(
                source=SourceProvider(provider),
                keyword=keyword,
                city=city,
                page_size=page_size,
                max_pages=max_pages,
            )

            def runner(report: Callable[[int, str], None]) -> int:
                report(25, "Preparing POI collection")
                store = JsonlStore(self.data_dir)
                try:
                    report(60, "Collecting and normalizing POI pages")
                    count = handle_poi_task(task, store, self.settings)
                    report(95, "Finalizing records")
                    return count
                finally:
                    store.close()

            task_id = self.task_manager.submit(
                task_type="poi",
                params={
                    "provider": provider,
                    "keyword": keyword,
                    "city": city,
                    "page_size": page_size,
                    "max_pages": max_pages,
                },
                runner=runner,
                task_id=task.task_id,
            )

            msg = quote_plus(f"POI task submitted. task_id={task_id}")
            self._redirect(f"/tasks?status=ok&message={msg}&task_id={task_id}")
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("webui_collect_poi_failed")
            msg = quote_plus(f"Failed: {exc}")
            self._redirect(f"/poi?status=error&message={msg}")

    def _handle_collect_xhs(self) -> None:
        try:
            form = self._read_post_form()
            keyword = form.get("keyword", [""])[0].strip()
            max_items = self._safe_int(form.get("max_items", ["10"])[0], default=10)
            debug = form.get("debug", ["0"])[0] == "1"

            if not keyword:
                raise ValueError("keyword is required")

            task = SocialCollectTask(
                source=SourceProvider.XIAOHONGSHU,
                keyword=keyword,
                max_items=max_items,
                headless=False,
                debug=debug,
            )

            def runner(report: Callable[[int, str], None]) -> int:
                report(25, "Launching collector")
                store = JsonlStore(self.data_dir)
                try:
                    report(35, "Collecting posts (may wait for login in headed mode)")
                    count = handle_social_task(task, store, self.settings, progress=report)
                    report(95, "Finalizing posts")
                    return count
                finally:
                    store.close()

            task_id = self.task_manager.submit(
                task_type="xhs",
                params={
                    "keyword": keyword,
                    "max_items": max_items,
                    "headless": False,
                    "debug": debug,
                },
                runner=runner,
                task_id=task.task_id,
            )

            msg = quote_plus(f"XHS task submitted. task_id={task_id}")
            self._redirect(f"/tasks?status=ok&message={msg}&task_id={task_id}")
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("webui_collect_xhs_failed")
            msg = quote_plus(f"Failed: {exc}")
            self._redirect(f"/xhs?status=error&message={msg}")

    def _read_post_form(self) -> dict[str, list[str]]:
        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length).decode("utf-8")
        return parse_qs(body)

    def _write_html(self, html: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _write_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def _write_static_file(self, request_path: str) -> None:
        rel_path = request_path.lstrip("/").replace("/", "\\")
        target = (Path.cwd() / rel_path).resolve()
        base = (Path.cwd() / "data").resolve()
        if base not in target.parents and target != base:
            self.send_response(403)
            self.end_headers()
            return
        if not target.exists() or not target.is_file():
            self.send_response(404)
            self.end_headers()
            return

        suffix = target.suffix.lower()
        content_type = "application/octet-stream"
        if suffix in {".jpg", ".jpeg"}:
            content_type = "image/jpeg"
        elif suffix == ".png":
            content_type = "image/png"
        elif suffix == ".webp":
            content_type = "image/webp"
        elif suffix == ".gif":
            content_type = "image/gif"
        elif suffix == ".json":
            content_type = "application/json; charset=utf-8"
        elif suffix == ".html":
            content_type = "text/html; charset=utf-8"

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(target.read_bytes())

    def _write_task_detail_json(self, task_id: str) -> None:
        if not task_id:
            self._write_json({"error": "task_id is required"}, status=400)
            return

        state = self.task_manager.get(task_id)
        if not state:
            self._write_json({"error": "task not found", "task_id": task_id}, status=404)
            return

        self._write_json({"task": state.to_dict()})

    def _write_task_list_json(self, limit: int = 20) -> None:
        tasks = [item.to_dict() for item in self.task_manager.recent(limit=limit)]
        self._write_json({"tasks": tasks})

    def _write_task_result_json(self, task_id: str) -> None:
        if not task_id:
            self._write_json({"error": "task_id is required"}, status=400)
            return

        poi_rows = _read_task_records(self.data_dir, task_id, "poi", limit=12)
        social_rows = _read_task_records(self.data_dir, task_id, "social_post", limit=12)
        self._write_json(
            {
                "task_id": task_id,
                "poi": poi_rows,
                "social_post": social_rows,
            }
        )

    def _render_flash(self, message: str, status: str) -> str:
        if not message:
            return ""
        cls = "ok" if status == "ok" else "error"
        return f'<div class="flash {cls}">{escape(message)}</div>'

    def _layout(self, *, title: str, body_html: str, message: str = "", status: str = "info") -> str:
        message_html = self._render_flash(message, status)
        return f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{escape(title)}</title>
    <style>
        :root {{
            --bg1: #f7fbff;
            --bg2: #ecf7ef;
      --ink: #102235;
      --accent: #0f766e;
      --danger: #9f1239;
      --card: #ffffffee;
      --line: #dbe6f0;
    }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      color: var(--ink);
      background: radial-gradient(1200px 500px at 5% -10%, #d5e8ff 0%, transparent 60%),
                  radial-gradient(1100px 500px at 110% 10%, #d8f4e0 0%, transparent 60%),
                  linear-gradient(160deg, var(--bg1), var(--bg2));
      min-height: 100vh;
    }}
    .wrap {{ max-width: 1080px; margin: 28px auto; padding: 0 16px; }}
    .card {{ background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 18px; backdrop-filter: blur(3px); }}
    .topnav {{ display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }}
    .navbtn {{
      text-decoration: none;
      border-radius: 10px;
      border: 1px solid #c6d5e4;
      padding: 8px 12px;
      color: #1f3850;
      background: #fff;
      font-size: 14px;
    }}
    h1 {{ margin-top: 0; font-weight: 700; }}
    .flash {{ margin: 10px 0 14px; padding: 10px 12px; border-radius: 10px; font-size: 14px; }}
    .flash.ok {{ background: #dbfce7; color: #14532d; }}
    .flash.error {{ background: #ffe4e6; color: #9f1239; }}
    form {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; align-items: end; }}
    label {{ font-size: 12px; color: #314a60; display: block; margin-bottom: 4px; }}
    input, select, button {{ width: 100%; box-sizing: border-box; padding: 10px; border-radius: 10px; border: 1px solid #c6d5e4; background: #fff; }}
    button {{ border: none; background: var(--accent); color: #fff; font-weight: 600; cursor: pointer; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
    th, td {{ border-bottom: 1px solid var(--line); text-align: left; padding: 10px 8px; font-size: 14px; }}
    .meta {{ margin-top: 8px; font-size: 12px; color: #415a72; }}
    .footer-meta {{ margin-top: 14px; padding-top: 10px; border-top: 1px dashed #cfe0ee; display: flex; gap: 10px; flex-wrap: wrap; }}
        .status-pill {{ display: inline-block; padding: 4px 8px; border-radius: 999px; font-size: 12px; border: 1px solid #c6d5e4; background: #eef3f8; }}
        .status-running {{ background: #dbeafe; color: #1e3a8a; border-color: #bfdbfe; }}
        .status-succeeded {{ background: #dcfce7; color: #166534; border-color: #86efac; }}
        .status-failed {{ background: #ffe4e6; color: #9f1239; border-color: #fda4af; }}
        .status-cancelled {{ background: #f3f4f6; color: #374151; border-color: #d1d5db; }}
        .status-queued {{ background: #fef9c3; color: #854d0e; border-color: #fde68a; }}
        .task-grid {{ display: grid; grid-template-columns: 1.1fr 0.9fr; gap: 16px; }}
        .task-panel {{ border: 1px solid var(--line); border-radius: 12px; padding: 14px; background: #fff; }}
          .task-span-2 {{ grid-column: 1 / span 2; }}
        .progress-track {{ width: 100%; height: 12px; border-radius: 999px; background: #e5edf6; overflow: hidden; border: 1px solid #d7e2ed; }}
        .progress-fill {{ height: 100%; width: 0%; background: linear-gradient(90deg, #0f766e, #14b8a6, #0f766e); background-size: 200% 100%; animation: pulsebar 1.8s linear infinite; transition: width .35s ease; }}
        .muted {{ color: #4b6178; font-size: 13px; }}
        .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; color: #24384d; word-break: break-all; }}
          .log-table td, .log-table th {{ font-size: 12px; padding: 8px 6px; }}
          .result-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; margin-top: 8px; }}
          .result-card {{ border: 1px solid var(--line); border-radius: 10px; padding: 10px; background: #fbfdff; }}
          .result-title {{ font-weight: 600; margin-bottom: 6px; font-size: 13px; }}
          .result-text {{ font-size: 12px; color: #334d63; max-height: 80px; overflow: auto; white-space: pre-wrap; }}
          .inline-imgs {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; margin-top: 8px; }}
          .inline-imgs img {{ width: 100%; height: 70px; object-fit: cover; border-radius: 6px; border: 1px solid #dbe6f0; }}
        @keyframes pulsebar {{ 0% {{ background-position: 0% 50%; }} 100% {{ background-position: 200% 50%; }} }}
          @media (max-width: 900px) {{ .task-grid {{ grid-template-columns: 1fr; }} .task-span-2 {{ grid-column: auto; }} }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"card\">
      <div class=\"topnav\">
        <a class=\"navbtn\" href=\"/\">Home</a>
        <a class=\"navbtn\" href=\"/poi\">POI Collect</a>
        <a class=\"navbtn\" href=\"/xhs\">XHS Collect</a>
                <a class=\"navbtn\" href=\"/tasks\">Task Status</a>
      </div>
      {message_html}
      {body_html}
            <div class="meta footer-meta">
                <span>Updated at: {escape(datetime.now().isoformat(timespec='seconds'))}</span>
                <span>WebUI Version: {escape(WEBUI_VERSION)}</span>
            </div>
    </div>
  </div>
</body>
</html>"""

    def _render_index(self, message: str, status: str) -> str:
        body_html = """
        <h1>SiriusToolbox WebUI</h1>
        <p>功能已拆分为独立页面，请从上方导航进入对应模块。</p>
        <ul>
          <li>POI Collect: 高德/百度 POI 抓取任务提交</li>
          <li>XHS Collect: 小红书关键词 + 阈值抓取任务提交</li>
                    <li>Task Status: 异步任务状态、操作日志与结果可视化</li>
        </ul>
        """
        return self._layout(title="SiriusToolbox WebUI", body_html=body_html, message=message, status=status)

    def _render_poi_page(self, message: str, status: str) -> str:
        body_html = """
        <h1>POI Collection</h1>
        <p>提交地图 POI 采集任务（高德/百度）。</p>
        <form method=\"post\" action=\"/collect-poi\">
          <div>
            <label>Provider</label>
            <select name=\"provider\"><option value=\"gaode\">gaode</option><option value=\"baidu\">baidu</option></select>
          </div>
          <div>
            <label>Keyword</label>
            <input name=\"keyword\" placeholder=\"coffee\" required />
          </div>
          <div>
            <label>City</label>
            <input name=\"city\" placeholder=\"beijing\" required />
          </div>
          <div>
            <label>Page Size</label>
            <input type=\"number\" name=\"page_size\" value=\"20\" min=\"1\" max=\"50\" />
          </div>
          <div>
            <label>Max Pages</label>
            <input type=\"number\" name=\"max_pages\" value=\"2\" min=\"1\" max=\"20\" />
          </div>
          <div>
            <button type=\"submit\">Run POI Collection</button>
          </div>
        </form>
        """
        return self._layout(title="POI Collection", body_html=body_html, message=message, status=status)

    def _render_xhs_page(self, message: str, status: str) -> str:
        body_html = """
        <h1>Xiaohongshu Collection</h1>
        <p>输入关键词并设置阈值（最大访问帖子数量）抓取帖子内容与图片。</p>
        <p>当检测到需要登录时，任务会暂停并等待你在弹出的浏览器中完成登录；如果你关闭浏览器窗口，任务将立即终止。</p>
        <form method=\"post\" action=\"/collect-xhs\">
          <div>
            <label>Keyword</label>
            <input name=\"keyword\" placeholder=\"护肤\" required />
          </div>
          <div>
            <label>Threshold(Max Posts)</label>
            <input type=\"number\" name=\"max_items\" value=\"10\" min=\"1\" max=\"50\" />
          </div>
                    <div>
                        <label>Debug Mode</label>
                        <select name=\"debug\"><option value=\"1\">on</option><option value=\"0\" selected>off</option></select>
                    </div>
          <div>
            <button type=\"submit\">Run XHS Collection</button>
          </div>
        </form>
        """
        return self._layout(title="XHS Collection", body_html=body_html, message=message, status=status)

    @staticmethod
    def _status_class(status: str) -> str:
        return {
            "queued": "status-queued",
            "running": "status-running",
            "succeeded": "status-succeeded",
            "failed": "status-failed",
            "cancelled": "status-cancelled",
        }.get(status, "")

    @staticmethod
    def _format_task_meta(state: AsyncTaskState) -> str:
        pieces = [f"created={state.created_at}"]
        if state.started_at:
            pieces.append(f"started={state.started_at}")
        if state.ended_at:
            pieces.append(f"ended={state.ended_at}")
        return " | ".join(pieces)

    def _push_task_records_to_webui(self, focus: AsyncTaskState | None) -> dict[str, Any]:
        if not focus:
            return {
                "logs": [],
                "social_rows": [],
                "poi_rows": [],
            }

        # Server-side push: build a consistent task snapshot for one-page rendering.
        return {
            "logs": list(reversed(focus.operation_logs)),
            "social_rows": _read_task_records(self.data_dir, focus.task_id, "social_post", limit=12),
            "poi_rows": _read_task_records(self.data_dir, focus.task_id, "poi", limit=20),
        }

    @staticmethod
    def _export_html_button(task_id: str) -> str:
        clean = task_id.strip()
        if not clean:
            return ""
        href = f"/data/exports/tasks/{escape(clean)}/social_posts.html"
        return (
            "<div style='margin-bottom:10px;'>"
            f"<a class='navbtn' href='{href}' target='_blank' rel='noreferrer'>Open Task HTML Report</a>"
            "</div>"
        )

    def _render_tasks_page(self, task_id: str, message: str, status: str) -> str:
        recent = self.task_manager.recent(limit=18)
        focus = self.task_manager.get(task_id) if task_id else (recent[0] if recent else None)
        task_payload = self._push_task_records_to_webui(focus)

        detail_html = "<h2>No tasks yet</h2><p class='muted'>提交 POI 或 XHS 任务后，这里会显示任务状态。</p>"
        focus_task_id = ""
        if focus:
            focus_task_id = focus.task_id
            status_cls = self._status_class(focus.status)
            progress = max(0, min(100, focus.progress))
            detail_html = (
                "<h2>Task Detail</h2>"
                f"<div class='mono'>task_id: {escape(focus.task_id)}</div>"
                f"<p><span id='task-status' class='status-pill {status_cls}'>{escape(focus.status)}</span></p>"
                "<div class='progress-track'><div id='task-progress-fill' class='progress-fill' "
                f"style='width:{progress}%;'></div></div>"
                f"<p id='task-progress-text' class='muted'>Progress: {progress}%</p>"
                f"<p id='task-message' class='muted'>{escape(focus.message)}</p>"
                f"<p id='task-result' class='muted'>Result Count: {'' if focus.result_count is None else focus.result_count}</p>"
                f"<p id='task-error' class='muted'>Error: {escape(focus.error or '')}</p>"
                f"<p id='task-meta' class='muted'>{escape(self._format_task_meta(focus))}</p>"
            )

        list_rows = ""
        for item in recent:
            status_cls = self._status_class(item.status)
            list_rows += (
                "<tr>"
                f"<td><a href='/tasks?task_id={escape(item.task_id)}'>{escape(item.task_id[:10])}...</a></td>"
                f"<td>{escape(item.task_type)}</td>"
                f"<td><span class='status-pill {status_cls}'>{escape(item.status)}</span></td>"
                f"<td>{item.progress}%</td>"
                f"<td>{escape(item.created_at)}</td>"
                "</tr>"
            )
        if not list_rows:
            list_rows = "<tr><td colspan='5'>No submitted tasks</td></tr>"

        logs_html = "<p class='muted'>暂无操作记录。</p>"
        result_html = "<p class='muted'>暂无结果数据。</p>"
        if focus:
            export_btn = self._export_html_button(focus.task_id)
            events = task_payload["logs"]

            def _event_row(event: dict[str, Any]) -> str:
                event_status = str(event.get("status") or "running")
                event_cls = self._status_class(event_status)
                return (
                    "<tr>"
                    f"<td>{escape(str(event.get('time') or ''))}</td>"
                    f"<td><span class='status-pill {event_cls}'>{escape(event_status)}</span></td>"
                    f"<td>{escape(str(event.get('progress') or 0))}%</td>"
                    f"<td>{escape(str(event.get('message') or ''))}</td>"
                    "</tr>"
                )

            latest_events = events[:3]
            older_events = events[3:]
            latest_rows = "".join(_event_row(event) for event in latest_events)
            older_rows = "".join(_event_row(event) for event in older_events)
            if latest_rows:
                logs_html = (
                    "<table class='log-table'><thead><tr><th>Time</th><th>Status</th><th>Progress</th><th>Step</th></tr></thead>"
                    f"<tbody id='task-log-body'>{latest_rows}</tbody></table>"
                )
                if older_rows:
                    logs_html += (
                        "<details id='task-log-more' style='margin-top:8px;'>"
                        f"<summary class='muted'>查看更早步骤（{len(older_events)} 条）</summary>"
                        "<table class='log-table'><tbody id='task-log-body-more'>"
                        f"{older_rows}</tbody></table></details>"
                    )

            social_rows = task_payload["social_rows"]
            poi_rows = task_payload["poi_rows"]
            if social_rows:
                cards = ""
                for row in social_rows:
                    raw_title = str(row.get("title") or "").strip()
                    raw_text = str(row.get("text") or "").strip()
                    first_line = raw_text.splitlines()[0] if raw_text else ""
                    if raw_title:
                        show_title = raw_title
                    elif first_line:
                        show_title = first_line[:36] + ("..." if len(first_line) > 36 else "")
                    else:
                        show_title = str(row.get("source_id") or "(untitled)")
                    title = escape(show_title)
                    text = escape(str(row.get("text") or "")[:120])
                    author = escape(str(row.get("author") or ""))
                    raw_images = row.get("local_images")
                    local_images = [str(item) for item in raw_images] if isinstance(raw_images, list) else []
                    imgs = ""
                    for img in local_images[:3]:
                        safe = escape(str(img).replace("\\", "/").lstrip("/"))
                        imgs += f"<a href='/{safe}' target='_blank' rel='noreferrer'><img src='/{safe}' loading='lazy' /></a>"
                    img_block = f"<div class='inline-imgs'>{imgs}</div>" if imgs else ""
                    cards += (
                        "<article class='result-card'>"
                        f"<div class='result-title'>{title}</div>"
                        f"<div class='muted'>author={author}</div>"
                        f"<div class='result-text'>{text}</div>"
                        f"{img_block}"
                        "</article>"
                    )
                result_html = (
                    f"{export_btn}"
                    f"<h3>XHS Result Preview</h3><div id='task-result-view' class='result-grid'>{cards}</div>"
                )
            elif poi_rows:
                poi_table = ""
                for row in poi_rows:
                    poi_table += (
                        "<tr>"
                        f"<td>{escape(str(row.get('name') or ''))}</td>"
                        f"<td>{escape(str(row.get('city') or ''))}</td>"
                        f"<td>{escape(str(row.get('address') or ''))}</td>"
                        f"<td>{escape(str(row.get('provider') or ''))}</td>"
                        "</tr>"
                    )
                result_html = (
                    "<h3>POI Result Preview</h3>"
                    "<table id='task-result-view'><thead><tr><th>Name</th><th>City</th><th>Address</th><th>Provider</th></tr></thead>"
                    f"<tbody>{poi_table}</tbody></table>"
                )
            else:
                result_html = f"{export_btn}<p class='muted'>暂无结果数据。</p>"

        body_html = (
            "<h1>Async Task Status</h1>"
            "<p>采集任务会在后台执行，页面会自动更新最新状态与操作历史。</p>"
            "<div class='task-grid'>"
            f"<div class='task-panel'>{detail_html}</div>"
            "<div class='task-panel'>"
            "<h2>Recent Tasks</h2>"
            "<table><thead><tr><th>Task ID</th><th>Type</th><th>Status</th><th>Progress</th><th>Created</th></tr></thead>"
            f"<tbody>{list_rows}</tbody></table>"
            "</div>"
            f"<div class='task-panel task-span-2'><h2>Task Operation History</h2><div id='task-log-wrap'>{logs_html}</div></div>"
            f"<div class='task-panel task-span-2'><h2>Task Output Visualization</h2><div id='task-result-wrap'>{result_html}</div></div>"
            "</div>"
            f"<script>{self._build_task_live_script(focus_task_id)}</script>"
        )
        return self._layout(title="Task Status", body_html=body_html, message=message, status=status)

    def _build_task_live_script(self, task_id: str) -> str:
        if not task_id:
            return ""

        return f"""
        (function () {{
          const taskId = {json.dumps(task_id)};
          const statusEl = document.getElementById('task-status');
          const progressFill = document.getElementById('task-progress-fill');
          const progressText = document.getElementById('task-progress-text');
          const messageEl = document.getElementById('task-message');
          const resultEl = document.getElementById('task-result');
          const errorEl = document.getElementById('task-error');
          const metaEl = document.getElementById('task-meta');
          const logWrap = document.getElementById('task-log-wrap');
          const resultWrap = document.getElementById('task-result-wrap');

          const clsMap = {{
            queued: 'status-queued',
            running: 'status-running',
            succeeded: 'status-succeeded',
            failed: 'status-failed',
            cancelled: 'status-cancelled'
          }};

          function applyStatusClass(el, status) {{
            if (!el) return;
            el.className = 'status-pill ' + (clsMap[status] || '');
          }}

          function escapeHtml(s) {{
            return String(s || '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
          }}

          function toRow(e) {{
            const st = e.status || 'running';
            return `<tr><td>${{escapeHtml(e.time)}}</td><td><span class="status-pill ${{clsMap[st] || ''}}">${{escapeHtml(st)}}</span></td><td>${{escapeHtml(e.progress)}}%</td><td>${{escapeHtml(e.message)}}</td></tr>`;
          }}

          function renderLogs(logs) {{
            if (!logWrap) return;
            if (!Array.isArray(logs) || logs.length === 0) {{
              logWrap.innerHTML = "<p class='muted'>暂无操作记录。</p>";
              return;
            }}

            const ordered = logs.slice().reverse();
            const latest = ordered.slice(0, 3);
            const older = ordered.slice(3);
            const latestRows = latest.map((e) => toRow(e)).join('');
            const olderRows = older.map((e) => toRow(e)).join('');
            const oldDetails = document.getElementById('task-log-more');
            const keepOpen = !!(oldDetails && oldDetails.open);

            let html = `<table class='log-table'><thead><tr><th>Time</th><th>Status</th><th>Progress</th><th>Step</th></tr></thead><tbody id='task-log-body'>${{latestRows}}</tbody></table>`;
            if (olderRows) {{
              html += `<details id='task-log-more' style='margin-top:8px;'><summary class='muted'>查看更早步骤（${{older.length}} 条）</summary><table class='log-table'><tbody id='task-log-body-more'>${{olderRows}}</tbody></table></details>`;
            }}
            logWrap.innerHTML = html;
            const newDetails = document.getElementById('task-log-more');
            if (newDetails) newDetails.open = keepOpen;
          }}

          function renderResult(data) {{
            if (!resultWrap) return;
                        const reportButton = `<div style='margin-bottom:10px;'><a class='navbtn' href='/data/exports/tasks/${{encodeURIComponent(taskId)}}/social_posts.html' target='_blank' rel='noreferrer'>Open Task HTML Report</a></div>`;
            if (Array.isArray(data.social_post) && data.social_post.length > 0) {{
              let cards = '';
              for (const row of data.social_post) {{
                const images = Array.isArray(row.local_images) ? row.local_images.slice(0, 3) : [];
                const imgs = images.map((p) => {{
                  const normalized = String(p).replaceAll('\\\\', '/');
                  const clean = normalized.startsWith('/') ? normalized.slice(1) : normalized;
                  const url = `/${{encodeURI(clean)}}`;
                  return `<a href='${{url}}' target='_blank' rel='noreferrer'><img src='${{url}}' loading='lazy' /></a>`;
                }}).join('');
                const titleRaw = String(row.title || '').trim();
                const textRaw = String(row.text || '').trim();
                                const firstLine = textRaw
                                    .replaceAll(String.fromCharCode(13), '')
                                    .split(String.fromCharCode(10))[0] || '';
                const title = titleRaw || (firstLine ? (firstLine.length > 36 ? firstLine.slice(0, 36) + '...' : firstLine) : String(row.source_id || '(untitled)'));
                cards += `<article class='result-card'><div class='result-title'>${{escapeHtml(title)}}</div><div class='muted'>author=${{escapeHtml(row.author || '')}}</div><div class='result-text'>${{escapeHtml((row.text || '').slice(0, 120))}}</div>${{imgs ? `<div class='inline-imgs'>${{imgs}}</div>` : ''}}</article>`;
              }}
                            resultWrap.innerHTML = `${{reportButton}}<h3>XHS Result Preview</h3><div id='task-result-view' class='result-grid'>${{cards}}</div>`;
              return;
            }}
            if (Array.isArray(data.poi) && data.poi.length > 0) {{
              const rows = data.poi.map((r) => `<tr><td>${{escapeHtml(r.name)}}</td><td>${{escapeHtml(r.city)}}</td><td>${{escapeHtml(r.address)}}</td><td>${{escapeHtml(r.provider)}}</td></tr>`).join('');
              resultWrap.innerHTML = `<h3>POI Result Preview</h3><table id='task-result-view'><thead><tr><th>Name</th><th>City</th><th>Address</th><th>Provider</th></tr></thead><tbody>${{rows}}</tbody></table>`;
              return;
            }}
                        resultWrap.innerHTML = reportButton + "<p class='muted'>暂无结果数据。</p>";
          }}

          function refresh() {{
            fetch('/api/tasks/' + encodeURIComponent(taskId), {{ cache: 'no-store' }})
              .then((resp) => resp.json())
              .then((data) => {{
                if (!data.task) return;
                const task = data.task;
                if (statusEl) {{
                  statusEl.textContent = task.status;
                  applyStatusClass(statusEl, task.status);
                }}
                const progress = Math.max(0, Math.min(100, Number(task.progress || 0)));
                if (progressFill) progressFill.style.width = progress + '%';
                if (progressText) progressText.textContent = 'Progress: ' + progress + '%';
                if (messageEl) messageEl.textContent = task.message || '';
                if (resultEl) resultEl.textContent = 'Result Count: ' + (task.result_count ?? '');
                if (errorEl) errorEl.textContent = 'Error: ' + (task.error || '');
                const parts = ['created=' + (task.created_at || '')];
                if (task.started_at) parts.push('started=' + task.started_at);
                if (task.ended_at) parts.push('ended=' + task.ended_at);
                if (metaEl) metaEl.textContent = parts.join(' | ');
                renderLogs(task.operation_logs || []);
              }})
              .catch(() => null);

            fetch('/api/task-results/' + encodeURIComponent(taskId), {{ cache: 'no-store' }})
              .then((resp) => resp.json())
              .then((payload) => renderResult(payload))
              .catch(() => null);
          }}

          refresh();
          window.setInterval(refresh, 1200);
        }})();
        """

    def log_message(self, format: str, *args: object) -> None:
        self.logger.info("webui_http " + format, *args)

    def _redirect(self, location: str) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    @staticmethod
    def _safe_int(raw: str, default: int) -> int:
        try:
            return int(raw)
        except ValueError:
            return default


def start_webui(settings: Settings, logger: logging.Logger, host: str, port: int) -> None:
    SiriusWebUIHandler.settings = settings
    SiriusWebUIHandler.logger = logger
    SiriusWebUIHandler.data_dir = Path(settings.data_dir)
    SiriusWebUIHandler.task_manager = AsyncTaskManager()
    SiriusWebUIHandler.data_dir.mkdir(parents=True, exist_ok=True)

    server = ThreadingHTTPServer((host, port), SiriusWebUIHandler)
    access_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    access_url = f"http://{access_host}:{port}"
    logger.info("webui_started access_url=%s", access_url)
    server.serve_forever()
