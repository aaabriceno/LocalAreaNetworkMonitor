# LocalAreaNetworkMonitor — Design

## Objetivo

Aplicación que descubre dispositivos conectados a la red local, trackea cuándo entran/salen de la red, y mide tráfico por dispositivo. CLI, cross-platform (Linux/Windows/Mac), Python.

## Alcance v1

- Descubrimiento de dispositivos en LAN (ARP scan): IP, MAC, hostname, vendor.
- Tracking de estado: detecta entrada/salida de dispositivos, guarda historial.
- Medición de tráfico por dispositivo (bytes/paquetes) vía captura pasiva.
- Interfaz: CLI/terminal, refresco periódico. Sin web UI en v1 (posible fase 2).
- Persistencia: SQLite local, cifrada (SQLCipher).

## Lenguaje y stack

- **Python 3**, por soporte cross-platform maduro para captura de paquetes y ARP sin reinventar sockets raw por OS.
- Librerías clave: `scapy` (ARP scan + sniff de paquetes), `psutil` (interfaces de red), `sqlcipher3` (persistencia cifrada).
- Docker para empaquetado y aislamiento (ver sección Seguridad).

## Arquitectura

```
main.py (orquestador/loop principal)
  ├── discovery/   → ARP scan, resuelve IP/MAC/hostname/vendor
  ├── tracker/     → compara snapshot actual vs DB, detecta entra/sale
  ├── traffic/     → sniff pasivo, agrega bytes/paquetes por IP
  ├── storage/     → SQLite: devices, sessions (entra/sale), traffic_samples
  └── cli/         → tabla en vivo, refresca cada N segundos
```

### Flujo de datos

1. Loop cada N segundos: `discovery` hace ARP scan → lista de devices activos.
2. `tracker` compara contra último estado en `storage` → genera eventos (nuevo device, device desapareció).
3. `traffic` corre en thread separado, sniff continuo, acumula bytes/paquetes por IP en ventana de tiempo.
4. Cada ciclo, `storage` persiste snapshot + eventos + traffic agregado.
5. `cli` lee estado actual y refresca display.

### Contratos de módulos

- `discovery.scan(subnet) -> list[Device(ip, mac, hostname, vendor)]` — sin estado, solo escanea. Implementa interfaz abstracta `Scanner` (ver Extensibilidad).
- `tracker.update(current_devices) -> list[Event]` — depende de storage para comparar contra estado previo.
- `traffic.Sniffer` — clase con `start()/stop()`, corre en thread, expone `get_stats() -> dict[ip, TrafficStats]`.
- `storage` — capa SQLite cifrada: `save_snapshot`, `log_event`, `save_traffic_sample`, `get_history(ip)`. Todas las queries parametrizadas (nunca concatenación de strings).
- `cli` — solo lee, nunca escribe directo a storage.

### Extensibilidad futura (no v1)

El objetivo a mediano plazo incluye monitoreo más allá de LAN doméstica — ej. conexiones activas en un server (SSH, etc). Para no rehacer el core cuando eso llegue:

- `discovery` se diseña detrás de una interfaz `Scanner` abstracta (`scan() -> list[Entity]`). Un futuro `ssh_connections.Scanner` o `server_connections.Scanner` se conecta al mismo `tracker`/`storage`/`cli` sin modificarlos.
- No se implementa en v1 — solo se deja el contrato preparado.

## Manejo de errores y permisos

- ARP scan y sniff requieren privilegios root/admin (raw sockets). App detecta falta de permiso al inicio y muestra mensaje claro (sudo en Linux/Mac, Npcap en Windows), no crash silencioso.
- `discovery` y `traffic` corren en threads separados del loop principal — fallo en uno (ej. interfaz cae) se loggea y reintenta el próximo ciclo, no tumba la app completa.
- Fallo de resolución de hostname/vendor → guarda `None`, no bloquea el resto del snapshot.
- Escrituras SQLite envueltas en try/except con retry simple ante lock por concurrencia entre threads.
- Sin interfaz de red detectada o subnet inválida → error temprano y claro.

## Seguridad

Diseño sigue principios técnicos de OWASP ASVS, CWE Top 25, e ISO/IEC 27001 Annex A (controles relevantes: A.8.15 logging, A.5.15 control de acceso, A.8.24 criptografía). Nota: certificación ISO 27001 completa es un proceso organizacional (auditoría externa, ISMS, políticas) que el código por sí solo no logra — esto es "diseñar siguiendo sus controles técnicos", no una certificación.

**Gestión de privilegios (mitiga CWE-250, uso excesivo de privilegios):**
- App requiere root/admin solo para abrir el raw socket / interfaz de captura.
- Inmediatamente después de abrir el socket, baja privilegios (`os.setuid()` a usuario no-privilegiado) en Linux/Mac. En Windows no existe un drop equivalente limpio — se documenta como limitación conocida (Npcap corre su propio servicio con privilegio separado, lo cual mitiga parcialmente).
- En Docker: contenedor usa `--cap-add=NET_RAW --cap-add=NET_ADMIN`, nunca `--privileged`.

**Cifrado de datos en reposo (mitiga exposición de datos, CWE-311):**
- DB completa cifrada vía SQLCipher. La DB guarda IP/MAC/hostname/tráfico — datos que identifican indirectamente dispositivos y personas reales.
- Key de cifrado viene de variable de entorno o archivo de secrets fuera del repo — nunca hardcoded, nunca commiteada. `.gitignore` cubre `*.db` y archivos de key/secrets.

**Validación de entrada (mitiga CWE-20, CWE-89):**
- Todas las queries SQLite parametrizadas — nunca f-string/concat en SQL (previene SQL injection).
- Parsing de paquetes de red (entrada no confiable por definición) envuelto en try/except específico por capa de protocolo — paquete malformado no crashea ni cuelga el proceso.
- Subnet/CIDR de entrada validado antes de escanear (evita rangos inválidos o escaneos accidentalmente masivos).

**Audit logging (mitiga falta de trazabilidad, control A.8.15):**
- Log estructurado JSON-lines separado (`audit.log`), append-only, distinto del logging operacional normal.
- Eventos registrados: inicio/fin de scan, fallos de permisos, drop de privilegios, paquetes malformados descartados, errores de DB.

**Docker (empaquetado + aislamiento):**
- `Dockerfile` multi-stage: build stage instala deps, runtime stage mínimo (`python:slim`), usuario no-root (`USER appuser`) salvo el capability específico de red necesario.
- `docker-compose.yml` documenta capabilities mínimas, monta volumen externo para persistencia de la DB cifrada.

## Testing

- `discovery`, `tracker`, `storage` son testeables sin red real: mocks de paquetes ARP, DB en memoria (`sqlite3 :memory:`).
- `traffic` se testea con paquetes grabados/mockeados (scapy permite inyectar pcap de prueba), no depende de tráfico real en CI.
- Tests de integración con privilegios reales son opcionales, marcados aparte, no bloquean CI sin privilegios.

## Fuera de alcance (v1)

- Dashboard web (posible fase 2, diseño ya deja capa `storage`/`cli` separada para no rehacer core).
- Alertas/notificaciones.
- Identificación de tipo de dispositivo más allá de vendor (MAC OUI).
