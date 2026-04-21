"""Learning-oriented top-level API entrypoint.

Keeps the visible layout as `app/main.py` while the FastAPI implementation
resides under `app/api/main.py`.
"""

from api.main import app, create_app

__all__ = ["app", "create_app"]
