from __future__ import annotations

import os
import time
from typing import Any

import httpx

from common.core.exceptions import MeilisearchTaskError, MeilisearchTimeoutError
from common.core.logging import get_logger

logger = get_logger(__name__)


class MeiliClient:
    def __init__(
        self,
        base_url: str | None = None,
        index_name: str = "properties",
        api_key: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        raw_url = base_url or os.getenv("MEILI_HTTP_ADDR", "meilisearch:7700")
        if raw_url.startswith("http://") or raw_url.startswith("https://"):
            self.base_url = raw_url.rstrip("/")
        else:
            self.base_url = f"http://{raw_url.strip('/')}"

        self.index_name = index_name
        self.timeout = timeout
        self.task_timeout_seconds = float(os.getenv("MEILI_TASK_TIMEOUT_SECONDS", "30"))
        self.task_poll_interval_seconds = float(os.getenv("MEILI_TASK_POLL_INTERVAL_SECONDS", "0.2"))
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    def _request(self, method: str, path: str, payload: Any | None = None) -> Any:
        url = f"{self.base_url}{path}"
        start_time = time.time()
        
        try:
            with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
                response = client.request(method, url, json=payload)
                response.raise_for_status()
                
                elapsed = time.time() - start_time
                logger.debug(
                    f"meilisearch_request_{method.lower()}",
                    extra={
                        "method": method,
                        "path": path,
                        "status_code": response.status_code,
                        "elapsed_time_ms": round(elapsed * 1000, 2),
                    },
                )
                
                if response.content:
                    return response.json()
                return {}
        except httpx.TimeoutException as exc:
            logger.error(
                "meilisearch_timeout",
                extra={
                    "method": method,
                    "path": path,
                    "timeout": self.timeout,
                    "error": str(exc),
                },
            )
            raise
        except httpx.HTTPError as exc:
            logger.error(
                "meilisearch_request_error",
                extra={
                    "method": method,
                    "path": path,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )
            raise

    def _wait_for_task(self, task_uid: int) -> None:
        started_at = time.monotonic()

        while True:
            task = self._request("GET", f"/tasks/{task_uid}")
            status = task.get("status")

            if status == "succeeded":
                return

            if status in {"failed", "canceled"}:
                raise MeilisearchTaskError(
                    f"Meilisearch task failed: uid={task_uid}, status={status}, detail={task}"
                )

            if time.monotonic() - started_at > self.task_timeout_seconds:
                raise MeilisearchTimeoutError(
                    f"Meilisearch task timed out: uid={task_uid}, timeout={self.task_timeout_seconds}s"
                )

            time.sleep(self.task_poll_interval_seconds)

    def search(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", f"/indexes/{self.index_name}/search", payload)

    def create_index_if_missing(self, primary_key: str = "id") -> None:
        indexes = self._request("GET", "/indexes")
        existing = {item.get("uid") for item in indexes.get("results", [])}
        if self.index_name in existing:
            return
        result = self._request(
            "POST",
            "/indexes",
            {"uid": self.index_name, "primaryKey": primary_key},
        )
        task_uid = result.get("taskUid")
        if task_uid is not None:
            self._wait_for_task(int(task_uid))

    def set_filterable_attributes(self, attributes: list[str]) -> None:
        result = self._request(
            "PUT",
            f"/indexes/{self.index_name}/settings/filterable-attributes",
            attributes,
        )
        task_uid = result.get("taskUid")
        if task_uid is not None:
            self._wait_for_task(int(task_uid))

    def add_documents(self, documents: list[dict[str, Any]]) -> None:
        if not documents:
            return
        result = self._request("POST", f"/indexes/{self.index_name}/documents", documents)
        task_uid = result.get("taskUid")
        if task_uid is not None:
            self._wait_for_task(int(task_uid))

    def delete_documents_by_ids(self, ids: list[int]) -> None:
        if not ids:
            return
        result = self._request("POST", f"/indexes/{self.index_name}/documents/delete-batch", ids)
        task_uid = result.get("taskUid")
        if task_uid is not None:
            self._wait_for_task(int(task_uid))
