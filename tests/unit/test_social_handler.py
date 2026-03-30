from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sirius_toolbox.core.types import SourceProvider
from sirius_toolbox.settings import Settings
from sirius_toolbox.storage.jsonl_store import JsonlStore
from sirius_toolbox.tasks import handlers as handler_module
from sirius_toolbox.tasks.handlers import handle_social_task
from sirius_toolbox.tasks.models import SocialCollectTask


class _FakeXhsCollector:
    def __init__(
        self,
        *,
        headless: bool,
        timeout_ms: int = 20000,
        debug: bool = False,
    ) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.debug = debug

    def collect(self, keyword: str, max_items: int) -> list[dict]:
        _ = keyword
        _ = max_items
        return [
            {
                "platform": "xiaohongshu",
                "source_id": "n1",
                "title": "Title A",
                "text": "Body",
                "author": "Alice",
                "publish_time": "",
                "images": ["https://img/1.jpg"],
                "tags": ["tag1"],
                "url": "https://www.xiaohongshu.com/explore/n1",
                "collected_at": "",
                "raw_ref": "",
            }
        ]


def test_handle_social_task_writes_records(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(handler_module, "XiaohongshuCollector", _FakeXhsCollector)

    task = SocialCollectTask(
        source=SourceProvider.XIAOHONGSHU,
        keyword="护肤",
        max_items=3,
    )
    store = JsonlStore(tmp_path)
    count = handle_social_task(task, store, Settings())

    assert count == 1
    output = tmp_path / "curated" / "tasks" / task.task_id / "social_post.jsonl"
    assert output.exists()
    assert "Title A" in output.read_text(encoding="utf-8")
