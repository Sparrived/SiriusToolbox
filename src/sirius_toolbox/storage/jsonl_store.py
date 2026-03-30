import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from sirius_toolbox.storage.base import Storage, ensure_parent


class JsonlStore(Storage):
    def __init__(self, root_dir: Path) -> None:
        self._root = root_dir
        self._raw_dir = self._root / "raw"
        self._curated_dir = self._root / "curated"
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        self._curated_dir.mkdir(parents=True, exist_ok=True)

    def write_raw(self, source: str, payload: dict[str, Any]) -> str:
        raw_id = str(uuid4())
        task_id = str(payload.get("task_id") or "").strip()
        if task_id:
            target = self._raw_dir / source / task_id / f"{raw_id}.json"
        else:
            target = self._raw_dir / source / f"{raw_id}.json"
        ensure_parent(target)
        target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return str(target)

    def write_record(self, stream: str, record: dict[str, Any]) -> None:
        task_id = str(record.get("task_id") or "").strip()
        if task_id:
            target = self._curated_dir / "tasks" / task_id / f"{stream}.jsonl"
        else:
            target = self._curated_dir / f"{stream}.jsonl"
        ensure_parent(target)

        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False))
            fh.write("\n")

    def close(self) -> None:
        return
