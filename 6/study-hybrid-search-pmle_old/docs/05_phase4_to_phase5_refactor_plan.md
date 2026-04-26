# Phase4 -> Phase05 コード品質リファクタリング調査計画

更新日: 2026-04-23  
対象: `5/study-hybrid-search-vertex`

---

## 1. 目的

- `Phase05` の「そもそも動かない」要因を、再現可能な形で特定する。
- `Phase4` で確立した品質ゲート（非空検索、3成分寄与、設定一貫性）を `Phase05` に移植する。
- 実装修正の前に、優先度付きバックログ（P0/P1/P2）と検証手順を固定化する。

---

## 2. 現時点の主要リスク（事前調査結果）

### P0（実行不能・即対応）

1. `deploy-all` の import パス不整合  
   - `scripts/local/setup/deploy_all.py` が `scripts.config.*`, `scripts.deploy.*`, `scripts.setup.*` を import  
   - 現行構成は `scripts/ci/*` と `scripts/local/*` であり、ImportError の可能性が高い
2. `destroy-all` の import パス不整合  
   - `scripts/local/setup/destroy_all.py` が `scripts.setup.seed_minimal_clean` を import
3. APIデプロイ時の検索必須設定不足  
   - `scripts/local/deploy/api_local.py` の `--set-env-vars` に `ENABLE_SEARCH` と `VERTEX_ENCODER_ENDPOINT_ID` が含まれない  
   - `/search` が無効化され 503 になる導線を作りやすい

### P1（高リスク・再発しやすい）

4. docs のコマンドパスが旧構成のまま（更新前の課題）  
   - `docs/04_運用.md` などが `scripts/local/setup/*`, `scripts/local/deploy/*`, `scripts/ci/*` と一致していなかった
5. 外部依存障害時の劣化が観測しづらい  
   - lexical/vertex 失敗時の挙動が「起動は通るが実検索不能」に寄りやすい

### P2（中長期の負債）

6. 実アダプタ層（Meili/BQ/Vertex）テスト不足
7. `make test` に coverage ゲートがなく、重要導線の未検証を見逃しやすい

---

## 3. 調査スコープ

- 実行導線: `Makefile` -> `scripts/local/setup/deploy_all.py` -> `scripts/local/deploy/api_local.py`
- API導線: `app/main.py` -> `app/services/adapters/*` -> `app/services/ranking.py`
- 設定導線: `env/config/setting.yaml` + `scripts/_common.py` + deploy env vars
- テスト導線: `tests/unit/*`, `tests/integration/parity/*`
- ドキュメント導線: `docs/04_運用.md`, `docs/03_実装カタログ.md`, `docs/README.md`

---

## 4. 実行フェーズ（調査計画）

### Phase A: 再現と事実固定（半日）

- `make deploy-all` / `make destroy-all` の実行可否を確認し、失敗ログを確定
- import/path mismatch を最小再現コマンドで記録
- `/search` が 503 になる条件（env不足）を再現・固定

成果物:
- 「失敗再現ノート」（コマンド、期待値、実結果、ログ抜粋）

### Phase B: 差分分析（半日）

- `Phase4` の品質ゲートと `Phase05` の導線を比較
- 欠落ゲートを一覧化（非空検索、3成分寄与、設定ドリフト検知）
- 影響範囲（コード/運用/docs/CI）をマッピング

成果物:
- 「Phase4 -> Phase05 品質ギャップ表」

### Phase C: 最小修正設計（半日）

- P0を最小差分で直す修正案を設計（1課題1PR粒度）
- P1/P2 の後続改善案（テスト/運用）を定義
- ロールバック条件を各修正に付与

成果物:
- 「優先度付き改善バックログ（P0/P1/P2）」

### Phase D: 検証計画確定（半日）

- 各修正の受け入れ基準（Go/No-Go）を定義
- `make` ベースの再検証フローを確定

成果物:
- 「受け入れ基準チェックリスト」

---

## 5. 優先実施バックログ（ドラフト）

1. `deploy_all.py` import を現行パスへ統一（P0）
2. `destroy_all.py` import を現行パスへ統一（P0）
3. `api_local.py` に検索必須 env を注入、未設定時 fail-fast（P0）
4. docs の旧コマンドパスを一括更新（P1）
5. `deploy-all/destroy-all` の import 崩れを検知する unit test 追加（P1）
6. `ops-search-components` 相当ゲートを Phase05 に追加（P1）
7. 実アダプタ（Meili/BQ/Vertex）失敗モードテスト追加（P2）
8. `make test` に coverage しきい値を導入（P2）

---

## 6. 受け入れ基準（調査完了の定義）

- P0 3件について、再現条件・原因・修正方針が文書化されている
- P1/P2 について、優先順位と着手順が合意済みである
- 次の実装フェーズで、そのまま着手できるPR単位まで分解済みである

---

## 7. 想定工数

- 調査計画の実施（A-D）: 1.5〜2.0 日
- P0修正の初回実装 + 再検証: 0.5〜1.0 日

