# TASKS.md (Phase 7 — current sprint)

Claude Code の新セッションが「**今 sprint で何をやり、何をやらないか**」を最初に確認する単一エントリポイント。

## 本ドキュメントの債務 (= 何が書いてあるか)

本ファイルの責務は **「今」 の sprint dashboard**。**今日のゴール / 達成済 / 残り work / sub-step 進捗** の single source of truth。

- **書く**: 今日のゴール・**死守ライン（V5 E2E）**・準死守 / 余力 / 最後の優先順位、V1-V6 の current status、sub-step 進捗、直近 timeline、次に動かす command
- **書かない (= 他 doc に委譲)**:
  - 「**何で OK と判定するか**」 (V1-V6 の検証ゲート定義) → [`../runbook/04_検証.md`](../runbook/04_検証.md) (検証 canonical 定義)
  - 「**過去 incident の詳細**」 (§4.X postmortem / Wave 計画 / 設計判断) → [`TASKS_ROADMAP.md`](TASKS_ROADMAP.md) (作業計画 + incident 母艦)
  - 「**やる手順**」 (`make deploy-all` の打ち方) → [`../runbook/05_運用.md`](../runbook/05_運用.md) (PDCA / runbook)

進捗を 3 箇所に書くと「片方だけ ✅ にして実は未達」のような虚偽 (= goal degradation) が起きやすい → **進捗は本ファイルに集約** (CLAUDE.md §「⛔ ゴール劣化禁止」と表裏一体)。

権威順位: `TASKS_ROADMAP.md > TASKS.md > 01_仕様と設計.md > README.md`。過去判断履歴は `docs/decisions/` (ADR 0001〜0008)。

---

## 🎯 ゴール状況ダッシュボード (2026-05-04 更新)

### 死守ライン（クライアントに怒られないための最低説明責任）

**「DAG がクラウドで起動した」「`check_retrain` だけ success」だけでは、ML 検索アプリとしての業務フロー実証にならない。** クライアント説明で安全なのは次まで完了したときだけである。

**Composer 経由の再学習 E2E 最小検証**（= 下表「🔴 死守ライン」チェックリスト **全項目**）を **任意・別 sprint にしない**（CLAUDE.md §「⛔ ゴール劣化禁止」と整合）。

### インフラ・run-all ライン（達成済）

| # | item | status | 備考 |
|---|---|---|---|
| **V1** | `make deploy-all` 完走 | ✅ **DONE** | Run 6 exit 0 / 35.5 min / state_recovery 12 type で `alreadyExists` ゼロ / Composer 作成 18m48s |
| **V2** | `make run-all-core` 完走 | ✅ **DONE** | retry 1 回目 PASS / `ndcg_at_10=1.0` / 3 種 lexical/semantic/rerank all non-zero / Vertex Pipeline SUCCEEDED |

### V5 の位置づけ（途中経過 vs 死守完了）

| 区分 | status | 備考 |
|---|---|---|
| **`check_retrain` のみ success**（§0.1 の狭いゲート） | ✅ Run 4 | F1–F5 反映済 |
| **Composer 経由の再学習フロー全体**（submit / wait / gate / promote + `/search` 健全性） | 🔴 **死守ライン未達** | Run 4 は `submit_train_pipeline` **failed** → V5-8 コード修正済。**live**: `build-composer-runner` → `composer-deploy-dags` → 再 trigger → 下 checklist |

### 🔴 死守ライン：V5 Composer 経由再学習 E2E 最小検証

- [ ] DAG trigger 成功（手動 `make ops-composer-trigger DAG=retrain_orchestration` または schedule）
- [ ] `submit_train_pipeline` の失敗時は **Pod log / `airflow-worker`** で取得し、原因を分類する  
  （**IAM** / **PIPELINE_ROOT_BUCKET・GCS** / **PIPELINE_TEMPLATE_GCS_PATH・template** / **compile・submit 引数** / **runner image・依存**）
- [ ] 修正後、同一 DAG Run 追跡 **または** 新 trigger で検証
- [ ] `check_retrain`: **success**
- [ ] `submit_train_pipeline`: **success**
- [ ] `wait_train_succeeded`: **success**
- [ ] `gate_auto_promote`: **期待どおりの判定**（例: `AUTO_PROMOTE=false` なら short-circuit で downstream skip が説明可能）
- [ ] `promote_reranker`: **success** または **意図どおり skip**
- [ ] **`/search` が 200 OK**（再学習完了後、`make ops-livez` / Gateway 経由）
- [ ] **lexical / semantic / rerank の 3 成分が壊れていない**（`make ops-search-components` 等で non-zero 維持）

このラインを超えたとき初めて、「DAG が起動しただけ」ではなく **「Composer 経由で ML 検索アプリの再学習フローが最低限成立した」** と説明できる。

### V5 実装サブステップ

| # | サブステップ | status | 詳細 |
|---|---|---|---|
| V5-1 | `composer-runner` Dockerfile 作成 | ✅ | `infra/run/services/composer_runner/Dockerfile` 新規 (Python 3.12 + `[pipelines]` extra + gcloud SDK + scripts/pipeline/ml source) |
| V5-2 | Cloud Build config + Make target | ✅ | `infra/run/services/composer_runner/cloudbuild.yaml` + `scripts/deploy/composer_runner.py` + `make build-composer-runner` |
| V5-3 | composer-runner image push | ✅ | Run 1 = OOM (exit 137、`[ml]` extra で snapshot 4GB+)、**Run 2 SUCCESS 187s** (`[ml]` 削除で ~700MB-1GB に縮小)。`composer-runner:latest` = `asia-northeast1-docker.pkg.dev/mlops-dev-a/mlops/composer-runner:latest` |
| V5-4 | 3 DAG を `KubernetesPodOperator` + provider Operator に書き換え (8 task) | ✅ | `pipeline/dags/_pod.py` (helper、`python_pod` / `gcloud_pod`)、`retrain_orchestration.py` (5 task)、`daily_feature_refresh.py` (5 task、Dataform は `DataformCreateWorkflowInvocationOperator` 化)、`monitoring_validation.py` (3 task) |
| V5-5 | DAG unit test 更新 | ✅ | `tests/unit/pipeline/dags/test_dag_files.py` に契約追加: `BashOperator` 禁止 / `uv run python` 文字列禁止 / `python_pod` or provider Operator 必須 / `_pod.py` 存在確認。**18 PASS** + `make check` **659 PASS / 1 skipped** |
| V5-6 | sa-composer IAM 追加 + Composer module env_var | ✅ | `iam/main.tf` に `artifactregistry.reader` + `storage.objectViewer` 追加 / `composer/main.tf` env_variables に `COMPOSER_RUNNER_IMAGE` 追加 / `composer/variables.tf` + `dev/main.tf` + `dev/variables.tf` 配線 / `tf-validate` Success |
| V5-7a Run 1 | `tf-apply` (新 IAM + COMPOSER_RUNNER_IMAGE) | ✅ 395s | `Apply complete! 5 added, 3 changed, 3 destroyed` |
| V5-7b Run 1 | `composer-deploy-dags` | ✅ | `_pod.py` 抜け落ち発見 → `composer_deploy_dags.py::_list_extra_files()` に追加 → 再 upload |
| V5-7c Run 1 | DAG smoke | 🔴 **FAILED** (~2 min) | F1 真因発見 (env name mismatch) |
| **F1 fix** | `_pod.py` `ENV_KEY_ALIASES = {"API_EXTERNAL_URL": ("API_URL",)}` で script 側 canonical 名にも複写 | ✅ | |
| V5-7a Run 2 | `tf-apply with TF_VAR_api_external_url=https://136.110.137.177` | ✅ 398s | `4 added, 3 changed, 3 destroyed` + `0 added, 2 changed` (Composer env update) |
| V5-7b Run 2 | `composer-deploy-dags` (修正版 `_pod.py` upload) | ✅ | |
| V5-7c Run 2 | DAG smoke | 🔴 **FAILED** (~2.5 min @ 16:08:29) | F2 + F3 + F4 真因発見 (TLS / Host / 観測性不足) |
| **F2 fix** | `composer/main.tf` env_variables に `API_HOST_HEADER=search-api.example.com` + `API_INSECURE_TLS=true` を追加 | ✅ | 自己署名 TLS + HTTPRoute mismatch 回避 |
| **F3 fix** | `_pod.py` PROPAGATED_ENV_KEYS に `API_HOST_HEADER` + `API_INSECURE_TLS` 追加 | ✅ | |
| **F4 fix** | `scripts/ops/check_retrain.py` に **stderr DIAG ログ** 追加 (env keys / resolved target / call result / 例外型) | ✅ | Run 3 が SUCCEEDED しなくても Pod log で原因直接観測可能に |
| V5-7a Run 3 | `tf-apply` (Composer env_var に TLS / Host 追加) | ✅ 372s | `Apply complete! 0 added 3 changed 0 destroyed` (Composer env_var 反映確認: gcloud describe で API_HOST_HEADER='search-api.example.com' / API_INSECURE_TLS='true' 確認) |
| V5 image rebuild Run 3 | `make build-composer-runner` (DIAG log 焼き込み) | ✅ 199s | `composer-runner:latest` 再 push |
| V5-7b Run 3 | `composer-deploy-dags` (修正版 `_pod.py` 再 upload) | ✅ | |
| V5-7c Run 3 | DAG smoke retry | 🔴 **FAILED** (193s @ 16:23:22) | **DIAG log で真因即視**: `env API_HOST_HEADER='<unset>'` / `env API_INSECURE_TLS='<unset>'` → tf-apply で Composer env_variables には注入済 (gcloud describe で確認) も **scheduler の `os.environ` まで反映されず** (Composer scheduler restart timing 依存) → SSL CERTIFICATE_VERIFY_FAILED |
| **F5 fix** | `_pod.py::_propagated_env_vars()` に `HARDCODED_DEFAULTS = {"API_HOST_HEADER": "search-api.example.com", "API_INSECURE_TLS": "true"}` を追加 (env scheduler 反映 timing 非依存に) | ✅ | |
| V5-7b Run 4 | `composer-deploy-dags` + 90s wait + `make ops-composer-trigger DAG=retrain_orchestration` | ✅ | run_id `manual__2026-05-03T07:27:14+00:00`。tf-apply / image rebuild 不要 |
| V5-7c Run 4 | **`check_retrain` task = success** (V5 検証ゲート) | ✅ | `tasks states-for-dag-run` — **check_retrain** 07:27:20–07:29:23Z **success**。 **submit_train_pipeline** 07:29:30–07:31:36Z **failed** → Run 全体 **failed**（Vertex submit は別イシュー。ゲート対象外） |
| **V5-8** | `submit_train_pipeline` argv/runtime fix | ✅ **コード** / ⏳ **live** | `scripts/ops/submit_train_pipeline.py` + DAG module差し替え。Run 4 失敗は **4 分類のうち 3+4（path + argv）確定** — 下節。live は **build-composer-runner** 後に再 trigger |

### Run 1/2 真因と Run 3 fixup マッピング

| # | 真因 | 検出方法 | fix file |
|---|---|---|---|
| F1 | Composer env_var = `API_EXTERNAL_URL`、script = `API_URL` の名称ミスマッチ | Pod manifest 確認で env 一覧見たら `API_URL` が無かった | `_pod.py` ENV_KEY_ALIASES |
| F2-a | `var.api_external_url` default `""` → `API_EXTERNAL_URL` 値が空 | Pod manifest で `name: API_EXTERNAL_URL\n(no value)` を確認 | tf-apply に `TF_VAR_api_external_url=https://...` 注入 |
| F2-b | 明示 `API_URL` パスは default `verify_tls=True` (自己署名 cert NG) | `_common.py::resolve_api_target()` を読み返した | `composer/main.tf` に `API_INSECURE_TLS=true` |
| F2-c | 明示 `API_URL` パスは default `host_header=None` (HTTPRoute mismatch) | 同上 | `composer/main.tf` に `API_HOST_HEADER=search-api.example.com` |
| F4 | Pod 失敗時に container stdout が Composer log に流れないため exit_code=1 だけで原因不明 | Run 1/2 とも 2-3 min で fail するが log に `Pod returned a failure` しか出なかった | `scripts/ops/check_retrain.py` に stderr DIAG log |

= **`check_retrain` のみのゲートは Run 4 で達成**（F1–F5）。**クライアント向けの死守説明**には不十分 — 上記 **🔴 死守ライン**（submit 以降 + `/search` 健全性）が未完了。

### V5-8 `submit_train_pipeline` 境界（失敗の 4 分類 + 確定原因）

`airflow-worker` ログ（Pod stdout / `pod_manager`）より Run 4 の一次エラーは **`FileNotFoundError: 'dist/pipelines'`**。根本原因は **分類 4（parameter / argv / workspace mismatch）**: DAG が `python_pod(..., extra_args=[..., "$(GCP_PROJECT)", ...])` を渡していたが **`KubernetesPodOperator` はシェル非経由のため `$(...)` がリテラルのまま** Vertex / compile に渡る。また相対パス **`dist/pipelines`** は Pod cwd・権限と噛み合わず compile 前に落ち得る。

| # | 分類 | 見るもの | Run 4 の位置づけ |
|---|---|---|---|
| 1 | **IAM** | `403` / `PermissionDenied` / sa-pipeline・aiplatform | ログ上は未到達（先に argv/path で失敗） |
| 2 | **GCS / pipeline root** | `PIPELINE_ROOT_BUCKET` / `gs://…/runs` / bucket IAM | 同上（ただし argv がリテラル `$(PIPELINE_ROOT_BUCKET)` なら未到達） |
| 3 | **template path** | compile 出力 YAML、`PIPELINE_TEMPLATE_GCS_PATH` | **`dist/pipelines` 未整備** で `FileNotFoundError`（確定） |
| 4 | **parameter / image / compile mismatch** | シェル形 argv、image に script 未同梱 | **`$(GCP_PROJECT)` 等が展開されない**（確定） |

**対応（コード）**: `scripts/ops/submit_train_pipeline.py` 新規 — 実行時に `os.environ` から project / region / bucket を読み、`pipeline.workflow.compile.main()` に concrete argv + **`/tmp/pipelines`**。DAG は `python_pod(module="scripts.ops.submit_train_pipeline")` のみ。

**対応（live）**: composer-runner image に `scripts/` を COPY 済みのため **`make build-composer-runner` → push → `make composer-deploy-dags` → DAG 再 trigger** で V5-8 を検証する（DAG upload だけでは runner image 内の新ファイルが古いままの可能性あり）。

### 直近 1.5 日の達成 (= **進捗ゼロではない**、構造的 incident fix が大量に入った)

| 日付 | 達成 | 備考 |
|---|---|---|
| 2026-05-02 | Wave 1 完了 + Wave 2 offline wiring 完了 + run-all-core 1 周 live PASS | `ndcg_at_10=1.0`、3 種 lexical/semantic/rerank all non-zero |
| 2026-05-03 朝 | destroy-all 失敗事故 → **§4.9 K fix** (`prevent_destroy` 撤回 + state rm + terraform import pattern)、contract test 9 → 12 件 | VVS 永続化アーキテクチャの根本修正 |
| 2026-05-03 昼 | tfstate orphan **151 → 0** cleanup (緊急 cleanup の副作用回復)、runbook §1.4-emergency 新節追加 | 緊急 kill switch + state-recover 推奨を runbook 化 |
| 2026-05-03 夕 | **§4.10 state_recovery.py 12 GCP type 徹底実装** (Run 1-5 で incremental 発見)、contract test 12 → 15 件、**Run 6 step 6 PASS** (Composer 作成 18m48s、`Apply complete! 1 added 2 changed`) | IAM SA / BQ / Pub/Sub / CF / Eventarc / Run / AR / Secret / Dataform / GCS / Feature Store (FG/FOS/FV) / FG Features 7 個 |

### 優先順位（クライアント説明と資源配分）

同列の TODO にしない。**死守 → 準死守 → 余力 → 最後** の順。

#### 🔴 死守ライン（最優先）

**V5: Composer 経由の再学習 E2E 最小検証** — 内容はダッシュボードのチェックリストが正本。`submit_train_pipeline` 以降の live 完走 + `/search` 健全性まで。

#### 🟡 準死守ライン（再デプロイ耐性）

| # | item | 備考 |
|---|---|---|
| **V4** | 2 周目 `make deploy-all`（`terraform import` / state 経路の live 検証） | alreadyExists を import・state で吸収できること。V5 E2E **完了後**に着手 |

#### 🟢 余力ライン（品質・差分）

| # | item | 備考 |
|---|---|---|
| **V6** | `tests/integration/parity/*` の `live_gcp` 本実行 | index / embedding / rerank / env 差分の分類。V5 E2E 後 |

#### ⚪ 最後でよい（破壊的検証）

| # | item | 備考 |
|---|---|---|
| **V3** | `make destroy-all` live 1 周 verify | state rm + import pattern。クライアント向け **前面に出しにくい** 作業。V5 E2E より **後** |

---

### クライアント向けに安全な表現（コピー用）

現在、Composer DAG の起動および `check_retrain` は成功している。ただし **ML 検索アプリとしての再学習 E2E**（Vertex submit・pipeline wait・gate / promote・再学習後の `/search` 健全性）は、**次の死守ラインとして優先して完了させる**。

完了すれば、「DAG が起動しただけ」ではなく **「Composer 経由で ML 検索アプリの再学習フローが最低限成立している」**と説明できる。V4・V6・V3 は E2E 成立後に優先度を分けて実施する。

---

詳細は [`TASKS_ROADMAP.md` 「現在地」](TASKS_ROADMAP.md#現在地) と [`04_検証.md`](../runbook/04_検証.md) §0（V5 の **狭いゲート** と本ファイルの **死守 E2E** の関係は §0 表直後の補足）。

---

## 現在の目的

Phase 7 = Phase 6 (PMLE + Composer 本線) と Phase 5 必須の Feature Store / Vertex Vector Search を継承し、**serving 層のみ Vertex AI Endpoint → GKE + KServe InferenceService に差し替える** 到達ゴール。

中核 (不動産ハイブリッド検索 / Meilisearch + Vertex Vector Search + ME5 + RRF + LightGBM LambdaRank) は不変。推論を cluster-local HTTP に委譲。

Phase 7 固有: KServe → Feature Online Store を **Feature View 経由で** opt-in 参照、TreeSHAP 用 explain 専用 Pod を独立 deploy。

## 進捗サマリ (2026-05-03 夜 時点 — `TASKS_ROADMAP.md §進捗サマリ` 抜粋)

| Wave | フェーズ | 状態 | 内容 |
|---|---|---|---|
| **Wave 1** | ローカル完結 (検索アプリ層) | ✅ **完了** (M-Local 達成) | PR-1 〜 PR-4 全 merge、`make lint` / `make fmt-check` / 関連 mypy / pytest 63 passed |
| **Wave 2** | GCP インフラ層 (クラウド側主作業) | 🟡 **インフラライン達成 / V5 E2E 死守未達** | V1+V2 ✅、`check_retrain` ✅ (Run 4)。**死守**: Composer 経由 **submit→wait→gate/promote→/search 健全性**（上表 🔴）。その後 V4 → V6 → V3 の順 |
| **Wave 3** | docs / reference architecture 整合 | ⏳ Wave 2 後 | `03_実装カタログ.md` / `05_運用.md` の semantic / feature / Composer 経路記述を Wave 1/2 に追従 |

## 今回の作業対象 (Wave 2 の残り)

`TASKS_ROADMAP.md §4` (Wave 2) を正本として以下を残作業として扱う:

**✅ 完了済 (offline で fix 可能な範囲)**:
- [x] `enable_feature_online_store` を `dev` で `true` に flip + Feature View outputs 反映の live apply
- [x] **W2-4 Composer 本実装** (Phase 7 = canonical 起点、Stage 1-3 全完了): module skeleton + 3 DAG + composer_deploy_dags.py + Make target + deploy_all 15 step + DAG unit tests + `enable_composer=true` flip + 軽量 trigger 格下げ
- [x] **W2-8 互換レイヤ削除** (canonical 1 経路化): `BigQuerySemanticSearch` / `BigQueryFeatureFetcher` / `SEMANTIC_BACKEND` / `FEATURE_FETCHER_BACKEND` env 撤去、container/configmap/deployment.yaml 同期完了
- [x] **§4.9 K fix** (VVS 永続化 = state rm + terraform import pattern): `prevent_destroy` 撤回、`vertex_import.py` 新規、`destroy_all.py` に state_rm ループ
- [x] **§4.10 state_recovery 徹底実装** (12 GCP type、`alreadyExists` fail 回避): `scripts/infra/state_recovery.py` (~700 行) + `make state-recover` + deploy_all で tf-apply 直前に呼出し
- [x] **destroy-all contract test 拡張** (旧 9 → 新 15 件、incident 3 + state_recovery 3 を契約化)
- [x] **runbook §1.4-emergency 新節追加** (緊急 kill switch + tfstate orphan cleanup + state-recover 推奨)
- [x] **tfstate orphan cleanup** (151 entries → 0 達成)
- [x] `scripts/setup/backfill_vector_search_index.py` の live 実行 (2026-05-02)
- [x] `scripts/ops/vertex/vector_search.py` smoke の live 実行 (2026-05-02)
- [x] `scripts/ops/vertex/feature_group.py` smoke の live 実行 (2026-05-02)
- [x] `make ops-feedback` / `make ops-ranking` / `make ops-accuracy-report` の live 実行 (2026-05-02)
- [x] `ops-train-wait` 追加 (`ops-train-now` submit 後に SUCCEEDED まで待つ contract)

**✅ インフラ・run-all (2026-05-03 夜)**:
- [x] **V1** `make deploy-all` 完走
- [x] **V2** `make run-all-core` 完走

**🔴 死守ライン（未完了扱い）**:
- [ ] **V5 E2E**: ダッシュボード「🔴 死守ライン」チェックリストを **すべて** 満たす（`check_retrain` のみ success で **完了にしない**）

**優先順位つき（明日以降の並べ方）**:
- [ ] **V5 E2E**（最優先・任意ラベル禁止）
- [ ] **V4** 2 周目 deploy-all（準死守）
- [ ] **V6** parity live_gcp（余力）
- [ ] **V3** destroy-all（最後・破壊的検証）

## 今回はやらない

- 中核 5 要素の置換 (Meilisearch → Elasticsearch 等) — User 合意必須
- `/search` デフォルト挙動の変更 — User 合意必須
- 全 Phase 共通禁止技術 (Agent Builder / Discovery Engine / Gemini RAG / Model Garden / Vizier / W&B / Looker Studio / Doppler)
- BigQuery fallback / backend 切替 env を「default off で残す」運用 — 教育コード原則として **撤去** (`TASKS_ROADMAP.md §2.1` / `§2.4`)

## 完了条件

- [x] `make check` (ruff + format + mypy strict + pytest) 通過
- [x] `make deploy-all` 完了 (sprint 実測 Run 6)
- [x] `make run-all-core` 通過
- [ ] **死守ライン**: **V5 Composer 経由再学習 E2E 最小検証**（ダッシュボード 🔴 チェックリスト全項目 — `submit_train_pipeline`〜`/search` 健全性）
- [x] （参考ゲート）`retrain_orchestration::check_retrain` **success** — Run 4、§0.1。**単体では死守完了にしない**
- [ ] `/search` semantic 経路が Vertex Vector Search 1 本 (BQ fallback 撤去後) — V2 で実機確認済、**再学習 E2E 後も**モニタ
- [ ] feature 取得経路が Feature Online Store (Feature View 経由) 1 本 — 同上
- [ ] Feature parity invariant (CLAUDE.md §「Feature parity invariant」) を維持

## 実装済 (Wave 1 + Wave 2 offline 部分)

### Wave 1 (`TASKS_ROADMAP.md §3` / 63 unit tests passed)
- [x] PR-1: `SemanticSearch` Port + `vertex_vector_search_semantic_search.py` adapter (17 tests)
- [x] PR-2: `FeatureFetcher` Port + Feature Online Store adapter (18 tests)
- [x] PR-3: `VectorSearchWriter` Port + pipeline component (17 tests)
- [x] PR-4: Container 配線 + `ranking.py` merge (11 tests)

### Wave 2 offline wiring (`TASKS_ROADMAP.md §4`)
- [x] W2-1: `infra/terraform/modules/vector_search/` module (main/variables/outputs/versions.tf) 新規
- [x] W2-2: `vertex/variables.tf` で `enable_feature_online_store` default `true` + Feature View outputs
- [x] W2-3: KServe SAs (vector search query / feature view read) IAM bindings (`modules/iam`)
- [x] W2-5: `search-api configmap.example` + `deployment.yaml` の env vehicle 追加
- [x] W2-6: `scripts/setup/backfill_vector_search_index.py` の実装
- [x] W2-7-a: `scripts/ops/vertex/vector_search.py` smoke の実装
- [x] `scripts/ci/sync_configmap.py` 追従 (`semantic_backend` / `vertex_vector_search_*` / `feature_fetcher_backend` / `vertex_feature_*` を generator が再現)
- [x] `tests/integration/parity/` の live GCP 雛形追加 (`live_gcp` marker で local skip)
- [x] W2-9: mypy pre-existing 9 件解消 (KFP 2.16 互換 issue のみ継続)

## 次 Phase

Phase 7 が到達ゴール。これ以降の phase は無い (`README.md` / 親 `CLAUDE.md` で 7 phase 構成と明記)。

## 参照

- `TASKS_ROADMAP.md` (本ファイルの正本、Wave 1/2/3 詳細)
- `docs/decisions/0001〜0008` (恒久対処ギャップの ADR)
- 親 `CLAUDE.md §「Cloud Composer (Phase 6 必須、Phase 7 継承)」` (orchestration 二重化禁止)


＝＝＝＝＝＝＝＝＝＝＝＝＝＝
V5 成功後

## 結論

はい。**V5 が成功したら、次にやるべきは機能検証の追加よりも、workflow contract test の強化です。**

理由は明確で、今回地獄になった原因は「機能が存在しない」ではなく、主にこれだからです。

```text
deploy-all / destroy-all / run-all-core / composer-deploy-dags の間で
実行順・env・IAM・upload対象・state recovery・DAG実行基盤の契約がズレた
```

つまり、**個別機能テストだけ増やしても再発防止になりにくい**です。
再発を止めるには、「この workflow はこういう構造でなければならない」を test で固定する必要があります。

---

## 理由

今回の V5 周辺だけでも、地獄ポイントはかなり workflow contract 寄りです。

| 事故                                 | 本質                             | contract 化すべき内容                            |
| ---------------------------------- | ------------------------------ | ------------------------------------------ |
| BashOperator + `uv run`            | Composer worker 前提の誤設計         | DAG で BashOperator / `uv run python` 禁止    |
| `_pod.py` upload 漏れ                | DAG helper 同梱漏れ                | `composer-deploy-dags` が helper file を含むこと |
| `API_EXTERNAL_URL` / `API_URL` 不一致 | env 名の契約破れ                     | Pod env alias が定義されていること                   |
| `api_external_url` 空               | Terraform → Composer env の配線漏れ | dev variables / module / env_variables の接続 |
| image pull 権限                      | SA と Artifact Registry の契約漏れ   | sa-composer に reader 権限                    |
| state orphan / alreadyExists       | destroy / deploy の state 契約漏れ  | state_recovery が tf-apply 前に走ること           |

添付の TASKS.md でも、V1/V2/V5 が罰金回避ライン、V3/V4 が destroy/deploy の品質ラインとして整理されています。V5 成功後に V3/V4 を地獄に戻さないには、workflow contract test の拡充が必要です。

---

## 有力シナリオ

### 1. 最優先で追加すべき contract test

```text
tests/integration/workflow/
```

ここに以下を追加するのがよいです。

| 優先 | contract                                                                       | 目的                            |
| -: | ------------------------------------------------------------------------------ | ----------------------------- |
|  1 | `deploy_all` が `state_recovery` を tf-apply 前に呼ぶ                                | alreadyExists 地獄の再発防止         |
|  2 | `deploy_all` の step 順が seed → meili → vvs → fv → manifests → dags → api になっている | run-all 前提の破壊防止               |
|  3 | `destroy_all` が VVS Index / Endpoint を state rm し、deployed_index は undeploy する | 高額課金・prevent_destroy 地獄防止     |
|  4 | `composer_deploy_dags` が `.py` DAG だけでなく `_pod.py` / sql helper を upload する    | DAG import fail 防止            |
|  5 | DAG 内に `BashOperator` / `uv run python` が存在しない                                 | Composer worker 依存の再発防止       |
|  6 | DAG task が `KubernetesPodOperator` or provider operator を使う                    | Composer-native 実行方式の固定       |
|  7 | `COMPOSER_RUNNER_IMAGE` が Terraform dev → module → Composer env に配線されている       | runner image 未注入防止            |
|  8 | `API_EXTERNAL_URL` が `API_URL` alias として Pod に渡る                               | check_retrain 再発防止            |
|  9 | sa-composer に `artifactregistry.reader` / `storage.objectViewer` がある           | image pull / GCS read fail 防止 |
| 10 | `make run-all-core` の中に `ops-train-now` と `ops-train-wait` が両方ある               | submit だけ成功の偽陽性防止             |

---

## 破綻条件

やってはいけないのは、**成功後に「機能テスト PASS したからOK」で止めること**です。

それだと次にこのあたりで再発します。

```text
1. deploy-all の step 順が誰かの修正で崩れる
2. destroy-all がまた state を壊す
3. Composer DAG helper の upload 漏れが再発する
4. Terraform env var 配線が片側だけ更新される
5. DAG が便利だからと BashOperator に戻される
6. run-all-core が train submit だけ見て wait しなくなる
```

今回の地獄は「実機で初めてわかる」部分が多かったですが、**構造違反そのものはローカル contract test でかなり弾けます。**

---

## 実務・行動への影響

V5 成功後の順番はこれが最善です。

```text
1. V5 成功ログを保存
2. TASKS.md を V5 ✅ に更新
3. workflow contract test を追加
4. make check を通す
5. V3 destroy-all live verify
6. V4 2周目 deploy-all import verify
7. run-all-core 再実行
```

特に、次の5つは即追加がよいです。

```text
A. DAG で BashOperator / uv run python 禁止
B. composer_deploy_dags が _pod.py を upload する
C. API_EXTERNAL_URL → API_URL alias がある
D. COMPOSER_RUNNER_IMAGE が Terraform から Composer env へ流れる
E. sa-composer に artifactregistry.reader がある
```

この5つは、今回の V5 地獄の再発防止に直結します。

---

## まとめ

V5 が成功したら、次の主戦場は **「動いた」ではなく「二度と壊れないように契約化する」**です。

今回の完成ラインはこうです（**優先順位は死守ラインに合わせる**）。

```text
V1 / V2 成功
↓
V5 Composer 経由 E2E（死守ライン・TASKS チェックリスト）
↓
workflow contract test 追加
↓
V4 deploy-all import 経路（準死守）
↓
V6 parity live_gcp（余力）
↓
V3 destroy-all（最後）
↓
run-all-core 再確認
```

ここまでやると、次の `deploy-all / destroy-all / run-all-core` でまた地獄になる確率をかなり落とせます。
