# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MLOps学習プロジェクト。Cloud Runベースで（Kubernetes不使用）MLパイプラインを構築する。
GCPプロジェクト: `mlops-dev-a`、リージョン: `asia-northeast1`

## Architecture

```
[Cloud Run Job (batch)]
   ├── データ取得（California Housing）
   ├── 特徴量生成 → 学習（scikit-learn RandomForest）
   ├── 評価（RMSE, MAE） → MLflow記録
   ├── モデル保存 → [GCS models/]
   ├── ログ出力 → [GCS logs/]
   └── メトリクス投入 → [BigQuery mlops.metrics]

[BigQuery]
   └── metrics テーブル → 最良モデル選択

[Cloud Run Service (FastAPI API)]
   ├── BigQueryから最良モデルパス取得
   ├── GCSからモデルロード
   └── POST /predict で推論レスポンス
```

- **batch/**: Cloud Run Job - データ取得→学習(scikit-learn)→評価(MLflow)→モデル保存(GCS)→ログ出力(GCS)→メトリクス投入(BigQuery)
- **api/**: Cloud Run Service - BigQueryで最良モデル選択→GCSからロード→FastAPIで推論レスポンス
- **terraform/**: GCS, BigQuery, Cloud Run (Job/Service), Artifact Registry, Cloud Scheduler のIaC定義

## Tech Stack

- **ML**: scikit-learn, MLflow, pandas
- **API**: FastAPI (Cloud Run Service)
- **Data**: BigQuery（評価メトリクス蓄積・最良モデル選択）
- **Infra**: Cloud Run (Job/Service), GCS, Artifact Registry, Cloud Scheduler
- **IaC**: Terraform
- **CI/CD**: GitHub Actions
- **将来**: Vertex AI

## GCP Setup

```bash
gcloud init
gcloud config set compute/region asia-northeast1
gcloud config set run/region asia-northeast1
```

## Language

このプロジェクトのドキュメントやコミットメッセージは日本語で記述する。
