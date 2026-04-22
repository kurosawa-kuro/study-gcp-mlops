# study-ml-foundations

ML Pipeline — カリフォルニア住宅価格予測（**Phase 1: ML 基礎**）

LightGBM によるカリフォルニア住宅価格予測の **学習パイプライン**。Docker Compose でデータ投入 → 学習 → 評価まで完結する、MLOps 教育用途の ML 基礎 Phase。

> 推論 API / FastAPI / Port-Adapter 等のデザインパターン導入は **Phase 2 (`2/study-ml-app-pipeline/`)** で扱う。本 Phase は ML コア（trainer / evaluation / preprocess / feature_engineering）に集中する。

## クイックスタート

```bash
make all    # build → seed → train
make test   # pytest
```

## コマンド一覧 (Makefile)

| コマンド | 説明 |
|---|---|
| `make build` | Docker イメージビルド |
| `make seed` | sklearn データを PostgreSQL に投入 |
| `make train` | LightGBM モデル学習 → `ml/registry/artifacts/{run_id}/` に保存 |
| `make test` | pytest 全テスト実行 (ローカル) |
| `make all` | build → seed → train を順番に実行 |
| `make down` | Docker Compose 停止 |
| `make clean` | Docker 停止 + 生成ファイルをすべて削除 |

Makefile は `scripts/` 配下のスクリプトに委譲する構成。

## アーキテクチャ

```
PostgreSQL (docker-compose: postgres サービス)
  → ml/data/loaders: Repository パターンでデータ取得
    → ml/data/preprocess: 前処理 (欠損値補完・外れ値キャップ・対数変換)
      → ml/data/feature_engineering: 特徴量エンジニアリング (BedroomRatio・RoomsPerPerson)
        → ml/training: LightGBM 学習
        → ml/evaluation: 精度評価 (RMSE, R²) + W&B ログ
          → ml/registry/artifacts/{run_id}/ に保存 + PostgreSQL に精度記録 + latest 更新
```

### パッケージ構成

| パッケージ | 責務 |
|---|---|
| `pipeline/` | data/training/evaluation/batch のジョブエントリーポイント |
| `ml/data/` | データ取得・前処理・特徴量生成 |
| `ml/training/` | LightGBM 学習アルゴリズム |
| `ml/evaluation/` | 精度評価 (RMSE, R²) + W&B 実験ログ |
| `ml/registry/` | 実行履歴メタデータとアーティファクト管理 |
| `ml/common/` | 共通定義 (特徴量カラム, 設定ベースクラス, ロギング, Run ID 生成) |

### 技術スタック

| 用途 | ツール |
|---|---|
| 学習 | LightGBM |
| データ | PostgreSQL 16 + sklearn California Housing |
| 評価 | numpy 自前実装 (RMSE, R²) |
| 実験ログ | W&B (オプション) |
| 設定管理 | pydantic-settings + YAML |
| インフラ | Docker Compose |

## Docker サービス

| サービス | Image / Dockerfile | ポート | 用途 |
|---|---|---|---|
| postgres | postgres:16 | 5432 | データ永続化 (volume: `postgres_data`) |
| seed | `infra/run/jobs/trainer/Dockerfile` | — | PostgreSQL データ投入 (run して終了) |
| trainer | `infra/run/jobs/trainer/Dockerfile` | — | 学習 (seed 完了後に実行) |

## モデルバージョニング

学習を実行するたびに一意な Run ID (`YYYYMMDD_HHMMSS_{UUID}`) が付与され、モデルが蓄積される。

```
ml/registry/artifacts/
├── 20260416_222525_5bfd5f/   ← 1回目
│   ├── model.lgb
│   └── metrics.json
├── 20260416_222540_05f983/   ← 2回目
│   ├── model.lgb
│   └── metrics.json
└── latest -> 20260416_222540_05f983
```

推論 API は Phase 2 で提供。Phase 2 の API が `ml/registry/artifacts/latest/model.lgb` を参照する想定（学習成果物の共有は手作業コピー、または Phase 2 が Phase 1 の artifacts ディレクトリを volume マウント）。

## W&B 連携

`env/secret/credential.yaml` に `wandb_api_key` を設定するとクラウドにログ送信。未設定時は offline モードで保存され、パイプライン本体の動作には影響しない。

## テスト

```bash
make test                                          # 全テスト
python scripts/local/ops/test.py -k test_train     # 単体テスト指定
```

## ドキュメント

- [設計書](docs/01_仕様と設計.md) — 全体設計・構成・設定
- [運用手順書](docs/04_運用.md) — セットアップ・実行手順・環境変数一覧
