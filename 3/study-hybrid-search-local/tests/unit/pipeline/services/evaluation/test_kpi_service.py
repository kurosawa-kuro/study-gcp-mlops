"""
正常系テスト: services/evaluation/kpi_service.py
"""
from pipeline.batch_serving_job.services.evaluation.kpi_service import compute_kpi_metrics


def test_basic_kpi():
    result = compute_kpi_metrics(
        impressions=100,
        clicks=10,
        favorites=5,
        inquiries=2,
    )
    assert result["impressions"] == 100
    assert result["clicks"] == 10
    assert result["ctr"] == 0.1
    assert result["favorite_rate"] == 0.05
    assert result["inquiry_rate"] == 0.02
    assert result["cvr"] == 0.2


def test_zero_impressions_returns_zero_rates():
    result = compute_kpi_metrics(impressions=0, clicks=0, favorites=0, inquiries=0)
    assert result["ctr"] == 0.0
    assert result["cvr"] == 0.0
