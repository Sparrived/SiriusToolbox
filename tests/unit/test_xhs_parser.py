from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sirius_toolbox.collectors.browser.xiaohongshu.parser import parse_note


def test_parse_note_normalizes_fields() -> None:
    parsed = parse_note(
        {
            "source_id": 123,
            "title": None,
            "text": " text ",
            "author": "",
            "images": ["a", None, "  ", "b"],
            "tags": [1, "tag"],
            "url": "https://xhs/explore/123",
            "like_count": 123,
            "comment_count_text": "评论 45",
            "author_profile_url": "https://www.xiaohongshu.com/user/profile/abc",
        }
    )

    assert parsed["source_id"] == "123"
    assert parsed["title"] == ""
    assert parsed["text"] == " text "
    assert parsed["images"] == ["a", "b"]
    assert parsed["tags"] == ["1", "tag"]
    assert parsed["like_count"] == 123
    assert parsed["comment_count_text"] == "评论 45"
    assert parsed["author_profile_url"] == "https://www.xiaohongshu.com/user/profile/abc"
