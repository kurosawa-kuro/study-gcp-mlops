from __future__ import annotations


def compute_kpi_metrics(
    *,
    impressions: int,
    clicks: int,
    favorites: int,
    inquiries: int,
) -> dict[str, float | int]:
    ctr = (clicks / impressions) if impressions > 0 else 0.0
    favorite_rate = (favorites / impressions) if impressions > 0 else 0.0
    inquiry_rate = (inquiries / impressions) if impressions > 0 else 0.0
    cvr = (inquiries / clicks) if clicks > 0 else 0.0

    return {
        "impressions": impressions,
        "clicks": clicks,
        "favorites": favorites,
        "inquiries": inquiries,
        "ctr": round(ctr, 6),
        "favorite_rate": round(favorite_rate, 6),
        "inquiry_rate": round(inquiry_rate, 6),
        "cvr": round(cvr, 6),
    }