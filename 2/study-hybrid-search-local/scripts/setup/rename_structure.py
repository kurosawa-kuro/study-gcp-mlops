#!/usr/bin/env python3
"""
src/ ディレクトリの命名規則統一スクリプト
技術名ベース → 責務ベースへリネーム

実行: python scripts/setup/rename_structure.py
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

# ---------------------------------------------------------------------------
# 1. ファイル移動マッピング  (旧パス → 新パス)  ※ SRC からの相対
# ---------------------------------------------------------------------------
FILE_MOVES: list[tuple[str, str]] = [
    # --- infra/database → repositories ---
    ("infra/database/db.py",                             "repositories/db.py"),

    # --- infra/repositories → repositories (責務名ベースにリネーム) ---
    ("infra/repositories/engagement.py",                 "repositories/search_log_repository.py"),
    ("infra/repositories/me5_repository.py",             "repositories/property_embedding_repository.py"),
    ("infra/repositories/ranking_compare.py",            "repositories/ranking_compare_repository.py"),

    # --- eval → services/evaluation ---
    ("eval/offline_metrics.py",                          "services/evaluation/offline_metrics_service.py"),

    # --- batch/evaluation/metrics/evaluation_store → repositories ---
    ("batch/evaluation/metrics/evaluation_store.py",     "repositories/evaluation_report_repository.py"),

    # --- batch/evaluation/metrics/kpi_utils → services/evaluation ---
    ("batch/evaluation/metrics/kpi_utils.py",            "services/evaluation/kpi_service.py"),

    # --- search → clients / services/search ---
    ("search/meili_client.py",                           "clients/meilisearch_client.py"),
    ("search/query_builder.py",                          "services/search/query_filter_builder.py"),
    ("search/search_service.py",                         "services/search/property_search_service.py"),

    # --- ranking → services/ranking ---
    ("ranking/features.py",                              "services/ranking/feature_service.py"),
    ("ranking/inference.py",                             "services/ranking/lgbm_reranker.py"),

    # --- ml → services/embeddings + training ---
    ("ml/me5_embed.py",                                  "services/embeddings/me5_embedding_service.py"),
    ("ml/similarity.py",                                 "services/embeddings/similarity_service.py"),
    ("ml/training_data.py",                              "training/training_dataset_builder.py"),
    ("ml/train_lgbm.py",                                 "training/lgbm_trainer.py"),

    # --- batch/* → jobs/* ---
    ("batch/maintenance/run_sql.py",                     "jobs/maintenance/run_migrations.py"),
    ("batch/search_index/meili_sync.py",                 "jobs/indexing/sync_properties_to_meilisearch.py"),
    ("batch/features/daily_stats.py",                    "jobs/features/aggregate_daily_property_stats.py"),
    ("batch/features/feature_report.py",                 "jobs/features/export_feature_report.py"),
    ("batch/embeddings/me5_generate.py",                 "jobs/embeddings/generate_property_embeddings.py"),
    ("batch/evaluation/metrics/offline_eval.py",         "jobs/evaluation/run_offline_evaluation.py"),
    ("batch/evaluation/metrics/kpi_daily.py",            "jobs/evaluation/aggregate_daily_kpi.py"),
    ("batch/evaluation/reports/ranking_compare_report.py","jobs/evaluation/export_ranking_compare_report.py"),
    ("batch/evaluation/reports/weekly_eval_report.py",   "jobs/evaluation/export_weekly_evaluation_report.py"),
    ("batch/training/weekly_retrain.py",                 "jobs/training/run_weekly_retraining.py"),
]

# ---------------------------------------------------------------------------
# 2. import パス書き換えマッピング  (旧モジュールパス → 新モジュールパス)
# ---------------------------------------------------------------------------
IMPORT_REPLACEMENTS: list[tuple[str, str]] = [
    # infra
    ("src.infra.database.db",                                    "src.repositories.db"),
    ("src.infra.repositories.engagement",                        "src.repositories.search_log_repository"),
    ("src.infra.repositories.me5_repository",                    "src.repositories.property_embedding_repository"),
    ("src.infra.repositories.ranking_compare",                   "src.repositories.ranking_compare_repository"),

    # eval
    ("src.eval.offline_metrics",                                 "src.services.evaluation.offline_metrics_service"),

    # evaluation_store / kpi_utils
    ("src.batch.evaluation.metrics.evaluation_store",            "src.repositories.evaluation_report_repository"),
    ("src.batch.evaluation.metrics.kpi_utils",                   "src.services.evaluation.kpi_service"),

    # search
    ("src.search.meili_client",                                  "src.clients.meilisearch_client"),
    ("src.search.query_builder",                                  "src.services.search.query_filter_builder"),
    ("src.search.search_service",                                 "src.services.search.property_search_service"),

    # ranking
    ("src.ranking.features",                                     "src.services.ranking.feature_service"),
    ("src.ranking.inference",                                    "src.services.ranking.lgbm_reranker"),

    # ml
    ("src.ml.me5_embed",                                         "src.services.embeddings.me5_embedding_service"),
    ("src.ml.similarity",                                        "src.services.embeddings.similarity_service"),
    ("src.ml.training_data",                                     "src.training.training_dataset_builder"),
    ("src.ml.train_lgbm",                                        "src.training.lgbm_trainer"),

    # batch
    ("src.batch.maintenance.run_sql",                            "src.jobs.maintenance.run_migrations"),
    ("src.batch.search_index.meili_sync",                        "src.jobs.indexing.sync_properties_to_meilisearch"),
    ("src.batch.features.daily_stats",                           "src.jobs.features.aggregate_daily_property_stats"),
    ("src.batch.features.feature_report",                        "src.jobs.features.export_feature_report"),
    ("src.batch.embeddings.me5_generate",                        "src.jobs.embeddings.generate_property_embeddings"),
    ("src.batch.evaluation.metrics.offline_eval",                "src.jobs.evaluation.run_offline_evaluation"),
    ("src.batch.evaluation.metrics.kpi_daily",                   "src.jobs.evaluation.aggregate_daily_kpi"),
    ("src.batch.evaluation.reports.ranking_compare_report",      "src.jobs.evaluation.export_ranking_compare_report"),
    ("src.batch.evaluation.reports.weekly_eval_report",          "src.jobs.evaluation.export_weekly_evaluation_report"),
    ("src.batch.training.weekly_retrain",                        "src.jobs.training.run_weekly_retraining"),
]

# ---------------------------------------------------------------------------
# 3. Makefile の書き換えマッピング  (旧文字列 → 新文字列)
# ---------------------------------------------------------------------------
MAKEFILE_REPLACEMENTS: list[tuple[str, str]] = [
    # python -m モジュール
    ("python -m src.batch.maintenance.run_sql",          "python -m src.jobs.maintenance.run_migrations"),
    ("python -m src.batch.search_index.meili_sync",      "python -m src.jobs.indexing.sync_properties_to_meilisearch"),
    ("python -m src.batch.features.daily_stats",         "python -m src.jobs.features.aggregate_daily_property_stats"),
    ("python -m src.batch.features.feature_report",      "python -m src.jobs.features.export_feature_report"),
    ("python -m src.batch.embeddings.me5_generate",      "python -m src.jobs.embeddings.generate_property_embeddings"),
    ("python -m src.ml.training_data",                   "python -m src.training.training_dataset_builder"),
    ("python -m src.ml.train_lgbm",                      "python -m src.training.lgbm_trainer"),
    ("python -m src.batch.evaluation.reports.ranking_compare_report",
                                                         "python -m src.jobs.evaluation.export_ranking_compare_report"),
    ("python -m src.batch.evaluation.metrics.offline_eval",
                                                         "python -m src.jobs.evaluation.run_offline_evaluation"),
    ("python -m src.batch.evaluation.metrics.kpi_daily", "python -m src.jobs.evaluation.aggregate_daily_kpi"),
    ("python -m src.batch.evaluation.reports.weekly_eval_report",
                                                         "python -m src.jobs.evaluation.export_weekly_evaluation_report"),
    ("python -m src.batch.training.weekly_retrain",      "python -m src.jobs.training.run_weekly_retraining"),
    # ファイルパス
    ("src/infra/migrations/",                            "src/migrations/"),
]

# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------
def ensure_init(pkg_dir: Path) -> None:
    """パッケージディレクトリに __init__.py がなければ作成する。"""
    init = pkg_dir / "__init__.py"
    if not init.exists():
        init.write_text("")


def apply_imports(content: str) -> str:
    """ファイル内容の import パスを一括書き換え。"""
    for old, new in IMPORT_REPLACEMENTS:
        content = content.replace(old, new)
    return content


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------
def main() -> None:
    # ----- Step 1: ファイル移動 -----
    for rel_old, rel_new in FILE_MOVES:
        src_path = SRC / rel_old
        dst_path = SRC / rel_new

        if not src_path.exists():
            print(f"[SKIP] 存在しません: {src_path.relative_to(ROOT)}")
            continue

        # 移動先ディレクトリと __init__.py を準備
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        for d in [dst_path.parent, *dst_path.parent.parents]:
            if d == SRC.parent:
                break
            ensure_init(d)

        # 内容を読み込み、import 書き換え
        content = src_path.read_text(encoding="utf-8")
        content = apply_imports(content)

        # 書き込み
        dst_path.write_text(content, encoding="utf-8")
        print(f"[MOVE] {src_path.relative_to(ROOT)}  →  {dst_path.relative_to(ROOT)}")

    # ----- Step 2: 移動しなかった Python ファイルの import 書き換え -----
    moved_srcs = {SRC / rel_old for rel_old, _ in FILE_MOVES}
    for py_file in SRC.rglob("*.py"):
        if "__pycache__" in py_file.parts:
            continue
        if py_file in moved_srcs:
            continue  # 移動済みは処理不要
        content = py_file.read_text(encoding="utf-8")
        new_content = apply_imports(content)
        if new_content != content:
            py_file.write_text(new_content, encoding="utf-8")
            print(f"[IMPORT] {py_file.relative_to(ROOT)}")

    # ----- Step 3: migrations フォルダ移動 -----
    old_migrations = SRC / "infra" / "migrations"
    new_migrations = SRC / "migrations"
    if old_migrations.exists() and not new_migrations.exists():
        shutil.copytree(str(old_migrations), str(new_migrations))
        print(f"[COPY]  infra/migrations/ → migrations/")

    # ----- Step 4: Makefile 書き換え -----
    makefile = ROOT / "Makefile"
    mf_content = makefile.read_text(encoding="utf-8")
    mf_new = mf_content
    for old, new in MAKEFILE_REPLACEMENTS:
        mf_new = mf_new.replace(old, new)
    if mf_new != mf_content:
        makefile.write_text(mf_new, encoding="utf-8")
        print("[MAKEFILE] Makefile を更新しました")

    # ----- Step 5: 旧ディレクトリ削除 -----
    OLD_DIRS = [
        SRC / "batch",
        SRC / "eval",
        SRC / "ml",
        SRC / "ranking",
        SRC / "search",
        SRC / "infra",
    ]
    for d in OLD_DIRS:
        if d.exists():
            shutil.rmtree(str(d))
            print(f"[RMDIR] {d.relative_to(ROOT)}")

    print("\n完了しました。")


if __name__ == "__main__":
    main()
