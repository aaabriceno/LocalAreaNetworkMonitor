from pathlib import Path

import sqlcipher3
from sqlcipher3 import dbapi2


_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class Database:
    def __init__(self, path: str, key: str):
        self._conn = sqlcipher3.connect(path)
        escaped_key = key.replace("'","''")
        self._conn.execute(f"PRAGMA key = '{escaped_key}'")
        self._conn.row_factory = dbapi2.Row
        self._init_schema()

    def _init_schema(self) -> None:
        schema = _SCHEMA_PATH.read_text()
        self._conn.executescript(schema)
        self._conn.commit()

    def save_snapshot(self, devices: list[dict]) -> None:
        self._conn.executemany(
            """
            INSERT OR REPLACE INTO devices (mac, ip, hostname, vendor, last_seen)
            VALUES (:mac, :ip, :hostname, :vendor, :last_seen)
            """,
            devices,
        )
        self._conn.commit()

    def get_last_known_devices(self) -> list[dict]:
        rows = self._conn.execute("SELECT * FROM devices").fetchall()
        return [dict(row) for row in rows]

    def log_event(self, event_type: str, mac: str, ip: str, timestamp: float) -> None:
        self._conn.execute(
            "INSERT INTO events (event_type, mac, ip, timestamp) VALUES (?, ?, ?, ?)",
            (event_type, mac, ip, timestamp),
        )
        self._conn.commit()

    def get_history(self, ip:str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM events WHERE ip = ? ORDER BY timestamp", (ip,) 
        ).fetchall()
        return [dict(row) for row in rows]

    def save_traffic_sample(self, ip:str, bytes_count: int, packet_count:int, timestamp: float) -> None:
        self._conn.execute(
            "INSERT INTO traffic_samples (ip, bytes_count, packet_count, timestamp) VALUES (?, ?, ?, ?)",
            (ip, bytes_count, packet_count, timestamp),
        )
        self._conn.commit()
    
    def close(self) -> None:
        self._conn.close()
