from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_fixed

from sirius_toolbox.collectors.maps.base import PoiClient


class GaodePoiClient(PoiClient):
    def __init__(self, api_key: str, timeout: float = 10.0) -> None:
        self._api_key = api_key
        self._client = httpx.Client(timeout=timeout)

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def search_poi(self, keyword: str, city: str, page: int, page_size: int) -> dict[str, Any]:
        response = self._client.get(
            "https://restapi.amap.com/v3/place/text",
            params={
                "key": self._api_key,
                "keywords": keyword,
                "city": city,
                "page": page,
                "offset": page_size,
                "extensions": "base",
            },
        )
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._client.close()
