"""Learning-oriented top-level API entrypoint.

Keeps the visible layout as `app/main.py` while the FastAPI implementation
resides under `app/api/main.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure legacy absolute imports in app/api/main.py (e.g. `from adapters import ...`)
# resolve regardless of current working directory.
APP_ROOT = Path(__file__).resolve().parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from api.main import app, create_app

__all__ = ["app", "create_app"]
