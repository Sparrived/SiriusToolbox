from contextlib import suppress
import json
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import httpx

from sirius_toolbox.collectors.browser.xiaohongshu.collector import XiaohongshuCollector
from sirius_toolbox.collectors.maps.baidu.client import BaiduPoiClient
from sirius_toolbox.collectors.maps.baidu.mapper import map_baidu_poi
from sirius_toolbox.collectors.maps.gaode.client import GaodePoiClient
from sirius_toolbox.collectors.maps.gaode.mapper import map_gaode_poi
from sirius_toolbox.core.types import SourceProvider
from sirius_toolbox.exporters.social_report import export_social_records
from sirius_toolbox.settings import Settings
from sirius_toolbox.storage.base import Storage
from sirius_toolbox.tasks.models import PoiCollectTask, SocialCollectTask, TaskBase


def _safe_name(value: str) -> str:
    compact = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value.strip())
    compact = compact.strip("_")
    return compact[:80] if compact else "item"


def _guess_ext_from_url(url: str) -> str:
    try:
        suffix = Path(urlparse(url).path).suffix.lower()
    except Exception:
        suffix = ""
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"} else ".jpg"


def _persist_social_assets(
    *,
    data_dir: str,
    task_id: str,
    index: int,
    post: dict[str, Any],
) -> tuple[str, list[str]]:
    workspace_root = Path.cwd().resolve()

    def _to_workspace_relative(path: Path) -> str:
        resolved = path.resolve()
        with suppress(Exception):
            return resolved.relative_to(workspace_root).as_posix()
        return resolved.as_posix()

    source_id = _safe_name(str(post.get("source_id") or f"post_{index}"))
    post_dir = Path(data_dir) / "raw" / "xiaohongshu" / task_id / "posts" / source_id
    image_dir = post_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    item_path = post_dir / "post.json"
    item_payload = dict(post)
    item_payload["task_id"] = task_id
    item_path.write_text(json.dumps(item_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    downloaded: list[str] = []
    image_urls = post.get("images") if isinstance(post.get("images"), list) else []
    if image_urls:
        with suppress(Exception):
            with httpx.Client(timeout=20.0, follow_redirects=True) as client:
                for pos, image_url in enumerate(image_urls, start=1):
                    if not image_url:
                        continue
                    ext = _guess_ext_from_url(str(image_url))
                    image_path = image_dir / f"{pos:02d}{ext}"
                    try:
                        response = client.get(str(image_url))
                        response.raise_for_status()
                    except Exception:
                        continue
                    image_path.write_bytes(response.content)
                    downloaded.append(_to_workspace_relative(image_path))

    return _to_workspace_relative(item_path), downloaded


def _select_map_components(
    source: SourceProvider, settings: Settings
) -> tuple[Any, Callable[[dict[str, Any]], dict[str, Any]], str, str]:
    if source == SourceProvider.GAODE:
        if not settings.gaode_api_key:
            raise ValueError("GAODE_API_KEY is required for gaode provider")
        return GaodePoiClient(settings.gaode_api_key), map_gaode_poi, "pois", "gaode"

    if source == SourceProvider.BAIDU:
        if not settings.baidu_api_key:
            raise ValueError("BAIDU_API_KEY is required for baidu provider")
        return BaiduPoiClient(settings.baidu_api_key), map_baidu_poi, "results", "baidu"

    raise ValueError(f"unsupported source provider: {source}")


def handle_poi_task(task: TaskBase, store: Storage, settings: Settings) -> int:
    if not isinstance(task, PoiCollectTask):
        raise TypeError("handle_poi_task expects PoiCollectTask")

    client, mapper, result_key, raw_source = _select_map_components(task.source, settings)
    total_records = 0
    try:
        for page in range(1, task.max_pages + 1):
            payload = client.search_poi(task.keyword, task.city, page, task.page_size)
            raw_ref = store.write_raw(
                raw_source,
                {
                    "task_id": task.task_id,
                    "page": page,
                    "payload": payload,
                },
            )

            items = payload.get(result_key, [])
            if not isinstance(items, list):
                items = []

            for item in items:
                record = mapper(item)
                record["raw_ref"] = raw_ref
                record["task_id"] = task.task_id
                store.write_record("poi", record)
                total_records += 1

            if len(items) < task.page_size:
                break
    finally:
        client.close()

    return total_records


def handle_social_task(
    task: TaskBase,
    store: Storage,
    settings: Settings,
    progress: Callable[[int, str], None] | None = None,
) -> int:
    if not isinstance(task, SocialCollectTask):
        raise TypeError("handle_social_task expects SocialCollectTask")

    if task.source != SourceProvider.XIAOHONGSHU:
        raise ValueError("only xiaohongshu social source is currently supported")

    try:
        collector = XiaohongshuCollector(
            headless=task.headless,
            debug=(task.debug or settings.xhs_debug),
            auto_install_chromium=settings.auto_install_chromium,
            progress_callback=progress,
        )
    except TypeError:
        collector = XiaohongshuCollector(
            headless=task.headless,
            debug=(task.debug or settings.xhs_debug),
            auto_install_chromium=settings.auto_install_chromium,
        )
    posts = collector.collect(keyword=task.keyword, max_items=task.max_items)

    total_records = 0
    for index, post in enumerate(posts, start=1):
        local_post_path, local_images = _persist_social_assets(
            data_dir=settings.data_dir,
            task_id=task.task_id,
            index=index,
            post=post,
        )
        raw_ref = store.write_raw(
            "xiaohongshu",
            {
                "task_id": task.task_id,
                "index": index,
                "payload": post,
            },
        )
        post["raw_ref"] = raw_ref
        post["task_id"] = task.task_id
        post["local_post_path"] = local_post_path
        post["local_images"] = local_images
        store.write_record("social_post", post)
        total_records += 1

    # Export each social task into an isolated bundle:
    # - images converted to JPG under data/exports/tasks/<task_id>/images
    # - text and structured fields saved in social_posts.xlsx
    task_input = Path(settings.data_dir) / "curated" / "tasks" / task.task_id / "social_post.jsonl"
    task_output = Path(settings.data_dir) / "exports" / "tasks"
    export_social_records(input_path=task_input, output_dir=task_output, limit=0, download_images=True)

    _ = settings
    return total_records
