"""Run the two local development services and stop both when either exits."""
import signal
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
children = []


def stop(*_):
    for child in children:
        if child.poll() is None:
            child.terminate()


signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)
try:
    children.append(subprocess.Popen([
        "uv", "run", "--project", "backend", "uvicorn",
        "backend.translatebit.main:app", "--host", "127.0.0.1", "--port", "8000",
        *(["--env-file", ".env"] if (ROOT / ".env").exists() else []),
    ], cwd=ROOT))
    children.append(subprocess.Popen(["npm", "run", "dev", "--", "--port", "5173", "--strictPort"], cwd=ROOT))
    while all(child.poll() is None for child in children):
        time.sleep(0.25)
finally:
    stop()
    for child in children:
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
