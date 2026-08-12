CREATE TABLE IF NOT EXISTS devices (
    mac TEXT PRIMARY KEY,
    ip TEXT,
    hostname TEXT,
    vendor TEXT,
    last_seen REAL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    mac TEXT NOT NULL,
    ip TEXT,
    timestamp REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS traffic_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT NOT NULL,
    bytes_count INTEGER NOT NULL,
    packet_count INTEGER NOT NULL,
    timestamp REAL NOT NULL
);