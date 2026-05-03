# TASKS.md (Phase 7 — current sprint)

新セッションが「**今 sprint で何をやり、何をやらないか**」を確認する単一エントリ。**実装済み・検証済みの細目は載せない** → [`../architecture/03_実装カタログ.md`](../architecture/03_実装カタログ.md) §「Composer / Wave 2 V5」。

## 本ドキュメントの債務

**書く**: 死守ライン・優先順位、V1–V6 の **今の** status、未完了の次コマンド。  
**書かない**: 検証定義 → [`04_検証.md`](../runbook/04_検証.md)；過去 incident 長文 → [`TASKS_ROADMAP.md`](TASKS_ROADMAP.md)；手順 → [`05_運用.md`](../runbook/05_運用.md)。

権威順位: `TASKS_ROADMAP.md` > `TASKS.md` > `01_仕様と設計.md` > `README.md`。

---

## 🎯 ダッシュボード (2026-05-04)

### 死守ライン（クライアント説明の最低条件）

`check_retrain` のみ success **では足りない**（[`04_検証.md` §0 補足](../runbook/04_検証.md)）。**下 checklist 全項目**まで。

- [ ] DAG trigger 成功
- [ ] 失敗時: Pod log / `airflow-worker` を取得し原因分類（IAM / GCS・`PIPELINE_ROOT_BUCKET` / template path / compile・submit 引数 / runner image）
- [ ] 修正後、同一 Run 追跡または新 trigger
- [ ] `check_retrain` **success**
- [ ] `submit_train_pipeline` **success**
- [ ] `wait_train_succeeded` **success**
- [ ] `gate_auto_promote` **期待どおり**（例: `AUTO_PROMOTE=false` なら downstream skip が説明可能）
- [ ] `promote_reranker` **success** または **意図どおり skip**
- [ ] 再学習後 **`/search` 200**（`make ops-livez` 等）
- [ ] **lexical / semantic / rerank** 3 成分が壊れていない（`make ops-search-components`）

### 今の到達度

| ライン | status | 一件コメント |
|---|---|---|
| V1 `deploy-all` | ✅ | 実測 Run 6 |
| V2 `run-all-core` | ✅ | |
| V5 **狭いゲート**（`check_retrain`） | ✅ Run 4 | F1–F5 反映済 |
| V5 **死守 E2E**（上 checklist） | 🔴 未達 | Run 4 は `submit_train_pipeline` **failed** → V5-8 コードあり、**`make build-composer-runner` + deploy-dags + trigger** で再検証（詳細は実装カタログ） |

### 優先順位（同列にしない）

1. **🔴 死守** — V5 E2E（上 checklist）
2. **🟡 準死守** — V4 2 周目 `deploy-all`（import 経路）
3. **🟢 余力** — V6 `parity` live_gcp
4. **⚪ 最後** — V3 `destroy-all`（破壊的・報告では後ろ）

### コピー用（対外向け）

Composer と `check_retrain` は成功済み。**ML 検索アプリとしての再学習 E2E**（Vertex submit・wait・gate/promote・再学習後 `/search`）は死守として **これから最優先**。V4 / V6 / V3 は E2E 後に順位を付けて実施。

---

## 残タスク（チェックボックス）

**インフラ・run-all**: V1・V2 ✅

**死守**: V5 E2E ⏳（上 checklist）

**並び順**: V5 E2E → V4 → V6 → V3

## 今回はやらない

中核 5 要素の置換、`/search` 既定変更、教材禁止技術、BQ fallback 系の「残す」運用 — [`TASKS_ROADMAP.md` §2](TASKS_ROADMAP.md) 参照。

## 完了条件（sprint）

- [x] `make check` / `deploy-all` / `run-all-core`
- [ ] **死守ライン**（本ファイル checklist 全項目）
- [ ] canonical 経路・parity invariant — [`04_検証.md`](../runbook/04_検証.md)

## 参照

| 何を知りたいか | どこ |
|---|---|
| 実装ファイル・F1–F5・Run 履歴・V5-8 | [`03_実装カタログ.md`](../architecture/03_実装カタログ.md)（§ Composer / Wave 2 V5） |
| Wave 計画・§4.x incident | [`TASKS_ROADMAP.md`](TASKS_ROADMAP.md) |
| OK 判定（V1–V6） | [`04_検証.md`](../runbook/04_検証.md) §0 |
| コマンド手順 | [`05_運用.md`](../runbook/05_運用.md) |
