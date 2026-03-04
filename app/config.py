from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DOWNLOAD_TOKEN = os.getenv("DISPATCH_BOX_DOWNLOAD_TOKEN", "")
