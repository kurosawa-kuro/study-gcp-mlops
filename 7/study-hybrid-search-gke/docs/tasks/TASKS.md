# TASKS.md (Phase 7 — current sprint)

新セッションが「**今 sprint で何をやり、何をやらないか**」を確認する単一エントリ。**実装済み・検証済みの細目は載せない** → [`../architecture/03_実装カタログ.md`](../architecture/03_実装カタログ.md) §「Composer / Wave 2 V5」。

## 本ドキュメントの債務

**書く**: 死守ライン・優先順位、V1–V6 の **今の** status、未完了の次コマンド。  
**書かない**: 検証定義 → [`04_検証.md`](../runbook/04_検証.md)；過去 incident 長文 → [`TASKS_ROADMAP.md`](TASKS_ROADMAP.md)；手順 → [`05_運用.md`](../runbook/05_運用.md)。

権威順位: `TASKS_ROADMAP.md` > `TASKS.md` > `01_仕様と設計.md` > `README.md`。

---

## 🎯 ダッシュボード (2026-05-03)

### 進捗ログ（長時間コマンド・待機ブロック時は **ここを更新**）

**ルール**: Cloud Build / DAG Run / Vertex pipeline 待ちなどで手が止まるたび、直近の **状態・Run ID・次コマンド** を 1〜3 行追記する（ゴール逃げ禁止・事実のみ）。

**⛔ エージェント向け（クレーム級）**: **死守・Composer live を `env/config/setting.yaml` の手編集で直そうとしない** — 正本は **Terraform Composer `env_variables`**。無意味に長い **`sleep` ループ**と、**根拠のない `make build-composer-runner`** も禁止。状況確認は **`make ops-composer-task-states` を短時間・必要最小限**。

| 時点 (UTC) | 状態 | メモ |
|---|---|---|
| 2026-05-03 | runner | `make build-composer-runner` **SUCCESS**（Cloud Build ~217s）・`:latest` 付与ログ確認済 |
| 2026-05-03 | DAG | `make composer-deploy-dags` 実施済（GCS upload OK） |
| 2026-05-03 | IAM | `submit_train_pipeline` 失敗の一因を **actAs 不足** と特定。live: `sa-composer` に `sa-pipeline` への `roles/iam.serviceAccountUser` + `pipeline-root` の `objectAdmin` を付与済（Terraform にも同内容をコード化済） |
| 2026-05-03 | trigger | `manual__2026-05-03T08:13:47+00:00` で再 trigger。**タスク完走までの states 確定はポーリング中断のため未クローズ** |
| 2026-05-04 | build | `make build-composer-runner` が **ユーザー中断**（完走ログ未取得）— 直前ビルドが新しい場合はスキップ可 |
| 2026-05-04 | ツール | `gcloud ...` 直 pipe + `json.loads` は **プロローグの `Executing the command: [ ... ]` で壊れる** → `make ops-composer-task-states` / `scripts.ops.composer_task_states` で **`[{` から** JSON 抽出（数万 ms で完了する想定） |
| 2026-05-03 | **E2E 締め** | Run `manual__2026-05-03T09:18:07+00:00`: `check_retrain` / `submit_train_pipeline` / `wait_train_succeeded` / `gate_auto_promote` **success**、`promote_reranker` **skipped**。runner 再ビルド **SUCCESS**（Cloud Build ~188s）。`make ops-livez` → `{"status":"ok"}`、`make ops-search-components` **exit 0**（lexical/semantic/rerank 非ゼロ）。 |

**次に実行（コピペ）**: 再検証時は `make composer-deploy-dags` → `make ops-composer-trigger DAG=retrain_orchestration` → **`make ops-composer-task-states`** → 緑なら `make ops-livez` / `make ops-search-components`。Terraform 単体実行時は `env/config/setting.yaml` の `oncall_email` を参照するか `make tf-plan` 経由にする。

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

1. **🔴 死守** — V5 E2E（上 checklist）
2. **🟡 準死守** — V4 2 周目 `deploy-all`（import 経路）
3. **🟢 余力** — V6 `parity` live_gcp
4. **⚪ 最後** — V3 `destroy-all`（破壊的・報告では後ろ）

### コピー用（対外向け）

Composer と `check_retrain` は成功済み。**ML 検索アプリとしての再学習 E2E**（Vertex submit・wait・gate/promote・再学習後 `/search`）は死守として **2026-05-03 Run で実測クローズ**。V4 / V6 / V3 は順位を付けて実施。

---

## 残タスク（チェックボックス）

**インフラ・run-all**: V1・V2 ✅

**死守**: V5 E2E ✅（上 checklist）

**並び順**: V5 E2E → V4 → V6 → V3

## 今回はやらない

中核 5 要素の置換、`/search` 既定変更、教材禁止技術、BQ fallback 系の「残す」運用 — [`TASKS_ROADMAP.md` §2](TASKS_ROADMAP.md) 参照。

## 完了条件（sprint）

- [x] `make check` / `deploy-all` / `run-all-core`
- [x] **死守ライン**（本ファイル checklist 全項目）
- [ ] canonical 経路・parity invariant — [`04_検証.md`](../runbook/04_検証.md)

## 参照

**設定と秘密の分離**: `env/README.md`（`setting.yaml` = 非秘密のみ、`credential.yaml` = ローカル秘密）。

| 何を知りたいか | どこ |
|---|---|
| 実装ファイル・F1–F5・Run 履歴・V5-8 | [`03_実装カタログ.md`](../architecture/03_実装カタログ.md)（§ Composer / Wave 2 V5） |
| Wave 計画・§4.x incident | [`TASKS_ROADMAP.md`](TASKS_ROADMAP.md) |
| OK 判定（V1–V6） | [`04_検証.md`](../runbook/04_検証.md) §0 |
| コマンド手順 | [`05_運用.md`](../runbook/05_運用.md) |
