"""
Run the FastAPI backend and the Vite frontend together for local development.

    cd backend && uv run python scripts/dev.py

Starts the backend with hot reload on :8000 and the Vite dev server on :5173.
Vite proxies API routes to the backend, so open http://localhost:5173.
Press Ctrl-C to stop both.
"""

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

# backend/scripts/dev.py -> parents[2] is the repo root.
ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"


def main() -> int:
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm is None:
        sys.exit("npm not found on PATH. Install Node.js to run the frontend.")
    if not (FRONTEND_DIR / "node_modules").exists():
        sys.exit(
            "frontend/node_modules missing — run `npm install` in the frontend/ directory first."
        )

    backend_env = {**os.environ, "HOT_RELOAD": "true"}
    procs = [
        subprocess.Popen([sys.executable, "main.py"], cwd=BACKEND_DIR, env=backend_env),
        subprocess.Popen([npm, "run", "dev"], cwd=FRONTEND_DIR),
    ]

    try:
        # Wait until either process exits, then tear the other one down.
        while True:
            for p in procs:
                code = p.poll()
                if code is not None:
                    print(f"\nProcess exited ({code}); shutting down.", file=sys.stderr)
                    return code or 0
            time.sleep(0.3)
    except KeyboardInterrupt:
        return 0
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    raise SystemExit(main())
