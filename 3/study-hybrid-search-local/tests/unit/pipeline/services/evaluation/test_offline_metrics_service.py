"""
正常系テスト: services/evaluation/offline_metrics_service.py（純粋関数のみ）
"""

from pipeline.batch_serving_job.services.evaluation.offline_metrics_service import (
    _avg_precision,
    _find_rank,
    _ndcg_at_10,
    _recall_at_20,
)


def test_find_rank_found():
    ids = [10, 20, 30, 40]
    assert _find_rank(ids, 30, 10) == 3


def test_find_rank_outside_k():
    ids = [10, 20, 30]
    assert _find_rank(ids, 30, 2) is None


def test_ndcg_rank1():
    gain = 1.0
    result = _ndcg_at_10(1, gain)
    assert result == 1.0


def test_ndcg_not_found():
    assert _ndcg_at_10(None, 1.0) == 0.0


def test_avg_precision_rank1():
    assert _avg_precision(1) == 1.0


def test_avg_precision_not_found():
    assert _avg_precision(None) == 0.0


def test_recall_at_20_found():
    assert _recall_at_20(5) == 1.0


def test_recall_at_20_not_found():
    assert _recall_at_20(None) == 0.0
