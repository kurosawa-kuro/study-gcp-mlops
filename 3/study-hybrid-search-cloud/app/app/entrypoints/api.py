"""Backward-compatible import path for the old `app.entrypoints.api` module."""

from app.api.main import app, create_app

__all__ = ["app", "create_app"]
