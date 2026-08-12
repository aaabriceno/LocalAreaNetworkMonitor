import json
from lanmon.security.audit_log import AuditLogger

def test_log_writes_json_line(tmp_path):
    log_path = tmp_path / "audit.log"
    logger = AuditLogger(str(log_path))
    logger.log("scan_started", subnet = "192.168.1.0/24")
    lineas = log_path.read_text().strip().split("\n")
    assert len(lineas) == 1
    entrada = json.loads(lineas[0])
    assert entrada["event"] == "scan_started"
    assert entrada["subnet"] == "192.168.1.0/24"
    assert "timestamp" in entrada
