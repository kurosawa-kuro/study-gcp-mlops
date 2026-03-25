# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MLOps学習プロジェクト。Cloud Runベースで（Kubernetes不使用）MLパイプラインを構築する。
GCPプロジェクト: `mlops-dev-a`、リージョン: `asia-northeast1`

## Architecture

```
[GCS raw] → [Cloud Run Job (batch)] → [GCS models] → [Cloud Run Service (FastAPI API)]
                    ↓
               [BigQuery] (features / metrics / predictions)
```

- **batch/**: Cloud Run Job - データ取得→特徴量生成→学習(scikit-learn)→評価(MLflow)→モデル保存(GCS)→結果保存(BigQuery)
- **api/**: Cloud Run Service - GCSからモデルロード→FastAPIで推論レスポンス
- **terraform/**: GCS, BigQuery, Cloud Run, Artifact Registry のIaC定義

## Tech Stack

- **ML**: scikit-learn, MLflow, pandas
- **API**: FastAPI
- **Infra**: Cloud Run (Job/Service), GCS, BigQuery, Artifact Registry
- **IaC**: Terraform
- **将来**: Vertex AIへの置き換え予定

## GCP Setup

```bash
gcloud init
gcloud config set compute/region asia-northeast1
```

## Language

このプロジェクトのドキュメントやコミットメッセージは日本語で記述する。
