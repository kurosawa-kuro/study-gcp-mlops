# pipeline/workflow

Phase 3 では実装本体がまだ `ml/embed`, `ml/train`, `ml/sync` に残っている。

学習用途では、ワークフローの見え方を `pipeline/` に集約する。

- `pipeline/data_job/main.py`
  埋め込み生成と検索インデックス同期の入口
- `pipeline/training_job/main.py`
  LambdaRank 学習ジョブの入口

次段階では `ml/*` 側の実行形態ベース配置を、責務ベースの `ml/data`, `ml/training`, `ml/evaluation`, `ml/registry`, `ml/serving` へ寄せる。
