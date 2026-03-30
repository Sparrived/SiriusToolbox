from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class Storage(ABC):
    @abstractmethod
    def write_raw(self, source: str, payload: dict[str, Any]) -> str:
        raise NotImplementedError

    @abstractmethod
    def write_record(self, stream: str, record: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
