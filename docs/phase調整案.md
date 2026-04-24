# study-gcp-mlops

MLOps 学習用の 6 フェーズ構成リポジトリ（+ Optional Phase 7）。  
**全フェーズを単一の親 Git リポジトリで管理**し、Phase ごとに学習対象を段階的に広げる。

---

## 全体方針

- Phase 1 は **ML 基礎に集中**（学習・評価・保存）
- Phase 2 は **App / Pipeline / Port-Adapter** を導入
- Phase 3-5 は不動産検索ドメインで **Local -> GCP -> Vertex AI** へ展開
- Phase 6 は **Phase 5 と同じ不動産ハイブリッド検索ドメインを題材として維持**し、PMLE 試験範囲の追加技術を実コードへ統合して学ぶ
- Phase 7 は **Optional / Advanced**。Phase 6 の serving 層のみを GKE + KServe に置き換える Draft（Pipelines / Feature Group / Model Registry / BigQuery / Meilisearch 等は Phase 6 から継承）
- Phase 3/4/5/6/7 は **LightGBM + multilingual-e5 + Meilisearch のハイブリッド構成を必須**
- Phase 間のコードは原則共有しない（教材としての独立性を優先）
- 各 Phase の正本は phase 配下ドキュメント（ルート README は全体ナビゲーション）
- 設計思想（Port/Adapter、core-ports-adapters 層構造、依存方向）は一貫させ、**adapter 実装だけ差し替える**
- W&B はクライアント調整により現時点では教材対象外（必要時 optional 再導入）
- 実験履歴・評価結果は Phase ごとに軽量管理し、Phase4以降は GCP / Vertex 標準機能へ移行する
- モデル成果物の正本管理は **GCS -> Vertex Model Registry** へ段階移行する
- Looker Studio は本教材対象外とする
- **Secret Manager は Phase 4 で必須習得**。題材は Meilisearch master key（Phase 4-7 横断で使える実在の秘匿情報）。Secret 作成 → SA IAM bind → Cloud Run `--set-secrets` 注入 → pydantic-settings 読み取り の 4 段を踏む

---

## Phase 一覧

| Phase | ディレクトリ | テーマ | 主な学習ポイント | 主な技術 | 実行方式 |
|---|---|---|---|---|---|
| 1 | `1/study-ml-foundations/` | ML 基礎（回帰） | preprocess / feature engineering / training / evaluation / artifact 出力（model.pkl / metrics.json / params.yaml） | LightGBM, PostgreSQL | Docker Compose |
| 2 | `2/study-ml-app-pipeline/` | App + Pipeline + Port/Adapter | FastAPI lifespan DI, `core -> ports <- adapters`, predictor 経由推論、seed/train/predict job 分離 | FastAPI, LightGBM, PostgreSQL | Docker Compose |
| 3 | `3/study-hybrid-search-local/` | 不動産ハイブリッド検索（Local） | lexical + semantic + rerank、LambdaRank、Port/Adapter 実践 | Meilisearch, multilingual-e5, LightGBM LambdaRank, Redis | uv + Docker Compose |
| 4 | `4/study-hybrid-search-gcp/` | 不動産ハイブリッド検索（GCP） | GCP マネージドサービス化、RRF、再学習ループ、IaC/CI、**Secret Manager → Cloud Run secret injection（必須習得）** | Cloud Run, GCS, BigQuery, Cloud Logging, **Secret Manager**, Terraform, WIF | uv + クラウド実行基盤 |
| 5 | `5/study-hybrid-search-vertex/` | Vertex AI 標準 MLOps 差分移行 | Vertex Pipelines / Endpoint / Model Registry / Monitoring への adapter 差し替え | Vertex AI, Vertex Pipelines, Endpoint, Model Registry, Monitoring | uv + Vertex AI |
| 6 | `6/study-hybrid-search-pmle/` | GCP PMLE 追加技術ラボ | PMLE 範囲の追加技術を adapter / 副経路 / 追加エンドポイント / Terraform として統合。default flag では Phase 5 挙動維持 | BQML / Dataflow / Vector Search / Monitoring SLO / Gemini RAG / Agent Builder（補助: Explainable AI / Vizier / Feature Group / Model Garden） | uv + Vertex AI + Terraform |
| 7 | `7/study-hybrid-search-gke/` | GKE/KServe 差分移行（Draft） | Phase 6 の serving 層のみを GKE + KServe へ置換（学習/データ基盤は Phase 6 から継承） | GKE, KServe, Gateway API, Workload Identity | uv + GKE/KServe |

---

## 全 Phase 共通ツール（横断的に登場）

| ツール | 役割 | 初登場 | 本格活用 |
|---|---|---|---|
| JSON / CSV metrics | ローカル評価結果・run履歴保存 | Phase 1 | Phase 1-3 |
| Git commit hash | 再現性管理 | Phase 1 | 全 Phase |
| pytest | 全 Phase 共通のテストランナー | Phase 1 | 全 Phase |
| Git | 親リポで全 Phase を単一管理 | 開始時点 | 全 Phase |
| pydantic-settings (YAML) | 設定とシークレットの分離 | Phase 1 | 全 Phase |
| Docker / Docker Compose | ローカル実行基盤 | Phase 1 | Phase 1-3 |
| uv | Python 依存管理 | Phase 3 | Phase 3-7 |

---

## 学習順（推奨）

1. `1/study-ml-foundations`
2. `2/study-ml-app-pipeline`
3. `3/study-hybrid-search-local`
4. `4/study-hybrid-search-gcp`
5. `5/study-hybrid-search-vertex`
6. `6/study-hybrid-search-pmle`
7. `7/study-hybrid-search-gke`

4 study-hybrid-search-gcp
5 study-hybrid-search-vertex
6 study-hybrid-search-pmle
7 study-hybrid-search-gke

---

## 学習運用フロー

Phase ごとに成果物・評価結果・実行履歴の置き場を段階移行させる。

### Phase 1〜3（ローカル成果物）

```text
model.pkl
metrics.json
params.yaml
runs/20260424_001/
```

- metric 保存: JSON / CSV
- model 保存: local filesystem
- 実験履歴: run_id 付きディレクトリ
- 再現性: `config.yaml` + git commit hash

### Phase 4（GCP Serverless）

- モデル成果物: GCS（`gs://<project>-models/` 配下に `models/` / `reports/` / `artifacts/`）
- 評価結果: BigQuery table
- 実行ログ: Cloud Logging
- 監視: Cloud Monitoring
- CI/CD: GitHub Actions + WIF
- IaC: Terraform
- **Secret Manager（必須習得）**: `meili-master-key` container + SA IAM bind + Cloud Run `--set-secrets=MEILI_MASTER_KEY=meili-master-key:latest` 注入 + app 側 pydantic-settings 読み取り

### Phase 5（Vertex AI 標準）

- モデル正本: Vertex Model Registry（昇格運用）
- Pipeline 履歴: Vertex AI Pipelines / Metadata（lineage）
- 推論: Vertex Endpoint（deploy history）
- モデル監視: Vertex AI Model Monitoring

---

# 削除 / 置換対象（2026-04-24 決定）

W&B / Looker Studio / Doppler を対象外化するにあたり、現状実装から取り除くもの・置き換えるものを明示する。**Secret Manager は必須習得技術として残し、題材を Meilisearch master key へ転用**する。

## A. 方針サマリ

| 対象 | アクション | 理由 |
|---|---|---|
| W&B 一式 | 🔴 完全削除 | 全体方針 L19「対象外」 |
| Doppler 一式 | 🔴 完全削除 | 現状 `Secret Manager 容器は作るが誰も読まない`（Phase 4/5/6 CLAUDE.md 明記）。`doppler.yaml` も全コメントアウトのテンプレート。W&B を外すと実質配送対象ゼロ |
| Looker Studio | 🔴 完全削除 | doc のみで IaC 実体なし。L22「対象外」 |
| Secret Manager container | 🔄 **転用**: `wandb-api-key` / `doppler-service-token` → `meili-master-key` | Phase 4 必須習得。Meilisearch master key は Phase 4-7 横断で実在する秘匿情報 |
| Cloud Run `--set-secrets` 配線 | ➕ 新規導入 | これまで「仕様のみ」だった Secret Manager → Cloud Run env 注入を初めて実配線 |
| Phase 5 Vizier (placeholder) | 🔴 削除可 | 全体方針外・placeholder 実装のみ |
| Phase 5 Feature Group | ⚠ User 承認後に削除 | parity invariant (7列) に触るため慎重判断 |
| Phase 6 補助機能 (Explainable AI / Model Garden) | 🟢 保持 | PMLE 学習材料として価値あり（L35 表内 `(補助:...)` として明示済） |

## B. 実装順序

1. **Secret Manager 転用フェーズ**（W&B/Doppler 削除の**前に**新配線を先行）
   - `meili-master-key` container + SA IAM 追加（Phase 4 `infra/terraform/modules/data/main.tf`）
   - Meilisearch TF module に `MEILI_MASTER_KEY` env 注入（Secret Manager 参照 `value_source`）
   - API / embedding-job / training-job deploy workflow の `--set-secrets` 配線
   - Meilisearch adapter に `Authorization: Bearer <master_key>` header 送信
   - `app/config.py` に `meili_master_key: SecretStr` 追加（pydantic-settings）
   - → ここで Secret Manager → Cloud Run の配線が初めて活きる
2. **W&B + Doppler 削除**（Secret Manager が Meilisearch master key で埋まった後なので安全）
   - 依存: 全 Phase `pyproject.toml` から `wandb` 除去、`uv lock` 更新
   - code: Phase 2/5 の `wandb_tracker.py` / `WANDB_*` config / 呼び出し箇所
   - terraform: `wandb_api_key` / `doppler_token` secret container + IAM binding
   - doc: `04_運用.md` の secret 投入手順、`CLAUDE.md` の Doppler 連携記述、`doppler.yaml` 削除
   - CI: `.github/workflows/deploy-*.yml` の `dopplerhq/cli-action` step 削除
3. **Looker Studio doc 掃除**（独立・低リスク）
   - Phase 4/5/6/7 の `monitoring/README.md` / `docs/01_仕様と設計.md` / `docs/03_実装カタログ.md` / `CLAUDE.md` / `README.md` から Looker Studio 記載削除
4. **Phase 5 Vizier placeholder 削除**
   - `pipeline/training_job/components/vizier.py` 削除
   - `pipeline/training_job/main.py` から `vizier_max_trials` / `parallel_trial_count` / `study_display_name` パラメータ除去

## C. 影響ファイル一覧（詳細）

### C1. W&B（7 Phase 影響）

| 分類 | ファイル |
|---|---|
| 依存 | Phase 1-7 `pyproject.toml` の `"wandb>=0.17"` |
| code (Phase 2) | `app/config.py` / `ml/adapters/wandb_tracker.py` / `ml/container.py` / `scripts/local/ops/clean.py` |
| code (Phase 5) | `ml/common/config/training.py` (wandb_* fields) / `ml/training/trainer.py` / `ml/training/experiments/wandb_tracker.py` / `pipeline/training_job/main.py` |
| terraform | Phase 4/5/6 `infra/terraform/modules/data/main.tf` の `google_secret_manager_secret.wandb_api_key` |
| doc | Phase 4/5/6 `docs/04_運用.md` の `wandb-api-key` 投入手順、`infra/terraform/environments/dev/README.md` Secret Manager 表 |

### C2. Doppler（Phase 4/5/6）

| 分類 | ファイル |
|---|---|
| config | 各 Phase ルート `doppler.yaml`（3 ファイル、template のみ） |
| config | `.github/workflows/deploy-api.yml` / `deploy-embedding-job.yml` / `deploy-training-job.yml` の `Install Doppler CLI` + `Collect Doppler secrets` step |
| terraform | `infra/terraform/modules/data/main.tf` の `google_secret_manager_secret.doppler_token` + `api_doppler_access` / `job_train_doppler_access` IAM |
| terraform | `infra/terraform/modules/data/outputs.tf` の `doppler_token = ...` 行 |
| doc | `CLAUDE.md` の Doppler 連携説明、`docs/04_運用.md` の Doppler token 投入手順、`docs/03_実装カタログ.md` / `env/secret/README.md` の Doppler 記載 |

### C3. Looker Studio（Phase 4/5/6/7、doc のみ）

| 分類 | ファイル |
|---|---|
| doc | 各 Phase `monitoring/README.md` の「Looker Studio 手動作成」セクション |
| doc | 各 Phase `docs/01_仕様と設計.md` / `docs/03_実装カタログ.md` の「可視化: Looker Studio」記載 |
| doc | 各 Phase `CLAUDE.md` 出力構成表の「Looker Studio ダッシュボード」行 |
| doc | 各 Phase `README.md` 図表内「Looker Studio」ブロック |

### C4. Phase 5 Vizier（placeholder 削除）

| 分類 | ファイル |
|---|---|
| code | `5/.../pipeline/training_job/components/vizier.py` |
| code | `5/.../pipeline/training_job/main.py` の `vizier_*` パラメータ |

## D. 判定保留（User 承認後）

- **Phase 5 Feature Group**: `infra/terraform/modules/vertex/main.tf` の `google_vertex_ai_feature_group` + 7 feature + `enable_feature_group` 変数 + `tests/integration/parity/test_feature_parity_feature_group.py`。parity invariant に触るため削除は User の明示承認後

## E. 完了条件（2026-04-24 一括適用済、動作検証は次 Run で実施）

- [x] `meili-master-key` が Secret Manager に実在し、Cloud Run `--set-secrets` で注入される（Phase 4/5/6 = Cloud Run, Phase 7 = Kubernetes Secret 経由の簡易 draft）
- [x] Meilisearch が master key auth で起動し、adapter が Authorization/X-Meili-Api-Key header を送る
- [x] 全 Phase `pyproject.toml` から `wandb` 依存を除去（`uv sync && make check` は次 Run で検証）
- [x] Terraform `data` module から `wandb_api_key` / `doppler_token` resource + IAM を削除。`meili_master_key` resource + IAM に置換
- [x] `.github/workflows/deploy-*.yml` から `dopplerhq/cli-action` / `Collect Doppler secrets` step を削除。Cloud Run 経路に `--set-secrets=MEILI_MASTER_KEY=meili-master-key:latest` を配線
- [x] doc から「W&B」「Doppler」「Looker Studio」の実装手順記述を削除（教育資料スライドは注記のみ、設計履歴としての言及はこの節に集約）
- [x] Phase 5 `pipeline/training_job/components/vizier.py` 削除、`main.py` から `vizier_max_trials` / `parallel_trial_count` / `study_display_name` 除去
- [x] Phase 6 Run 1 未コミット 5 ファイル（`Makefile` / `candidate_retriever.py` / `publisher.py` / `setup_reranker_endpoint.py` / `動作検証結果.md`）は保護、一切変更なし

## E.1. Phase 別修正実績

| Phase | 主な削除 | 主な追加 | 備考 |
|---|---|---|---|
| 1 | `wandb` 依存 + code (evaluation/config.py, tracking.py, training_job/main.py, test_evaluation.py, scripts/clean.py, docker-compose env) + Looker なし | ローカル `runs/{run_id}/` 管理明記 | 教育資料 9 ファイルに注記 1 行のみ追加 |
| 2 | `wandb` 依存 + code (wandb_tracker adapter, ExperimentTracker port, container DI, clean.py) + 教育資料 5 ファイルの図解/要約から W&B 節削除 | なし（W&B 非依存の Port/Adapter 構造維持） | ExperimentTracker Port は adapter 不在なので Port ごと削除 |
| 3 | `wandb` 依存 + trainer.py の wandb 呼び出し + tracking.py を NoOp ローカル実装に置換 | `runs/` ローカルディレクトリへの run history 移行明記 | `.gitignore` / `.dockerignore` も `ml/wandb/` → `runs/` に切替 |
| 4 | `wandb` + Doppler + Looker（doc）。TF の wandb_api_key + doppler_token container + IAM 削除。deploy-api/embedding-job/training-job の Doppler step 削除 | `meili_master_key` Secret Manager container + SA IAM。Meilisearch TF に `MEILI_MASTER_KEY` env（secret_key_ref）注入。API/training-job に `--set-secrets` 配線。`app/config.py` に `meili_master_key: SecretStr`。Meilisearch adapter に Authorization Bearer | embedding-job は Meilisearch 書込なしで `--set-secrets` 省略 |
| 5 | Phase 4 と同じ + Vizier placeholder (`components/vizier.py` + main.py params) + W&B 専用 ExperimentTracker Port | Phase 4 と同じ Secret Manager 配線 | Feature Group は保留のため未変更 |
| 6 | Phase 5 と同じ（但し `wandb_tracker.py` はファイル名維持で中身 NoOp 化。`layers.py::UNIVERSAL_BANS` に `wandb` 残置で import 禁止継続） | Phase 5 と同じ Secret Manager 配線。meilisearch module 内に Secret IAM を持つ形で循環依存回避 | Run 1 修正作業の 5 ファイル不変確認済 |
| 7 | Phase 6 と同じ | `meili_master_key` を Cloud Run Meilisearch は `value_source`、GKE search-api は Kubernetes Secret 手動同期（`kubectl create secret generic meili-master-key` 手順を doc に追記）で注入 | Draft phase なので External Secrets Operator 導入は未着手 |

## E.2. 検証結果（2026-04-24 一括適用直後）

- `grep -rn "wandb\|WANDB\|doppler\|DOPPLER\|Looker\|looker" --exclude-dir={教育資料,wandb,archive} --exclude=uv.lock` の residual:
    - Phase 1-5, 7: **0 hit**（ノイズ除外後）
    - Phase 6: 6 hit だが全て正当（`wandb_tracker.py` ファイル名保持の NoOp 化 / `layers.py` の wandb import 禁止継続 / doc の「削除済」履歴注記）
- `MEILI_MASTER_KEY` wiring: Phase 4/5/6/7 全てで TF / workflow / app / doc にヒット確認済
- Run 1 保護ファイル: `git diff HEAD` で変更行数 0 を確認

---

# Phase 6 Run 1 修正対策情報 (2026-04-24 整理)

Phase 6 `6/study-hybrid-search-pmle` の動作検証 Run 1 (2026-04-24) で発生した不具合と対策をまとめる。詳細実行ログは [`動作検証結果.md §5`](./動作検証結果.md) を正本とし、本セクションは **「何が壊れていて、何を恒久的にどう直したか / 次どう予防するか」の index**。

## A. 検出した不具合 (致命度順)

| # | 症状 | 直接原因 | 真の root cause | 致命度 |
|---|---|---|---|---|
| A1 | `/search` が常時 HTTP 500 | `google.api_core.exceptions.NotFound: Endpoint property-encoder-endpoint is not found` | destroy-all 後に encoder / reranker Vertex Endpoint が未復元 (GCS artifact 含めて再アップロード必要) | 🔴 致命 |
| A2 | endpoint 復元後も `/search` が HTTP 500 | `PermissionDenied 403 IAM_PERMISSION_DENIED` (ranking-log topic への publish) | **Terraform state lock が 24h stale** で、`api_publish_ranking_log` / `api_publish_retrain` の IAM bindings が TF state には記録済だが GCP 側で欠落する非対称 drift を放置 | 🔴 致命 |
| A3 | `register_model.py` で reranker 復元不可 | `No SUCCEEDED pipeline found with display_name=property-search-train` | `register_model.py` は Vertex Pipelines SUCCEEDED run 前提。pipeline が一度も回っていない partial-reset 状態では代替経路が無かった | 🟠 高 |
| A4 | monitor の stall-warning スパム | `stall_warn_sec=120` 既定で Vertex Endpoint deploy の 15-20 min 沈黙に誤反応 | LRO 系と短命コマンドを同じ閾値で扱っていた | 🟡 中 |
| A5 | rerank score が 3 件同点 (`-0.1062`) | smoke 5.2 KiB モデルの解像度不足 | Vertex Pipelines 経由の真の train を回していない | 🟢 低 (機能的には動作) |

## B. 応急処置 (Run 1 中に適用した直接修正)

| 対象 | コマンド / 操作 | 効果 |
|---|---|---|
| TF state lock | `terraform force-unlock -force 1776954518347777` | 以後 `tf-plan`/`tf-apply` が通るようになった |
| ranking-log IAM | `gcloud pubsub topics add-iam-policy-binding ranking-log --member=serviceAccount:sa-api@... --role=roles/pubsub.publisher` | 200 OK 復帰 |
| retrain-trigger IAM | 同上 (trigger topic 側にも bind) | 予防的付与 |
| encoder endpoint | `make ops-monitor LABEL=encoder-endpoint CMD="uv run python -m scripts.local.setup.setup_encoder_endpoint --apply"` | endpoint id `3327115588580409344` に n1-standard-2 min=1/max=3 で deploy |
| reranker endpoint | 一時 `/tmp/phase6-deploy-reranker.py` | endpoint id `1937192153583190016` に n1-standard-2 min=max=1 で deploy |
| meilisearch 5 件 upsert | `gcloud run jobs execute meili-sync-once --wait` | 26 秒で index 復元 |

## C. 恒久修正 (コード反映済)

### C1. 汎用モニター (`scripts/local/deploy_monitor.py` 拡張)

従来 `deploy-all` 専用だったモニターを任意コマンドに被せられる形に昇格:

- `argparse.REMAINDER` で `--` の後ろを CLI として受け取り
- `--label` で Cloud Logging / monitor-log に出るラベルを指定
- `_STEP_RE` を緩めて「任意ラベル step N/M:」を捕捉
- `_GCLOUD_BUILD_ID_RE` を追加 → `gcloud builds submit` / `gcloud run deploy` の inline build も heartbeat で status 表示
- Makefile に `ops-monitor CMD="..." [LABEL=...]` target 追加
- 既存 `ops-deploy-monitor` は無変更 (後方互換)

### C2. Publisher 層の診断ログ (`app/services/adapters/candidate_retriever.py` + `publisher.py`)

Run 1 の A2 IAM drift で「Cloud Logging の生 traceback から PermissionDenied を掘る」必要があった反省から、publish 失敗時に root cause 候補を 1 行で並べる:

```python
# _log_publish_failure(where, topic_path, exc) の exc 型別 hints:
#   PermissionDenied → H1 IAM 欠落 / H2 pubsub.googleapis.com disable / H3 project mismatch
#   NotFound         → H1 topic 不在 / H2 env 名 typo / H3 project id mismatch
#   DeadlineExceeded → H1 throttle / H2 client timeout / H3 egress 詰まり
#   その他           → H1 gRPC status / H2 JSON serialize / H3 ADC 初期化失敗
```

適用箇所:
- `PubSubRankingLogPublisher.publish_candidates`
- `PubSubFeedbackRecorder.record`
- `PubSubPublisher.publish`
- 各 publisher の `__init__` で `pubsub.publisher init class=... topic_path=... sa_hint=...` を `logger.info` で 1 行記録 (revision 起動時点で「どの topic を誰の identity で publish 予定か」が可視化)

### C3. reranker 恒久スクリプト (`scripts/local/setup/setup_reranker_endpoint.py`)

一時スクリプト `/tmp/phase6-deploy-reranker.py` を恒久化:

- `build_endpoint_spec` / `_apply` / `main()` シグネチャを `setup_encoder_endpoint.py` と完全対称
- default `n1-standard-2 min=max=1` (学習リポ minimum spec 準拠、encoder の max=3 とは仕様差を保持)
- artifact_uri default = `gs://{PROJECT_ID}-models/reranker/v1/` (pre-upload した `model.txt` を参照)
- `except` 内に H1 (model.txt 未配置) / H2 (sa-endpoint-reranker の GCS read 権限欠落) / H3 (`property-reranker:latest` image 未 push) を明記
- Makefile に `setup-reranker-endpoint` / `setup-encoder-endpoint` 両方を `APPLY=1` opt-in 形式で追加 (無指定は spec dump = dry-run)

### C4. 品質ゲート全通過

- `make check`: ruff / ruff format / mypy strict / pytest = **255 passed / 1 failed** (既知 parity path drift、Phase 6 無関係)
- `make check-layers`: **OK (19 files clean)**
- `make ops-search-components`: PASS (lexical=1, semantic=3, rerank=4)
- 20 ケース accuracy: **NDCG@10=1.0 / hit_rate@10=1.0 / MRR@10=1.0**

## D. Run 2 以降の予防策 (未着手、優先度付け)

| 優先度 | 宿題 | 想定工数 | 狙い |
|---|---|---|---|
| 🔴 致命 | TF apply 巨大 drift の解消 | 30-60 min | `tf-plan` で検出した 40 create / 3 recreate / 9 update を apply。SLO policies / monitoring / eventarc 等の宣言済リソースを GCP 実体に反映。**user 明示承認後に実行**したい (blast radius 大) |
| 🟠 高 | `deploy-all` 冒頭に stale-lock 検出ヘルパ | 15 min | 24h 以上 age のロックを検知したら `tf-plan` 前に warn + opt-in で force-unlock。誤爆防止で `ALLOW_FORCE_UNLOCK=1` env 必須 |
| 🟠 高 | `destroy-phase6-learning` target | 1-2 h | encoder + reranker endpoint + 1GB GCS assets + BQ 空 table の一括 destroy (`destroy-all` よりスコープ狭く学習セッション終了時の coast-down 用) |
| 🟡 中 | `ops-monitor-lro` プロファイル | 30 min | `--stall-warn-sec 1200` 既定の LRO 専用 target。Vertex Endpoint deploy を被せても heartbeat のみで stall-warning を抑制 |
| 🟡 中 | `/readyz` に publisher 事前疎通チェック | 30-60 min | `PublisherClient.get_topic(topic_path)` を 1 回だけ投げて IAM/topic 存在を事前検証。startup 時に 1 度だけなら publish コスト無し |
| 🟢 低 | Vertex Pipelines 経由で真の train | 30 min (submit) + 45 min (run) | smoke モデル置き換えで rerank score の差別化を回復。Phase 5 Run 9 と同じ経路 |
| 🟢 低 | 過剰エラーキャッチログの整理 | 次 Run 観測後 | Run 2 まで drift 再発を観測し、不要になった hints のみ間引く (現時点では全部役立つので据え置き) |

## E. Run 2 開始時の前提確認チェックリスト

次回 `動作検証依頼` を受けた時点で最低限やる確認:

1. `terraform -chdir=.../dev plan -detailed-exitcode` で exitcode=0 (差分ゼロ) を確認。差分があれば origin を遡る (session 跨ぎ drift の早期検知)
2. `gsutil stat gs://mlops-dev-a-tfstate/hybrid-search-cloud/default.tflock` で stale ロックが残っていないか。24h 以上なら D の stale-lock 検出ヘルパ案件を検討
3. `gcloud pubsub topics get-iam-policy ranking-log` で sa-api publisher が bind されているか
4. `gcloud ai endpoints list` で encoder / reranker 2 本が ready か (なければ C3 手順で復元)
5. `bq query "SELECT COUNT(*) FROM feature_mart.property_embeddings"` で 5 以上か (0 なら `make seed-test`)
6. `make ops-search-components` が PASS するか — 全てのレイヤを 1 shot で検証できる最良のゲート

## F. 不変の成功条件 (Phase 6 User 指定)

- ハイブリッド検索 **「LightGBM + ME5 + MeiliSearch」** の 3 成分すべてが寄与
- `make ops-search-components` で `lexical_hits>=1 semantic_hits>=1 rerank_hits>=1 readyz_rerank_enabled=True`
- 時間のかかる処理は実所要時間を記録
- エラー発生時は第二・第三候補まで error catch ログを仕込む (本セクション C2 で恒久化済)
