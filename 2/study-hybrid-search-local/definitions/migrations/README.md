# Migrations

PostgreSQL スキーマ更新用の SQL ファイルを管理するディレクトリ。

## Rule

- ファイル名は `NNN_description.sql` 形式で連番を使う
- 既存番号の SQL は原則編集しない（履歴として固定）
- 同じ SQL を再実行しても壊れないよう、`IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` を優先する

## Migration Files

- `001_create_properties.sql`
	- `properties` テーブル作成
	- 検索条件向け index 作成（city/layout/price/walk_min/pet）
- `002_seed_properties.sql`
	- 初期物件データ投入（`ON CONFLICT DO NOTHING`）
- `003_create_logs_and_stats.sql`
	- `property_stats`, `search_logs` 作成
- `004_features_and_batch_logs.sql`
	- `properties.is_active` 追加
	- `property_features`, `batch_job_logs` 作成
- `005_me5.sql`
	- `property_embeddings` 作成
	- `search_logs.me5_scores`, `property_features.me5_score` 追加
- `006_learning_logs.sql`
	- `search_logs.actioned_id`, `search_logs.action_type` 追加
	- `action_type` 制約と index 追加
- `007_ranking_compare_logs.sql`
	- `ranking_compare_logs` 作成
- `008_eval_and_kpi.sql`
	- `offline_eval_reports`, `kpi_daily_stats`, `model_adoption_decisions` 作成

## How To Apply

`run_sql.py`（`src.batch.maintenance.run_sql`）経由で適用する。

例:

```bash
docker compose exec -T api python -m src.jobs.maintenance.run_migrations src/migrations/008_eval_and_kpi.sql
```

通常は `Makefile` の migrate ターゲットを使う。

- `make db-migrate-learning`
- `make db-migrate-eval`

## Notes

- rollback 用 SQL は現時点で未整備。必要時は別途 `down` 用ファイルを追加する
- 本番運用では適用前に DB バックアップ取得を推奨
