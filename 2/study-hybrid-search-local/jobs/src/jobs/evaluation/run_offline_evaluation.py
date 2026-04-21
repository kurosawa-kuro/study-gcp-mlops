from __future__ import annotations

from pipelines.repositories.evaluation_report_repository import insert_offline_eval_report
from pipelines.services.evaluation.offline_metrics_service import compute_offline_metrics


def main() -> None:
    metrics = compute_offline_metrics()
    report = insert_offline_eval_report(metrics)

    print(
        "Offline eval completed: "
        f"report_id={report['id']}, queries={metrics['evaluated_queries']}, "
        f"ndcg10(meili={metrics['ndcg10_meili']}, lgbm={metrics['ndcg10_lgbm']}), "
        f"map(meili={metrics['map_meili']}, lgbm={metrics['map_lgbm']}), "
        f"recall20(meili={metrics['recall20_meili']}, lgbm={metrics['recall20_lgbm']})"
    )


if __name__ == "__main__":
    main()
