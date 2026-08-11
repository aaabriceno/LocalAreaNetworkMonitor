# LocalAreaNetworkMonitor — Design

## Objetivo

Aplicación que descubre dispositivos conectados a la red local, trackea cuándo entran/salen de la red, y mide tráfico por dispositivo. CLI, cross-platform (Linux/Windows/Mac), Python.

## Alcance v1

- Descubrimiento de dispositivos en LAN (ARP scan): IP, MAC, hostname, vendor.
- Tracking de estado: detecta entrada/salida de dispositivos, guarda historial.
- Medición de tráfico por dispositivo (bytes/paquetes) vía captura pasiva.
- Interfaz: CLI/terminal, refresco periódico. Sin web UI en v1 (posible fase 2).
- Persistencia: SQLite local.

## Lenguaje y stack

- **Python 3**, por soporte cross-platform maduro para captura de paquetes y ARP sin reinventar sockets raw por OS.
- Librerías clave: `scapy` (ARP scan + sniff de paquetes), `psutil` (interfaces de red), `sqlite3` (stdlib).

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

- `discovery.scan(subnet) -> list[Device(ip, mac, hostname, vendor)]` — sin estado, solo escanea.
- `tracker.update(current_devices) -> list[Event]` — depende de storage para comparar contra estado previo.
- `traffic.Sniffer` — clase con `start()/stop()`, corre en thread, expone `get_stats() -> dict[ip, TrafficStats]`.
- `storage` — capa SQLite: `save_snapshot`, `log_event`, `save_traffic_sample`, `get_history(ip)`.
- `cli` — solo lee, nunca escribe directo a storage.

## Manejo de errores y permisos

- ARP scan y sniff requieren privilegios root/admin (raw sockets). App detecta falta de permiso al inicio y muestra mensaje claro (sudo en Linux/Mac, Npcap en Windows), no crash silencioso.
- `discovery` y `traffic` corren en threads separados del loop principal — fallo en uno (ej. interfaz cae) se loggea y reintenta el próximo ciclo, no tumba la app completa.
- Fallo de resolución de hostname/vendor → guarda `None`, no bloquea el resto del snapshot.
- Escrituras SQLite envueltas en try/except con retry simple ante lock por concurrencia entre threads.
- Sin interfaz de red detectada o subnet inválida → error temprano y claro.

## Testing

- `discovery`, `tracker`, `storage` son testeables sin red real: mocks de paquetes ARP, DB en memoria (`sqlite3 :memory:`).
- `traffic` se testea con paquetes grabados/mockeados (scapy permite inyectar pcap de prueba), no depende de tráfico real en CI.
- Tests de integración con privilegios reales son opcionales, marcados aparte, no bloquean CI sin privilegios.

## Fuera de alcance (v1)

- Dashboard web (posible fase 2, diseño ya deja capa `storage`/`cli` separada para no rehacer core).
- Alertas/notificaciones.
- Identificación de tipo de dispositivo más allá de vendor (MAC OUI).
