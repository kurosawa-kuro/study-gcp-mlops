def build_response(items: list[dict]) -> dict:
    return {"items": items, "count": len(items)}


__all__ = ["build_response"]
