from __future__ import annotations

from pipelines.repositories.evaluation_report_repository import latest_adoption_decision
from train.dataset_builder import fetch_training_rows, write_csv
from train.trainer import train_model


def run_weekly_retrain() -> dict[str, object]:
    """最新の採用判定が adopt_lgbm=True の場合に再学習を実行する。

    Returns:
        dict: skipped=True（採用判定なし or 非採用）またはトレーニング結果 metadata
    """
    decision = latest_adoption_decision()

    if decision is None:
        print("weekly_retrain: skipped — no adoption decision found (run phase6-weekly-report first)")
        return {"skipped": True, "reason": "no_decision"}

    if not decision["adopt_lgbm"]:
        print(
            f"weekly_retrain: skipped — latest decision is adopt_lgbm=False "
            f"(reason={decision['reason']}, evaluated_at={decision['evaluated_at']})"
        )
        return {"skipped": True, "reason": decision["reason"]}

    print(
        f"weekly_retrain: adopt_lgbm=True confirmed "
        f"(decision_id={decision['id']}, evaluated_at={decision['evaluated_at']})"
    )

    rows = fetch_training_rows()
    write_csv(rows)
    positive = sum(1 for row in rows if int(row["label"]) > 0)
    print(
        f"weekly_retrain: training data generated — rows={len(rows)}, positive={positive}, "
        f"queries={len(set(int(row['search_log_id']) for row in rows))}"
    )

    metadata = train_model()
    print(
        f"weekly_retrain: LightGBM retrained — rows={metadata['rows']}, "
        f"queries={metadata['queries']}, positive_rows={metadata['positive_rows']}, "
        f"model={metadata['model_path']}"
    )
    return metadata


def main() -> None:
    run_weekly_retrain()


if __name__ == "__main__":
    main()
