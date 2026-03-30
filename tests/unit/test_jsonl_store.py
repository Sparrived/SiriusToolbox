from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sirius_toolbox.storage.jsonl_store import JsonlStore


def test_jsonl_store_write_record(tmp_path: Path) -> None:
    store = JsonlStore(root_dir=tmp_path)
    store.write_record("poi", {"name": "sample", "task_id": "task-1"})

    output = tmp_path / "curated" / "tasks" / "task-1" / "poi.jsonl"
    assert output.exists()
    assert "sample" in output.read_text(encoding="utf-8")
