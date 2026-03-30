from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sirius_toolbox.core.types import SourceProvider
from sirius_toolbox.tasks.models import PoiCollectTask
from sirius_toolbox.tasks.queue import InMemoryTaskQueue


def test_queue_push_pop_roundtrip() -> None:
    queue = InMemoryTaskQueue()
    task = PoiCollectTask(source=SourceProvider.GAODE, keyword="cafe", city="beijing")

    queue.push(task)
    popped = queue.pop()

    assert popped is not None
    assert popped.task_id == task.task_id
    assert queue.pop() is None
