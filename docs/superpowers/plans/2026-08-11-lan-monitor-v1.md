# LocalAreaNetworkMonitor v1 — Plan de Implementación

> **Nota de ejecución:** este plan NO se ejecuta con subagentes ni de forma automática. El código lo escribe el usuario, paso a paso, con guía de Claude en cada tarea. Claude explica qué hacer y por qué, revisa lo escrito, pero no edita los archivos de código directamente.

**Objetivo:** app CLI en Python que descubre dispositivos en la LAN, trackea su entrada/salida, y mide tráfico por dispositivo — con diseño seguro desde el inicio (privilegios mínimos, DB cifrada, logging de auditoría, Docker).

**Arquitectura:** módulos aislados (`discovery`, `tracker`, `traffic`, `storage`, `cli`, `security`) coordinados por un loop principal en `main.py`. Cada módulo es testeable sin depender de red real ni privilegios (mocks/DB en memoria).

**Stack:** Python 3, `scapy`, `psutil`, `sqlcipher3`, `pytest`, Docker.

## Restricciones globales

- Todas las queries SQL parametrizadas — nunca f-string/concat.
- Todo parsing de paquetes de red envuelto en try/except específico.
- Ningún secreto (keys, passphrases) hardcoded ni commiteado — vía variable de entorno.
- Cada módulo debe funcionar y testearse sin privilegios root reales (usar mocks).
- Ver spec completo en [`docs/superpowers/specs/2026-08-11-lan-monitor-design.md`](../specs/2026-08-11-lan-monitor-design.md).

---

## Estructura de archivos (destino final)

```
src/lanmon/
  __init__.py
  main.py
  discovery/{__init__.py, scanner.py}
  tracker/{__init__.py, tracker.py}
  traffic/{__init__.py, sniffer.py}
  storage/{__init__.py, db.py, schema.sql}
  cli/{__init__.py, display.py}
  security/{__init__.py, privileges.py, audit_log.py}
tests/{discovery,tracker,traffic,storage,security}/test_*.py
Dockerfile
docker-compose.yml
requirements.txt
pyproject.toml
```

---

### Tarea 0: Scaffolding del proyecto

**Archivos:**
- Crear: `pyproject.toml`, `requirements.txt`, `src/lanmon/__init__.py`, todos los `__init__.py` de submódulos vacíos, `tests/__init__.py`

**Qué hace:** deja el proyecto instalable (`pip install -e .`) y con estructura de paquete válida, sin lógica todavía.

- [ ] **Paso 1:** Crear `pyproject.toml` con metadata mínima del paquete (`name = "lanmon"`, `requires-python = ">=3.10"`) y dependencias: `scapy`, `psutil`, `sqlcipher3-binary`, y en `[project.optional-dependencies] dev`: `pytest`.
- [ ] **Paso 2:** Crear `requirements.txt` reflejando las mismas deps (para quien no use pyproject).
- [ ] **Paso 3:** Crear la estructura de carpetas `src/lanmon/{discovery,tracker,traffic,storage,cli,security}/` cada una con `__init__.py` vacío. Crear `src/lanmon/__init__.py` y `src/lanmon/main.py` (vacío por ahora, solo `if __name__ == "__main__":`).
- [ ] **Paso 4:** Crear `tests/__init__.py` y subcarpetas `tests/{discovery,tracker,traffic,storage,security}/__init__.py`.
- [ ] **Paso 5:** Instalar en modo editable: `pip install -e ".[dev]"` dentro de un venv. Verificar: `python -c "import lanmon"` no falla.
- [ ] **Paso 6 (usuario):** commit del scaffolding.

---

### Tarea 1: `storage` — esquema y capa de acceso a datos

**Archivos:**
- Crear: `src/lanmon/storage/schema.sql`, `src/lanmon/storage/db.py`
- Test: `tests/storage/test_db.py`

**Interfaces (lo que produce esta tarea, usado por tareas futuras):**
- `Database(path: str, key: str)` — clase, abre conexión SQLCipher con la key dada.
- `Database.save_snapshot(devices: list[dict]) -> None`
- `Database.log_event(event_type: str, ip: str, mac: str, timestamp: float) -> None`
- `Database.save_traffic_sample(ip: str, bytes_count: int, packet_count: int, timestamp: float) -> None`
- `Database.get_history(ip: str) -> list[dict]`
- `Database.get_last_known_devices() -> list[dict]` — usado por `tracker` para diff.

**Por qué primero:** todos los demás módulos dependen de `storage` para persistir o comparar estado. Sin esto no se puede testear `tracker` de forma realista.

- [ ] **Paso 1: Diseñar el schema.** En `src/lanmon/storage/schema.sql` definir 3 tablas:
  - `devices(mac TEXT PRIMARY KEY, ip TEXT, hostname TEXT, vendor TEXT, last_seen REAL)`
  - `events(id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT, mac TEXT, ip TEXT, timestamp REAL)`
  - `traffic_samples(id INTEGER PRIMARY KEY AUTOINCREMENT, ip TEXT, bytes_count INTEGER, packet_count INTEGER, timestamp REAL)`

- [ ] **Paso 2: Escribir el test que falla primero.** En `tests/storage/test_db.py`:
```python
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
```

- [ ] **Paso 2b:** Correr `pytest tests/storage/test_db.py -v` → debe fallar (`ModuleNotFoundError` o `ImportError`, `Database` no existe todavía).

- [ ] **Paso 3: Implementar lo mínimo.** En `src/lanmon/storage/db.py`, clase `Database` que:
  - Abre conexión con `sqlcipher3` (no `sqlite3` — nota de seguridad: la key se pasa via `PRAGMA key`, nunca en la connection string en texto plano dentro de logs).
  - Ejecuta el `schema.sql` al abrir (si las tablas no existen).
  - Implementa `save_snapshot` con `INSERT OR REPLACE` parametrizado (placeholders `?`, nunca f-string).
  - Implementa `get_last_known_devices` con `SELECT` simple.

- [ ] **Paso 4:** Correr test de nuevo → debe pasar.

- [ ] **Paso 5: Repetir TDD para `log_event`, `save_traffic_sample`, `get_history`.** Un test por método, mismo ciclo rojo→verde. Todas las queries parametrizadas.

- [ ] **Paso 6 (usuario):** commit de `storage` completo con tests pasando.

**Nota de guía:** en este paso te acompaño validando que ninguna query use f-string/concat (chequeo de seguridad manual, no solo tests) antes de dar el OK al commit.

---

### Tarea 2: `security` — manejo de privilegios y audit log

**Archivos:**
- Crear: `src/lanmon/security/privileges.py`, `src/lanmon/security/audit_log.py`
- Test: `tests/security/test_privileges.py`, `tests/security/test_audit_log.py`

**Interfaces:**
- `privileges.check_required_privileges() -> bool` — True si corre con permisos suficientes para raw socket.
- `privileges.drop_privileges(target_user: str) -> None` — baja privilegios tras abrir el socket (Linux/Mac vía `os.setuid`; no-op documentado en Windows).
- `AuditLogger(path: str)` — clase.
- `AuditLogger.log(event: str, **fields) -> None` — escribe línea JSON append-only.

**Por qué ahora:** es transversal — `discovery` y `traffic` lo van a usar cuando abran el socket, y quiero que exista antes de escribir esos módulos para no tener que volver atrás.

- [ ] **Paso 1: Test de audit log.**
```python
import json
from lanmon.security.audit_log import AuditLogger

def test_log_writes_json_line(tmp_path):
    log_path = tmp_path / "audit.log"
    logger = AuditLogger(str(log_path))
    logger.log("scan_started", subnet="192.168.1.0/24")
    lines = log_path.read_text().strip().split("\n")
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["event"] == "scan_started"
    assert entry["subnet"] == "192.168.1.0/24"
    assert "timestamp" in entry
```
- [ ] **Paso 2:** correr, debe fallar (módulo no existe).
- [ ] **Paso 3: Implementar `AuditLogger`** — abre archivo en modo append, cada `log()` arma dict con `timestamp` (epoch), `event`, y **fields, lo serializa con `json.dumps` y escribe + newline. Sin dependencias externas, solo stdlib.
- [ ] **Paso 4:** correr test, debe pasar.
- [ ] **Paso 5: Test de `check_required_privileges`.** Mockear `os.geteuid` (Linux) para simular ambos casos (0 = root, otro = no root). En Windows la verificación real es distinta (`ctypes.windll.shell32.IsUserAnAdmin()`) — el test debe mockear según plataforma, usando `sys.platform` para decidir qué mockear.
- [ ] **Paso 6: Implementar `check_required_privileges`.**
- [ ] **Paso 7: Test + implementación de `drop_privileges`.** En Linux/Mac usa `os.setuid(pwd.getpwnam(target_user).pw_uid)`. Documentar con un comentario corto por qué en Windows es no-op (no hay equivalente directo a nivel de proceso Python estándar).
- [ ] **Paso 8 (usuario):** commit de `security`.

**Nota de guía:** privilege-drop es la parte más sensible del proyecto — reviso el código línea por línea contigo antes del commit, no solo los tests.

---

### Tarea 3: `discovery` — ARP scan

**Archivos:**
- Crear: `src/lanmon/discovery/scanner.py`
- Test: `tests/discovery/test_scanner.py`

**Interfaces:**
- `Device` — dataclass o namedtuple: `ip: str, mac: str, hostname: str | None, vendor: str | None`.
- `Scanner` — clase base abstracta (`abc.ABC`) con método `scan(self) -> list[Device]`. Deja la puerta abierta a futuros scanners (SSH/server) sin tocar `tracker`/`storage`.
- `ArpScanner(Scanner)` — implementación concreta, `ArpScanner(subnet: str).scan() -> list[Device]`.
- `validate_subnet(subnet: str) -> bool` — valida formato CIDR antes de escanear.

**Consume:** nada de tareas previas directamente (es independiente), pero su output (`list[Device]`) lo va a consumir `tracker` en la Tarea 4.

- [ ] **Paso 1: Test de `validate_subnet`.**
```python
from lanmon.discovery.scanner import validate_subnet

def test_valid_cidr():
    assert validate_subnet("192.168.1.0/24") is True

def test_invalid_cidr_rejected():
    assert validate_subnet("not-a-subnet") is False

def test_absurd_range_rejected():
    assert validate_subnet("0.0.0.0/0") is False
```
- [ ] **Paso 2:** correr, falla.
- [ ] **Paso 3: Implementar `validate_subnet`** usando `ipaddress.ip_network(subnet, strict=True)` en try/except, más un chequeo de tamaño máximo razonable (ej. rechazar prefijos `/0` a `/8`, evitar escaneo masivo accidental).
- [ ] **Paso 4:** correr, pasa.
- [ ] **Paso 5: Test de `ArpScanner.scan()` con mock de scapy.** No se hace scan real en tests — se mockea `scapy.all.srp` para devolver respuestas ARP simuladas:
```python
from unittest.mock import patch, MagicMock
from lanmon.discovery.scanner import ArpScanner

@patch("lanmon.discovery.scanner.srp")
def test_scan_parses_arp_responses(mock_srp):
    mock_answered = MagicMock()
    mock_answered.__iter__.return_value = [
        (MagicMock(), MagicMock(psrc="192.168.1.10", hwsrc="aa:bb:cc:dd:ee:ff"))
    ]
    mock_srp.return_value = (mock_answered, MagicMock())

    scanner = ArpScanner("192.168.1.0/24")
    devices = scanner.scan()

    assert len(devices) == 1
    assert devices[0].ip == "192.168.1.10"
    assert devices[0].mac == "aa:bb:cc:dd:ee:ff"
```
- [ ] **Paso 6:** correr, falla.
- [ ] **Paso 7: Implementar `ArpScanner`.** Construye paquete ARP con scapy (`ARP(pdst=subnet)/Ether(dst="ff:ff:ff:ff:ff:ff")`), envía con `srp`, parsea respuestas a `Device`. Envolver el `srp()` en try/except específico (captura `PermissionError` para dar mensaje claro de "necesitás privilegios", y excepción genérica de scapy para paquete/interfaz inválida) — nunca dejar que una excepción de red tumbe todo el proceso.
- [ ] **Paso 8:** correr, pasa.
- [ ] **Paso 9 (usuario):** commit de `discovery`.

---

### Tarea 4: `tracker` — detección de entrada/salida

**Archivos:**
- Crear: `src/lanmon/tracker/tracker.py`
- Test: `tests/tracker/test_tracker.py`

**Consume:**
- `Device` de `discovery.scanner` (Tarea 3).
- `Database.get_last_known_devices()` / `Database.save_snapshot()` / `Database.log_event()` de `storage.db` (Tarea 1).

**Produce:**
- `Event` — dataclass: `event_type: Literal["joined", "left"], mac: str, ip: str, timestamp: float`.
- `Tracker(db: Database)` — clase.
- `Tracker.update(current_devices: list[Device]) -> list[Event]`.

- [ ] **Paso 1: Test — dispositivo nuevo genera evento "joined".**
```python
from lanmon.tracker.tracker import Tracker
from lanmon.discovery.scanner import Device
from lanmon.storage.db import Database

def test_new_device_generates_joined_event():
    db = Database(":memory:", key="test-key")
    tracker = Tracker(db)
    devices = [Device(ip="192.168.1.10", mac="aa:bb:cc:dd:ee:ff", hostname=None, vendor=None)]

    events = tracker.update(devices)

    assert len(events) == 1
    assert events[0].event_type == "joined"
    assert events[0].mac == "aa:bb:cc:dd:ee:ff"
```
- [ ] **Paso 2:** correr, falla.
- [ ] **Paso 3: Implementar caso "joined".** `update()` lee `db.get_last_known_devices()`, compara MACs contra `current_devices`, los que están en current pero no en last → evento `joined`. Guarda snapshot nuevo vía `db.save_snapshot()` y cada evento vía `db.log_event()`.
- [ ] **Paso 4:** correr, pasa.
- [ ] **Paso 5: Test — dispositivo que estaba y ya no está genera "left".** Mismo patrón: primero `update()` con el device presente, después `update()` con lista vacía, verificar evento `left`.
- [ ] **Paso 6:** implementar caso "left", correr test, pasa.
- [ ] **Paso 7: Test — dispositivo que sigue presente no genera eventos.**
- [ ] **Paso 8:** verificar que ya pasa con la implementación actual (no debería requerir código nuevo si el diff está bien hecho).
- [ ] **Paso 9 (usuario):** commit de `tracker`.

---

### Tarea 5: `traffic` — sniffer de tráfico por dispositivo

**Archivos:**
- Crear: `src/lanmon/traffic/sniffer.py`
- Test: `tests/traffic/test_sniffer.py`

**Produce:**
- `TrafficStats` — dataclass: `bytes_count: int, packet_count: int`.
- `Sniffer(interface: str)` — clase con `start() -> None`, `stop() -> None`, `get_stats() -> dict[str, TrafficStats]` (key = IP).

**Nota de seguridad:** este es el módulo que procesa paquetes crudos de la red (entrada no confiable). Cada paquete parseado va envuelto en try/except específico por capa.

- [ ] **Paso 1: Test con paquetes simulados (no red real).** Usar `scapy` para construir paquetes de prueba en memoria (no requiere privilegios) y pasarlos directo al callback del sniffer:
```python
from scapy.layers.inet import IP, TCP
from lanmon.traffic.sniffer import Sniffer

def test_process_packet_accumulates_stats():
    sniffer = Sniffer(interface="lo")
    packet = IP(src="192.168.1.10", dst="192.168.1.1", len=100) / TCP()

    sniffer._process_packet(packet)

    stats = sniffer.get_stats()
    assert stats["192.168.1.10"].packet_count == 1
    assert stats["192.168.1.10"].bytes_count == 100
```
- [ ] **Paso 2:** correr, falla.
- [ ] **Paso 3: Implementar `_process_packet` y `get_stats`.** `_process_packet` es el callback interno (lo que scapy llamaría por cada paquete capturado): extrae `IP.src`, `IP.len`, acumula en un dict interno protegido por `threading.Lock` (porque el sniff real corre en otro thread). Envolver el acceso a capas del paquete en try/except (`IndexError`/`AttributeError` si el paquete no tiene capa IP — paquete malformado o no-IP, se descarta y se loggea al audit log, no crashea).
- [ ] **Paso 4:** correr, pasa.
- [ ] **Paso 5: Test — paquete malformado no crashea.**
```python
def test_malformed_packet_does_not_crash():
    sniffer = Sniffer(interface="lo")
    from scapy.layers.l2 import Ether
    packet = Ether()  # sin capa IP

    sniffer._process_packet(packet)  # no debe lanzar excepción

    assert sniffer.get_stats() == {}
```
- [ ] **Paso 6:** correr (probablemente ya pasa si el try/except del paso 3 está bien hecho; si no, ajustar).
- [ ] **Paso 7: Implementar `start()`/`stop()`** usando `scapy.sniff(iface=interface, prn=self._process_packet, store=False, stop_filter=...)` corriendo en un `threading.Thread` separado. No testeado directamente (requiere privilegios reales) — se prueba manualmente en la Tarea 7.
- [ ] **Paso 8 (usuario):** commit de `traffic`.

---

### Tarea 6: `cli` — display en vivo

**Archivos:**
- Crear: `src/lanmon/cli/display.py`
- Test: `tests/cli` (opcional — es la capa menos crítica de testear, prioridad baja)

**Consume:** `Device` de `discovery`, `TrafficStats` de `traffic`, `Event` de `tracker` — todos ya en memoria, `cli` no llama a `storage` directo.

**Produce:** `render(devices: list[Device], traffic: dict[str, TrafficStats], recent_events: list[Event]) -> str` — arma la tabla como texto (usar `rich.table.Table` o formato simple con `str.format`, a tu elección).

- [ ] **Paso 1:** decidir con el usuario si usamos `rich` (tablas lindas, requiere dependencia extra) o solo `print` formateado (cero dependencias). Recomiendo `rich` — mejora mucho la legibilidad de una tabla que se refresca en loop.
- [ ] **Paso 2: Test simple de `render`** — dado un `Device` y stats, el string resultante contiene la IP y el hostname (test de humo, no exhaustivo).
- [ ] **Paso 3: Implementar `render`.**
- [ ] **Paso 4 (usuario):** commit de `cli`.

---

### Tarea 7: `main.py` — orquestador y prueba end-to-end

**Archivos:**
- Modificar: `src/lanmon/main.py`

**Consume:** todo lo anterior — `ArpScanner`, `Tracker`, `Sniffer`, `Database`, `AuditLogger`, `render`, `check_required_privileges`, `drop_privileges`.

- [ ] **Paso 1:** al arrancar, llamar `check_required_privileges()`. Si falla, imprimir mensaje claro (sudo en Linux/Mac, admin+Npcap en Windows) y salir con código de error — no continuar en modo degradado silencioso.
- [ ] **Paso 2:** abrir `Database` con key leída de variable de entorno (`os.environ["LANMON_DB_KEY"]`), fallar con mensaje claro si no está seteada.
- [ ] **Paso 3:** iniciar `Sniffer` (thread), luego llamar `drop_privileges()`.
- [ ] **Paso 4:** loop principal: cada N segundos, `ArpScanner.scan()` → `Tracker.update()` → leer `Sniffer.get_stats()` → `render()` → print. Loggear cada ciclo relevante al `AuditLogger`.
- [ ] **Paso 5:** manejar `KeyboardInterrupt` (Ctrl+C) para `Sniffer.stop()` limpio antes de salir.
- [ ] **Paso 6 (usuario, manual, con privilegios reales):** correr `sudo LANMON_DB_KEY=... python -m lanmon.main` en tu LAN real, verificar que la tabla se llena con tus dispositivos reales y el tráfico se acumula. Este es el único paso que requiere red real — todo lo anterior se validó con mocks.
- [ ] **Paso 7 (usuario):** commit final de `main.py`.

---

### Tarea 8: Docker

**Archivos:**
- Crear: `Dockerfile`, `docker-compose.yml`, `.dockerignore`

- [ ] **Paso 1: `Dockerfile` multi-stage.** Stage `build`: `python:3.12-slim`, instala deps de compilación necesarias para `scapy`/`sqlcipher3` (`libpcap-dev`, `libsqlcipher-dev`, `build-essential`), corre `pip install`. Stage `runtime`: `python:3.12-slim` limpio, copia solo site-packages del build stage, crea `USER appuser` no-root, copia código.
- [ ] **Paso 2: `docker-compose.yml`** — define el servicio con `cap_add: [NET_RAW, NET_ADMIN]` (nunca `privileged: true`), variable de entorno `LANMON_DB_KEY` desde `.env` (no hardcoded en el compose file), volumen para persistir la DB fuera del contenedor.
- [ ] **Paso 3: `.dockerignore`** — excluir `.git`, `tests/`, `docs/`, `.venv`.
- [ ] **Paso 4 (usuario):** `docker compose build && docker compose up`, verificar que el contenedor escanea la red del host correctamente (puede necesitar `network_mode: host` en Linux para que el ARP scan vea la LAN real — documentar esta decisión y su trade-off de seguridad en un comentario en el compose file).
- [ ] **Paso 5 (usuario):** commit de Docker setup.

---

## Autorevisión del plan

- **Cobertura del spec:** discovery ✓ (Tarea 3), tracking ✓ (Tarea 4), traffic ✓ (Tarea 5), CLI ✓ (Tarea 6), SQLite/SQLCipher ✓ (Tarea 1), privilegios ✓ (Tarea 2), audit log ✓ (Tarea 2), validación de input ✓ (Tarea 3 paso 1-4), Docker ✓ (Tarea 8), extensibilidad (`Scanner` abstracto) ✓ (Tarea 3).
- **Placeholders:** ninguno — cada paso tiene código concreto o instrucción ejecutable.
- **Consistencia de tipos:** `Device`, `Event`, `TrafficStats` usados con los mismos campos en todas las tareas que los consumen. `Database` methods referenciados con firma consistente entre Tarea 1 y su uso en Tareas 4/7.
