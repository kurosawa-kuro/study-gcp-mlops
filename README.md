# study-gcp-mlops

MLOps 学習用の 4 フェーズ構成リポジトリ。各フェーズは独立した Git リポジトリとしてサブディレクトリに入っている（トップディレクトリ自体は Git リポジトリではない）。

---

## Phase 別テーマ

| Phase | ディレクトリ | テーマ | 学習の主題 | 主要技術 |
|---|---|---|---|---|
| 1 | `1/study-ml-foundations/` | カリフォルニア住宅価格予測 | ML 基礎固め（回帰 / 評価 / 特徴量エンジニアリング） | LightGBM（回帰）+ FastAPI + PostgreSQL + Docker Compose + W&B |
| 2 | `2/study-hybrid-search-local/` | 不動産検索（Local） | ハイブリッド検索アーキテクチャの理解（Port/Adapter 設計 / スコア融合 / ランキング学習） | LightGBM **LambdaRank** + multilingual-e5 + Meilisearch + PostgreSQL + Redis |
| 3 | `3/study-hybrid-search-cloud/` | 不動産検索（GCP） | Cloud Native 化と MLOps パイプライン（IaC / CI/CD / 監視 / 再学習ループ） | Cloud Run + BigQuery（`VECTOR_SEARCH`）+ Dataform + **RRF** + Terraform + WIF |
| 4 | `4/study-hybrid-search-vertex/` | 不動産検索（Vertex AI） | Vertex AI プリミティブへの「差分工事」移行（adapter 差し替え） | Vertex Pipelines (KFP) / Endpoints × 2 / Model Registry / Feature Group / Monitoring v2 / Vizier |

**ドメイン統一の経緯:** 構想段階では「社内規定検索（検証）→ 商品検索（実務）」の転用案もあったが、Phase 2 → 3 の移植の学びに集中するため、両 Phase とも不動産検索でドメイン統一した（2026-04-20 確定）。

各 Phase の詳細な習得要素と Phase 間の差分（残す / 変える / 加える / やめる）は下記セクションを参照。

---

## 各フェーズ習得要素（`docs/教育資料/` より抽出）

各 Phase の `docs/教育資料/` 配下（`01_スライド.md` / `02_ナレーション台本.md` / `03_デモシナリオ.md` / `04_デモナレーション台本.md` / `05_図解.md`）を正として、受講者が到達するべき知識・技能を列挙する。

### Phase 1: ML 基礎（`1/study-ml-foundations/docs/教育資料/`）

動画タイトル「機械学習入門」、題材: California Housing。IT エンジニアが ML の基本語彙を掴むことがゴール。

**概念（ソフトウェア開発の類似概念で対応付け）**
- 機械学習とは — 「人がルールを書く」から「データからルールを導出する」への発想転換
- モデル = 入力から出力を導く関数。パラメータをデータから自動決定
- 特徴量 = 入力パラメータ相当（MedInc / HouseAge / AveRooms / Population 等 8 個）
- 特徴量エンジニアリング = 派生カラム生成。`BedroomRatio = AveBedrms/AveRooms`、`RoomsPerPerson = AveRooms/AveOccup` で 8 → 10 特徴量に拡張
- 訓練データ / テストデータ（80/20 分割、テストは学習に一切使わない＝汎化性能の検証）
- 前処理 = 欠損値補完（中央値）/ 外れ値キャップ / 対数変換（右裾の分布圧縮）
- アルゴリズムの分類（線形 / 木ベース / NN）と LightGBM の位置付け（勾配ブースティング決定木、テーブルデータで高速）
- ハイパーパラメータ = config に相当する「人が事前に決める」設定値（`learning_rate` / `num_leaves` / `num_boost_round`）
- 学習 = 訓練 = Training（ビルド/コンパイル相当）
- 評価指標 RMSE / R²（numpy で自前実装、scikit-learn 不使用）
- オフライン評価（デプロイ前、テストデータ）と オンライン評価（デプロイ後、本番監視）の違い
- 推論 = 本番リクエスト処理相当、学習と比べて計算コストは軽い
- モデルのバージョニング（`Run ID = YYYYMMDD_HHMMSS_xxxxxx`、`models/latest` シンボリックリンクで最新参照）
- 実験管理（W&B）の位置付け — 精度計算は numpy、W&B は「蓄積・可視化担当」

**技術スタック**
- LightGBM（ML エンジン）、numpy（評価指標自前実装）、scikit-learn（データ取得のみ）
- FastAPI（`/predict` / `/metrics` / `/data` の Web UI 付き推論 API、lifespan でモデルを 1 回ロード）
- PostgreSQL（データ保管）、Docker Compose、Makefile、W&B

**デモ導線**
- `make seed`（sklearn → PostgreSQL 投入）→ `make train`（前処理 / 特徴量 / 学習 / 評価 / 保存）→ `make serve`（FastAPI 起動）→ ブラウザで `/` 予測フォーム・`/metrics` 精度表示・`/data` 学習データビューア
- 学習ログの読み解き（`[50]/[300] valid_0's rmse`、Run ID 付与、`Model saved to ...`）

### Phase 2: ハイブリッド検索 Local（`2/study-hybrid-search-local/docs/教育資料/`）

動画タイトル「ハイブリッド検索入門」。Phase 1 の ML 基礎を前提に、「検索システムの中で ML をどう使うか」へ視点転換するのがゴール。

**Phase 1 → 2 で変わる項目（stack 差分表）**
| 軸 | Phase 1 | Phase 2 |
|---|---|---|
| 題材 | カリフォルニア住宅価格予測（sklearn） | 不動産検索（`properties` テーブル） |
| ML タスク | **回帰**（住宅価格を当てる） | **ランキング学習**（検索結果を良い順に並べる） |
| LightGBM の役割 | 単独の予測器 | 3 段構成の最後段 reranker |
| 目的関数 | `regression_l2`（二乗誤差） | **`lambdarank`**（NDCG 最大化、ペアワイズ順序） |
| 評価指標 | RMSE / R² | **NDCG@10** / MAP / Recall@20 |
| ラベル | 連続値（住宅価格） | 行動から作る gain 値（click / favorite / inquiry） |
| 入力単位 | 1 レコード単位 | クエリ単位のグループ（`group_sizes`） |
| 推論 API | `/predict` 単発 | `/search` + `/feedback` の検索フロー |
| データストア | PostgreSQL（1 DB） | PostgreSQL（物件 + ログ + 特徴量 + 埋め込みの複数テーブル） |

**Phase 1 から引き継がれる設計**
- LightGBM（エンジンそのものは同じ、目的関数だけ差し替え）
- FastAPI（`/predict` → `/search` + `/feedback` へ拡張）
- Docker Compose（ローカル起動基盤）
- PostgreSQL（DB エンジンは同じ、スキーマが増える）
- Makefile（タスクランナー）
- W&B（実験管理、本 Phase では `ranking_compare_logs` 中心に併用）
- numpy での評価指標自前実装の思想

**Phase 2 で新規登場**
- ハイブリッド検索アーキテクチャ（lexical 候補抽出 + semantic 類似度 + rerank の 3 段）
- Meilisearch（BM25 全文検索 + 構造化フィルタ）
- multilingual-e5（Embedding、`query:` / `passage:` prefix 規約）
- cosine similarity（意味類似度の数値化）
- Redis（応答キャッシュ、TTL 120 秒）
- Port/Adapter 設計パターン（検索エンジン / 埋め込み / reranker / キャッシュの抽象化）
- 行動ログ設計（`search_logs` / `ranking_compare_logs` / `feedback_events`）
- `candidate_limit` vs `limit` の責務分離
- モデル未配置時のフォールバック可用性（`/search` が止まらない設計）
- オンライン KPI（CTR / favorite_rate / inquiry_rate / CVR）

**Phase 2 でやめる / 登場しないもの**
- 回帰タスクとしての住宅価格予測
- 単発推論（`/predict`）の UI（予測フォーム / `/metrics` ページ / `/data` ページ）
- RMSE / R² の運用

**Phase 1 からの概念スライド**
- 特徴量 → 物件属性 + 行動特徴 + 意味類似度
- 推論 → `/search` 実行時の順位計算
- 1 つのモデル → Meilisearch + Embedding + LightGBM の連携

**ハイブリッド検索の核心**
- なぜハイブリッドか — キーワード検索（表記ゆれ / 曖昧語に弱い）とベクトル検索（厳密条件に弱い）それぞれの弱点補完
- 3 段構成の役割分担:
  1. Meilisearch（BM25）で候補抽出 — 全文検索 + 構造化フィルタ（`city` / `layout` / `price_lte` / `pet` / `walk_min`）
  2. multilingual-e5（ME5）で意味類似度計算 — `query:` / `passage:` prefix を使い分け、cosine similarity → `me5_score`
  3. LightGBM で再ランキング — 物件属性 + 行動特徴 + 意味特徴をまとめて最終順位
- 候補取得（recall 重視） vs 再ランキング（precision 重視）の責務分離
- `candidate_limit`（再ランキング前件数）と `limit`（最終返却件数）の分離 — 精度と速度のトレードオフのチューニングポイント

**Embedding 実装**
- 物件側: バッチで `encode_passages()` → `property_embeddings` テーブルへ保存
- クエリ側: オンラインで `encode_queries()` → 候補と cosine similarity
- 空クエリ時は embedding を作らず、`me5_score = 0.0`（条件検索だけでも動作）
- prefix 分けの理由（E5 系モデルの想定入力に合わせる）

**再ランキング特徴量（LightGBM 入力）**
- 物件属性: `price` / `walk_min` / `age` / `area`
- 行動特徴: `ctr` / `fav_rate` / `inquiry_rate`
- 意味特徴: `me5_score`
- モデル未配置時のフォールバック（weighted sum: `ctr*0.4 + fav_rate*0.2 + inquiry_rate*0.2 + me5_score*0.2`）で疎通可能

**運用レイヤ**
- Redis キャッシュ（TTL 120 秒、条件そのものをキー化、キャッシュヒット時はログ保存スキップ）
- ログ設計: `search_logs`（最終結果 + `me5_score`）/ `ranking_compare_logs`（Meili 順と rerank 後順の比較）
- 改善ポイントの切り分け方（recall 不足 / 順位品質 / 曖昧語 / 応答時間）

**処理フロー**
`cache → candidate search (Meilisearch) → query embedding (ME5) → cosine → LightGBM rerank → log (search/compare) → cache`

### Phase 3: ハイブリッド検索 GCP（`3/study-hybrid-search-cloud/docs/教育資料/`）

動画タイトル「GCP-ML入門 — Cloud Run + BigQuery で学ぶ MLOps パイプライン」。Phase 2 の検索思想を保ったまま実行基盤を GCP に置き換え、「MLOps = 工程の連結」を掴むのがゴール。**Vertex AI は使わない**軽量 MLOps。

**Phase 2 → 3 で変わる項目（stack 差分表）**
| 軸 | Phase 2 | Phase 3 |
|---|---|---|
| 実行環境 | Docker Compose（Local） | **Cloud Run**（Service + Jobs）+ Terraform + WIF |
| データストア | PostgreSQL（物件 + ログ + 特徴量 + 埋め込み全部入り） | **BigQuery**（`raw` / `feature_mart` / `mlops` の 3 データセット分離） |
| Lexical 検索 | Meilisearch on Docker | Meilisearch on **Cloud Run**（GCS FUSE 永続化 + IAM gate + sync Job） |
| Vector 検索 | PostgreSQL `DOUBLE PRECISION[]` + Python cosine（pgvector 不使用） | **BigQuery `VECTOR_SEARCH`**（+ `CREATE VECTOR INDEX` 手動 DDL） |
| lexical × semantic 融合 | `me5_score` を LightGBM 特徴量に入れて混ぜ方を**モデルに委ねる** | **RRF（Reciprocal Rank Fusion）で順位ベースに事前融合**してから rerank |
| 特徴量生成 | バッチスクリプト（`features-daily` 等の Make ターゲット） | **Dataform** SQL + assertions（`feature_mart.property_features_daily`） |
| キャッシュ | Redis（TTL 120 秒、サーバプロセス） | `cachetools.TTLCache`（**in-memory**、Memorystore コスト回避） |
| ログ収集 | PostgreSQL INSERT（同期） | **Pub/Sub → BQ Subscription**（`ranking-log` / `search-feedback`） |
| 再学習起動 | 手動（`make retrain-weekly`） | **Cloud Scheduler → `/jobs/check-retrain` → Pub/Sub → Eventarc → Cloud Run Job** |
| 権限管理 | 単一 DB ユーザ | **5 SA 分離**（`sa-api` / `sa-job-train` / `sa-job-embed` / `sa-dataform` / `sa-scheduler`）+ `sa-github-deployer`（WIF 専用） |
| CI/CD | なし | GitHub Actions + **WIF**（SA Key 禁止）+ `cloudbuild.*.yaml` |
| モデル成果物 | `models/{run_id}/lgbm_ranker.txt` ローカル | **GCS**（`gs://mlops-dev-a-models/lgbm/{date}/{run_id}/model.txt`）+ `mlops.training_runs` BQ 系譜 |

**Phase 2 から引き継がれる設計**
- 3 段構成（lexical 候補 → semantic 候補 → rerank）の思想
- 候補取得 / 再ランキングの責務分離
- **LightGBM LambdaRank + NDCG 監視**（Phase 2 で導入済、目的関数は変わらず）
- `multilingual-e5` の `query:` / `passage:` prefix 規約
- モデル未配置時のフォールバック可用性（Phase 3 では **rerank-free MVP** として `final_rank = lexical_rank`）
- `candidate_limit` vs `limit` の責務分離
- Port/Adapter パターン（本 Phase で **AST/parity テスト**により強制検査まで拡張）
- 行動ログ設計の考え方（テーブル名とパイプ経路が変わるだけで意図は同じ）

**Phase 3 で新規登場**
- **RRF（Reciprocal Rank Fusion）** — lexical rank と semantic rank の順位ベース融合。スコアスケール差に頑健（Phase 2 の特徴量化方式からの置換）
- `lexical_rank` / `semantic_rank` / `rrf_rank` の rank 系特徴量（計 10 列に拡張）
- **Training-Serving Skew 対策**（5 ファイル parity invariant、同一 PR 原則）
- Cloud Run Service vs Jobs の役割分担（`search-api` / `training-job` / `embedding-job`）
- Dataform による特徴量加工と assertions 品質チェック
- `mlops.training_runs` BQ テーブルでの系譜管理（SQL でアドホック監査可能）
- 再学習ループ 3 経路の基礎形（Scheduler + Eventarc、Phase 4 で 3 経路に拡張）
- Workload Identity Federation（GitHub Actions → GCP、SA Key 禁止）
- 非負制約 / 権威順位 / feature parity invariant の運用ドキュメント体系

**Phase 3 でやめる / 登場しないもの**
- PostgreSQL（DB として。Phase 2 のローカル DB はもう使わない）
- Redis サーバ（プロセスとしては停止、in-memory TTL で代替）
- Docker Compose（本番運用から外れる。開発ローカル作業には残存可）
- pgAdmin（DB 管理 UI）
- 手動スクリプトでの特徴量生成（Dataform に置換）

**MLOps パイプライン 7 工程の連結**
1. 生データ受領（`raw.properties`）
2. 特徴量生成（Dataform で `feature_mart.property_features_daily`、assertions で品質チェック）
3. 埋め込み生成（`embedding-job` が物件テキストを `passage:` prefix で埋め込み、`feature_mart.property_embeddings` に保存）
4. 学習（`training-job` が学習 → GCS に `model.txt` 保存、`mlops.training_runs` に系譜記録）
5. 推論 API（`search-api` が E5 埋め込み → Meilisearch BM25 と BigQuery `VECTOR_SEARCH` の 2 系統 → RRF 融合 → `build_ranker_features` → LightGBM rerank）
6. ログ収集（Pub/Sub → BQ Subscription で `ranking_log` / `feedback_events`）
7. 再学習起動（Scheduler → `/jobs/check-retrain` → Pub/Sub `retrain-trigger` → Eventarc → training-job）

**Phase 2 から変わった実装ポイント**
- データストア: PostgreSQL → BigQuery（raw / feature_mart / mlops に分離）
- Vector 検索: PostgreSQL の `DOUBLE PRECISION[]` + Python cosine → BigQuery `VECTOR_SEARCH`
- Lexical 検索: Meilisearch on Docker → Meilisearch on Cloud Run
- キャッシュ: Redis → `cachetools.TTLCache`（in-memory、Memorystore コスト回避）
- モデル: LightGBM（通常） → LightGBM LambdaRank（ランキング専用目的関数）
- 特徴量: 物件属性 + 行動特徴 + 意味特徴に加え `lexical_rank` / `semantic_rank` / `rrf_rank` の 3 rank 特徴が追加

**Cloud Run を Service / Jobs 両方で使う設計**
- Service: `search-api`（推論オンライン）
- Jobs: `embedding-job` / `training-job`（バッチ）
- 「推論だけ別基盤」という分断を避ける意図

**Training-Serving Skew 対策**
- Dataform SQL（訓練側）と `common.feature_engineering.build_ranker_features`（推論側 Python）を同一式で lockstep 維持
- `ctr = SAFE_DIVIDE(click_count, impression_count)` のような分子分母順が訓練 / 推論で 1:1

**RRF（Reciprocal Rank Fusion）候補統合**
- lexical rank と semantic rank を順位ベースで融合、スコアスケール差を吸収

**rerank-free MVP 思想**
- booster 未配置でも `final_rank = lexical_rank` で `/search` が返る
- 候補抽出と rerank を切り離して段階疎通できる

**IaC / 運用**
- Terraform + Cloud Run + WIF（Workload Identity Federation、SA Key 禁止）
- 5 SA 分離（`sa-api` / `sa-job-train` / `sa-job-embed` / `sa-dataform` / `sa-scheduler`）＋ `sa-github-deployer`
- `mlops.training_runs` を SQL で直接監査可能

**デモで見るべきもの**
- コード: `entrypoints/api.py` / `services/ranking.py` / `adapters/candidate_retriever.py` / `adapters/lexical_search.py` / `adapters/cache_store.py` / `training/entrypoints/rank_cli.py`
- GCP: `mlops.training_runs` / `feature_mart.property_embeddings` / `mlops.ranking_log` / `mlops.feedback_events`
- 運用: `make ops-search` / `make ops-ranking` / `make ops-check-retrain`

### Phase 4: ハイブリッド検索 Vertex AI（`4/study-hybrid-search-vertex/docs/教育資料/`）

動画タイトル「GCP-ML Vertex 編 — Phase 3 に Vertex AI レイヤを後付けする」。Phase 1〜3 受講済みを前提に、**Phase 3 のコア（検索 / 特徴量 / 学習ロジック）を残したまま、Port/Adapter の adapter だけ Vertex 実装に差し替える「差分工事」** がゴール。

**Phase 3 → 4 で変わる項目（stack 差分表）**
| 軸 | Phase 3 | Phase 4 |
|---|---|---|
| 学習オーケ | Cloud Run Jobs (`training-job` / `embedding-job`) | **Vertex AI Pipelines (KFP) × 2**（`embed_pipeline` / `train_pipeline`） |
| rerank 推論 | `search-api` lifespan で `lgb.Booster` を GCS load | **Vertex Endpoint** `property-reranker-endpoint`（CPR container） |
| クエリ埋め込み | `search-api` lifespan で sentence-transformers load | **Vertex Endpoint** `property-encoder-endpoint`（CPR container） |
| 物件バッチ埋め込み | Cloud Run Job `embedding-job` | `embed_pipeline` の `ModelBatchPredictOp` ステップ |
| Model 管理 | GCS パス命名 + `mlops.training_runs` | **Vertex AI Model Registry**（+ `training_runs` dual write） |
| 特徴量管理 | Dataform `property_features_daily` | 同 + **Vertex Feature Group**（wrap） |
| 監視 | Scheduled Query `mean_drift_sigma` | **Vertex Model Monitoring v2**（旧 SQL は backup） |
| 実験管理 | W&B のみ | **Vertex Experiments + W&B** dual write |
| ハイパラ探索 | 手動 | **Vertex Vizier**（`enable_tuning=True` 時のみ） |
| 再学習 subscriber | Eventarc → Cloud Run Job | Eventarc → **Cloud Function `pipeline-trigger`** |
| Cloud Run Service メモリ | 4Gi（encoder + booster 同居） | **2Gi**（外部化で軽量化） |
| Service Account | 5 + 1（WIF） | **9 + 1**（`sa-pipeline` / `sa-endpoint-encoder` / `sa-endpoint-reranker` / `sa-pipeline-trigger` 追加） |

**Phase 3 から変えない項目（Vertex に相当物なし / 移行 ROI 低 / 既存運用の保全）**
- Meilisearch on Cloud Run（BM25） — Vertex に BM25 相当なし
- BigQuery `VECTOR_SEARCH` + VECTOR INDEX — Matching Engine 化は別スコープ
- Dataform `property_features_daily` + assertions — Feature Group のソーステーブル
- Pub/Sub → BQ Subscription（`ranking-log` / `search-feedback`）
- `monitoring/validate_feature_skew.sql` — Vertex Monitoring のバックアップ兼 SQL アドホック可用性
- Port/Adapter + AST/parity テスト — adapter 追加だけで境界が効く

**Vertex AI コンポーネントと担当工程（7 コンポーネント + 周辺）**
| コンポーネント | 担当 | 実装箇所 |
|---|---|---|
| Vertex AI Pipelines (KFP) | 学習 / 埋め込み DAG | `pipelines/src/pipelines/property_search/{embed,train}_pipeline.py` |
| Google Cloud Pipeline Components | `BigqueryQueryJobOp` / `ModelBatchPredictOp` / `ModelUploadOp` | `pipelines/.../components/*.py` |
| Feature Store (Feature Group) | `property_features_daily` wrap + lineage | `infra/modules/vertex/main.tf` |
| Model Registry | `staging` / `production` alias × 2 model | `components/register_reranker.py`、`scripts/ops/promote.py` |
| Endpoints × 2 | encoder / reranker のオンライン推論 | `infra/modules/vertex/main.tf` + CPR コンテナ |
| Experiments | W&B と dual write | `adapters/bigquery_ranker_repository.py::_log_vertex_experiment` |
| Vizier (HPTuningJob) | LambdaRank ハイパラ探索 | `components/vizier.py` |
| Batch Prediction | 物件側埋め込み | `components/batch_predict_embeddings.py` |
| Model Monitoring v2 | ドリフト検知 → Pub/Sub | `scripts/setup/setup_model_monitoring.py` |
| ML Metadata | 系譜追跡（KFP 実行で自動生成） | 自動 |
| PipelineJobSchedule | 定期 CT | `scripts/setup/create_schedule.py` |

**Port/Adapter 境界の維持（Phase 4 の核心）**
- 新 Port（Protocol、`google.cloud` 非依存、AST で強制）: `EncoderClient.embed(text, kind)` / `RerankerClient.predict(instances)`
- 新 Adapter: `app/src/app/adapters/vertex_prediction.py::VertexEndpointEncoder` / `VertexEndpointReranker`（`aiplatform.Endpoint.predict` を叩く薄い wrapper）
- `services/ranking.py::run_search`（RRF → rerank → top-K の骨格）は **不変**
- → 「Vertex を入れても pure logic は書き換えない」が守られる

**CPR（Custom Prediction Routine）コンテナ 2 本**
- `encoder_server.py`: FastAPI、`AIP_HEALTH_ROUTE` / `AIP_PREDICT_ROUTE` / `AIP_HTTP_PORT` 準拠。起動時 `AIP_STORAGE_URI`（GCS）から ME5 checkpoint を download → `E5Encoder.load`。推論ロジックは `common/embeddings/e5_encoder.py` をそのまま import（Phase 3 と同一）
- `reranker_server.py`: 同様に AIP_* 準拠。`model.txt` を GCS から download → `lgb.Booster(model_file=...)`。入力 10 次元 float / 出力 scalar。特徴量作成は API 側（`common/feature_engineering.py::build_ranker_features` と lockstep）

**KFP パイプライン 2 本**
- `embed_pipeline`（日次）: `load_properties → batch_predict_embeddings → write_embeddings`（text_hash 差分で再エンコード対象を絞る）
- `train_pipeline`（週次 + アラート起動）: `load_features → (Vizier 分岐) → train_reranker → evaluate → dsl.Condition(pass) → register_reranker`（NDCG@10 閾値 PASS で Model Registry + Endpoint カナリア）

**Model Registry + カナリアデプロイ**
- `ModelUploadOp` で `property-reranker` に version 追加、初期 alias は `staging`
- `scripts/ops/promote.py reranker v<N>` で `production` 付け替え + traffic 100%
- `Model.deploy(traffic_split={"<new>": 10, "<current>": 90})` で 10% カナリア投入
- 旧モデルは昇格完了後 `Endpoint.undeploy_model(...)` で剥がす
- Registry と `mlops.training_runs` BQ テーブルは **dual write** 併存（SQL アドホック集計の保全）

**Feature parity invariant は 6 ファイルに拡張**
Phase 3 の 5 ファイル lockstep（schema / feature_engineering / infra `ranking_log` RECORD / monitoring SQL / Dataform SQLX）に、**6 番目として `infra/modules/vertex/main.tf::google_vertex_ai_feature_group_feature` × 7 列** を追加。`tests/parity/test_feature_parity_feature_group.py` が `FEATURE_COLS_RANKER` との 1:1 対応を検査。クエリ時算出の 3 列（`me5_score` / `lexical_rank` / `semantic_rank`）は Feature Group 非登録（Phase 3 の監視 SQL 除外規則と同じ）。

**Continuous Training の 3 経路（全経路が `pipeline-trigger` Cloud Function に集約）**
- (a) Cloud Scheduler（04:00 JST）→ `/jobs/check-retrain` → Pub/Sub `retrain-trigger` → Eventarc → Cloud Function → `train_pipeline`（`enable_tuning=False`）
- (b) Vertex Model Monitoring v2 閾値超え → Pub/Sub `model-monitoring-alerts` → Eventarc → Cloud Function → `train_pipeline`（**ドリフト検知時は `enable_tuning=True`** で Vizier ON）
- (c) PipelineJobSchedule（cron セーフティネット）: `embed_pipeline` 03:30 JST 日次 / `train_pipeline` 04:00 JST 日曜

**9 Service Account 分離（Phase 3 の 5 SA から +4）**
- `sa-api`（継続、`aiplatform.user` 追加）/ `sa-pipeline`（`sa-job-train` リネーム + `aiplatform.user`）/ `sa-endpoint-encoder`・`sa-endpoint-reranker`（models bucket reader のみ）/ `sa-pipeline-trigger`（Cloud Function 専用、`aiplatform.user` + `eventarc.eventReceiver` + `pubsub.subscriber` + `sa-pipeline` の `serviceAccountUser`）
- 不変: `sa-job-embed`（`embed_pipeline` 完走後に段階削除予定）/ `sa-dataform` / `sa-scheduler` / `sa-github-deployer`
- 意図: Endpoint ランタイム SA と Pipeline 起動 SA を分けて blast radius を小さく保つ

**やめたもの（Phase 3 からの削除）**
- Cloud Run Jobs `training-job` / `embedding-job`（KFP で代替、`infra/modules/runtime/main.tf` から削除）
- `app.services.model_store`（booster local load、Endpoint 化で 3 ファイル削除）
- `/events/retrain` + `CloudRunJobRunner`（subscriber が Cloud Function に移行したため dead code）

**ハマりどころ（Phase 4 固有）**
- `google_vertex_ai_endpoint` は空の shell しか Terraform で宣言できない — `deployed_models` / `traffic_split` は provider から見て computed、Python SDK (`aiplatform.Model.deploy`) 側で投入。`ignore_changes` すら書かない（unsupported attribute エラー）
- **encoder の初回投入は KFP 外**: `scripts/setup/upload_encoder_assets.py --apply`（ME5 checkpoint を GCS）→ `scripts/setup/setup_encoder_endpoint.py --apply`（`Model.upload` + `Endpoint.deploy`）。reranker は `train_pipeline::register_reranker` で自動化される
- VECTOR INDEX は provider 未対応、手動 DDL 必須（Phase 3 から継続）
- Doppler → Cloud Run Secret Manager 経路は未配線（roadmap §9 確定）、`--set-env-vars` 直書き運用

**デモで見るべき観点**
- コード: `entrypoints/api.py`（lifespan が Vertex クライアント DI に変わった点）/ `adapters/vertex_prediction.py`（Endpoint.predict ラッパの薄さ）/ `services/ranking.py`（**変わっていない** ことの確認）/ `infra/modules/vertex/main.tf`（Feature Group + 2 Endpoints + Cloud Function + Eventarc × 2）
- Vertex 側: `pipelines/.../{embed,train}_pipeline.py`（DAG）/ `jobs/.../{encoder,reranker}_server.py`（CPR server）/ `functions/pipeline_trigger/main.py`（Pipeline submit entry）/ `scripts/setup/setup_encoder_endpoint.py`（one-off setup spec）
- 運用: `scripts/ops/promote.py`（カナリア昇格）/ 9 SA の分離 / `scripts/setup/create_schedule.py`（PipelineJobSchedule 冪等作成）


/home/ubuntu/repos/study-gcp-mlops/4/study-hybrid-search-vertex
/home/ubuntu/repos/study-gcp-mlops/3/study-hybrid-search-cloud
/home/ubuntu/repos/study-gcp-mlops/2
/home/ubuntu/repos/study-gcp-mlops/2/study-hybrid-search-local
/home/ubuntu/repos/study-gcp-mlops/1
/home/ubuntu/repos/study-gcp-mlops/1/study-ml-foundations

/home/ubuntu/repos/study-gcp-mlops/1/study-ml-foundationsを参考に
phase2-4でもwandbを導入コーディング依頼

/home/ubuntu/repos/study-gcp-mlops/1/study-ml-foundations/ml/evaluation/report/tracking.py
/home/ubuntu/repos/study-gcp-mlops/1/study-ml-foundations/ml/wandb
/home/ubuntu/repos/study-gcp-mlops/1/study-ml-foundations/ml/wandb/wandb