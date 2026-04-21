"""
正常系テスト: services/embeddings/similarity_service.py
"""
from pipelines.services.embeddings.similarity_service import cosine_similarity


def test_identical_vectors():
    v = [1.0, 0.0, 0.0]
    assert cosine_similarity(v, v) == 1.0


def test_orthogonal_vectors():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert cosine_similarity(a, b) == 0.0


def test_normalized_vectors():
    import math
    a = [1.0, 1.0]
    norm = math.sqrt(2)
    a_n = [v / norm for v in a]
    result = cosine_similarity(a_n, a_n)
    assert abs(result - 1.0) < 1e-9
