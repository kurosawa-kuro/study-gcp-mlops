"""
正常系テスト: services/search/query_filter_builder.py
"""
from pipelines.services.search.query_filter_builder import build_search_payload


def test_no_filters():
    payload = build_search_payload(
        q="マンション", city=None, layout=None,
        price_lte=None, pet=None, walk_min=None,
    )
    assert payload["q"] == "マンション"
    assert payload["limit"] == 100
    assert "filter" not in payload


def test_all_filters():
    payload = build_search_payload(
        q="", city="札幌市", layout="2LDK",
        price_lte=80000, pet=True, walk_min=10,
    )
    filters = payload["filter"]
    assert any("city" in f for f in filters)
    assert any("layout" in f for f in filters)
    assert any("price" in f for f in filters)
    assert any("pet = true" in f for f in filters)
    assert any("walk_min" in f for f in filters)


def test_candidate_limit():
    payload = build_search_payload(
        q="", city=None, layout=None,
        price_lte=None, pet=None, walk_min=None,
        candidate_limit=50,
    )
    assert payload["limit"] == 50
