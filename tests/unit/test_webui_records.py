from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sirius_toolbox.webui.server import read_recent_poi_records


def test_read_recent_poi_records(tmp_path: Path) -> None:
    curated = tmp_path / "curated"
    curated.mkdir(parents=True)
    target = curated / "poi.jsonl"
    target.write_text(
        "\n".join(
            [
                '{"name":"a","city":"x"}',
                '{"name":"b","city":"y"}',
                '{"name":"c","city":"z"}',
            ]
        ),
        encoding="utf-8",
    )

    records = read_recent_poi_records(tmp_path, limit=2)
    assert len(records) == 2
    assert records[0]["name"] == "c"
    assert records[1]["name"] == "b"
