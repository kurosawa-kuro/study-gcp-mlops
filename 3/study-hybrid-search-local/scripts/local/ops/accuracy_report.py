from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EvalCase:
    name: str
    q: str
    layout: str | None
    price_lte: int | None
    pet: bool | None
    limit: int
    relevant_ids: list[str]


def _default_cases_path() -> Path:
    return Path(__file__).resolve().parent / "data" / "accuracy_eval_cases.sample.json"


def _load_cases(path: Path) -> list[EvalCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("cases")
    if not isinstance(rows, list) or not rows:
        raise ValueError("cases must be a non-empty list")
    out: list[EvalCase] = []
    for i, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"case[{i}] must be an object")
        q = str(row.get("q", "")).strip()
        if not q:
            raise ValueError(f"case[{i}] q is required")
        rel = row.get("relevant_ids")
        if not isinstance(rel, list) or not rel:
            raise ValueError(f"case[{i}] relevant_ids must be non-empty list")
        out.append(
            EvalCase(
                name=str(row.get("name") or f"case-{i}"),
                q=q,
                layout=str(row["layout"]) if row.get("layout") is not None else None,
                price_lte=int(row["price_lte"]) if row.get("price_lte") is not None else None,
                pet=bool(row["pet"]) if row.get("pet") is not None else None,
                limit=int(row.get("limit", 20)),
                relevant_ids=[str(x) for x in rel],
            )
        )
    return out


def _dcg_binary(relevance: list[int], *, k: int) -> float:
    score = 0.0
    for i, rel in enumerate(relevance[:k], start=1):
        if rel > 0:
            score += 1.0 / math.log2(i + 1.0)
    return score


def _ndcg_at_k_binary(relevance: list[int], *, k: int) -> float:
    actual = _dcg_binary(relevance, k=k)
    ideal = _dcg_binary(sorted(relevance, reverse=True), k=k)
    if ideal == 0.0:
        return 0.0
    return actual / ideal


def _hit_rate_at_k_binary(relevance: list[int], *, k: int) -> float:
    return 1.0 if any(r > 0 for r in relevance[:k]) else 0.0


def _mrr_at_k_binary(relevance: list[int], *, k: int) -> float:
    for i, rel in enumerate(relevance[:k], start=1):
        if rel > 0:
            return 1.0 / float(i)
    return 0.0


def _request(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return exc.code, body


def main() -> int:
    api_base = os.environ.get("LOCAL_API_URL", "http://localhost:8000").rstrip("/")
    cases_path = Path(os.environ.get("EVAL_CASES_FILE", str(_default_cases_path())))
    k = int(os.environ.get("EVAL_K", "10"))
    min_hit_rate = float(os.environ.get("MIN_HIT_RATE_AT_K", "0.0001"))

    try:
        cases = _load_cases(cases_path)
    except Exception as exc:
        print(f"accuracy-report config error: {exc}")
        return 1

    ndcgs: list[float] = []
    hit_rates: list[float] = []
    mrrs: list[float] = []
    per_case: list[dict] = []

    for case in cases:
        params: dict[str, str] = {"q": case.q, "limit": str(case.limit)}
        if case.layout is not None:
            params["layout"] = case.layout
        if case.price_lte is not None:
            params["price_lte"] = str(case.price_lte)
        if case.pet is not None:
            params["pet"] = "true" if case.pet else "false"
        query = urllib.parse.urlencode(params)
        status, body = _request(f"{api_base}/search?{query}")
        if status != 200:
            print(f"accuracy-report search failed ({case.name}) HTTP {status}: {body}")
            return 1
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            print(f"accuracy-report search returned non-JSON ({case.name}): {body}")
            return 1
        items = data.get("items")
        if not isinstance(items, list):
            print(f"accuracy-report malformed items ({case.name})")
            return 1

        relevant_set = set(case.relevant_ids)
        relevance: list[int] = []
        matched = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            pid = str(item.get("id", ""))
            hit = 1 if pid in relevant_set else 0
            relevance.append(hit)
            matched += hit

        ndcg = _ndcg_at_k_binary(relevance, k=k)
        hit_rate = _hit_rate_at_k_binary(relevance, k=k)
        mrr = _mrr_at_k_binary(relevance, k=k)
        ndcgs.append(ndcg)
        hit_rates.append(hit_rate)
        mrrs.append(mrr)
        per_case.append(
            {
                "name": case.name,
                "q": case.q,
                "returned": len(items),
                "relevant_total": len(case.relevant_ids),
                "matched_in_results": matched,
                f"ndcg_at_{k}": round(ndcg, 4),
                f"hit_rate_at_{k}": round(hit_rate, 4),
                f"mrr_at_{k}": round(mrr, 4),
            }
        )

    summary = {
        f"ndcg_at_{k}": round(sum(ndcgs) / len(ndcgs), 4),
        f"hit_rate_at_{k}": round(sum(hit_rates) / len(hit_rates), 4),
        f"mrr_at_{k}": round(sum(mrrs) / len(mrrs), 4),
    }
    report = {
        "target": "local",
        "api_url": api_base,
        "cases_file": str(cases_path),
        "num_cases": len(cases),
        "k": k,
        "summary": summary,
        "per_case": per_case,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if summary[f"hit_rate_at_{k}"] < min_hit_rate:
        print(
            "accuracy-report gate failed: "
            f"hit_rate_at_{k}={summary[f'hit_rate_at_{k}']} < MIN_HIT_RATE_AT_K={min_hit_rate}"
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
