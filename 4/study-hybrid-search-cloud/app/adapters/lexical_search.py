"""Lexical search adapters."""

from __future__ import annotations

from typing import Any

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from ports.lexical_search import LexicalSearchPort

from common import get_logger


class NoopLexicalSearch(LexicalSearchPort):
    def search(
        self,
        *,
        query: str,
        filters: dict[str, Any],
        top_k: int,
    ) -> list[tuple[str, int]]:
        return []


class MeilisearchLexical(LexicalSearchPort):
    """Calls Meilisearch ``/indexes/properties/search`` and returns rank list.

    Authentication precedence (all optional, applied in this order):
    1. ``master_key`` — sent as ``Authorization: Bearer <key>`` directly to
       Meilisearch. Takes precedence over identity-token-based Cloud Run IAM
       auth when both are present, because Meilisearch itself enforces the key.
       Injected via Secret Manager ``--set-secrets=MEILI_MASTER_KEY`` in Cloud
       Run. Empty string means no Meilisearch-level auth header is added.
    2. ``require_identity_token`` — obtains a Google ID token and sends it as
       ``Authorization: Bearer <id-token>`` for Cloud Run IAM authentication.
       When ``master_key`` is non-empty this step is still executed so that the
       Cloud Run ingress lets the request through; the Meilisearch process then
       uses the master key from env (``MEILI_MASTER_KEY``) for its own auth.
    3. ``api_key`` — legacy ``x-meili-api-key`` header (kept for backward
       compatibility; not used in new deployments).
    """

    def __init__(
        self,
        *,
        base_url: str,
        index_name: str = "properties",
        timeout_seconds: float = 3.0,
        api_key: str = "",
        master_key: str = "",
        require_identity_token: bool = True,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._index_name = index_name
        self._timeout_seconds = timeout_seconds
        self._api_key = api_key
        self._master_key = master_key
        self._require_identity_token = require_identity_token
        self._logger = get_logger("app")

    def search(
        self,
        *,
        query: str,
        filters: dict[str, Any],
        top_k: int,
    ) -> list[tuple[str, int]]:
        headers: dict[str, str] = {"content-type": "application/json"}
        if self._api_key:
            headers["x-meili-api-key"] = self._api_key
        if self._master_key:
            headers["authorization"] = f"Bearer {self._master_key}"
        if self._require_identity_token:
            try:
                token = id_token.fetch_id_token(Request(), self._base_url)
                if not self._master_key:
                    # Only override Authorization with ID token when master key
                    # is absent; Cloud Run IAM auth still occurs via ingress.
                    headers["authorization"] = f"Bearer {token}"
            except Exception:
                self._logger.exception("Failed to mint ID token for meili-search")
                return []

        payload: dict[str, Any] = {
            "q": query,
            "limit": top_k,
        }
        filter_expr = _to_meili_filter(filters)
        if filter_expr:
            payload["filter"] = filter_expr

        url = f"{self._base_url}/indexes/{self._index_name}/search"
        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            self._logger.exception("Meilisearch request failed")
            return []

        hits = data.get("hits") or []
        out: list[tuple[str, int]] = []
        for idx, hit in enumerate(hits, start=1):
            property_id = str(hit.get("property_id") or "").strip()
            if not property_id:
                continue
            out.append((property_id, idx))
        return out


def _to_meili_filter(filters: dict[str, Any]) -> str | None:
    clauses: list[str] = []
    max_rent = filters.get("max_rent")
    if max_rent is not None:
        clauses.append(f"rent <= {int(max_rent)}")

    layout = filters.get("layout")
    if layout:
        escaped = str(layout).replace('"', '\\"')
        clauses.append(f'layout = "{escaped}"')

    max_walk_min = filters.get("max_walk_min")
    if max_walk_min is not None:
        clauses.append(f"walk_min <= {int(max_walk_min)}")

    pet_ok = filters.get("pet_ok")
    if pet_ok is not None:
        clauses.append(f"pet_ok = {'true' if bool(pet_ok) else 'false'}")

    max_age = filters.get("max_age")
    if max_age is not None:
        clauses.append(f"age_years <= {int(max_age)}")

    if not clauses:
        return None
    return " AND ".join(clauses)
