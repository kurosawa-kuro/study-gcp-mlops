# Phase3/4/5 コマンド・テスト差分マトリクス

更新日: 2026-04-23  
目的: 学習教材として、`Phase3` / `Phase4` / `Phase5` の運用導線と品質観点を揃えるための差分可視化。

---

## 1. コマンド名差分マトリクス

| 項目 | Phase3 (`3/study-hybrid-search-local`) | Phase4 (`4/study-hybrid-search-cloud`) | Phase5 (`5/study-hybrid-search-vertex`) | 方針 |
|---|---|---|---|---|
| `deploy-all` | なし（ローカルは `run-all` / `verify-pipeline` が中心） | あり | あり | Phase3 は `deploy-all` を作らず、`run-all` を教材の主導線として扱う |
| `deploy-all-direct` | なし | あり | **あり（今回追加）** | Phase4/5 の語彙を統一 |
| `run-all` | あり | あり | あり | 3フェーズ共通の代表導線として維持 |
| `destroy-all` | なし（`down`） | あり | あり | Phase3 は Docker 前提のため `down` 維持（意味差があるため無理に統一しない） |
| `ops-livez` | あり | あり | あり | 共通化済み |
| `ops-search` | あり | あり | あり | 共通化済み |
| `ops-feedback` | あり | あり | あり | 共通化済み |
| `ops-ranking` | あり | あり | あり | 共通化済み |
| `ops-label-seed` | あり | あり | あり | 共通化済み |
| `ops-check-retrain` | なし | あり | あり | Phase3 は再学習トリガ構成が異なるため対象外 |
| `ops-search-components` | あり | あり | **あり（今回追加）** | 3成分寄与ゲートを共通化 |
| `ops-accuracy-report` | あり | あり | **あり（今回追加）** | 精度ゲートの名称を共通化 |

---

## 2. テスト観点差分マトリクス

| テスト観点 | Phase3 | Phase4 | Phase5 | 備考 |
|---|---|---|---|---|
| API契約 (`/search`, `/feedback`, `/readyz` など) | あり | あり | あり | 共通化済み |
| 検索成分（lexical/semantic/rerank） | あり | あり | あり | Phase5 は今回 `ops-search-components` を追加し運用ゲートも揃えた |
| データ契約（BQ/Dataform/feature整合） | あり | あり | あり | Phase4/5 の parity 系が厚い |
| インフラ/スクリプト構造検証 | 部分的 | あり | あり | Phase3 はローカル中心で Terraform/Workflow 検証は限定的 |
| 運用ガード（policy guard / deploy順序 / env drift） | 部分的 | あり | あり | Phase5 は `tests/unit/scripts/test_setup_policy_guard.py` で補強済み |

---

## 3. 今回の統一実施（第3弾）

### Phase5 へ追加した共通コマンド

- `deploy-all-direct`（`deploy-all` の互換 alias）
- `ops-search-components`
- `ops-accuracy-report`
- `local-accuracy-report`

### Phase5 に追加した共通スクリプト

- `scripts/local/ops/search_component_check.py`
- `scripts/local/ops/accuracy_report.py`

### 回帰防止テスト

- `tests/unit/scripts/test_setup_policy_guard.py` に、上記コマンド存在とスクリプト参照を検証するテストを追加

---

## 4. 次の順次統一候補

1. **エラーハンドリング文言の統一**  
   `/search` 失敗・設定不足時の fail-fast メッセージを Phase4/5 で共通化
2. **`run-all` 内容の完全揃え**  
   Phase4/5 の `run-all` ステップ列を同順に寄せる（Phase差分は adapter 内に閉じる）
3. **テストの共通ケース化**  
   API契約・検索成分の共通ケースを parametrized 化し、フェーズ別 fixture のみ差し替える

---

## 5. 根拠ファイル

- `3/study-hybrid-search-local/Makefile`
- `4/study-hybrid-search-cloud/Makefile`
- `5/study-hybrid-search-vertex/Makefile`
- `4/study-hybrid-search-cloud/tests/`
- `5/study-hybrid-search-vertex/tests/`
- `3/study-hybrid-search-local/tests/`

