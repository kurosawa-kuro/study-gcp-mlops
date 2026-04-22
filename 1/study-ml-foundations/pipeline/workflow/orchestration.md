# Pipeline Orchestration

- data_job: PostgreSQL に学習/評価データを投入
- training_job: 前処理・特徴量生成・学習・評価・登録
- evaluation_job: latest metrics の確認とレポート出力
- （Phase 2 移管）推論・配信ジョブは `2/study-ml-app-pipeline/` 側で実施
