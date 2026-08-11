# CLAUDE.md

Guidance for Claude Code working in this repo.

## Project

LocalAreaNetworkMonitor: CLI app that discovers devices on the local network, tracks when they join/leave, and measures traffic per device. See [README.md](README.md) for the one-line pitch and [docs/superpowers/specs/2026-08-11-lan-monitor-design.md](docs/superpowers/specs/2026-08-11-lan-monitor-design.md) for the full design.

## Stack

- Python 3
- `scapy` — ARP scan + packet sniffing
- `psutil` — network interface enumeration
- `sqlite3` (stdlib) — persistence
- No web UI in v1 (CLI only). Design keeps `storage`/`cli` layers separate so a web dashboard can be added later without touching core logic.

## Architecture

```
main.py (orchestrator/main loop)
  ├── discovery/   → ARP scan, resolves IP/MAC/hostname/vendor
  ├── tracker/     → diffs current snapshot vs DB, emits join/leave events
  ├── traffic/     → passive sniff in a thread, aggregates bytes/packets per IP
  ├── storage/     → SQLite: devices, sessions, traffic_samples
  └── cli/         → live table display, refreshes every N seconds
```

Module contracts:
- `discovery.scan(subnet) -> list[Device(ip, mac, hostname, vendor)]` — stateless.
- `tracker.update(current_devices) -> list[Event]` — reads/writes via storage.
- `traffic.Sniffer` — `start()/stop()`, runs in its own thread, `get_stats() -> dict[ip, TrafficStats]`.
- `storage` — `save_snapshot`, `log_event`, `save_traffic_sample`, `get_history(ip)`.
- `cli` — read-only consumer, never writes to storage directly.

## Conventions

- Keep modules isolated: `discovery`, `tracker`, `traffic`, `storage` must each be understandable and testable without the others running.
- `discovery`/`traffic` failures (e.g. interface drops) must log and retry next cycle — never crash the whole loop.
- Raw-socket operations (ARP scan, sniffing) need root/admin. Fail fast at startup with a clear message if privileges are missing — never fail silently or scan empty.
- `sqlite3` writes need try/except with simple retry for cross-thread lock contention.

## Testing

- `discovery`, `tracker`, `storage` are tested without real network access: mock ARP packets, `sqlite3 :memory:` for DB tests.
- `traffic` is tested against recorded/mocked packets (scapy can replay pcap files) — never depend on real live traffic in CI.
- Tests requiring real privileges are integration-only, marked separately, and must not block CI runs without privileges.

## Workflow

- Design specs live in `docs/superpowers/specs/`. Check there before proposing architecture changes — the current design already made trade-off decisions (Python over C++, CLI over web for v1, SQLite over JSON) documented with reasoning.
- Track active work in [PROGRESS.md](PROGRESS.md); update it as milestones complete, not just at the end.
- This is a learning-oriented project (networking + systems programming + web dev per README) — prefer clear, well-commented-where-non-obvious code over cleverness.
