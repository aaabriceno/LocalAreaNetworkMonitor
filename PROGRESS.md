# Progress

Tracks milestones for LocalAreaNetworkMonitor. Update as work completes — see [CLAUDE.md](CLAUDE.md) for architecture/conventions.

## Status: Design phase complete, implementation not started

## Done

- [x] Repo cloned, README reviewed.
- [x] Brainstormed scope, stack, architecture with user.
- [x] Design spec written and committed: [docs/superpowers/specs/2026-08-11-lan-monitor-design.md](docs/superpowers/specs/2026-08-11-lan-monitor-design.md).
- [x] `.gitignore` set up for Python project.
- [x] `CLAUDE.md` and `PROGRESS.md` created.

## Next

- [ ] User reviews the design spec.
- [ ] Write implementation plan (writing-plans skill).
- [ ] Scaffold project structure (`discovery/`, `tracker/`, `traffic/`, `storage/`, `cli/`, `main.py`).
- [ ] Set up `requirements.txt` / venv (scapy, psutil).
- [ ] Implement `discovery` module (ARP scan) + tests.
- [ ] Implement `storage` module (SQLite schema + CRUD) + tests.
- [ ] Implement `tracker` module (join/leave diffing) + tests.
- [ ] Implement `traffic` module (sniffer thread) + tests.
- [ ] Implement `cli` module (live display).
- [ ] Wire up `main.py` orchestrator loop.
- [ ] End-to-end manual test on real LAN (requires sudo/admin).

## Key decisions (see spec for full reasoning)

- **Language:** Python (cross-platform packet capture via scapy beats hand-rolled C++ raw sockets per OS).
- **Interface:** CLI only for v1. Web dashboard is a possible phase 2 — design already separates `storage`/`cli` to support that later.
- **Persistence:** SQLite (supports historical queries, no external server).
- **v1 scope:** discovery + join/leave tracking + per-device traffic. No alerts, no device-type detection beyond MAC vendor.

## Open questions / blockers

None currently.
