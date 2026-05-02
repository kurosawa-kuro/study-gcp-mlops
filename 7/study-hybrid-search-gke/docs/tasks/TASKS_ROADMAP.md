# 02. 移行ロードマップ — 検索アプリを最新仕様へ

Phase 7 の現コードを、最新仕様 (親 [README.md](../../../../README.md) §1-§3 / 親 [docs/01_仕様と設計.md](../../../../docs/architecture/01_仕様と設計.md) / 本 phase [docs/01_仕様と設計.md](../architecture/01_仕様と設計.md)) に追従させるための移行計画。

> **方針**: **Wave 1 = 検索アプリ自体 (app / ml / pipeline コード)** を先に整える。**Wave 2 = GCP インフラ (Terraform / IAM / deploy)** はその後。Wave 3 は docs / reference architecture との整合確認のみ (コード変更なし)。
>
> Port / Adapter / DI 大枠の整理は [`docs/TASKS_ROADMAP.md`](TASKS_ROADMAP.md)、過去の制約決定は [`docs/decisions/`](../decisions/README.md) を参照。
>
> **教育コード原則**: 後方互換・legacy fallback・旧 env 名 alias・旧 UI redirect・使われない shell resource は残さない。移行の都合で一時導入した互換レイヤも、役目を終えた時点で削除する。

---

## 現在地 (2026-05-03)

停止点:
- Composer DAG smoke の import error 修正待ち
- その後に `run-all-core` / `destroy-all` の最終 re-verify

完了済み実装・検証の正本:
- [`docs/03_実装カタログ.md`](../architecture/03_実装カタログ.md)
- [`docs/05_運用.md`](../runbook/05_運用.md)

### 残り作業

- **DAG import error 修正**: `composer_deploy_dags.py` の upload layout を変更 — `pipeline/__init__.py` + `pipeline/dags/__init__.py` + `pipeline/dags/_common.py` を `pipeline/dags/` 階層保持で upload、DAG ファイルは top-level の `dags/` に置く構造へ
- `make ops-composer-trigger DAG=retrain_orchestration` で SUCCEEDED 確認
- `make run-all-core` PASS 維持確認 (`ndcg_at_10=1.0`)
- 最後の `make destroy-all` (新 stale VVS guard + reserved env contract が live で動作することの検証も兼ねる)
- `tests/integration/parity/*` の `live_gcp` 本実行 (別 session 妥当)

補足:
- 完了条件は `destroy-all -> deploy-all -> composer-deploy-dags -> run-all-core -> destroy-all`
- 実測・恒久対処の詳細は `03_実装カタログ.md` と `05_運用.md` を正本とし、この roadmap には再掲しない

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

## 1. 現状ギャップ

詳細な完了差分は [`docs/03_実装カタログ.md`](../architecture/03_実装カタログ.md) を正本とする。

残ギャップ:
- Composer DAG import layout 修正
- `tests/integration/parity/*` の live 実行
- KFP 2.16 互換 issue の根本対処
- [docs/01_仕様と設計.md](../architecture/01_仕様と設計.md) の最終同期

---

## 2. 移行戦略

### 2.1 暫定互換レイヤの扱い

Wave 1 ではローカル完結のために一時的な backend 切替と fallback を導入したが、**教育コードの完成条件はそれらを削除すること**。`BigQuerySemanticSearch` / `BigQueryFeatureFetcher` / backend 切替 env / legacy alias は Wave 2 の live 検証後に撤去し、Phase 7 の canonical 実装を 1 本に収束させる。

### 2.2 補足

- 実装方針や移行履歴の詳細は `03_実装カタログ.md` を正本とする

---

## 3. Wave 1 — 検索アプリ層 (本 roadmap の主タスク)

残:
- [ ] `tests/integration/parity/test_semantic_backend_parity.py` の live 実行
- [ ] `tests/integration/parity/test_feature_fetcher_parity.py` の live 実行
- [ ] Cloud Logging ベースの eventual consistency 観測
- [ ] KFP 2.16 import 互換 issue の根本対処

---

## 4. Wave 2 — GCP インフラ層 (Wave 1 完了後 = 着手可能、**クラウド側の主作業計画**)

> **Wave 1 のローカル完結が完了したので、Wave 2 は GCP リソース provision に集中できる。**
> Wave 1 の検証残課題 (live GCP smoke、KFP 2.16 互換 issue) もここで吸収する。
>
> **位置付け**: 本セクションは **クラウド側 (GCP インフラ) の修正作業計画の母艦**。親 [`README.md`](../../../../README.md) は教育設計、本 phase [`docs/01_仕様と設計.md`](../architecture/01_仕様と設計.md) は仕様 canonical、本セクションが **「いつ何を Terraform / kubectl / gcloud で叩くか」の作業計画** を持つ。

### 4.0 Wave 2 残タスク

- [ ] Composer DAG import layout 修正
- [ ] `make ops-composer-trigger DAG=retrain_orchestration` で SUCCEEDED 確認
- [ ] `make run-all-core` PASS 維持確認
- [ ] `make destroy-all` の最終 re-verify (新 `prevent_destroy` + `PERSISTENT_VVS_RESOURCES` の live 検証も兼ねる — §4.9 参照)
- [ ] `tests/integration/parity/*` の live 実行

### 4.1 Stage 3.5 未解決

Composer DAG smoke の現状:
- DAG bag 登録: 3 本とも成功
- import errors: なし
- 手動 trigger: 可能
- task SUCCEEDED: 未達

未解決事象:
- `check_retrain` が数秒で fail する
- 真因は、DAG が `BashOperator` で `uv run python -m scripts.ops.X` を呼ぶ設計なのに、Composer worker に `uv` と repo module が存在しないこと

判断待ち:
- `A`: 現状で W2-4 完了とみなし、Stage 3.6 (`run-all-core`) へ進む
- `B`: Composer-native な実行方式へ寄せて、task `SUCCEEDED` まで深追いする

含意:
- `A` は「Composer 環境 provision + DAG 認識 + trigger 成立」までを今回の完了条件にする判断
- `B` は DAG 実装方式の見直しを含むため、別 sprint 級の追加作業になる

### 4.7 Cloud Composer 本実装 (W2-4、Phase 7 = canonical / 引き算で Phase 6 派生)

**Phase 7 で Composer module / 3 DAG / make target / scripts を本実装する** (= 教材コード完成版の到達ゴールに必要な技術が Phase 7 に揃っている前提。引き算チェーン上の Phase 6 論理境界は別 phase 作業で派生させる)。

実装済み内容は [`docs/03_実装カタログ.md`](../architecture/03_実装カタログ.md) を正本とする。

コスト見積もりは [docs/05_運用.md](../runbook/05_運用.md) を正本とする。

### 4.8 Wave 1 由来の負債解消 (W2-9、並行可)

- [ ] KFP 2.16 互換 issue の根本対処
- [ ] `tests/integration/parity/*` の live 実行

### 4.9 VVS 永続化アーキテクチャ — MVP 完了 / 拡張は別 sprint (W2-10)

**背景**: Vertex Vector Search の課金構造は非対称。Index 自体と空の Index Endpoint は **無料** (公式: "Models that are not deployed or have failed to deploy are not charged.")、課金されるのは `deployed_index` (replica 起動状態) のみ。Index build に 5-15 min、Endpoint 作成 + DNS propagation に数分かかるため、PDCA cycle ごとに作り直すと deploy-all 全体の短縮効果が消える。

#### MVP (実装済 ✅、2026-05-03)

シナリオ A の MVP として、現単一 stack 内で同等の動作を実現:

- [`infra/terraform/modules/vector_search/main.tf`](../../infra/terraform/modules/vector_search/main.tf): `google_vertex_ai_index` と `google_vertex_ai_index_endpoint` に `lifecycle { prevent_destroy = true }`。`google_vertex_ai_index_endpoint_deployed_index` (= 課金 resource) は永続化対象外
- [`scripts/setup/destroy_all.py`](../../scripts/setup/destroy_all.py): `PERSISTENT_VVS_RESOURCES` 定数 + step [6/6] で `state_list` 全 addr から persistent prefix を除外して `-target` 指定で destroy
- [`tests/integration/workflow/test_destroy_all_contract.py::test_destroy_all_persists_vvs_index_and_endpoint`](../../tests/integration/workflow/test_destroy_all_contract.py): 永続化契約を offline で pin
- [`docs/runbook/05_運用.md §1.4`](../runbook/05_運用.md): 「残るもの」に Index / Endpoint を追加、deploy-all 短縮効果 (27 min → 10-15 min) を明記

期待効果:

| シナリオ | 従来 | 新 |
|---|---|---|
| 初回 deploy-all | 27-30 min | 27-30 min (Index build 込み) |
| 2 回目以降 deploy-all | 27-30 min | **10-15 min** (deployed_index attach のみ) |
| 維持コスト (放置時) | replica 課金 ¥1,460/日 | **¥0/月** (Index/Endpoint は無料) |

#### 残タスク (Wave 2 / Wave 3 跨ぎ)

- [ ] **Stage 3.7 = live verify** (今 sprint の最終ゲート、§4.0 と重複): `make destroy-all` 実行で、(1) Index / Endpoint が state にも GCP にも残る (2) deployed_index は destroy される (3) 次回 deploy-all で deployed_index のみ create されて時間短縮
- [ ] **Stack 分離 (別 sprint、PR 1-3 相当)**: `infra/terraform/stacks/{persistent,vector_search,core}/` に分離し、`terraform_remote_state` で接続。core stack の destroy で deployed_index のみ消える設計が完成。MVP との違いは「stack 単位で operation 境界が明示」「persistent / vector_search の prevent_destroy が Terraform 側にも構造化される」点
- [ ] **Cloud Scheduler 自動 undeploy (別 sprint、PR 4 相当)**: deployed_index 残置による課金事故防止。4h timeout で強制 undeploy する Cloud Scheduler job
- [ ] **Billing Budget Alert (別 sprint、PR 5 相当)**: 日次 ¥3,000 閾値で notification、加えて監視ダッシュボード

破綻条件 (注意):
- Embedding model のバージョン変更 (次元 / 分布変更) → Index 再 build 必要 (27 min の出戻り)
- Vector Search の major upgrade → 構造変更で移行作業発生
- 数ヶ月放置時の Google 側 GC (公式に未明記、念の為 monthly health check 推奨)
- **deployed_index 残置が最大リスク** (1 replica = ¥1,460/日 = ¥44,000/月) → Cloud Scheduler 自動 undeploy が後続 sprint で必須

---

## 5. Wave 3 — docs / reference architecture との整合 (確認のみ)

- [ ] 本 phase [docs/01_仕様と設計.md](../architecture/01_仕様と設計.md) §「実案件想定の reference architecture」(Phase 5 docs を参照する旨) が最新であること — W2-8 削除と同期して再確認 (canonical 1 経路化後)
- [ ] コードに `Elasticsearch` / `synonym` / `query expansion` 等の固有名が混入していないことを `scripts/ci/layers.py` の禁止語リスト (or grep based check) で守る — 任意の追加チェック (現状コード grep では hit 無しを 2026-05-02 終端で確認)
- [x] [docs/05_運用.md](../runbook/05_運用.md) の「semantic 経路」「feature 取得経路」記述は更新済

---

## 6. リスクと回避

| 状態 | リスク | 回避 |
|---|---|---|
| ⚠ 残存 | Composer DAG import layout | upload layout 修正後に DAG smoke を再実行 |
| ⚠ 残存 | KFP 2.16 互換 issue | `scripts.ops.train_now` で暫定回避、根本 fix は別 PR |
| ⏳ Wave 2 | Feature Online Store のコスト | `make destroy-all` 運用を維持 |

---

## 7. マイルストーン

| ID | フェーズ | 状態 | メモ |
|---|---|---|---|
| M-Local | ローカル | ✅ | 詳細は `03_実装カタログ.md` を参照 |
| M-GCP | GCP | ⏳ | Composer DAG smoke 修正と最終 re-verify が残り |
| M-Docs | docs | ⏳ | `01_仕様と設計.md` の最終同期が残り |

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
