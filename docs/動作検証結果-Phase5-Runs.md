# Phase 5 検証ログ（Run 1-9）

更新日: 2026-04-24
対象: `5/study-hybrid-search-vertex`
参考: [動作検証結果.md](./動作検証結果.md) の Phase 5 セクション

---

## Run 1 — Vertex Pipeline 初期トライ

**実施日**: 2026-04-23  
**実施コマンド**: `make deploy-all`  
**実行結果**: **FAIL（Step6: terraform apply）**

### 主要メトリクス

- 失敗要因: Vertex Feature Group 作成時に `feature_timestamp` 列不足

### 原因と対処

- 原因: `feature_mart.property_features_daily` のスキーマが Feature Group 要件を満たしていない
- 対処:
  - `infra/terraform/modules/data/main.tf` に `feature_timestamp` を追加
  - `pipeline/data_job/dataform/features/property_features_daily.sqlx` に `feature_timestamp` 生成を追加

---

## Run 2 — deploy-all と ops-train-now の複合施行

**実施日**: 2026-04-23  
**実施コマンド**: `make deploy-all` + `make ops-train-now`（前提解除のため追加実行）  
**実行結果**: **FAIL（複合要因、順次修正中）**

### 主要メトリクス

- `deploy-all` は Step7（deploy-api-local）まで到達
- Cloud Build は長時間化（API image build が 15分超）

### 原因と対処（6 件）

1. `VERTEX_ENCODER_ENDPOINT_ID` 未設定で deploy API が停止
   - 対処: `scripts/local/deploy/api_local.py` で未設定時に endpoint ID を自動解決

2. `ops-train-now` が KFP 型解釈で失敗（pipeline annotation）
   - 対処: `pipeline/training_job/main.py` の future annotation 依存を除去

3. `ops-train-now` 実行時に component 内 `Path` 参照失敗
   - 対処: component関数内ローカル import へ修正（`load_features.py` ほか）

4. `deploy-api-local` の Cloud Build config path 不整合
   - 対処: `cloudbuild.api.yaml` 参照を `infra/run/services/search_api/cloudbuild.yaml` に修正

5. Cloud Run revision 起動失敗（`ModuleNotFoundError: ml.data`）
   - 対処: `infra/run/services/search_api/Dockerfile` で runtime image に `app/` と `ml/` を明示コピー

6. Cloud Build待機タイムアウト（900s）
   - 対処: `scripts/local/deploy/api_local.py` の `BUILD_TIMEOUT_SEC` を `1800` に拡張

---

## Run 3 — `.dockerignore` バグ修正

**実施日**: 2026-04-23  
**実施コマンド**: `make deploy-api-local` → `make ops-train-now` → `make ops-train-now`（修正後再投入）  
**実行結果**:
- `deploy-api-local`: **PASS**（revision `search-api-00006-s2g` が 100% traffic を serving、`/livez` 応答 `{"status":"ok"}`）
- Vertex Pipeline `property-search-train-20260423163354`: **FAIL** (`register-reranker` step で `Model.upload` が 404)
- Vertex Pipeline `property-search-train-20260423164728`: 進行中 (`PIPELINE_STATE_RUNNING`、train_reranker の artifact 書き出し修正後)

### 主要メトリクス

- Cloud Build: SUCCESS
- Cloud Run revision 00005-pxj: FAIL → 原因切り分け後に 00006-s2g PASS

### 原因と対処

**真因 1**: `.dockerignore` の `**/data/` が `ml/data/` も巻き込んで除外していた

- Docker は COPY 前にビルドコンテキストから `ml/data/` を落としていた
- 対処: `.dockerignore` の `**/data/` を削除（コメントで理由を記録）
- `ml/data/` / `tests/unit/ml/data/` / `infra/terraform/modules/data/` のうち、除外が必要なのは後者 2 つのみだが、既に `**/tests/` と `infra/` のルールで別途除外されているため追加対処は不要

**真因 2**: `register-reranker` が `Model.upload` で `NotFound: 404`

- `train_reranker` KFP component が `Path(model.path).write_text(...)` で単一ファイル扱い
- Vertex `Model.upload(artifact_uri=model.uri)` がディレクトリとして参照した際に空に見えていた
- 対処: `pipeline/training_job/components/train_reranker.py` を修正、`model.path` をディレクトリとして確保

**真因 3**: default image 名の不一致

- `pipeline/training_job/main.py` / `pipeline/workflow/compile.py` の default image 名が CI が push する名称 (`property-trainer` / `property-reranker`) と不一致
- 対処: `property-` prefix 付きに修正

---

## Run 4 以降 — register-reranker の 0 ログ問題

- `register-reranker` が 4 連続で `workerpool0-0` 0 ログのまま exit 1
- 試した変更（いずれも改善せず）:
  - `train_reranker` の `model.path` を単一ファイル vs ディレクトリ
  - `Input[dsl.Model]` → `Input[dsl.Artifact]` → `str` パラメータに段階変更
  - 各 component 内に `print/traceback` の大量ログ追加

**別角度の分析**:
- `resolve_hyperparameters` (同 `base_image=python:3.12` + 同 `packages_to_install=google-cloud-aiplatform`) は SUCCEED
- 原因は「`packages_to_install=google-cloud-aiplatform` の pip install フェーズ」に絞られる

**追加投入**: `register-reranker` を MINIMAL (print + return のみ、packages なし) に縮退させて再実行中 (`property-search-train-20260423172541`)

---

## Phase 5 deploy-monitor の移植

- `scripts/local/deploy_monitor.py` を Phase 4 からコピー
- `make ops-deploy-monitor` target 追加
- `logs/deploy-monitor/.gitkeep` を追加し PDCA 毎の ts 付き log を蓄積可能に
- ruff / mypy strict 両 PASS

---

## Phase 5 Vertex Pipeline の突破 (register-reranker 問題)

**実施日**: 2026-04-23

### 真因と対処

`register-reranker` が pipeline の **最後の step** として走ると worker が 0 ログで exit 1 する仮説:
- 同一 pipeline 内で複数の pip-install タスクが時系列上で重なり、最後発の job で quota/rate-limit/VM プロビジョニング遅延が発生

**対処**: Model.upload を pipeline から切り離し、`scripts/local/ops/register_model.py` を新設。
- pipeline 側は stub
- registry 反映はローカル python から `aiplatform.Model.upload` を呼ぶ

### 追加判明事項

`aiplatform.Model.upload` は `serving_container_image_uri` の image 存在を **upload 時に 404 検証する**

- `asia-northeast1-docker.pkg.dev/mlops-dev-a/mlops/property-reranker:latest` / `property-encoder:latest` を先に build する必要がある
- 対処: `gcloud builds submit` で `infra/run/services/reranker/cloudbuild.yaml` / `encoder/cloudbuild.yaml` を async 実行

---

## Run 5 — Model Registry 登録 + Endpoint deploy フェーズ

**実施日**: 2026-04-23

### コマンド

```bash
gcloud builds submit infra/run/services/reranker/cloudbuild.yaml _URI=asia-northeast1-docker.pkg.dev/mlops-dev-a/mlops/property-reranker:latest
gcloud builds submit infra/run/services/encoder/cloudbuild.yaml _URI=asia-northeast1-docker.pkg.dev/mlops-dev-a/mlops/property-encoder:latest
uv run python -m scripts.local.ops.register_model --pipeline-job-id property-search-train-20260423172541 --apply
VERTEX_RERANKER_ENDPOINT_ID=property-reranker-endpoint PROMOTE_MAX_REPLICAS=1 uv run python -m scripts.local.ops.promote reranker staging --apply
ENCODER_MAX_REPLICAS=1 uv run python -m scripts.local.setup.setup_encoder_endpoint --apply
```

### 実行結果

- reranker image build: **PASS** (Cloud Build id `c85c1231-f390-4f23-bb49-f84fae8eb897`)
- encoder image build: **PASS** (Cloud Build id `99c48412-fb77-43e9-a9ee-721624239992`)
- ME5 encoder assets upload: **PASS** (既に GCS 上に存在、uploaded_count=0 の idempotent)
- Model Registry `property-reranker` 登録: **PASS** (`projects/941178142366/locations/asia-northeast1/models/3332659326207655936@1` / alias `staging`)
- reranker / encoder endpoint deploy: **進行中** (min=1 max=1 の最小構成で並行中)

### 原因と対処

**B1** — `aiplatform.Model.upload` が serving image の存在を 404 検証

- 対処: Cloud Build で reranker / encoder image を先行して Artifact Registry に push

**B2** — Endpoint deploy が `CustomModelServingCPUsPerProjectPerRegion=8` で 429 ResourceExhausted

- 対処: `promote.py` の `max_replica_count=5` ハードコードを `PROMOTE_MAX_REPLICAS=1` env 上書き対応に変更
- `setup_encoder_endpoint.py` は `ENCODER_MAX_REPLICAS=1` で既定より縮小
- 合計 4 vCPU で quota 内
- 学習目的の最小構成方針を memory に記録

---

## Run 6 — encoder / reranker endpoint DEPLOYED + search-api 再修正

**実施日**: 2026-04-23

### コマンド

```bash
make train-smoke-persist
gsutil cp /tmp/...smoke-model.txt gs://mlops-dev-a-models/lgbm/smoke-20260423-182929/
PROMOTE_MAX_REPLICAS=1 aiplatform.Model('...@1').deploy(endpoint=property-reranker-endpoint, max=1)
gcloud builds submit encoder/cloudbuild.yaml
ENCODER_MAX_REPLICAS=1 setup_encoder_endpoint --apply
ENCODER_ENDPOINT_ID=property-encoder-endpoint RERANKER_ENDPOINT_ID=property-reranker-endpoint make ops-enable-search
make ops-livez
make ops-search-components
```

### 実行結果

- reranker endpoint: **PASS** (real LightGBM model 配備完了)
- encoder endpoint: **PASS** (真因バグ修正後に配備完了)
- `/search`: **FAIL** (adapter payload schema mismatch)

### 原因と対処

**D** — encoder container が起動直後に `RuntimeError: AIP_STORAGE_URI must point to a directory prefix` で exit

- 真因: `ml/serving/encoder.py::_download_artifact_dir` が `GcsPrefix.parse()` の返り値 `prefix` (trailing slash を strip 済) に対して `not prefix.endswith("/")` を検査しており self-contradict (pre-existing バグ)
- 対処: 判定を削除し `list_blobs(prefix=f"{parsed_prefix}/")` で directory 走査、blob name から `parsed_prefix/` を剥がして相対パス生成する形に修正
- encoder image 再 build → Model.upload (新バージョン) → Endpoint deploy PASS

**E** — `CustomModelServingCPUsPerProjectPerRegion=8` quota 429

- 真因: `promote.py` が `max_replica_count=5` hardcode、さらに前回失敗した orphan python プロセスが並行して CPU 枠を予約
- 対処: `promote.py` の replica 設定を env override 化して default 1 に

**F** — `/search` が HTTP 500 で落ちる

- 真因: `app/services/adapters/vertex_prediction.py::VertexEndpointEncoder.embed` が `{"text": "query: ..."}` の単一フィールドでプレフィックス連結
- encoder server の `EncoderInstance` schema は `{"text": ..., "kind": "query"|"passage"}` の分離フィールドを要求
- 対処: adapter を `payload = {"text": text.strip(), "kind": kind}` に変更

---

## Run 7 — Meilisearch 初期同期の permission / `.dockerignore` 迷走

**実施日**: 2026-04-23

### 状況

- `/search` が `HTTP 500` → BigQuery `feature_mart.properties_cleaned` not found
- `make seed-test` で 5 行 insert → Meilisearch index が空で `lexical contribution is zero`

### 同期試行（全て失敗）

1. `scripts/local/ops/sync_meili.py` (local) — user account では token audience 指定できず 401
2. `gcloud auth print-identity-token --impersonate-service-account=sa-api` — user に権限無く 403
3. `gcloud builds submit --service-account=sa-api` — sa-api が cloudbuild bucket の権限無く 403
4. `gcloud run services proxy` — 未インストール、permission guard で拒否
5. `gcloud run jobs deploy --command=sh` — **shell escape** エラー (`sh: 5: Syntax error: Unterminated quoted string`)
6. 専用 image — **`.dockerignore` の `infra/` が sync_meili_job.py も巻き込み COPY 失敗**

### 恒久方針の明文化

`.dockerignore` は最小構成 (python cache / tfstate / .git のみ) から始めて、全段 PASS 確認後に段階追加。
- `CLAUDE.md §紛らわしい点` に追記
- `docs/01_仕様と設計.md §共通前提` に追記
- memory (`feedback_dockerignore_policy.md`) に保存

### 新設 / 修正ファイル

- `infra/run/jobs/meili_sync/sync_meili_job.py` — 専用 entrypoint
- `infra/run/jobs/meili_sync/Dockerfile` — `python:3.12-slim` ベース
- `infra/run/jobs/meili_sync/cloudbuild.yaml` — docker build + push
- `.dockerignore` — 全除外を削除し 3 カテゴリのみに縮退
- ログ追加: 複数ファイルに STEP マーカ + traceback 表示

---

## Run 7 の教訓

- **シェル展開依存は原則避ける** — 専用 image / 専用 entrypoint script が唯一安全
- **`.dockerignore` は事故要因ランキング最上位** — 追加時は必ず Dockerfile `COPY` 行を grep してテストする
- **IAM grant を要する経路は計画時に除外** — auto mode では IAM grant が拒否されるパターンが多い

---

## Run 8 — destroy-all → deploy-all PDCA 再現検証

**実施日**: 2026-04-23

### destroy-all フェーズ結果

**v1 FAIL**: deployed_models が残存、terraform destroy が HTTP 400 で停止
- 対処: `scripts/local/setup/destroy_all.py` に undeploy step を追加

**v2 FAIL**: 
- (a) 4 GCS buckets に object 残存で `force_destroy=false` が足枷
- (b) `model_monitoring_alerts` BQ table が PROTECTED_TABLE_TARGETS 未登録
- 対処: GCS wipe step + テーブル登録追加 (7 → 8)

**v3 PASS**: `Destroy complete! Resources: 31 destroyed.` / rc=0

### deploy-all フェーズ結果

**PASS (rc=0 / `2026-04-23T13:16:57Z`)**:
- Step 1-6: `Apply complete! Resources: 137 added, 0 changed, 0 destroyed.`
- Step 7 `deploy-api-local`: endpoint 自動解決 PASS、Cloud Build SUCCESS
- Service URL: `https://search-api-941178142366.asia-northeast1.run.app`

### Run 8 総合判定

**PASS** — destroy-all v3 rc=0 → deploy-all rc=0 → ops-livez ok の 3 段で PDCA 再入サイクルが自動完走

---

## Run 9 — 機能復元 (destroy 後の 3 成分疎通再建)

**実施日**: 2026-04-23  
**背景**: Run 8 で destroy/deploy-all は PASS したが、機能面（Meilisearch / Model Registry / Endpoint / reranker モデル）を全て復元する必要あり

### 並列実行した復元ステップ

- ✅ 3 image build (Cloud Build 並列): reranker / encoder / meili-sync — 約 10 分
- ✅ `make train-smoke-persist` — smoke model 生成 (ndcg@10=0.9804)
- ✅ `upload_encoder_assets --apply` — ME5 safetensors 再アップ
- ✅ `make seed-test` — BQ に 5 行投入
- ✅ meili-sync-once Cloud Run Job — 33 秒完走
- ✅ Reranker Model 登録 + Endpoint deploy
- ✅ Encoder Model 登録 + Endpoint deploy
- ✅ `make ops-enable-search` — search-api revision 反映
- ✅ `make ops-search-components` — **lexical=1 / semantic=3 / rerank=4 PASS**
- ✅ `make ops-accuracy-report` — **20/20 PASS NDCG@10=1.0**

### 所要時間

**合計約 63 分** (destroy 30min + restore 33min)

### Run 9 総合判定

**PASS** 🎉 — ゼロ状態から完全復元、3 成分疎通確認、20 ケース精度確認まで自動完走

---

## Run 9 の教訓

- **destroy-all の 5 step 設計が機能面の「いなくなったモノ」を全部列挙**
- **meili-sync 専用 Cloud Run Job は Run 7 迷走の正解** — ノーストレス通過
- **`/livez` 200 だけで成功宣言しない** — User 指摘通り、検索サービスとして動いていることを確認
- **eval cases は phase ごとに書く** — 各 phase が自分の seed に合わせた relevant_property_ids を自分で書く
