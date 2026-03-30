from abc import ABC, abstractmethod
from typing import Any


class BrowserCollector(ABC):
    @abstractmethod
    def collect(self, keyword: str, max_items: int) -> list[dict[str, Any]]:
        raise NotImplementedError
