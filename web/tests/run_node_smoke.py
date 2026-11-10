"""Start a real FastAPI server and test the actual JS frontend API via Node 22."""
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
backend = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '18081', '--no-access-log'],
    cwd=ROOT/'backend', stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
try:
    for _ in range(50):
        try:
            with urlopen('http://127.0.0.1:18081/api/health', timeout=1) as response:
                if response.status == 200:
                    break
        except OSError:
            time.sleep(0.1)
    else:
        raise RuntimeError('FastAPI failed to start')
    subprocess.run(['node', str(ROOT/'tests'/'smoke_upload_node.mjs')], check=True, cwd=ROOT)
finally:
    backend.terminate()
    try:
        backend.wait(timeout=4)
    except subprocess.TimeoutExpired:
        backend.kill()
