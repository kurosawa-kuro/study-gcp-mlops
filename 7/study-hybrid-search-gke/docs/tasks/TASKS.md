# TASKS.md (Phase 7 — current sprint)

Claude Code の新セッションが「**今 sprint で何をやり、何をやらないか**」を最初に確認する単一エントリポイント。

## 本ドキュメントの債務 (= 何が書いてあるか)

本ファイルの責務は **「今」 の sprint dashboard**。**今日のゴール / 達成済 / 残り work / sub-step 進捗** の single source of truth。

- **書く**: 今日のゴール (罰金回避ライン)、V1-V6 の current status、sub-step 進捗、直近 timeline、次に動かす command
- **書かない (= 他 doc に委譲)**:
  - 「**何で OK と判定するか**」 (V1-V6 の検証ゲート定義) → [`../runbook/04_検証.md`](../runbook/04_検証.md) (検証 canonical 定義)
  - 「**過去 incident の詳細**」 (§4.X postmortem / Wave 計画 / 設計判断) → [`TASKS_ROADMAP.md`](TASKS_ROADMAP.md) (作業計画 + incident 母艦)
  - 「**やる手順**」 (`make deploy-all` の打ち方) → [`../runbook/05_運用.md`](../runbook/05_運用.md) (PDCA / runbook)

進捗を 3 箇所に書くと「片方だけ ✅ にして実は未達」のような虚偽 (= goal degradation) が起きやすい → **進捗は本ファイルに集約** (CLAUDE.md §「⛔ ゴール劣化禁止」と表裏一体)。

権威順位: `TASKS_ROADMAP.md > TASKS.md > 01_仕様と設計.md > README.md`。過去判断履歴は `docs/decisions/` (ADR 0001〜0008)。

---

## 🎯 ゴール状況ダッシュボード (2026-05-03 夕 更新)

### 今日のゴール (罰金回避ライン = Phase 7 canonical 充足)

`make deploy-all` + `make run-all-core` + **Composer DAG SUCCEEDED** (V5) の **3 つ完遂** が今日のゴール。`make destroy-all` の live verify は明日に繰り延べ。

**V5 を含める理由**: CLAUDE.md / 親 README に「**本線 retrain schedule は Composer DAG**」と明記されており、SUCCEEDED 未達は canonical の根幹未実証 (= MLOps として動いていない = ゴミ納品)。「明日以降」「別 sprint」という hedging label でこれを scope 外に逃がすことは禁止 (CLAUDE.md §「⛔ ゴール劣化禁止」)。

### 今日の達成・残り work

| # | item | status | 備考 |
|---|---|---|---|
| **V1** | `make deploy-all` 完走 | ✅ **DONE** | Run 6 exit 0 / 35.5 min / state_recovery 12 type で `alreadyExists` ゼロ / Composer 作成 18m48s |
| **V2** | `make run-all-core` 完走 | ✅ **DONE** | retry 1 回目 PASS / `ndcg_at_10=1.0 hit_rate=1.0 mrr=1.0` / 3 種 lexical/semantic/rerank all non-zero / Vertex Pipeline SUCCEEDED |
| **V5** | Composer DAG `retrain_orchestration::check_retrain` SUCCEEDED | 🔄 **70% 進行中** (詳細下表) | 🔴 canonical 必須 = 罰金確定ライン |

### V5 実装サブステップ

| # | サブステップ | status | 詳細 |
|---|---|---|---|
| V5-1 | `composer-runner` Dockerfile 作成 | ✅ | `infra/run/services/composer_runner/Dockerfile` 新規 (Python 3.12 + `[pipelines]` extra + gcloud SDK + scripts/pipeline/ml source) |
| V5-2 | Cloud Build config + Make target | ✅ | `infra/run/services/composer_runner/cloudbuild.yaml` + `scripts/deploy/composer_runner.py` + `make build-composer-runner` |
| V5-3 | composer-runner image push | ✅ | Run 1 = OOM (exit 137、`[ml]` extra で snapshot 4GB+)、**Run 2 SUCCESS 187s** (`[ml]` 削除で ~700MB-1GB に縮小)。`composer-runner:latest` = `asia-northeast1-docker.pkg.dev/mlops-dev-a/mlops/composer-runner:latest` |
| V5-4 | 3 DAG を `KubernetesPodOperator` + provider Operator に書き換え (8 task) | ✅ | `pipeline/dags/_pod.py` (helper、`python_pod` / `gcloud_pod`)、`retrain_orchestration.py` (5 task)、`daily_feature_refresh.py` (5 task、Dataform は `DataformCreateWorkflowInvocationOperator` 化)、`monitoring_validation.py` (3 task) |
| V5-5 | DAG unit test 更新 | ✅ | `tests/unit/pipeline/dags/test_dag_files.py` に契約追加: `BashOperator` 禁止 / `uv run python` 文字列禁止 / `python_pod` or provider Operator 必須 / `_pod.py` 存在確認。**18 PASS** + `make check` **659 PASS / 1 skipped** |
| V5-6 | sa-composer IAM 追加 + Composer module env_var | ✅ | `iam/main.tf` に `artifactregistry.reader` + `storage.objectViewer` 追加 / `composer/main.tf` env_variables に `COMPOSER_RUNNER_IMAGE` 追加 / `composer/variables.tf` + `dev/main.tf` + `dev/variables.tf` 配線 / `tf-validate` Success |
| V5-7a | `tf-apply` (新 IAM + Composer env_var update) | ✅ **DONE** (395s) | sa-composer に artifactregistry.reader + storage.objectViewer 追加 / Composer env_variables に `COMPOSER_RUNNER_IMAGE` 注入 / `Apply complete! 5 added, 3 changed, 3 destroyed` |
| V5-7b | `composer-deploy-dags` (新 DAG upload + `_pod.py` helper) | ✅ **DONE** | 初回 `_pod.py` 抜け落ち発見 → `composer_deploy_dags.py` の `_list_extra_files()` に追加 → 再 upload で 3 DAG + `_pod.py` + sql 2 件 upload 確認 |
| V5-7c | DAG smoke (`make ops-composer-trigger DAG=retrain_orchestration` → SUCCEEDED 確認) | 🔴 **Run 1 FAILED** (~2 min)、真因 fix → Run 2 準備中 | `check_retrain` task が container exit 1 で fail。**真因 2 件発見** (V5-fixup 表参照) |

### V5 fixup (Run 1 fail postmortem 2026-05-03 晩)

| # | 真因 | 対処 | status |
|---|---|---|---|
| F1 | **環境変数名のミスマッチ**: Composer env_variables = `API_EXTERNAL_URL` (terraform canonical)、`scripts.ops.check_retrain` → `resolve_api_target()` → `API_URL` env を読む。Pod に `API_URL` が inject されておらず、`gateway_url()` の kubectl 経路も Composer Pod では使えない | `pipeline/dags/_pod.py` に `ENV_KEY_ALIASES = {"API_EXTERNAL_URL": ("API_URL",)}` を追加し、Pod に inject する際に script 側 canonical 名にも複製 | ✅ **fix 済 (本セッション)** |
| F2 | **`API_EXTERNAL_URL` 値未設定**: `var.api_external_url` default = `""`、Gateway URL 未注入。`make ops-api-url` = `https://136.110.137.177` を `-var=api_external_url=...` で渡し直す必要 | tf-apply に `-var=api_external_url=https://136.110.137.177` を追加して Composer env を更新 | ⏳ Run 2 で適用予定 |

= **V5 ゴール到達まで残り ~10 分** (fixup 適用 + composer-deploy-dags + smoke retry)

### 直近 1.5 日の達成 (= **進捗ゼロではない**、構造的 incident fix が大量に入った)

| 日付 | 達成 | 備考 |
|---|---|---|
| 2026-05-02 | Wave 1 完了 + Wave 2 offline wiring 完了 + run-all-core 1 周 live PASS | `ndcg_at_10=1.0`、3 種 lexical/semantic/rerank all non-zero |
| 2026-05-03 朝 | destroy-all 失敗事故 → **§4.9 K fix** (`prevent_destroy` 撤回 + state rm + terraform import pattern)、contract test 9 → 12 件 | VVS 永続化アーキテクチャの根本修正 |
| 2026-05-03 昼 | tfstate orphan **151 → 0** cleanup (緊急 cleanup の副作用回復)、runbook §1.4-emergency 新節追加 | 緊急 kill switch + state-recover 推奨を runbook 化 |
| 2026-05-03 夕 | **§4.10 state_recovery.py 12 GCP type 徹底実装** (Run 1-5 で incremental 発見)、contract test 12 → 15 件、**Run 6 step 6 PASS** (Composer 作成 18m48s、`Apply complete! 1 added 2 changed`) | IAM SA / BQ / Pub/Sub / CF / Eventarc / Run / AR / Secret / Dataform / GCS / Feature Store (FG/FOS/FV) / FG Features 7 個 |

### 明日以降 (今日のゴールに含めない)

| # | item | 備考 |
|---|---|---|
| V3 | `make destroy-all` live 1 周 verify (state rm + import pattern) | 12-17 min 想定 |
| V4 | 2 周目 `make deploy-all` (`terraform import` 経路の live 検証) | 30 min → **10-15 min** に短縮の期待 (§4.9) |
| **V5 ⚠️ canonical 未達** | Composer DAG `retrain_orchestration::check_retrain` SUCCEEDED smoke | **追加 sprint 必須** (§4.1、CLAUDE.md「本線 retrain = Composer DAG」の根幹実証。「深追いは別 sprint」は hedging label) |
| V6 | `tests/integration/parity/*` `live_gcp` mark 本実行 | 別 session 妥当 (機能影響低) |

詳細は [`TASKS_ROADMAP.md` 「現在地」](TASKS_ROADMAP.md#現在地-2026-05-03-夕-更新) と [`04_検証.md §0`](../runbook/04_検証.md#0-現在の検証状況と重点未済項目-2026-05-03-夕-更新)。

---

## 現在の目的

Phase 7 = Phase 6 (PMLE + Composer 本線) と Phase 5 必須の Feature Store / Vertex Vector Search を継承し、**serving 層のみ Vertex AI Endpoint → GKE + KServe InferenceService に差し替える** 到達ゴール。

中核 (不動産ハイブリッド検索 / Meilisearch + Vertex Vector Search + ME5 + RRF + LightGBM LambdaRank) は不変。推論を cluster-local HTTP に委譲。

Phase 7 固有: KServe → Feature Online Store を **Feature View 経由で** opt-in 参照、TreeSHAP 用 explain 専用 Pod を独立 deploy。

## 進捗サマリ (2026-05-03 夕 時点 — `TASKS_ROADMAP.md §進捗サマリ` 抜粋)

| Wave | フェーズ | 状態 | 内容 |
|---|---|---|---|
| **Wave 1** | ローカル完結 (検索アプリ層) | ✅ **完了** (M-Local 達成) | PR-1 〜 PR-4 全 merge、`make lint` / `make fmt-check` / 関連 mypy / pytest 63 passed |
| **Wave 2** | GCP インフラ層 (クラウド側主作業) | 🟡 **罰金回避ライン直前** (V1+V2 で達成) | offline 部 ✅ (W2-8 互換レイヤ削除 / W2-4 Composer 本実装 / state_recovery 12 type / contract 15 件 / runbook §1.4-emergency)、live 部 🔄 (V1 Run 6 進行中、V2 はその後) |
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

**🟢 進行中 (今日のゴール = V1+V2)**:
- [ ] **V1**: `make deploy-all` Run 6 完走 — **step 1-6 ✅ PASS** (Composer 作成 18m48s、`Apply complete! 1 added 2 changed`、`alreadyExists` ゼロ達成)、step 7-15 (seed → meili → vvs → fv → manifest → configmap → dags → api) 進行中、残り ~12-15 min
- [ ] **V2**: `make run-all-core` 完走 (V1 直後、~3-5 min、`ndcg_at_10=1.0` 維持確認)

**⏳ 明日以降 (今日のゴールに含めない、ただし V5 は質低下マーカー)**:
- [ ] V3: `make destroy-all` live 1 周 verify (state rm + import pattern)
- [ ] V4: 2 周目 deploy-all で `terraform import` 経路の live 検証
- [ ] **V5 ⚠️ canonical 未達 (= ゴール劣化)**: Composer DAG `retrain_orchestration::check_retrain` task が SUCCEEDED **しない** (数秒 fail)。真因 = DAG が `BashOperator: uv run python -m scripts.ops.X` を呼ぶ設計なのに Composer worker に `uv` と repo module 不在 (§4.1)。CLAUDE.md は「**本線 retrain schedule は Composer DAG**」と謳うため、SUCCEEDED 未達は Phase 7 canonical の根幹未実証。**「深追いは別 sprint」と書くのは hedging、本来は V1+V2 完走後の追加 sprint で必ず潰すべき必須項目**
- [ ] V6: `tests/integration/parity/test_semantic_backend_parity.py` / `test_feature_fetcher_parity.py` の `live_gcp` 本実行 (W2-8 削除後の cross-check、機能影響低)

## 今回はやらない

- 中核 5 要素の置換 (Meilisearch → Elasticsearch 等) — User 合意必須
- `/search` デフォルト挙動の変更 — User 合意必須
- 全 Phase 共通禁止技術 (Agent Builder / Discovery Engine / Gemini RAG / Model Garden / Vizier / W&B / Looker Studio / Doppler)
- BigQuery fallback / backend 切替 env を「default off で残す」運用 — 教育コード原則として **撤去** (`TASKS_ROADMAP.md §2.1` / `§2.4`)

## 完了条件

- [ ] `make check` (ruff + format + mypy strict + pytest) 通過
- [ ] `make deploy-all` 完了 (tf-bootstrap → tf-init → WIF 復元 → sync-dataform-config → tf-plan → tf apply stage1/stage2 → seed-lgbm-model → seed-test → sync-meili → backfill-vvs → trigger-fv-sync → apply-manifests → overlay-configmap → deploy-api、初回は VVS attach 次第で 30-40 分)
- [ ] `make run-all-core` 通過 (check-layers → seed-test → sync-meili → ops-train-now → ops-train-wait → ops-livez/search/search-components/VVS/FOS/feedback/ranking/label-seed → ops-daily → ops-accuracy-report)
- [ ] Composer 3 DAG が retrain schedule の本線として稼働
- [ ] `/search` semantic 経路が Vertex Vector Search 1 本 (BQ fallback 撤去後)
- [ ] feature 取得経路が Feature Online Store (Feature View 経由) 1 本 (BQ direct fetch 撤去後)
- [ ] Feature parity invariant 6 ファイル原則 (CLAUDE.md §「Feature parity invariant」) を維持

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

今回の完成ラインはこうです。

```text
V1 / V2 / V5 成功
↓
workflow contract test 追加
↓
V3 destroy-all
↓
V4 deploy-all import 経路
↓
run-all-core 再確認
```

ここまでやると、次の `deploy-all / destroy-all / run-all-core` でまた地獄になる確率をかなり落とせます。
