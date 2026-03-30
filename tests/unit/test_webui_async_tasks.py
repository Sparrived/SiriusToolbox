from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sirius_toolbox.webui.server import AsyncTaskManager


def _wait_for_terminal_status(manager: AsyncTaskManager, task_id: str, timeout_sec: float = 2.0) -> str:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        state = manager.get(task_id)
        assert state is not None
        if state.status in {"succeeded", "failed", "cancelled"}:
            return state.status
        time.sleep(0.02)
    raise AssertionError("task did not reach terminal status in time")


def test_async_task_manager_success() -> None:
    manager = AsyncTaskManager()

    def runner(report):
        report(40, "running")
        return 3

    task_id = manager.submit(task_type="poi", params={"keyword": "coffee"}, runner=runner)
    status = _wait_for_terminal_status(manager, task_id)
    state = manager.get(task_id)

    assert state is not None
    assert status == "succeeded"
    assert state.progress == 100
    assert state.result_count == 3


def test_async_task_manager_failed() -> None:
    manager = AsyncTaskManager()

    def runner(report):
        report(50, "running")
        raise ValueError("boom")

    task_id = manager.submit(task_type="xhs", params={"keyword": "护肤"}, runner=runner)
    status = _wait_for_terminal_status(manager, task_id)
    state = manager.get(task_id)

    assert state is not None
    assert status == "failed"
    assert state.progress == 100
    assert state.error is not None
    assert "boom" in state.error
