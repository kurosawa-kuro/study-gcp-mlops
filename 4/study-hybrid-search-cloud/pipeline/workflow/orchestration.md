# pipeline/workflow

Phase 3 では実装本体は `ml/data` と `ml/training` に集約済み。

学習用途では、ワークフローの見え方を `pipeline/` に集約する。

- `pipeline/data_job/main.py`
  埋め込み生成と検索インデックス同期の入口
- `pipeline/training_job/main.py`
  LambdaRank 学習ジョブの入口

次段階は `pipeline/` 側の入口設計を維持しつつ、責務ベースの `ml/data`, `ml/training`, `ml/evaluation`, `ml/registry`, `ml/serving` を唯一の正として運用する。
