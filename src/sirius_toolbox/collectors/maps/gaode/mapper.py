from datetime import UTC, datetime
from typing import Any


def map_gaode_poi(item: dict[str, Any]) -> dict[str, Any]:
    location_text = item.get("location", ",")
    lng_text, lat_text = location_text.split(",", maxsplit=1)

    return {
        "provider": "gaode",
        "poi_id": item.get("id"),
        "name": item.get("name"),
        "address": item.get("address"),
        "province": item.get("pname"),
        "city": item.get("cityname"),
        "district": item.get("adname"),
        "location": {
            "lng": float(lng_text) if lng_text else None,
            "lat": float(lat_text) if lat_text else None,
        },
        "category": item.get("type"),
        "phone": item.get("tel") or None,
        "source_url": None,
        "collected_at": datetime.now(UTC).isoformat(),
        "raw_ref": "",
    }
