Ready to code?                                                                                                                                                                                                                                                                                                                                                                       
                                                                                                                                                                                                                                                                                                                                                                                      
 Here is Claude's plan:                                                                                                                                                                                                                                                                                                                                                               
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
 Phase 7 Wave 2 — VVS / FOS live 検証中に発覚した 8 件のバグ徹底修正                                                                                                                                                                                                                                                                                                                  
                                                                                                                                                                                                                                                                                                                                                                                    
 Context

 直前のセッションで Vertex Vector Search の live 起動 → semantic 経路 VVS で動作確認まで達成 (W2-1 / W2-6 / W2-7 / G4 前段)。ただしその過程で 8 件のバグ / 設計欠落が発覚 し、いずれも次回 PDCA loop で再発する危険性がある。本セッションでこれらを 徹底修正 し、make destroy-all && make deploy-all 1 発で「3 種 all non-zero (VVS+FOS) + G4 前後段」が自動的に成立する状態にする。

 修正なしで残ると毎回:
 - TF_VAR_enable_*=true を手で export し忘れる (#11)
 - VVS Index 作成に feature_norm_type 系の謎 400 で詰まる (修正済 #1)
 - VVS upsert で v1/v1beta1 mismatch (修正済 #2)
 - ConfigMap drift で Pod が起動できない (修正済 #3)
 - FOS Optimized の Update 不可で plan が apply 不能 (#4)
 - FV sync が seed 投入前に走り FV が空のままでテスト fail (#5)
 - ConfigMap の VVS/FOS 値が空のままで semantic 経路を flip 不能 (#6)
 - provider data source race で localhost:80 401 連発 (#7)
 - pipe の | tail -N で deploy_all のエラーが exit 0 にすり替わる (#8)
 - deploy-all 1 発で完結せず手動 step が複数必要 (#9)
 - FV fetch 404 のとき何も診断情報が出ない (#10)

 …という状態が続き、毎回の destroy-all → deploy-all PDCA で別々の手作業を要求される。

 8 件の修正方針

 #4 FOS Optimized は Update API 未サポート → terraform の plan 差分を抑止

 症状: Error 400: UpdateFeatureOnlineStore action is not supported for Optimized FeatureOnlineStore yet.

 原因: infra/terraform/modules/vertex/main.tf の google_vertex_ai_feature_online_store.property_features は optimized {} (Optimized type) で create するが、provider が空 block 等の minor diff を検知すると update を試みる → API 拒否で apply fail。

 修正: lifecycle { ignore_changes = [optimized, dedicated_serving_endpoint, labels] } を追加。これで作成後の minor diff を terraform が無視。create-only リソースとして扱う。

 ファイル: infra/terraform/modules/vertex/main.tf の resource "google_vertex_ai_feature_online_store" "property_features" block

 #5 + #9 FV sync は seed 投入後 に走る必要がある + deploy-all が 1 発で完結しない

 症状: tf apply 直後に走る FV 初回 sync は BQ source が空 → FV にデータ無し → feature_group.py fetch が 404。

 原因: deploy_all step リストに seed-test も trigger-fv-sync も含まれていない。手動で make seed-test → manual sync 必要。

 修正: scripts/setup/deploy_all.py::_steps() に新 step を 2 つ追加:
 - 新 step "seed-test" (元 step 7 の後): scripts.setup.seed_minimal.main() を呼ぶ
 - 新 step "trigger-fv-sync" (新 seed-test の後、enable_feature_online_store=true 時のみ): FV sync を REST API で trigger + 完了 polling

 新 helper を scripts/infra/feature_view_sync.py に作成 (W3 リファクタの infra/ 層に整合)。10 step → 12 step 構成に増える。

 ファイル:
 - scripts/setup/deploy_all.py — step list 拡張
 - 新規 scripts/infra/feature_view_sync.py — sync trigger + polling
 - 新規 tests/unit/scripts/test_infra_feature_view_sync.py — mock test

 #6 ConfigMap の VVS / FOS 値を terraform output から自動注入

 症状: scripts/deploy/configmap_overlay.py は meili_base_url だけ動的解決、VVS / FOS 値は strangler default の空文字のまま。kubectl patch を手で叩く必要があった。

 修正: configmap_overlay.py::main() で terraform -chdir=... output -json を呼び、出力から:
 - vector_search_index_endpoint_id
 - vector_search_deployed_index_id
 - vertex_feature_online_store_id
 - vertex_feature_view_id
 - vertex_feature_online_store_endpoint
 を取得して generate_configmap_data() の入力に追加。

 scripts/lib/config.py::generate_configmap_data の signature を拡張 (新 keyword 引数を default 空文字で受ける、既存呼び出しと互換)。

 semantic_backend / feature_fetcher_backend は引き続き strangler default "bq" を使う (この session の本目的は wiring を完成させることで、自動 flip は別件)。

 ファイル:
 - scripts/lib/config.py — generate_configmap_data 拡張
 - scripts/deploy/configmap_overlay.py — terraform output 読み込み追加
 - tests/unit/scripts/test_lib_config.py — 新引数の test 追加

 #7 provider data source の評価レース → localhost:80 401

 症状: terraform plan 実行時に data.google_container_cluster.hybrid_search が空評価され local.k8s_host = "https://" → kubernetes provider が localhost にフォールバック → module.kserve.kubernetes_namespace の refresh で 401 エラー連発。

 原因: data "google_container_cluster" "hybrid_search" は depends_on = [module.gke] を持つが、data source は plan/refresh 時に毎回再評価される。最初の evaluation で provider が初期化される瞬間に data source 結果が遅延し、空文字が provider config に流れる場合がある (terraform の data source ↔ provider config 評価順の既知問題)。

 修正: provider config から data source 直参照を 削除し、gcloud container clusters get-credentials 経由の kubeconfig だけを使う形に切替え。具体的には:

 provider "kubernetes" {
   config_path    = "~/.kube/config"
   config_context = "gke_${var.project_id}_${var.region}_${var.gke_cluster_name}"
 }

 provider "helm" {
   kubernetes {
     config_path    = "~/.kube/config"
     config_context = "gke_${var.project_id}_${var.region}_${var.gke_cluster_name}"
   }
 }

 deploy-all は step "ensure_kubectl_context" で gcloud container clusters get-credentials を必ず先行実行する (既に存在、scripts/infra/kubectl_context.py::ensure)。state op を行う scripts/setup/recover_wif.py 用の k8s_use_data_source=false ロジックは廃止可能 (kubeconfig が無くても provider init は失敗しない、resource 操作時のみ kubectl 呼ぶ)。

 ただしこの fix は module.gke の depends_on を kubernetes/helm provider 側で明示できなくなる ため、tf apply は事前に cluster が存在する状態を要求する。これは現状の運用 (2 段階 apply: cluster 先行 → 残部) と整合。

 var.k8s_use_data_source 変数は廃止 → recover_wif.py::_tf_env_for_no_cluster() も簡略化。

 ファイル:
 - infra/terraform/environments/dev/provider.tf — kubernetes/helm provider を kubeconfig-based に
 - infra/terraform/environments/dev/variables.tf — k8s_use_data_source 削除
 - scripts/setup/recover_wif.py — _tf_env_for_no_cluster 簡略化 (TF_VAR 不要)

 #8 deploy_all 失敗時の exit code が | tail で隠れる問題

 症状: uv run python -m scripts.setup.deploy_all ... 2>&1 | tail -30 形式の wrapper invocation で、deploy_all が exit 1 で落ちても tail の exit 0 が wrapper の rc になり、上位の Bash tool が「成功」と誤認識。

 原因: shell pipe の rc 仕様。

 修正: Python script 側を強化 (本 session 以降の Bash 呼び出しでは | tail を使わない、または set -o pipefail を入れる) + script 自体に 失敗時の last-line summary を出して見落としにくくする:
 - scripts/setup/deploy_all.py::main() の例外 handler で「==> deploy-all FAILED at step N (name) — see traceback above」を stdout 末尾に出してから raise する。

 ファイル: scripts/setup/deploy_all.py::main に try/except 追加

 #10 feature_group.py 404 時の診断情報強化

 症状: 404 が出たとき "FeatureView sync ran" と書くだけで、実際に sync が走ったか / 何時に走ったか / source row count はいくつかが見えない。

 修正: 404 fail 時に追加で:
 1. 直近 sync の featureViewSyncs:list を呼び、runTime.startTime/endTime/finalStatus.code を表示
 2. BQ source table ({project_id}.feature_mart.property_features_daily) の COUNT(*) を表示
 3. 「次に何をすればよいか」の hint (sync trigger / wait / source 投入)

 ファイル: scripts/ops/vertex/feature_group.py::main の except 句強化

 #11 enable_vector_search / enable_feature_online_store の default を true に

 症状: infra/terraform/environments/dev/variables.tf で両方 default false → TF_VAR_enable_*=true を毎回 export 必要、忘れると VVS/FOS が空走。

 修正: dev environment は PDCA loop 用なので true を default に。コスト懸念があるなら destroy-all で全消しする運用を継続する (本 phase 設計意図)。

 ファイル: infra/terraform/environments/dev/variables.tf の 2 var の default を true に変更 + description 修正。

 修正順序と依存

 1. #11 (default flag) — 1 行 × 2、即適用、make check のみ
 2. #10 (feature_group diagnostics) — script 追加、unit test 追加
 3. #6 (configmap_overlay terraform output 注入) — lib/config.py 拡張 + configmap_overlay.py 拡張 + test 拡張
 4. #5 + #9 (deploy-all に seed-test + FV sync 統合) — 新 step 2 個追加 + 新 module 追加 + test 追加
 5. #4 (FOS lifecycle) — terraform 1 block 追加
 6. #7 (provider kubeconfig-based) — provider.tf 書き換え + var.k8s_use_data_source 撤去 + recover_wif.py 簡略化
 7. #8 (deploy_all exit code visibility) — main() に except 句追加

 検証

 各 fix 後:
 - make check (ruff + fmt + mypy strict + pytest) 全 PASS
 - make sync-configmap で committed YAML が unchanged

 全 fix 後の end-to-end 再検証:
 1. make destroy-all (現在の cluster 完全消去)
 2. make deploy-all (新 12-step、TF_VAR_enable_*=true export 不要)
 3. make ops-search-components で 3 種 all non-zero
 4. make ops-vertex-vector-search-smoke (= python -m scripts.ops.vertex.vector_search) で 1 件以上 neighbor
 5. python -m scripts.ops.vertex.feature_group で property feature 値表示 (FOS sync が deploy-all 内で走っているはず)
 6. kubectl logs deployment/search-api | grep vertex_vector_search で adapter 起動 log 確認 (但し semantic_backend は default bq のまま、本 session ではあくまで wiring 完成)

 Critical Files

     Critical Files

     新規作成

     - scripts/infra/feature_view_sync.py — FV sync trigger + polling
     - tests/unit/scripts/test_infra_feature_view_sync.py — mock test

     編集

     - infra/terraform/environments/dev/variables.tf — default 切替 (#11) + k8s_use_data_source 撤去 (#7)
     - infra/terraform/environments/dev/provider.tf — kubeconfig-based provider (#7)
     - infra/terraform/modules/vertex/main.tf — FOS lifecycle (#4)
     - scripts/lib/config.py — generate_configmap_data 拡張 (#6)
     - scripts/deploy/configmap_overlay.py — terraform output 読み込み (#6)
     - scripts/setup/deploy_all.py — step list 拡張 (#5+#9) + main() exit visibility (#8)
     - scripts/setup/recover_wif.py — _tf_env_for_no_cluster 簡略化 (#7)
     - scripts/ops/vertex/feature_group.py — 404 診断強化 (#10)
     - tests/unit/scripts/test_lib_config.py — 新引数 test (#6)

     全体所要時間 (見積)

     ┌────────────────────────────────────────────────┬─────────────┐
     │                     Phase                      │    所要     │
     ├────────────────────────────────────────────────┼─────────────┤
     │ 修正実装 (8 件) + unit test                    │ ~60-90 分   │
     ├────────────────────────────────────────────────┼─────────────┤
     │ make check 反復                                │ ~10 分      │
     ├────────────────────────────────────────────────┼─────────────┤
     │ destroy-all → deploy-all (full live)           │ ~30-40 分   │
     ├────────────────────────────────────────────────┼─────────────┤
     │ End-to-end smoke (3 種 + VVS smoke + FV fetch) │ ~5 分       │
     ├────────────────────────────────────────────────┼─────────────┤
     │ 最終 destroy-all                               │ ~5 分       │
     ├────────────────────────────────────────────────┼─────────────┤
     │ 合計                                           │ ~110-150 分 │
     └────────────────────────────────────────────────┴─────────────┘

     Out of Scope (今 session でやらない)

     - W2-8 互換レイヤ撤去 (SEMANTIC_BACKEND 等の env 削除) — 別 session
     - ConfigMap が VVS canonical を default にする (= semantic_backend default を vertex_vector_search に flip) — wiring 完成 → soak → 別 session で flip
     - 中核 5 要素 / /search デフォルト挙動の変更 — 非負制約

● 修正開始。まず #11 (default flag) と #4 (FOS lifecycle) と #10 (feature_group 診断強化) — 独立で小さい変更から。


そもそも今回の仕様変更のVertex Vector Searchは機能していましたか？

 次の判断 (user 選択)                                                                                                                                                                                                                                                                                                                                                              
                                                                                                                                                                                                                                                                                                                                                                                      
  3 種検証は通ったので、ここから先は user の方針次第です:                                                                                                                                                                                                                                                                                                                             
                                                                                                                                                                                                                                                                                                                                                                                      
  A. ここで PDCA 完了 → make destroy-all でコスト止める (~3-5分、tfstate / API 有効化は残るので翌日 deploy-all 数分で復帰可能)                                                                                                                                                                                                                                                        
                                                                                                                                                                                                                                                                                                                                                                                      
  B. Wave 2 W2-1 (VVS live apply) + W2-6 (backfill) を続けて canonical G4 経路 (semantic を VVS 直接に flip) まで達成する (+ ~10-15分、追加コスト発生)                                                                                                                                                                                                                                
                                                                                                                                                                                                                                                                                                                                                                                      
  C. cluster 残しつつ別の検証に進む (e.g. make ops-feedback/ops-ranking/ops-accuracy-report、Wave 2 残作業ぶん)                                                                                                                                                                                                                                                                       
                                                                                                                                                                                                                                                                                                                                                                                    
  どれにしますか?       


W2-1: Create infra/terraform/modules/vector_search/ module (main/variables/outputs/versions.tf)

W2-1: Wire module "vector_search" into environments/dev/main.tf + root variables.tf/outputs.tf

W2-2: Flip enable_feature_online_store default to true in vertex/variables.tf + add feature_view outputs

W2-3: Add IAM bindings for KServe SAs (vector search query / feature view read) in modules/iam

W2-5: Add new env vehicles to search-api configmap.example + deployment.yaml

W2-6: Implement scripts/setup/backfill_vector_search_index.py

W2-7: Implement scripts/ops/vertex/vector_search.py smoke

Run make tf-validate / make check / pytest to confirm offline correctness


# 02. 移行ロードマップ — 検索アプリを最新仕様へ

Phase 7 の現コードを、最新仕様 (親 [README.md](../../../../README.md) §1-§3 / 親 [docs/01_仕様と設計.md](../../../../docs/architecture/01_仕様と設計.md) / 本 phase [docs/01_仕様と設計.md](../architecture/01_仕様と設計.md)) に追従させるための移行計画。

> **方針**: **Wave 1 = 検索アプリ自体 (app / ml / pipeline コード)** を先に整える。**Wave 2 = GCP インフラ (Terraform / IAM / deploy)** はその後。Wave 3 は docs / reference architecture との整合確認のみ (コード変更なし)。
>
> Port / Adapter / DI 大枠の整理は [`docs/TASKS_ROADMAP.md`](TASKS_ROADMAP.md)、過去の制約決定は [`docs/decisions/`](../decisions/README.md) を参照。
>
> **教育コード原則**: 後方互換・legacy fallback・旧 env 名 alias・旧 UI redirect・使われない shell resource は残さない。移行の都合で一時導入した互換レイヤも、役目を終えた時点で削除する。

---

## 進捗サマリ (2026-05-02 時点)

| Wave | フェーズ | 状態 | 内容 |
|---|---|---|---|
| **Wave 1** | ローカル完結 (検索アプリ層) | **✅ 完了 (M-Local 達成)** | PR-1 〜 PR-4 全 merge、`make lint` / `make fmt-check` / 関連 mypy / pytest 63 passed |
| **Wave 2** | **GCP インフラ層 (= クラウド側の主作業計画)** | 🟡 live 検証中 | §4 が母艦。**W2-1 / W2-2 / W2-3 / W2-5 / W2-6 / W2-7 の live wiring は成立**: VVS smoke / FOS fetch / feedback / ranking / accuracy / retrain wait を実測 PASS。**追加で canonical ConfigMap auto-flip と `ops-train-wait` を実装**。未完了は full PDCA 完走、Composer 継承、互換レイヤのコード削除 |
| Wave 3 | docs / reference architecture 整合 | ⏳ Wave 2 後 | 03_実装カタログ.md / 05_運用.md の「semantic 経路」「feature 取得経路」「Composer DAG 経路」記述を Wave 1/2 に追従 |

### 進捗ログ (2026-05-02)

「何も進んでいないのでは」という不安を避けるため、Wave 2 live 検証で実際に通した項目と、まだ残る項目を分離して記録する。

**この時点で実測 PASS 済み**

- local boot contract:
  - Docker build 成功
  - import smoke 成功
  - `ENABLE_SEARCH=false` で ADC なし `/livez` 200
- GCP canonical path:
  - `make ops-livez`
  - `make ops-search-components` (`lexical=1 semantic=3 rerank=5`)
  - `make ops-vertex-vector-search-smoke`
  - `uv run python -m scripts.infra.feature_view_sync`
  - `make ops-vertex-feature-group`
  - `make ops-feedback`
  - `make ops-ranking`
  - `make ops-accuracy-report` (`ndcg_at_10=1.0`)
  - `make ops-train-now` + `make ops-train-wait`
- workflow contract 強化:
  - ConfigMap overlay が Terraform outputs から VVS/FOS 値を注入
  - live overlay 時に `semantic_backend=vertex_vector_search` / `feature_fetcher_backend=online_store` へ auto-flip
  - `run-all-core` に `ops-vertex-vector-search-smoke` / `ops-vertex-feature-group` / `ops-train-wait` を組み込み
  - opt-in live acceptance gate に `feedback / ranking / accuracy / canonical ConfigMap` を追加
- destroy-all 再現性修正:
  - `Gateway` / `ServiceNetworkEndpointGroup` finalizer 詰まりを実害として確認し、回避手順を反映
  - `property_features_online_latest` の `deletion_protection` 漏れを修正
  - `tests/integration/infra/test_destroy_all_table_parity.py` を更新して再発防止
- docs 同期:
  - `TASKS.md`
  - `03_実装カタログ.md`
  - `04_検証.md`
  - `05_運用.md`

**この時点で進行中**

- full PDCA 再検証:
  - `destroy-all` 完了
  - clean state から `deploy-all` を再実行中
  - `step 6 tf-apply` は staged apply 化により、前回の blocker だった
    `property_features_online_latest` 404 と `module.kserve` / `helm_release`
    の GKE ready race を回避できる構造へ修正済み
  - live 再実行では `property_features_online_latest` 作成成功、
    `module.kserve` に入る前の `stage1` まで到達し、現在は
    `module.vector_search.google_vertex_ai_index_endpoint_deployed_index`
    の attach 長時間化 (10 分超の create 待ち) を観測中
  - その後の live 実測で `deploy-all` 自体は完走。VVS attach は
    **26m21s** で最終的に成功した
  - `deploy-all` 完走直後の実測では、
    - `ops-vertex-feature-group` は PASS
    - `ops-vertex-vector-search-smoke` は VVS index 空のため `0 neighbors` で FAIL
    - `ops-search-components` は lexical lane 未同期のため `lexical=0` で FAIL
  - root cause は `deploy-all` 本線に `backfill_vector_search_index --apply`
    と `sync-meili` が入っていなかったこと。両方を step 追加で修正し、
    workflow contract も `seed-test -> sync-meili -> backfill-vvs -> trigger-fv-sync`
    に更新中
  - 続いて `run-all-core` → 最後の `destroy-all` を通す

**まだ未完了**

- **W2-8 互換レイヤ削除**
  - `SEMANTIC_BACKEND`
  - `FEATURE_FETCHER_BACKEND`
  - `BigQuerySemanticSearch`
  - `BigQueryFeatureFetcher`
  - manifest / docs 上の暫定切替 vehicle
- Composer 継承確認
- `tests/integration/parity/*` の `live_gcp` 本実行

要点:

- 「主要な live wiring が動くか」は確認済み
- 「PDCA を clean state から最後まで 1 発で完走できるか」はまだ進行中
- 「暫定互換レイヤをコードごと消す」はまだ未着手ではなく、次の主作業として残っている

**Wave 1 の位置付け**:

- Wave 1 は **最終形ではなく暫定配線**。ローカル完結で adapter / Terraform / script を先に揃えただけで、教育コードとしての完成条件は **互換レイヤ削除後** とする
- 実 GCP 通信を伴う検証は Wave 2 で provision 後にまとめて smoke
- 受け入れ条件のローカル部分は satisfied、ただし GCP smoke 未実行・互換レイヤ未撤去のため **教育コードとしては未完成**

**63 unit tests 内訳** (`pytest tests/unit/app/test_*feature_fetcher* tests/unit/app/test_*semantic* tests/unit/app/test_*search_builder* tests/unit/app/test_*run_search_feature_fetcher* tests/unit/pipeline/test_vector_search* tests/unit/pipeline/test_data_job_dag*`):

- PR-1 (SemanticSearch / Vertex Vector Search): 17 tests
- PR-2 (FeatureFetcher / FOS): 18 tests
- PR-3 (VectorSearchWriter / pipeline): 17 tests
- PR-4 (Container 配線 + ranking.py merge): 11 tests

**Wave 2 で確認済みの補足**:
- `infra/manifests/kserve/reranker.yaml` の env vehicle 追加は **不要**。旧案は廃止し、search-api ConfigMap 経由へ一本化済。PR-4 docstring の予告は close
- `scripts/ci/sync_configmap.py` は **追従済**。`configmap.example.yaml` の Wave 2 キー (`semantic_backend` / `vertex_vector_search_*` / `feature_fetcher_backend` / `vertex_feature_*`) を generator が再現する
- `scripts/lib/config.py` / `scripts.deploy.configmap_overlay` は **live canonical flip 対応済**。Terraform outputs から VVS/FOS 値が入ると `semantic_backend=vertex_vector_search` / `feature_fetcher_backend=online_store` に自動で切り替わる
- `tests/integration/parity/test_semantic_backend_parity.py` / `test_feature_fetcher_parity.py` の **live GCP 雛形は追加済**。local / CI では `live_gcp` marker で skip、実行は Wave 2 live smoke 時に行う
- `W2-9` の **mypy pre-existing 9 件** (`search_service.py` / `lexical_search.py` / `ops_router.py` / `tests/conftest.py`) は解消済。KFP 2.16 互換 issue のみ継続

---

## 0. 前提と非負ルール (作業前に必ず確認)

- **中核 5 要素は不変**: Meilisearch BM25 / multilingual-e5 / ベクトルストア (Phase 4 = BQ `VECTOR_SEARCH` / Phase 5+ = Vertex AI Vector Search) / RRF / LightGBM LambdaRank
- **Phase 7 の canonical 挙動は 1 本にする**: `/search` の本線は Vertex Vector Search + Feature Online Store とし、BigQuery fallback や backend 切替スイッチを最終形に残さない
- **embedding 生成履歴・メタデータの正本は BigQuery 側**: Vertex Vector Search は本番 serving index、source は BQ embedding テーブル (`feature_mart.property_embeddings`)
- **Feature Store (Phase 5 必須)** を Phase 7 でも継承: training-serving skew 防止のため、Feature Online Store 経路を canonical とする
- **Meilisearch / Redis 同義語辞書は据え置き**: 実案件 reference architecture (Elasticsearch + Redis 同義語辞書) を教材向け substitute で維持しつつ、本 phase でも中核コードの意味を崩さない
- **Feature parity invariant 6 ファイル原則** は SemanticSearch / FeatureFetcher 変更でも継続 PASS
- **Cloud Composer は Phase 6 で導入 (本線昇格 + PMLE DAG 増設)、Phase 7 で継承**: Phase 6 で `daily_feature_refresh` / `retrain_orchestration` / `monitoring_validation` の 3 本 DAG が orchestration 本線になり、PMLE step (Dataflow / BQML / SLO / Explainability) も同 DAG に増設される。Vertex `PipelineJobSchedule` は Phase 6 で完全撤去、Cloud Scheduler / Eventarc / Cloud Function trigger は本線から軽量代替へ格下げ (= Phase 5 → 6 引き算境界)。Phase 5 では Composer は導入せず、Phase 4 軽量経路を本線として継続。Phase 7 はそのまま継承し、orchestration 二重化を作らない (詳細は親 [`README.md` §「Cloud Composer の位置づけ」](../../../../README.md))。Wave 2 GCP インフラの中で Composer 関連 (Composer 環境 Terraform 継承確認 + DAG deploy) も含む

---

## 1. 現状コードと仕様のギャップ

✅ = Wave 1 で解消済 / ⏳ = Wave 2 / 3 で対応予定。

| 状態 | 観点 | 現状コード (Wave 1 前) | 最新仕様 (target) | 対応 |
|---|---|---|---|---|
| ✅ | Semantic 検索 adapter | [`bigquery_semantic_search.py`](../app/services/adapters/bigquery_semantic_search.py) のみ (BQ `VECTOR_SEARCH`) | Vertex AI Vector Search を本番 serving index にする (Phase 5+ 仕様) | **PR-1 完了**: [`vertex_vector_search_semantic_search.py`](../app/services/adapters/vertex_vector_search_semantic_search.py) 新規追加、BQ adapter 据え置き |
| ✅ | `SemanticSearch` 切替 | composition_root に backend 切替なし、常に BQ | Vertex Vector Search を canonical とし、暫定切替を撤去する | **PR-1 完了**: [`SearchBuilder._resolve_semantic_search`](../app/container/search.py) で暫定分岐を導入。**Wave 2 で削除対象** |
| ✅ | Feature 取得 (rerank 入力) | `BigQueryCandidateRetriever._enrich_from_bq` 内 SQL JOIN で direct fetch | Phase 5 で Feature Online Store 経由可能に (training-serving skew 防止) | **PR-2 完了**: [`FeatureFetcher`](../app/services/protocols/feature_fetcher.py) Port + 2 adapters + fake、PR-4 で Container 配線 |
| ✅ | Feature Online Store 統合 | 未実装 | Feature View 経由で fresh feature を取得する | **PR-4 完了**: `Container.feature_fetcher` + `SearchService` + `run_search` の `_augment_with_fresh_features` で merge。**Wave 2 で旧 BQ 経路削除対象** |
| ✅ | Embed pipeline の出力先 | `feature_mart.property_embeddings` (BQ) のみ | BQ + Vertex Vector Search index 双方に書く (BQ は正本、VVS は serving index) | **PR-3 完了**: [`upsert_vector_search`](../pipeline/data_job/components/upsert_vector_search.py) component + [`VectorSearchWriter`](../pipeline/data_job/ports/vector_search_writer.py) Port + 2 adapters。runner 側 gate (`vector_search_index_resource_name=""` で no-op) |
| ⏳ | Vector Search Terraform モジュール | [`infra/terraform/modules/vector_search/`](../infra/terraform/modules/vector_search/) ディレクトリは存在するが空 | `google_vertex_ai_index` + `google_vertex_ai_index_endpoint` + deployed index | **Wave 2** で実装 |
| ⏳ | Feature Online Store Terraform | 既に [`modules/vertex/main.tf:273`](../infra/terraform/modules/vertex/main.tf) に資源定義あり、`enable_feature_online_store` default = `false` | Phase 5 必須要素なので default `true` 化、ただし `mlops-dev-a` の PDCA 都合で env 切替可能 | **Wave 2** で flag 切替方針を整理 |
| ⏳ | docs reference architecture (Elasticsearch / Redis 同義語辞書) | コードに無い (✓ 期待通り) | 実装しない (docs only) | **Wave 3** で lint 化 (codeに固有名が漏れていないか確認) |

---

## 2. 移行戦略

### 2.1 暫定互換レイヤの扱い

Wave 1 ではローカル完結のために一時的な backend 切替と fallback を導入したが、**教育コードの完成条件はそれらを削除すること**。`BigQuerySemanticSearch` / `BigQueryFeatureFetcher` / backend 切替 env / legacy alias は Wave 2 の live 検証後に撤去し、Phase 7 の canonical 実装を 1 本に収束させる。

### 2.2 PR 分割粒度 (1 PR = 1 Port 原則)

| PR | スコープ | 受け入れ条件 |
|---|---|---|
| PR-1 | `SemanticSearch` Port + Vertex Vector Search adapter (app 層) + fake / unit test | `SEMANTIC_BACKEND=vertex_vector_search` で `/search` が in-memory fake 経由で 200 を返す |
| PR-2 | `FeatureFetcher` Port + Feature Online Store adapter (app 層) + fake | `FEATURE_FETCHER_BACKEND=online_store` で ranking が fake 経由で動作 |
| PR-3 | `VectorSearchWriter` Port + adapter (pipeline 層) + embed pipeline 二重書き | `pipeline/data_job/main.py` がローカルで BQ + fake VVS の両方に書く |
| PR-4 | Feature Online Store 統合 (Phase 7 固有) | Feature View 経由の fresh feature 取得が動作する |
| Wave 2 → | Terraform / IAM / deploy | 別 roadmap section §4 参照 |

### 2.3 互換レイヤ撤去の段取り

```
Step A: Wave 1 で live 以外の wiring を先に完成
Step B: Wave 2 で GCP apply / smoke / parity を完了
Step C: BigQuery fallback / backend 切替 env / legacy alias / 旧 shell resource を削除
Step D: docs/01, docs/03, docs/05 を canonical 実装 1 本に更新
```

### 2.4 ローカル完結スコープ (まず取りかかる範囲)

> **Wave 1 のコード変更はすべてローカル完結で書ける**。実 GCP 通信を伴う検証は Wave 2 で provision された後にまとめて行う。Wave 1 の受け入れ条件 (`make check` / `make check-layers` / unit test / in-memory fake 経由の `/search`) はすべて GCP 認証無しで成立する。

| PR | コード作業 | ローカル検証 | GCP 必要な部分 (Wave 2 で実施) |
|---|---|---|---|
| PR-1 SemanticSearch | adapter / settings / composition / fake / unit test の追加 — 全てローカル可 | `SEMANTIC_BACKEND=vertex_vector_search` + in-memory fake で `/search` 200 / mock で `find_neighbors` を呼ぶ unit test | live `aiplatform.MatchingEngineIndexEndpoint.find_neighbors` smoke (Wave 2 で `VERTEX_VECTOR_SEARCH_INDEX_ENDPOINT_ID` 投入後) |
| PR-2 FeatureFetcher | Port / 2 adapter / fake / `ranking.py` 改修 — 全てローカル可 | `FEATURE_FETCHER_BACKEND=online_store` + fake fetcher で ranking 動作 | live `FeatureOnlineStoreServiceClient.fetch_feature_values` smoke |
| PR-3 VectorSearchWriter | Port / 2 adapter / pipeline component 改修 — 全てローカル可 | `pipeline/data_job/main.py` を fake adapter (BQ も fake) で完走 | live `MatchingEngineIndex.upsert_datapoints` smoke + 初回 backfill |
| PR-4 Feature Store integration | adapter / settings / manifest env 追加 — 全てローカル可 (manifest apply は Wave 2) | unit test で fresh feature merge を確認 | live search-api 経路での Feature View 参照 smoke |

**ローカル開発前提**:

- Python 3.12 + `uv sync` で全依存解決済 (`google-cloud-aiplatform` は `pyproject.toml` に既存)
- `gcloud auth application-default login` は **不要** (mock / fake で完結)
- Docker 不要 (Meilisearch / Vertex SDK 通信は fake で stub)
- `make check` (ruff / format / mypy / pytest) は WSL ローカルで完走する前提

**ローカル完結の境界線**:

- `app/services/adapters/vertex_vector_search_semantic_search.py` の中身で Vertex SDK を import するのは OK。**実通信せず**、unit test で SDK call を mock して PASS させる
- `tests/integration/parity/` 配下の "live GCP 比較" テストは Wave 2 まで `pytest -m 'not live_gcp'` でスキップ可能なよう marker を付与する
- Wave 1 で導入した切替 env は **最終的に削除する**。教育コードでは「default off のまま残す」は許容しない

---

## 3. Wave 1 — 検索アプリ層 (本 roadmap の主タスク)

### 3.1 PR-1: `SemanticSearch` Port — Vertex Vector Search adapter [ローカル完結 ✓ / **実装済 ✅ 2026-05-01**]

**目的**: ME5 で encode したクエリベクトルを Vertex AI Vector Search の match endpoint に投げ、候補 (property_id + score) を返す経路を Port/Adapter で追加。BQ adapter は据え置き。**コードと unit/integration test までローカル完結。live GCP smoke は Wave 2。**

**実装結果 (2026-05-01)**:

- `app/services/adapters/vertex_vector_search_semantic_search.py` 新規 — `endpoint_factory` 注入 seam で SDK 未 import 完結
- `app/services/adapters/__init__.py` に export 追加
- `app/settings/api.py` に `semantic_backend: Literal["bq", "vertex_vector_search"] = "bq"` + `vertex_vector_search_index_endpoint_id` / `_deployed_index_id` フィールド追加
- `app/container/search.py` に `_resolve_semantic_search()` 追加 + `build_candidate_retriever` で wire
- `tests/unit/app/test_vertex_vector_search_semantic_search.py` 11 tests + `test_search_builder_semantic_backend.py` 6 tests = **17 tests PASS**
- mypy / ruff / format clean (PR-1 関連ファイル単体)
- 既存 `tests/_fakes/in_memory_semantic_search.py` を再利用 (新規 fake 不要だった)

**実装上の plan からの乖離**:

- 計画では `app/services/noop_adapters/in_memory_semantic_search.py` を新規追加予定 → 既存 `tests/_fakes/in_memory_semantic_search.py` で充足のため新規追加せず
- 計画の `tests/integration/parity/test_semantic_backend_parity.py` (live 比較) は Wave 2 用なので未追加
- 計画の `scripts/ci/layers.py` 更新: 既存 RULES が directory-level で吸収するため明示的更新不要だった
- `env/.env.example` ファイルは存在しないため未追加 (`env/config/setting.yaml` 流儀に合わせる)

**ファイル一覧**:

| 操作 | パス | 役割 |
|---|---|---|
| 新規 | `app/services/adapters/vertex_vector_search_semantic_search.py` | `aiplatform.MatchingEngineIndexEndpoint.find_neighbors()` を叩く adapter |
| 削除予定 | `app/services/adapters/bigquery_semantic_search.py` | Wave 1 暫定 fallback。Phase 7 canonical 化後に撤去 |
| 維持 | `app/services/protocols/semantic_search.py` | Port 定義は不変 (interface 同形なら既存で吸収) |
| 編集 | `app/composition_root.py` (or `app/container/search.py`) | `SEMANTIC_BACKEND` 環境変数で adapter 注入分岐 |
| 編集 | `app/settings/settings.py` | `semantic_backend` を暫定導入。Wave 2 の live 検証後に削除対象 |
| 新規 | `app/services/noop_adapters/in_memory_semantic_search.py` | テスト / ローカル開発用 fake (任意の固定 candidate を返す) |
| 新規 | `tests/unit/services/test_vertex_vector_search_semantic_search.py` | adapter 単体 (Vertex SDK は mock) |
| 新規 | `tests/integration/parity/test_semantic_backend_parity.py` | 同一クエリで BQ adapter と VVS adapter の上位 K が極端にズレないことを検証 (許容差は文書化) |
| 編集 | `scripts/ci/layers.py` の RULES | 新 adapter のレイヤ境界を追加 |

**設計メモ**:

- Vertex Vector Search の `find_neighbors` は `(neighbor_id, distance)` を返す。Port が要求する `SemanticResult(property_id, score, rank)` に合わせて変換する mapper をこの adapter 内に持つ
- `embedding_dim` は 768 (`ml/common/config/embedding.py`) で固定、index 作成時とランタイムで一致を保証
- 失敗時に旧 backend へ逃がさない。live 検証完了後は backend 切替自体を削除する
- 認証は ADC (Cloud Run / GKE の Workload Identity 経由)、ローカルは `gcloud auth application-default login`

**受け入れ条件**:

ローカル (PR merge 時に必須):
- [x] `make lint` (ruff check) PASS
- [x] `make fmt-check` (ruff format) PASS
- [x] PR-1 関連ファイル単体 mypy clean
- [x] PR-1 関連 17 tests PASS
- [x] in-memory fake 経由で `/search` adapter selection が分岐 (composition wiring test)
- [x] mock で Vertex SDK call (`find_neighbors`) を stub した unit test PASS
- [x] 既存 `tests/unit/app/test_api_contract_template.py` 不変
- [ ] `SEMANTIC_BACKEND=vertex_vector_search` を `env/.env.example` に追記 (該当ファイル無のため skip。`env/config/setting.yaml` 流儀)
- [ ] `make check-layers` PASS (DIRECTORY_RULES で吸収を確認、明示更新不要)

GCP smoke (Wave 2 で実施):
- [ ] live `MatchingEngineIndexEndpoint.find_neighbors` 経由で `/search` 200
- [ ] `tests/integration/parity/test_semantic_backend_parity.py` の live 比較 PASS

---

### 3.2 PR-2: `FeatureFetcher` Port — Feature Online Store adapter [ローカル完結 ✓ / **実装済 ✅ 2026-05-01**]

**目的**: rerank 入力 feature を Feature Online Store から取得する経路を Port/Adapter として用意。training-serving skew 防止 (Phase 5 必須要素を Phase 7 でも維持)。

**実装結果 (2026-05-01)**:

- `app/services/protocols/feature_fetcher.py` 新規 — Port + `FeatureRow` value object (`ctr` / `fav_rate` / `inquiry_rate` の 3 軸、`property_features_daily` の動的 feature と一致)
- `app/services/adapters/bigquery_feature_fetcher.py` 新規 — `property_features_daily` の latest event_date scan
- `app/services/adapters/feature_online_store_fetcher.py` 新規 — Vertex AI v1beta1 SDK lazy import + `endpoint_resolver` / `client_factory` 注入 seam
- `tests/_fakes/in_memory_feature_fetcher.py` 新規 — call 記録機能付き
- `app/settings/api.py` に `feature_fetcher_backend` + `vertex_feature_online_store_id` / `vertex_feature_view_id` / `vertex_feature_online_store_endpoint` 追加
- `app/container/search.py` に `resolve_feature_fetcher()` 追加 (public method、PR-4 が Container 配線で消費)
- `tests/unit/app/test_feature_fetcher_adapters.py` 11 tests + `test_feature_fetcher_wiring.py` 7 tests = **18 tests PASS**

**実装上の plan からの乖離**:

- 計画では PR-2 で `app/services/ranking.py` を改修して `FeatureFetcher` を直接呼ぶ予定だった → アーキテクチャ調査の結果、ranking.py からは `candidate.property_features` を読むだけで feature 取得は `BigQueryCandidateRetriever._enrich_from_bq` で完了している判明。**FeatureFetcher の Container 配線と consumption は PR-4 にまとめて実施**
- 計画の `tests/integration/parity/test_feature_fetcher_parity.py` (BQ vs FOS の値比較) は live GCP が必要なため Wave 2 用に skip
- PR-2 merge 段階では Container に未配線だったが、教育コードの完成条件は **未配線維持ではなく旧 BQ 経路の撤去** とする

**ファイル一覧**:

| 操作 | パス | 役割 |
|---|---|---|
| 新規 | `app/services/protocols/feature_fetcher.py` | `class FeatureFetcher(Protocol): def fetch(self, property_ids: list[str]) -> dict[str, FeatureRow]` |
| 新規 | `app/services/adapters/feature_online_store_fetcher.py` | Vertex AI SDK `FeatureOnlineStoreServiceClient.fetch_feature_values` |
| 削除予定 | `app/services/adapters/bigquery_feature_fetcher.py` | Wave 1 暫定 fallback。Phase 7 canonical 化後に撤去 |
| 新規 | `app/services/noop_adapters/in_memory_feature_fetcher.py` | fake (固定 feature を返す) |
| 編集 | `app/services/ranking.py` | feature 取得を直書きから `FeatureFetcher` Port 経由に変更 |
| 編集 | `app/composition_root.py` | `FEATURE_FETCHER_BACKEND` による暫定切替を導入。Wave 2 後に削除対象 |
| 編集 | `app/settings/settings.py` | `feature_fetcher_backend` を暫定導入。Wave 2 の live 検証後に削除対象 |
| 新規 | `tests/unit/services/test_feature_online_store_fetcher.py` | adapter 単体 |
| 新規 | `tests/integration/parity/test_feature_fetcher_parity.py` | bq fetcher と online store fetcher の取得値が一致 (training-serving skew チェック) |

**受け入れ条件**:

ローカル (PR merge 時に必須):
- [x] `make lint` (ruff check) PASS
- [x] `make fmt-check` PASS
- [x] PR-2 関連ファイル単体 mypy clean
- [x] PR-2 関連 18 tests PASS
- [x] in-memory fake fetcher が `FeatureFetcher` Port を充足することを test で確認
- [x] feature parity invariant 6 ファイル ([`pipeline/data_job/dataform/features/property_features_daily.sqlx`](../pipeline/data_job/dataform/features/property_features_daily.sqlx) etc.) は不変
- [ ] `make check-layers` PASS (DIRECTORY_RULES 吸収を確認、明示更新不要)

GCP smoke (Wave 2 で実施):
- [ ] live `FeatureOnlineStoreServiceClient.fetch_feature_values` 経由で ranking 動作
- [ ] `tests/integration/parity/test_feature_fetcher_parity.py` の live skew check PASS

---

### 3.3 PR-3: `VectorSearchWriter` Port — embed pipeline の二重書き [ローカル完結 ✓ / **実装済 ✅ 2026-05-01**]

**目的**: `embed_pipeline` が BQ embedding テーブルを書いた後、同じ embedding を Vertex Vector Search index に upsert する経路を追加。BQ は正本、Vertex Vector Search は serving index。

**実装結果 (2026-05-01)**:

- `pipeline/data_job/ports/vector_search_writer.py` 新規 — `VectorSearchWriter` Port + `EmbeddingDatapoint` value object
- `pipeline/data_job/adapters/vertex_vector_search_writer.py` 新規 — `MatchingEngineIndex.upsert_datapoints` lazy import + chunking (default 500/batch)
- `pipeline/data_job/adapters/in_memory_vector_search_writer.py` 新規 — idempotent in-memory writer + call recorder
- `pipeline/data_job/components/upsert_vector_search.py` 新規 — KFP component (manifest emit 型、`write_embeddings` と同パターン)
- `pipeline/data_job/main.py` 編集 — DAG に component 組み込み + `enable_vector_search_upsert` / `vector_search_index_resource_name` / `vector_search_upsert_batch_size` parameters 追加
- `tests/unit/pipeline/test_vector_search_writer.py` 12 tests + `test_data_job_dag_wiring.py` 5 tests = **17 tests PASS**

**実装上の plan からの乖離**:

- 計画では `dsl.If(enable_vector_search_upsert == True, ...)` で DAG 内 conditional 配置 → KFP 2.16 で `dsl.If` の version 互換性が fragile だったため、**「常に component を含める + runner 側 manifest を見て no-op」方針に変更**。`vector_search_index_resource_name == ""` で gate
- 計画の wiring test (`from pipeline.data_job import main` で signature 確認) が KFP 2.16 の **pre-existing import 失敗** で動かないことが判明 (HEAD でも再現)。**text-based 静的検証** (main.py を文字列として grep) に変更、テスト docstring に理由明記
- 計画の `ml/data/loaders/vector_search_upserter.py` は不要だった (adapter 内で完結)
- 初回 backfill `scripts/setup/backfill_vector_search_index.py` は予定通り Wave 2 へ

**ファイル一覧**:

| 操作 | パス | 役割 |
|---|---|---|
| 新規 | `pipeline/data_job/ports/vector_search_writer.py` | Port: `def upsert(rows: list[EmbeddingRow]) -> None` |
| 新規 | `pipeline/data_job/adapters/vertex_vector_search_writer.py` | `aiplatform.MatchingEngineIndex.upsert_datapoints` を呼ぶ adapter |
| 新規 | `pipeline/data_job/adapters/in_memory_vector_search_writer.py` | local fake |
| 編集 | `pipeline/data_job/components/` 内の embed コンポーネント | BQ MERGE の後段に upsert step を追加 (失敗しても BQ 側を巻き戻さない、観測可能性を持たせる) |
| 編集 | `pipeline/data_job/main.py` | DAG の wiring に upsert step を組み込み、`ENABLE_VECTOR_SEARCH_UPSERT` flag で skip 可能 |
| 新規 | `ml/data/loaders/vector_search_upserter.py` (任意) | low-level クライアント wrapper を ml 共通層に置く |
| 新規 | `tests/unit/pipeline/test_vector_search_writer.py` | fake で upsert が呼ばれることを検証 |

**設計メモ**:

- BQ MERGE と Vertex Vector Search upsert は **別トランザクション**。一方が失敗しても他方は完了する (eventual consistency 設計、観測可能性は Cloud Logging の構造化ログで担保)
- Vertex Vector Search index の build / refresh は本番では batch update を推奨。streaming update は cost が大きい
- 初回 backfill は別スクリプト (`scripts/setup/backfill_vector_search_index.py`) を Wave 2 で追加 — Wave 1 では DAG への組み込みのみ

**受け入れ条件**:

ローカル (PR merge 時に必須):
- [x] `make lint` (ruff check) PASS
- [x] `make fmt-check` PASS
- [x] PR-3 関連ファイル単体 mypy clean
- [x] PR-3 関連 17 tests PASS
- [x] `vector_search_index_resource_name=""` で no-op gate されることを test で確認
- [x] mock で `MatchingEngineIndex.upsert_datapoints` を stub した unit test PASS
- [x] DAG signature の暫定 gate (`enable_vector_search_upsert=False` 等) を text 検証
- [ ] `pipeline/data_job/main.py` を fake で完走 — KFP 2.16 import 不可のため **deferred**: text wiring test で代替 (上記乖離参照)

GCP smoke (Wave 2 で実施):
- [ ] live `MatchingEngineIndex.upsert_datapoints` で実 index に書き込み
- [ ] BQ MERGE と VVS upsert が同一 run で eventual に整合 (Cloud Logging 観測)
- [ ] KFP 2.16 import 互換 issue の根本対処 (別 issue 化推奨、PR-3 の text test はあくまで暫定)

---

### 3.4 PR-4: Feature Online Store 統合 (Phase 7 固有) [ローカル完結 ✓ / **実装済 ✅ 2026-05-01** — manifest apply のみ Wave 2]

**目的**: search-api が rerank 直前に Feature Online Store から feature を引く経路を追加し、旧 BQ enrich 依存を撤去する準備を整える。Wave 1 は live 前提を外した実装まで、完成条件は Wave 2 後の旧経路削除。

**実装結果 (2026-05-01)**:

- `app/services/ranking.py` 編集 — `_augment_with_fresh_features(candidates, fetcher)` ヘルパ追加 + `run_search` に `feature_fetcher: FeatureFetcher | None = None` パラメータ追加。fetch 失敗時は `logger.exception` + BQ-enriched 値で rerank 続行 (503 にしない)
- `app/services/search_service.py` 編集 — `__init__` で `feature_fetcher` 受取 → `run_search` に pass-through
- `app/composition_root.py` 編集 — `Container.feature_fetcher: FeatureFetcher | None` field 追加 + `ContainerBuilder.build` で `SearchBuilder.resolve_feature_fetcher()` の戻り値を SearchService に注入
- `tests/conftest.py` 編集 — `fake_container_factory` の defaults に `feature_fetcher: None` 追加 + SearchService 構築で渡す
- `tests/unit/app/test_run_search_feature_fetcher.py` 新規 — **11 tests PASS** (helper unit / run_search integration / Container wiring / signature 確認)

**実装上の plan からの乖離 (=> 設計改善)**:

- 計画では `app/services/adapters/kserve_reranker.py` を編集して predict 前に FeatureFetcher を呼ぶ予定 → アーキテクチャ調査で `KServeReranker.predict(instances)` は **既に build 済み feature 行列**を受け取る設計と判明。FOS merge は **特徴 fetch のレイヤ (= ranking.py の `_build_feature_matrix` 直前)** で行う方が責務分担として正しい。**`KServeReranker` は完全に touch せず**、ranking.py / SearchService / Container の 3 層で merge を完成
- 計画段階の旧 env 案は廃止 → PR-2 で導入した `FEATURE_FETCHER_BACKEND=online_store` + `vertex_feature_online_store_*` group で統一 (重複なし)
- 計画の `infra/manifests/kserve/reranker.yaml` env vehicle 追加は **Wave 2 と一緒に扱う方針**に変更 (manifest apply タイミングと一致させる方が安全)
- 計画の `tests/integration/test_kserve_reranker_with_online_store.py` (live KServe pod 検証) は Wave 2 用なので未追加 (代わりに run_search レベルの integration test で merge 経路を確認)

**ファイル一覧**:

| 操作 | パス | 役割 |
|---|---|---|
| 編集 | `app/services/adapters/kserve_reranker.py` | predict 前に `FeatureFetcher` を呼ぶ (Wave 1 では `FEATURE_FETCHER_BACKEND=online_store` group で暫定制御) |
| 編集 | `app/composition_root.py` | KServe reranker に対して FeatureOnlineStoreFetcher を注入する分岐 |
| 編集 | `app/settings/settings.py` | `kserve_feature_online_url: str | None = None` を追加 |
| 編集 | `infra/manifests/kserve/reranker.yaml` (Wave 2 寄りだが env だけ Wave 1 で追加可) | env 変数の vehicle を用意 |
| 新規 | `tests/integration/test_kserve_reranker_with_online_store.py` | 暫定制御あり / なしそれぞれで分岐確認 |

**受け入れ条件**:

ローカル (PR merge 時に必須):
- [x] `make lint` (ruff check) PASS
- [x] `make fmt-check` PASS
- [x] PR-4 関連ファイル単体 mypy clean (search_service.py の pre-existing 負債は別件)
- [x] PR-4 関連 11 tests PASS
- [x] default (`feature_fetcher=None`) で挙動変わらず (test で `fetcher.calls == []` を確認)
- [x] 設定時のみ FOS の fetch 経路に分岐 (test で `fetcher.calls == [["p001"]]` + matrix の 4/5/6 列が FOS-fresh 値)
- [x] FOS が落ちても `/search` は 503 にならず BQ-enriched 値で続行 (test で確認)
- [ ] `infra/manifests/kserve/reranker.yaml` env vehicle 追加 — **Wave 2 へ deferred** (manifest apply とまとめる方針)

GCP smoke (Wave 2 で実施):
- [ ] live KServe pod (というより search-api pod) に env 注入 → 実 Feature Online Store fetch 経路で `/search` 200
- [ ] env 未設定で従来挙動 (cluster 上で確認)

---

### 3.5 全 PR 共通: composition root + settings + env 取り扱い (Wave 1 実装後)

| 環境変数 | 値域 | default | 影響 | 実装 PR |
|---|---|---|---|---|
| `SEMANTIC_BACKEND` | `bq` / `vertex_vector_search` | `bq` | semantic 検索 adapter 切替 | PR-1 ✅ |
| `VERTEX_VECTOR_SEARCH_INDEX_ENDPOINT_ID` | string | `""` | VVS adapter が参照する Index Endpoint ID (Wave 2 で provision) | PR-1 ✅ |
| `VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID` | string | `""` | VVS adapter の `deployed_index_id` (Wave 2 で provision) | PR-1 ✅ |
| `FEATURE_FETCHER_BACKEND` | `bq` / `online_store` | `bq` | rerank 用 feature 取得 adapter 切替 | PR-2 ✅ |
| `VERTEX_FEATURE_ONLINE_STORE_ID` | string | `""` | FOS adapter が参照する store ID (Wave 2 で provision) | PR-2 ✅ |
| `VERTEX_FEATURE_VIEW_ID` | string | `""` | FOS adapter が参照する view ID (Wave 2 で provision) | PR-2 ✅ |
| `VERTEX_FEATURE_ONLINE_STORE_ENDPOINT` | string | `""` | FOS regional public endpoint (Wave 2 で Admin API 経由 lookup) | PR-2 ✅ |
| (KFP pipeline param) `vector_search_index_resource_name` | string | `""` | embed pipeline の VVS upsert gate (空なら no-op) | PR-3 ✅ |
| (KFP pipeline param) `enable_vector_search_upsert` | bool | `false` | manifest メタデータに乗る gate (Cloud Function runner で消費予定) | PR-3 ✅ |
| (KFP pipeline param) `vector_search_upsert_batch_size` | int | `500` | upsert chunk size | PR-3 ✅ |

**変更**: 計画段階の旧 env 案 / `ENABLE_VECTOR_SEARCH_UPSERT` は廃止。FOS は `FEATURE_FETCHER_BACKEND` group で統一、VVS upsert は KFP pipeline parameter として表現 (env で gate しない設計に変更)。

`infra/manifests/search-api/configmap.example.yaml` への env 反映は **Wave 2 (manifest apply とまとめる)** に deferred。

---

## 4. Wave 2 — GCP インフラ層 (Wave 1 完了後 = 着手可能、**クラウド側の主作業計画**)

> **Wave 1 のローカル完結が完了したので、Wave 2 は GCP リソース provision に集中できる。**
> Wave 1 の検証残課題 (live GCP smoke、KFP 2.16 互換 issue) もここで吸収する。
>
> **位置付け**: 本セクションは **クラウド側 (GCP インフラ) の修正作業計画の母艦**。親 [`README.md`](../../../../README.md) は教育設計、本 phase [`docs/01_仕様と設計.md`](../architecture/01_仕様と設計.md) は仕様 canonical、本セクションが **「いつ何を Terraform / kubectl / gcloud で叩くか」の作業計画** を持つ。

### 4.0 Wave 2 実施順序 (時系列俯瞰)

GCP リソースの依存関係に従って以下の順序で進める。各 step は前段が完了するまで開始できない:

| Step | スコープ | サブセクション | 依存 | 観測される変化 |
|---|---|---|---|---|
| **W2-1** | Vertex Vector Search Terraform 実装 + apply | §4.1 | — | Index endpoint provision、index ID 出力 |
| **W2-2** | Feature Online Store default flip (`enable_feature_online_store=true`) + Feature View provision | §4.1 | — | Feature View ID 取得、regional public endpoint URL 取得 |
| **W2-3** | IAM / Workload Identity bind (KServe SA + Pipeline SA に Vertex Vector Search query / Feature View read 権限) | §4.2 | W2-1 / W2-2 | search-api / KServe pod が VVS / FOS に access 可能に |
| **W2-4** | Composer 環境継承確認 (Phase 6 で実装済の `module "composer"` を Phase 7 dev へ apply、撤去対象が再導入されていないこと検証) | §4.7 | W2-1 / W2-2 / W2-3 | Composer 環境作成、3 DAG (`daily_feature_refresh` / `retrain_orchestration` / `monitoring_validation`) deploy |
| **W2-5** | Manifest env vehicle 追加 (search-api ConfigMap に暫定 backend 切替 env を追加し、live 検証後に撤去準備) | §4.3 | W2-1 / W2-2 | env 投入準備完了 |
| **W2-6** | 初回 backfill (`scripts/setup/backfill_vector_search_index.py` で `feature_mart.property_embeddings` → VVS index) | §4.4 | W2-1 / W2-3 | VVS index に既存 embedding 投入完了 |
| **W2-7** | smoke 確認 (`/search` が `SEMANTIC_BACKEND=vertex_vector_search` env で 200、live `find_neighbors` 経由) | §4.4 / §4.5 | W2-3 / W2-5 / W2-6 | live GCP smoke PASS、parity test PASS |
| **W2-8** | 互換レイヤ撤去 (backend 切替 env / BQ fallback / legacy alias を削除し、PMLE 4 技術 + Composer-managed BQ monitoring query が canonical 経路で動作確認) | §4.6 | W2-7 + 1 週間 dev 安定 | M6 達成 (search-api / pipeline が canonical 1 経路、本線 retrain は Composer DAG) |
| **W2-9** | 負債解消 (KFP 2.16 互換 / mypy pre-existing 9 件 / parity test live 化) — 並行可 | §4.8 | — | 別 PR で吸収 |

各 step の詳細チェックリストは下記 §4.1〜§4.8 を参照。**Composer は Phase 6 で本線昇格済の `module "composer"` を継承するだけ** (新規実装は Phase 6 側、Phase 7 では `environments/dev/main.tf` で呼ぶのみ — §4.7)。

---

### 4.1 Terraform モジュール / リソース (W2-1 / W2-2)

**新規実装が必要な Terraform**:

- [x] **W2-1**: **`infra/terraform/modules/vector_search/`** を実装 (Wave 1 PR-1 が `app/services/adapters/vertex_vector_search_semantic_search.py` を空 endpoint で先行追加済、本ステップで実 resource を provision)
  - `main.tf` — `google_vertex_ai_index` + `google_vertex_ai_index_endpoint` + `google_vertex_ai_index_endpoint_deployed_index_resource`
  - `variables.tf` — `dimensions = 768` (`ml/common/config/embedding.py` と一致)、`distance_measure = "COSINE_DISTANCE"`、`approximate_neighbors_count` etc.
  - `outputs.tf` — `index_endpoint_id` / `deployed_index_id` / `index_resource_name` を runtime ConfigMap / IAM / pipeline param に伝搬
- [x] **W2-1**: `infra/terraform/environments/dev/main.tf` で `module "vector_search"` を有効化 + 出力を root outputs / search-api ConfigMap / pipeline param へ伝搬

**既存 Terraform の設定変更**:

- [x] **W2-2**: `infra/terraform/modules/vertex/variables.tf::enable_feature_online_store` の default を `true` に変更 (`mlops-dev-a` PDCA 都合は `terraform.tfvars` で override 可)。**Feature View** (`property_features` を source とする View) も同モジュールで provision する実装を追加し、Feature View ID と regional public endpoint URL を outputs に追加 (Wave 1 PR-2 が `vertex_feature_view_id` / `vertex_feature_online_store_endpoint` を settings に予約済)
- [ ] **W2-4**: `infra/terraform/modules/composer/` (**Phase 6 で実装**) を Phase 7 `environments/dev/main.tf` から呼ぶ (新規実装は Phase 6 側、Phase 7 では copy のみ)。詳細 checklist は §4.7

### 4.2 IAM / Workload Identity (W2-3)

Wave 1 の env 切替を活かすには、KServe / search-api / pipeline SA から VVS / FOS / Feature View へ access できる WI bind が必要:

- [x] `infra/terraform/modules/iam/main.tf` の現状確認 — `sa-api` には既に `roles/aiplatform.user` 付与済 ✓、`sa-pipeline` / `sa-pipeline-trigger` も同様 ✓
- [ ] **新規 (W2-3-a)**: search-api KSA (`search/search-api`) → `sa-api` の WI bind が VVS `find_neighbors` / Feature View `fetch_feature_values` 双方を許可していることを確認 (`roles/aiplatform.user` で含意される想定、必要なら `roles/aiplatform.featurestoreUser` 追加)
- [ ] **新規 (W2-3-b)**: KServe encoder / reranker KSA (`kserve-inference/encoder`, `kserve-inference/reranker`) → 専用 GCP SA に WI bind し、Vertex Vector Search query / Feature View read 権限付与。Phase 7 の canonical 経路で Feature View を参照するため
- [ ] **新規 (W2-3-c)**: `sa-pipeline` (embed pipeline) に Vertex Vector Search upsert 権限 (`roles/aiplatform.user` で含意済か `roles/aiplatform.indexUser` が別途必要か Terraform plan で確認)
- [ ] **W2-4 関連**: Composer 環境の SA (Phase 6 で `sa-composer` 等を `infra/terraform/modules/composer/` で定義済) が Vertex AI Pipeline submit / Dataform run / Dataflow launch / BQ monitoring query 実行権限を持つことを Phase 7 環境でも確認 (Phase 6 から継承)

### 4.3 Manifests (W2-5、Wave 1 deferred 含む)

- [x] **W2-5-a**: `infra/manifests/search-api/configmap.example.yaml` に新 env vehicle を追加 — Wave 1 の暫定切替 env。Wave 2 後に削除前提で、現時点では空 placeholder を持つ:
  - `SEMANTIC_BACKEND` (default `bq`)
  - `VERTEX_VECTOR_SEARCH_INDEX_ENDPOINT_ID` / `VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID`
  - `FEATURE_FETCHER_BACKEND` (default `bq`)
  - `VERTEX_FEATURE_ONLINE_STORE_ID` / `VERTEX_FEATURE_VIEW_ID` / `VERTEX_FEATURE_ONLINE_STORE_ENDPOINT`
- [x] **W2-5-b**: `infra/manifests/search-api/deployment.yaml` の env で上記を ConfigMap から参照 (Wave 2 後に削除するまでの暫定配線)
- [x] **W2-5-c**: ConfigMap generator (`scripts/ci/sync_configmap.py`) は Wave 2 キーを再現するところまで追従済。**残タスク**は §4.1 W2-1 / W2-2 の Terraform outputs を `scripts.setup.deploy_all` live overlay へ接続すること
- [x] **PR-4 deferred 解消**: `infra/manifests/kserve/reranker.yaml` の env vehicle は不要 → search-api ConfigMap 経由で完結。原本記述は不要、Wave 1 PR-4 docstring の予告は close

### 4.4 ops スクリプト / one-off (W2-6 / W2-7)

- [x] **W2-6**: `scripts/setup/backfill_vector_search_index.py` (初回 backfill 用 one-off。`feature_mart.property_embeddings` 全行を読み出し → `MatchingEngineIndex.upsert_datapoints` で push、batch size = 500 = Wave 1 PR-3 の `vector_search_upsert_batch_size` default と一致)
- [x] **W2-7-a**: `scripts/ops/vertex/vector_search.py` (smoke 用、`find_neighbors` を直接叩いて top-K を表示)
- [x] **W2-7-b**: `scripts/ops/vertex/feature_group.py` の既存 smoke を `FEATURE_FETCHER_BACKEND=online_store` 切替後の経路 (Feature View 経由) で確認済。search-api ConfigMap も live canonical 値へ flip 済
- [x] **W2-7-c**: `tests/integration/parity/test_semantic_backend_parity.py` (BQ vs VVS 上位 K diff) と `test_feature_fetcher_parity.py` (BQ vs FOS feature 値 diff) の **live GCP marker 付き雛形**を実装済。**残タスク**は Wave 2 live 環境で env を投入して実行・閾値調整すること

### 4.5 deploy / CI 統合 (W2-7)

- [ ] `make deploy-all` の wiring に `module.vector_search` を tf apply 順序へ組み込み (順序: bootstrap → init → WIF → sync-dataform-config → tf-plan → tf apply (vector_search 含む) → deploy-api → deploy-kserve-models)
- [ ] `scripts.deploy.monitor` に vector_search smoke step を追加 (`find_neighbors` を 1 回叩いて 200 確認)
- [x] `make run-all-core` に `ops-vertex-vector-search-smoke` を追加 (PDCA loop で smoke 自動化)
- [x] `make run-all-core` に `ops-vertex-feature-group` を追加 (Feature View fetch を本線へ昇格)
- [x] `make run-all-core` に `ops-train-wait` を追加 (`ops-train-now` submit だけで終わらせず、SUCCEEDED まで待つ)
- [ ] `make composer-deploy-dags` (Phase 6 から継承) が Phase 7 環境でも DAG deploy できることを確認 (§4.7)

### 4.6 互換レイヤ撤去 + canonical 化 (W2-8 = M6 達成)

Wave 1 で導入した backend 切替 env / BQ fallback / legacy alias を撤去し、Phase 7 の実装を 1 経路に収束させる:

- [ ] live で Vertex Vector Search / Feature Online Store / embed pipeline upsert の canonical 経路を 1 週間 dev で動かす (`mlops.ranking_log` の latency / NDCG diff を観測、Cloud Monitoring で alert 設定)
- [ ] `BigQuerySemanticSearch` と `BigQueryFeatureFetcher` を削除し、対応 unit / integration test を Vertex canonical 前提へ更新する
- [ ] `SEMANTIC_BACKEND` / `FEATURE_FETCHER_BACKEND` / related ConfigMap keys を削除し、search-api manifest を canonical 1 経路の設定だけに縮約する
- [ ] embed pipeline の `enable_vector_search_upsert=true` + `vector_search_index_resource_name` を実 index に向けて daily run (Composer DAG `daily_feature_refresh` から submit、§4.7)
- [ ] 本 phase [docs/01_仕様と設計.md](../architecture/01_仕様と設計.md) / [docs/03_実装カタログ.md](../architecture/03_実装カタログ.md) / [docs/05_運用.md](../runbook/05_運用.md) を canonical 実装 1 本に更新する

### 4.7 Cloud Composer 継承確認 (W2-4、Phase 6 起点 → Phase 7 継承)

**Phase 7 では Composer 自体は新規実装しない** — Phase 6 で本線昇格された `infra/terraform/modules/composer/` と 3 DAG (`daily_feature_refresh` / `retrain_orchestration` / `monitoring_validation`) を Phase 7 dev 環境へ apply するだけ。本セクションは「継承して動く」ことの確認チェックリスト:

**継承の confirm**:

- [ ] `infra/terraform/modules/composer/` (**Phase 6 で実装済**) を Phase 7 `environments/dev/main.tf` で `module "composer"` として呼ぶ (Phase 6 からの copy、新規実装なし)
- [ ] Phase 6 で増設した PMLE step が Phase 7 環境でも動作:
  - `daily_feature_refresh` DAG: Dataform run + Feature Store sync + (Phase 6B 増設) Composer-managed BigQuery monitoring query
  - `retrain_orchestration` DAG: Vertex training pipeline submit + (Phase 6B 増設) BQML training / TreeSHAP Explainability eval
  - `monitoring_validation` DAG: skew / drift / SLO + burn-rate (Phase 6B 増設)
- [ ] `pipeline/dags/{daily_feature_refresh,retrain_orchestration,monitoring_validation}.py` を Phase 7 環境へ deploy (`composer-deploy-dags` make target、Phase 6 から継承)

**撤去対象が本線として再導入されていないこと** (CI 検証。infra リソース自体は軽量代替 / smoke 用途で残置可、本線 trigger からは外れていること):

- [ ] Cloud Scheduler `check-retrain-daily` が本線 retrain trigger になっていない (Phase 6 で本線から外し済を継承)
- [ ] Eventarc `retrain-to-pipeline` が本線 trigger になっていない
- [ ] Cloud Function (Gen2) `pipeline-trigger` が本線 trigger になっていない
- [ ] Vertex `PipelineJobSchedule` resource が残っていない (これだけは Phase 6 で完全撤去)
- [ ] `/jobs/check-retrain` HTTP endpoint は API smoke / manual trigger 専用に格下げ済 (本線スケジューラから外れている) ことを smoke で確認

**live smoke**:

- [ ] Composer DAG が本線として Vertex Pipelines を submit できる (live smoke)
- [ ] Composer DAG から VVS upsert (Wave 1 PR-3 の `enable_vector_search_upsert=true`) を実 index に向けて daily run

### 4.8 Wave 1 由来の負債解消 (W2-9、並行可)

Wave 2 本線と並行で別 PR にて吸収可:

- [ ] **KFP 2.16 互換 issue**: `pipeline.data_job.main` の `@dsl.pipeline` decorator が KFP 2.16 で TypeError を出す pre-existing 問題 (PR-3 の text wiring test で暫定対処)。根本 fix は KFP version pin or component annotation 修正
- [x] **mypy pre-existing 負債** (PR-1 audit で発見): `app/services/search_service.py` / `app/services/adapters/lexical_search.py` / `app/api/routers/ops_router.py` / `tests/conftest.py` の対象 9 件は解消済
- [x] **`tests/integration/parity/`** に live GCP 比較 test の雛形を追加 (`test_semantic_backend_parity.py` / `test_feature_fetcher_parity.py`、§4.4 W2-7-c と統合)。実行は Wave 2 live 環境で行う

---

## 5. Wave 3 — docs / reference architecture との整合 (確認のみ)

- [ ] 本 phase [docs/01_仕様と設計.md](../architecture/01_仕様と設計.md) §「実案件想定の reference architecture」(Phase 5 docs を参照する旨) が最新であること
- [ ] コードに `Elasticsearch` / `synonym` / `query expansion` 等の固有名が混入していないことを `scripts/ci/layers.py` の禁止語リスト (or grep based check) で守る — 任意の追加チェック
- [ ] [docs/03_実装カタログ.md](../architecture/03_実装カタログ.md) と [docs/05_運用.md](../runbook/05_運用.md) の「semantic 経路」「feature 取得経路」の記述を Wave 1 / Wave 2 完了に追従して更新

---

## 6. リスクと回避

| 状態 | リスク | 回避 |
|---|---|---|
| ✅ 解消 | 大型 PR になりがち | 1 PR = 1 Port (PR-1 ～ PR-4) で 4 PR に分割。Wave 2 で互換レイヤ削除まで完了させる前提に修正 |
| ⚠ 要解消 | 互換レイヤを完成形と誤認する | Wave 1 の backend 切替・fallback は暫定。M6 の達成条件に **削除** を含め、教育コードとして 1 経路へ収束させる |
| ✅ 解消 | feature parity 6 ファイル更新漏れ | PR-2 / PR-4 ともに `FEATURE_COLS_RANKER` の 3 軸 (ctr / fav_rate / inquiry_rate) を merge する設計で、新規追加の 6 ファイル不変 (parity invariant test を破らない) |
| ⏳ Wave 2 | Vertex Vector Search index の build 時間 | Wave 2 で別ジョブ化。初回は手動 trigger (`scripts/setup/backfill_vector_search_index.py`)、以後 `embed_pipeline` schedule にチェーン (PR-3 の upsert step が daily incremental 担当) |
| ⏳ Wave 2 | Feature Online Store のコスト | コスト都合の toggle を残しても backend 切替や fallback は残さない。必要なら infra 変数側に限定し、app 層の互換レイヤは削除する |
| ⏳ Wave 2 | Vertex Vector Search match endpoint の権限不足で 403 | `sa-api` には `roles/aiplatform.user` 付与済 ✓。KServe encoder/reranker SA への WI bind は Wave 2 §4.2 |
| ⏳ Wave 2 | BQ → VVS の embedding 不整合 | PR-3 の upsert は BQ MERGE と分離 (eventual consistency)。整合性は Wave 2 で `tests/integration/parity/` 追加して検証、観測は Cloud Logging |
| ⚠ 新規 | KFP 2.16 と既存 `data_job.main` の `@dsl.pipeline` validation error (HEAD でも再現) | PR-3 の wiring test を text-based に変更で暫定対処。根本 fix は Wave 2 §4.7 の負債解消で別 PR 化 |

---

## 7. マイルストーン

| ID | フェーズ | 状態 | 完了内容 | 達成日 / 証跡 |
|---|---|---|---|---|
| M1 | ローカル | ✅ | PR-1 merge | 2026-05-01 — `SEMANTIC_BACKEND=vertex_vector_search` で adapter 切替動作、PR-1 17 tests PASS |
| M2 | ローカル | ✅ | PR-2 merge | 2026-05-01 — `FEATURE_FETCHER_BACKEND` group で adapter 切替、PR-2 18 tests PASS (Container 配線は M4 で完成) |
| M3 | ローカル | ✅ | PR-3 merge | 2026-05-01 — embed pipeline DAG に upsert component 追加、PR-3 17 tests PASS |
| M4 | ローカル | ✅ | PR-4 merge | 2026-05-01 — Container/SearchService/run_search 配線完了、`feature_fetcher=None` で挙動不変、PR-4 11 tests PASS |
| **M-Local** | **ローカル完結** | **✅** | **M1〜M4 全 merge** | **2026-05-01 — `make lint` / `make fmt-check` / 関連 mypy / pytest 63 passed**。**ただし教育コードとしては未完成で、Wave 2 の live 検証と互換レイヤ削除が残る** |
| M5 | GCP | ⏳ | Wave 2 完了 | live GCP で `/search` が Vertex Vector Search / Feature Online Store の canonical 経路で動作 |
| M6 | GCP | ⏳ | 互換レイヤ撤去 | backend 切替 env / BQ fallback / legacy alias を削除し、本 phase docs/01 §4 表を canonical 実装 1 本へ更新 |
| M7 | docs | ⏳ | Wave 3 確認 | reference architecture 整合 docs check + コードに固有名混入なし、`docs/03_実装カタログ.md` / `docs/05_運用.md` の semantic / feature 取得経路記述を Wave 1/2 に追従 |

---

## 8. 関連 docs

- 親リポ:
  - [README.md](../../../../README.md) §1 教材対象外 / §3 非負制約 / §4 学習運用
  - [CLAUDE.md](../../../CLAUDE.md) §「非負制約 (Phase 3/4/5/6/7 共通)」
  - [docs/01_仕様と設計.md](../../../../docs/architecture/01_仕様と設計.md) §「ハイブリッド検索の仕様と設計 (Phase 3-7 共通)」
- 本 phase:
  - [README.md](../README.md)
  - [CLAUDE.md](../CLAUDE.md)
  - [docs/01_仕様と設計.md](../architecture/01_仕様と設計.md) §「実案件想定の reference architecture」(Phase 5 を継承)
  - [docs/TASKS_ROADMAP.md](TASKS_ROADMAP.md) Port / Adapter / DI 大枠
  - [docs/decisions/](../decisions/README.md) 過去の制約決定 (ADR 0001〜0008)
- Phase 5 (継承元):
  - [5/study-hybrid-search-vertex/docs/01_仕様と設計.md](../../../../5/study-hybrid-search-vertex/docs/01_仕様と設計.md)
  - [5/study-hybrid-search-vertex/docs/02_移行ロードマップ.md](../../../../5/study-hybrid-search-vertex/docs/02_移行ロードマップ.md)
