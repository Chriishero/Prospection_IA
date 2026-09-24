from pathlib import Path
import shutil

root = Path(__file__).resolve().parent

for path in root.rglob("__pycache__"):
    if path.is_dir():
        shutil.rmtree(path)

for pattern in ("*.pyc", "*.pyo", "~$*"):
    for path in root.rglob(pattern):
        if path.is_file():
            path.unlink()
