import pytest
from lanmon.storage.db import Database


@pytest.fixture
def db():
    database = Database(":memory:", key="test-key-not-real")
    yield database
    database.close()


def test_save_and_retrieve_snapshot(db):
    devices = [{"mac": "aa:bb:cc:dd:ee:ff", "ip": "192.168.1.10",
                "hostname": "laptop", "vendor": "Dell", "last_seen": 1000.0}]
    db.save_snapshot(devices)
    result = db.get_last_known_devices()
    assert len(result) == 1
    assert result[0]["mac"] == "aa:bb:cc:dd:ee:ff"

def test_log_event(db):
    db.log_event(event_type="joined", mac="aa:bb:cc:dd:ee:ff", ip="192.168.1.10", timestamp=1000.0)
    history = db.get_history("192.168.1.10")
    assert len(history) == 1
    assert history[0]["event_type"] == "joined"

def test_save_traffic_sample(db):
    db.save_traffic_sample(ip = "192.168.1.10", bytes_count = 1500, packet_count = 10, timestamp = 1000.0)
    rows = db._conn.execute("SELECT * FROM traffic_samples").fetchall()
    assert len(rows) == 1
    assert rows[0]["bytes_count"] == 1500

def save_traffic_sample(self, ip: str, bytes_count:int, packet_count, timestamp: float) -> None:
    self._conn.execute(
        "INSERT INTO traffic_samples (ip, bytes, bytes_count, packet_count, timestamp) VALUES (?, ?, ?, ?)",
        (ip, bytes_count, packet_count, timestamp),
    )
    self._conn.commit()
