"""Backward-compat shim for ``ApiSettings``.

Canonical import path is now ``app.settings.ApiSettings``.
"""

from app.settings import ApiSettings

__all__ = ["ApiSettings"]
