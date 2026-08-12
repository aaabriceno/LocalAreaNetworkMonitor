import json
import time
from pathlib import Path

class AuditLogger:
    def __init__(self, path: str):
        self._path = Path(path)

    def log(self, event: str, **fields) -> None:
        entrada = {"timestamp": time.time(), "event": event, **fields}
        with self._path.open("a") as f:
            f.write(json.dumps(entrada) + "\n")