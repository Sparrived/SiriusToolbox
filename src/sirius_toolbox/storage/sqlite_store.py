import json
from pathlib import Path
import sqlite3
from typing import Any

from sirius_toolbox.storage.base import Storage


class SqliteStore(Storage):
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._initialize()

    def _initialize(self) -> None:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stream TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def write_raw(self, source: str, payload: dict[str, Any]) -> str:
        cursor = self._conn.cursor()
        cursor.execute(
            "INSERT INTO raw_data(source, payload) VALUES (?, ?)",
            (source, json.dumps(payload, ensure_ascii=False)),
        )
        self._conn.commit()
        return str(cursor.lastrowid)

    def write_record(self, stream: str, record: dict[str, Any]) -> None:
        cursor = self._conn.cursor()
        cursor.execute(
            "INSERT INTO records(stream, payload) VALUES (?, ?)",
            (stream, json.dumps(record, ensure_ascii=False)),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
