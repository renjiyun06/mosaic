from pathlib import Path
from typing import Literal

class SessionLogger:
    def __init__(self, mesh_id: str, node_id: str, session_id: str):
        self._mesh_id = mesh_id
        self._node_id = node_id
        self._session_id = session_id
        self._log_dir = Path.home() / ".mosaic" / "logs" / mesh_id / node_id / "sessions"
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self._log_dir / f"{session_id}.log"
        self._log_file.touch(exist_ok=True)

    def log(self, role: Literal["User", "Assistant", "System"], message: str):
        with open(self._log_file, "a") as f:
            f.write(f"{role}: {message}\n")