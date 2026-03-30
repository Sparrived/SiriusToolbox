import argparse
from pathlib import Path

from sirius_toolbox.core.types import SourceProvider
from sirius_toolbox.core.logging import build_logger
from sirius_toolbox.exporters.social_report import export_social_records
from sirius_toolbox.settings import Settings
from sirius_toolbox.storage.jsonl_store import JsonlStore
from sirius_toolbox.tasks.handlers import handle_poi_task, handle_social_task
from sirius_toolbox.tasks.models import PoiCollectTask, SocialCollectTask
from sirius_toolbox.tasks.queue import InMemoryTaskQueue
from sirius_toolbox.tasks.scheduler import TaskScheduler
from sirius_toolbox.webui.server import start_webui


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SiriusToolbox data collector")
    subparsers = parser.add_subparsers(dest="command")

    poi = subparsers.add_parser("poi", help="Collect POI via official map API")
    poi.add_argument("--provider", required=True, choices=["gaode", "baidu"])
    poi.add_argument("--keyword", required=True)
    poi.add_argument("--city", required=True)
    poi.add_argument("--page-size", type=int, default=20)
    poi.add_argument("--max-pages", type=int, default=3)

    xhs = subparsers.add_parser("xhs", help="Collect Xiaohongshu posts by keyword")
    xhs.add_argument("--keyword", required=True)
    xhs.add_argument("--max-items", type=int, default=20)
    xhs.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose debug logs for Xiaohongshu collection",
    )

    webui = subparsers.add_parser("webui", help="Start Web UI for task submission")
    webui.add_argument("--host", default="127.0.0.1")
    webui.add_argument("--port", type=int, default=8787)

    export_social = subparsers.add_parser(
        "export-social",
        help="Export curated social posts to easy-to-read files (Excel + HTML)",
    )
    export_social.add_argument(
        "--input",
        default="data/curated/tasks",
        help="Input path for curated social posts file or tasks directory",
    )
    export_social.add_argument(
        "--output-dir",
        default="data/exports",
        help="Directory to write export files",
    )
    export_social.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Export only the latest N records, 0 means all",
    )
    export_social.add_argument(
        "--skip-image-download",
        action="store_true",
        help="Skip downloading images to local files",
    )
    return parser


def _enqueue_tasks(queue: InMemoryTaskQueue, args: argparse.Namespace) -> None:
    if args.command == "poi":
        queue.push(
            PoiCollectTask(
                source=SourceProvider(args.provider),
                keyword=args.keyword,
                city=args.city,
                page_size=args.page_size,
                max_pages=args.max_pages,
            )
        )
        return

    if args.command == "xhs":
        queue.push(
            SocialCollectTask(
                source=SourceProvider.XIAOHONGSHU,
                keyword=args.keyword,
                max_items=args.max_items,
                headless=False,
                debug=args.debug,
            )
        )
        return


def run(argv: list[str] | None = None) -> None:
    settings = Settings.from_env()
    logger = build_logger(settings.log_level)
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "webui":
        start_webui(settings=settings, logger=logger, host=args.host, port=args.port)
        return

    if args.command == "export-social":
        input_path = Path(args.input)
        if not input_path.exists() and str(args.input).replace("\\", "/") == "data/curated/tasks":
            legacy = Path("data/curated/social_post.jsonl")
            if legacy.exists():
                input_path = legacy

        result = export_social_records(
            input_path=input_path,
            output_dir=Path(args.output_dir),
            limit=max(0, int(args.limit)),
            download_images=not args.skip_image_download,
        )
        logger.info(
            "social_export_finished",
            extra={
                "records": result.record_count,
                "downloaded_images": result.downloaded_images,
                "image_dir": str(result.image_dir),
                "excel_path": str(result.excel_path),
                "html_path": str(result.html_path),
            },
        )
        return

    if args.command not in {"poi", "xhs"}:
        parser.print_help()
        return

    data_dir = Path(settings.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    store = JsonlStore(root_dir=data_dir)
    queue = InMemoryTaskQueue()
    scheduler = TaskScheduler(store=store, logger=logger)
    scheduler.register("map_poi", lambda task, st: handle_poi_task(task, st, settings))
    scheduler.register(
        "social_post",
        lambda task, st: handle_social_task(task, st, settings),
    )
    _enqueue_tasks(queue, args)

    logger.info(
        "application_started",
        extra={
            "env": settings.app_env,
            "data_dir": str(data_dir),
            "queued_tasks": queue.size,
        },
    )

    scheduler.run(queue)
    store.close()

    logger.info("application_finished")
