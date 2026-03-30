from collections import deque
from typing import Deque

from sirius_toolbox.tasks.models import TaskBase


class InMemoryTaskQueue:
    def __init__(self) -> None:
        self._queue: Deque[TaskBase] = deque()

    def push(self, task: TaskBase) -> None:
        self._queue.append(task)

    def pop(self) -> TaskBase | None:
        if not self._queue:
            return None
        return self._queue.popleft()

    @property
    def size(self) -> int:
        return len(self._queue)
