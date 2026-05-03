# TASKS.md (Phase 7 — current sprint)

新セッションが「**今 sprint で何をやり、何をやらないか**」を確認する単一エントリ。**実装済み・検証済みの細目は載せない** → [`../architecture/03_実装カタログ.md`](../architecture/03_実装カタログ.md) §「Composer / Wave 2 V5」。

## 本ドキュメントの債務

**書く**: 死守ライン・優先順位、V1–V6 の **今の** status、未完了の次コマンド。  
**書かない**: 検証定義 → [`04_検証.md`](../runbook/04_検証.md)；過去 incident 長文 → [`TASKS_ROADMAP.md`](TASKS_ROADMAP.md)；手順 → [`05_運用.md`](../runbook/05_運用.md)。

権威順位: `TASKS_ROADMAP.md` > `TASKS.md` > `01_仕様と設計.md` > `README.md`。

---

## 🎯 ダッシュボード (sprint 更新)

### 進捗ログ（長時間コマンド・待機ブロック時は **ここを更新**）

**ルール**: Cloud Build / DAG Run / Vertex pipeline 待ちなどで手が止まるたび、直近の **状態・Run ID・次コマンド** を 1〜3 行追記する（ゴール逃げ禁止・事実のみ）。

**⛔ エージェント向け（クレーム級）**: **Composer live を `env/config/setting.yaml` の手編集で直そうとしない** — 正本は **Terraform Composer `env_variables`**。無意味に長い **`sleep` ループ**と、**根拠のない `make build-composer-runner`** も禁止。状況確認は **`make ops-composer-task-states` を短時間・必要最小限**。

| 時点 (UTC) | 状態 | メモ |
|---|---|---|
| 2026-05-03 | **V5 E2E 締め** | Run `manual__2026-05-03T09:18:07+00:00`: `check_retrain` / `submit_train_pipeline` / `wait_train_succeeded` / `gate_auto_promote` **success**、`promote_reranker` **skipped**（`AUTO_PROMOTE=false`）。`make ops-livez` / `make ops-search-components` **緑**（lexical / semantic / rerank）。→ **死守ラインは実測クローズ**。 |
| (参照) | IAM / runner | `sa-composer`→`sa-pipeline` actAs + pipeline-root 書き込み、runner 再ビルド・`[{` JSON 抽出修正などは実装カタログ / 進捗ログ履歴を参照。 |
| **2026-05-03** (JST 夕) | **V4** | `make deploy-all` **exit 0**（全 15 step、step 6 tf-apply ~421s含む・計 ~14.7 min）。ログ `_v4_deploy_all.log`。 |
| **2026-05-03** (JST 夕) | **V6** | `RUN_LIVE_GCP_ACCEPTANCE=1 pytest … -m live_gcp` **FAILED**（計 ~48 min）。`destroy-all` 後の **`deploy-all`** で Vertex **409**（`FeatureGroup` / `FeatureOnlineStore` が **削除中の同名**に再作成しようとした）+ Terraform **Invalid target address**。ログ `_v6_acceptance.log`。 |
| **2026-05-03** (JST 夕) | **V3** | `make destroy-all` **exit 0**（計 ~8 min）。ログ `_v3_destroy_all.log`。 |

**次に実行（V6 再試行・環境復旧）**:

1. **復旧**: 現状 **スタックは teardown 済み寄り**（V6 失敗後に V3 `destroy-all` まで実施）。通常運用に戻すなら **`make deploy-all`** を改めて実行（Vertex の **409** は destroy 直後は **15–60 min** 程度あとで再試行するか、[§4.9 / state_recovery](../tasks/TASKS_ROADMAP.md) に沿って **plan を確認**）。
2. **V6 再試行**: 復旧後かつ Vertex **409** が解消したタイミングで `RUN_LIVE_GCP_ACCEPTANCE=1 pytest tests/e2e/test_phase7_acceptance_gate.py -m live_gcp`。**Invalid target address** は `terraform state list` で該当 `-target` と実 state のズレを確認。

**再検証（Composer E2E だけ繰り返す場合）**: `make composer-deploy-dags` → `make ops-composer-trigger DAG=retrain_orchestration` → **`make ops-composer-task-states`** → `make ops-livez` / `make ops-search-components`。Terraform 単体は `make tf-plan` 経由。

### 死守ライン（クライアント説明の最低条件）

`check_retrain` のみ success **では足りない**（[`04_検証.md` §0 補足](../runbook/04_検証.md)）。**下 checklist 全項目**まで。

- [x] DAG trigger 成功
- [x] 失敗時: Pod log / `airflow-worker` を取得し原因分類（IAM / GCS・`PIPELINE_ROOT_BUCKET` / template path / compile・submit 引数 / runner image）（※今回の締め Run は成功経路のため該当手順は未実施）
- [x] 修正後、同一 Run 追跡または新 trigger
- [x] `check_retrain` **success**
- [x] `submit_train_pipeline` **success**
- [x] `wait_train_succeeded` **success**
- [x] `gate_auto_promote` **期待どおり**（例: `AUTO_PROMOTE=false` なら downstream skip が説明可能）
- [x] `promote_reranker` **success** または **意図どおり skip**
- [x] 再学習後 **`/search` 200**（`make ops-livez` 等）
- [x] **lexical / semantic / rerank** 3 成分が壊れていない（`make ops-search-components`）

### 今の到達度

| ライン | status | 一件コメント |
|---|---|---|
| V1 `deploy-all` | ✅ | 実測 Run 6 |
| V2 `run-all-core` | ✅ | |
| V5 **狭いゲート**（`check_retrain`） | ✅ Run 4 | F1–F5 反映済 |
| V5 **死守 E2E**（上 checklist） | ✅ Run `manual__2026-05-03T09:18:07+00:00` | task states / `ops-livez` / `ops-search-components` まで実測済（上進捗ログ参照） |

### 優先順位（同列にしない）

1. **✅ 死守（完了）** — V5 E2E（上 checklist・2026-05-03 Run で実測クローズ）
2. **✅ V4** — 2 周目 `make deploy-all` **実測済**（2026-05-03 JST 夕）
3. **❌→再試行** — **V6** e2e `live_gcp` は **失敗**（409 + Invalid target）。復旧後に再実行。
4. **✅ V3** — `make destroy-all` **実測済**（同一セッション・exit 0）

### コピー用（対外向け）

**Composer 経由の再学習 E2E**は **2026-05-03 Run** で実測クローズ（`check_retrain`、Vertex Pipeline submit・完走待ち、gate まで成功、`AUTO_PROMOTE=false` で promote は設計どおり skip、再学習後 `/search` 200 と 3 成分疎通確認済み）。**残りは死守ではなく**、**V4（import 経路の再検証）→ V6（parity live_gcp）→ V3（destroy-all）** の順で進める。

---

## 残タスク（チェックボックス）

**インフラ・run-all**: V1・V2 ✅

**死守**: V5 E2E ✅（上 checklist）

**並び順（実行順）**: ~~V5 E2E~~ ✅ → ~~**V4**~~ ✅ → **V6**（要再試行）→ ~~**V3**~~ ✅

## 今回はやらない

中核 5 要素の置換、`/search` 既定変更、教材禁止技術、BQ fallback 系の「残す」運用 — [`TASKS_ROADMAP.md` §2](TASKS_ROADMAP.md) 参照。

## 完了条件（sprint）

- [x] `make check` / `deploy-all` / `run-all-core`
- [x] **死守ライン**（本ファイル checklist 全項目）
- [x] **V4** 2 周目 `deploy-all`（2026-05-03 実測）
- [ ] **V6** e2e `live_gcp`（**未達**・409 / Invalid target → 復旧後に再試行）
- [x] **V3** `destroy-all`（2026-05-03 実測）
- [ ] canonical 経路・parity invariant の完全締め — [`04_検証.md`](../runbook/04_検証.md)

## 参照

**設定と秘密の分離**: `env/README.md`（`setting.yaml` = 非秘密のみ、`credential.yaml` = ローカル秘密）。

| 何を知りたいか | どこ |
|---|---|
| 実装ファイル・F1–F5・Run 履歴・V5-8 | [`03_実装カタログ.md`](../architecture/03_実装カタログ.md)（§ Composer / Wave 2 V5） |
| Wave 計画・§4.x incident | [`TASKS_ROADMAP.md`](TASKS_ROADMAP.md) |
| OK 判定（V1–V6） | [`04_検証.md`](../runbook/04_検証.md) §0 |
| コマンド手順 | [`05_運用.md`](../runbook/05_運用.md) |
