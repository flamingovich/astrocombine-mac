from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "server" / "studio_ipc_worker.py"


class StudioBridge:
    """Single-threaded request serialization to one studio IPC worker process."""

    def __init__(self) -> None:
        self._proc: Optional[subprocess.Popen[str]] = None
        self._lock = threading.Lock()
        self._last_error: Optional[str] = None

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @property
    def ready(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> None:
        with self._lock:
            self._ensure_unlocked()

    def _ensure_unlocked(self) -> None:
        if self._proc and self._proc.poll() is None:
            return
        self._proc = None
        self._last_error = None
        try:
            env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
            self._proc = subprocess.Popen(
                [sys.executable, "-u", str(WORKER)],
                cwd=str(ROOT),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env,
            )
            out = self._request_unlocked({"cmd": "ping"})
            if not out.get("ok"):
                raise RuntimeError(out.get("error") or "ping failed")
        except Exception as e:
            self._last_error = str(e)
            if self._proc:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

    def stop(self) -> None:
        with self._lock:
            if not self._proc:
                return
            try:
                self._request_unlocked({"cmd": "shutdown"})
            except Exception:
                pass
            try:
                self._proc.kill()
            except Exception:
                pass
            self._proc = None

    def _request_unlocked(self, obj: Dict[str, Any]) -> Dict[str, Any]:
        if not self._proc or not self._proc.stdin or not self._proc.stdout:
            return {"ok": False, "error": "studio worker not running"}
        line = json.dumps(obj, ensure_ascii=False) + "\n"
        self._proc.stdin.write(line)
        self._proc.stdin.flush()
        out_line = self._proc.stdout.readline()
        if not out_line:
            err = ""
            try:
                if self._proc.stderr:
                    err = self._proc.stderr.read()[:4000]
            except Exception:
                pass
            return {"ok": False, "error": f"worker stdout closed: {err}"}
        try:
            return json.loads(out_line)
        except Exception as e:
            return {"ok": False, "error": f"bad worker json: {e}: {out_line[:500]!r}"}

    def request(self, obj: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            self._ensure_unlocked()
            if not self._proc:
                return {"ok": False, "error": self._last_error or "studio worker failed to start"}
            return self._request_unlocked(obj)


bridge = StudioBridge()
