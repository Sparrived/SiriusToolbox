from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sirius_toolbox.core.types import SourceProvider
from sirius_toolbox.settings import Settings
from sirius_toolbox.storage.jsonl_store import JsonlStore
from sirius_toolbox.tasks import handlers as handler_module
from sirius_toolbox.tasks.handlers import handle_poi_task
from sirius_toolbox.tasks.models import PoiCollectTask


class _FakeGaodeClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def search_poi(self, keyword: str, city: str, page: int, page_size: int) -> dict:
        _ = keyword
        _ = city
        _ = page_size
        if page == 1:
            return {
                "pois": [
                    {
                        "id": "p1",
                        "name": "Sample Cafe",
                        "address": "Road 1",
                        "pname": "Beijing",
                        "cityname": "Beijing",
                        "adname": "Haidian",
                        "location": "116.3,39.9",
                        "type": "Food",
                    }
                ]
            }
        return {"pois": []}

    def close(self) -> None:
        return


def test_handle_poi_task_writes_records(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(handler_module, "GaodePoiClient", _FakeGaodeClient)

    task = PoiCollectTask(
        source=SourceProvider.GAODE,
        keyword="cafe",
        city="beijing",
        page_size=20,
        max_pages=2,
    )
    settings = Settings(gaode_api_key="fake")
    store = JsonlStore(tmp_path)

    handle_poi_task(task, store, settings)

    output = tmp_path / "curated" / "tasks" / task.task_id / "poi.jsonl"
    assert output.exists()
    text = output.read_text(encoding="utf-8")
    assert "Sample Cafe" in text
    assert "raw_ref" in text
