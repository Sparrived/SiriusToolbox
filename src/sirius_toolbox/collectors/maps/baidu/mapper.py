from datetime import UTC, datetime
from typing import Any


def map_baidu_poi(item: dict[str, Any]) -> dict[str, Any]:
    location = item.get("location") or {}

    return {
        "provider": "baidu",
        "poi_id": item.get("uid"),
        "name": item.get("name"),
        "address": item.get("address"),
        "province": item.get("province"),
        "city": item.get("city"),
        "district": item.get("area"),
        "location": {
            "lng": location.get("lng"),
            "lat": location.get("lat"),
        },
        "category": item.get("detail_info", {}).get("tag"),
        "phone": item.get("telephone") or None,
        "source_url": item.get("detail_info", {}).get("detail_url"),
        "collected_at": datetime.now(UTC).isoformat(),
        "raw_ref": "",
    }
