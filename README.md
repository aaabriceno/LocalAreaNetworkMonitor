# LocalAreaNetworkMonitor

Aplicación CLI para el monitoreo de la red local: descubre los dispositivos conectados a la LAN, trackea cuándo se conectan/desconectan, y mide el tráfico por dispositivo. Proyecto de aprendizaje que combina redes, programación de sistemas y (a futuro) desarrollo web.

## Qué hace

- **Descubrimiento**: escanea la red local (ARP scan) y detecta IP, MAC, hostname y fabricante (vendor) de cada dispositivo conectado.
- **Tracking de estado**: detecta cuándo un dispositivo se une o abandona la red, y guarda el historial.
- **Tráfico por dispositivo**: mide bytes y paquetes transmitidos por cada dispositivo mediante captura pasiva.
- **Interfaz CLI**: tabla en vivo en terminal, con refresco periódico. Sin interfaz web en v1 — el diseño deja preparada esa extensión para una fase futura.

## Stack

- **Python 3** — soporte cross-platform maduro para captura de paquetes sin reinventar sockets raw por sistema operativo.
- `scapy` — ARP scan y sniffing de paquetes.
- `psutil` — enumeración de interfaces de red.
- `sqlcipher3` — persistencia local cifrada (SQLite + cifrado en reposo).
- Docker — empaquetado y aislamiento con privilegios mínimos.

## Seguridad

El diseño se guía por controles técnicos de OWASP ASVS, CWE Top 25 e ISO/IEC 27001 Annex A (logging de auditoría, control de acceso, criptografía). Puntos clave:

- La app requiere privilegios root/admin solo para abrir el socket de captura, y los baja inmediatamente después.
- La base de datos local se guarda cifrada (SQLCipher) — nunca en texto plano.
- Todas las queries SQL son parametrizadas; nunca concatenación de strings.
- Log de auditoría estructurado, separado del log operacional.
- En Docker: capabilities mínimas (`NET_RAW`, `NET_ADMIN`), nunca `--privileged`.

Detalle completo en el [spec de diseño](docs/superpowers/specs/2026-08-11-lan-monitor-design.md).

## Estado del proyecto

En desarrollo activo. Ver el [plan de implementación](docs/superpowers/plans/2026-08-11-lan-monitor-v1.md) para el detalle de tareas y su progreso.

## Documentación

- [Spec de diseño](docs/superpowers/specs/2026-08-11-lan-monitor-design.md) — arquitectura, módulos, decisiones y su justificación.
- [Plan de implementación](docs/superpowers/plans/2026-08-11-lan-monitor-v1.md) — tareas paso a paso con TDD.
