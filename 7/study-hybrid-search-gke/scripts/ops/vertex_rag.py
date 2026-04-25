"""POST /rag end-to-end smoke (search-api → Gemini → summary).

Verifies the search-api routes a search through the LLM (Gemini) and
returns a non-empty natural-language summary. The Phase 6 RAG path
chains: SearchService.search() → top_n results → GeminiGenerator →
RagSummary. This script proves the full chain on the deployed Pod.

Requires ``ENABLE_RAG=true`` on the deployment + a working Gemini
binding (sa-api with ``aiplatform.user`` IAM).

Usage::

    QUERY="新宿 ペット可" make ops-vertex-rag

Exit codes:
    0  — /rag 200 with non-empty summary text
    1  — non-200 or empty summary (config / IAM / model error)
"""

from __future__ import annotations

import json
import os

from scripts._common import fail, http_json, resolve_api_target


def main() -> int:
    query = os.environ.get("QUERY", "新宿 1LDK ペット可")
    top_n = int(os.environ.get("RAG_TOP_N", "5"))

    try:
        target = resolve_api_target()
    except Exception as exc:
        return fail(f"vertex-rag: config error: {exc}")

    payload = {"query": query, "top_k": 20, "rag_top_n": top_n}
    status, body = http_json("POST", f"{target.url}/rag", token=target.token, payload=payload)
    if status != 200:
        return fail(f"vertex-rag: HTTP {status}: {body}")

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return fail(f"vertex-rag: non-JSON body: {body[:200]}")

    summary = (data.get("summary") or "").strip()
    if not summary:
        return fail(
            f"vertex-rag: empty summary. "
            f"Check ENABLE_RAG / GEMINI_MODEL_NAME / aiplatform.user IAM. response={data}"
        )

    print("vertex-rag PASS")
    print(f"  query={query!r}")
    print(f"  prompt_chars={data.get('prompt_chars')}")
    print(f"  top_n={top_n}")
    print(f"  summary[:300]={summary[:300]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
