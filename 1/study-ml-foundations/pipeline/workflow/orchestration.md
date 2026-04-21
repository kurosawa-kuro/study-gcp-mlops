# Pipeline Orchestration

- data_job: PostgreSQL に学習/評価データを投入
- training_job: 前処理・特徴量生成・学習・評価・登録
- evaluation_job: latest metrics の確認とレポート出力
- batch_serving_job: latest model を使ったバッチ推論
