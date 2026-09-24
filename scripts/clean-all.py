from pathlib import Path
import shutil

root = Path(__file__).resolve().parent

for path in root.rglob(".venv"):
    if path.is_dir():
        shutil.rmtree(path)
