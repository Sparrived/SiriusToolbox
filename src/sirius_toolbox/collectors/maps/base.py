from abc import ABC, abstractmethod
from typing import Any


class PoiClient(ABC):
    @abstractmethod
    def search_poi(self, keyword: str, city: str, page: int, page_size: int) -> dict[str, Any]:
        raise NotImplementedError
