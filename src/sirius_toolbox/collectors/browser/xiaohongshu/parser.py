from datetime import UTC, datetime
from typing import Any


def _normalize_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized


def parse_note(raw: dict[str, Any]) -> dict[str, Any]:
    parsed = {
        "platform": "xiaohongshu",
        "source_id": str(raw.get("source_id") or ""),
        "title": str(raw.get("title") or ""),
        "text": str(raw.get("text") or ""),
        "author": str(raw.get("author") or ""),
        "publish_time": str(raw.get("publish_time") or ""),
        "images": _normalize_list(raw.get("images")),
        "tags": _normalize_list(raw.get("tags")),
        "url": str(raw.get("url") or ""),
        "collected_at": datetime.now(UTC).isoformat(),
        "raw_ref": "",
    }

    # Preserve additional useful fields scraped from detail page.
    passthrough_fields = [
        "note_type",
        "author_profile_url",
        "author_id",
        "like_count",
        "like_count_text",
        "collect_count",
        "collect_count_text",
        "comment_count",
        "comment_count_text",
        "share_count",
        "share_count_text",
        "ip_location",
    ]
    for key in passthrough_fields:
        if key not in raw:
            continue
        value = raw.get(key)
        if value is None:
            continue
        if isinstance(value, list):
            parsed[key] = _normalize_list(value)
            continue
        parsed[key] = str(value).strip() if isinstance(value, str) else value

    return parsed
