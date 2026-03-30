from collections.abc import Callable
import logging

from sirius_toolbox.storage.base import Storage
from sirius_toolbox.tasks.models import TaskBase
from sirius_toolbox.tasks.queue import InMemoryTaskQueue


TaskHandler = Callable[[TaskBase, Storage], None]


class TaskScheduler:
    def __init__(self, store: Storage, logger: logging.Logger) -> None:
        self._store = store
        self._logger = logger
        self._handlers: dict[str, TaskHandler] = {}

    def register(self, task_type: str, handler: TaskHandler) -> None:
        self._handlers[task_type] = handler

    def run(self, queue: InMemoryTaskQueue) -> None:
        while True:
            task = queue.pop()
            if task is None:
                break

            handler = self._handlers.get(str(task.task_type))
            if handler is None:
                self._logger.warning(
                    "task_handler_missing",
                    extra={"task_type": str(task.task_type), "task_id": task.task_id},
                )
                continue

            self._logger.info(
                "task_processing",
                extra={"task_type": str(task.task_type), "task_id": task.task_id},
            )

            success = False
            for attempt in range(task.max_retries + 1):
                try:
                    handler(task, self._store)
                    success = True
                    break
                except Exception as exc:
                    self._logger.warning(
                        "task_attempt_failed",
                        extra={
                            "task_id": task.task_id,
                            "task_type": str(task.task_type),
                            "attempt": attempt + 1,
                            "error": str(exc),
                        },
                    )

            if not success:
                self._logger.error(
                    "task_failed",
                    extra={"task_id": task.task_id, "task_type": str(task.task_type)},
                )
