# Phase 4 課題履歴

更新日: 2026-04-24
対象: `4/study-hybrid-search-gcp`

---

## 課題 A-F: 検証時に発生した課題と対応

### A. `deploy-all` の初期失敗（Dockerfile）

- 事象: Step 7 相当で `docker build` 失敗
- 原因: 存在しない `ml/*/pyproject.toml` を `COPY`
- 対応: `infra/run/services/search_api/Dockerfile` 修正
- 状態: **原因修正済み**

### B. `run-all` の JSONDecodeError

- 事象: `ops-feedback` で JSON 解析失敗
- 原因: Cloud Run placeholder 応答や認証/到達経路の不整合
- 対応: 認証経路・Meilisearch 実体デプロイ・環境変数反映を是正
- 状態: **原因修正済み**

### C. `seed-test` / Meilisearch 同期失敗（taskUid欠落）

- 事象: `meili response missing taskUid for async operation`
- 対応:
  - `ml/data/loaders/meili_sync.py` で task 解決リトライ追加
  - `/tasks` クエリのフォールバック追加（`indexUids` / `indexUid` / `indexUids[]`）
  - 単体テスト追加（`tests/unit/ml/data/loaders/test_meili_sync.py`）
- 状態: **原因修正済み**

### D. component gate の実行順序不整合

- 事象: 再学習前に component gate が実行され、`ME5 semantic contribution is zero` で停止
- 対応:
  - `scripts/dev/deploy_all.py` の順序を修正
  - `ops-label-seed` → `training-data gate` → `run-training-job` の後に `component gate`
  - `tests/unit/scripts/test_deploy_all.py` 更新
- 状態: **原因修正済み（最終通し検証PASS）**

### E. `false` 設定起因の品質低下リスク

- 事象: `MEILI_REQUIRE_IDENTITY_TOKEN=false` 等の緩和設定が残ると、運用目線で失敗判定と整合しない
- 対応:
  - `MEILI_REQUIRE_IDENTITY_TOKEN=true` を runtime/deploy/workflow で統一
  - Meili `allUsers` invoker を削除（token 前提に統一）
  - 設定退行を検出する policy guard テスト追加
  - deploy-monitor の表示を `WAITING` / `READY` に改善（誤読防止）
- 状態: **原因修正済み**

### F. Step10 seed-test の Meilisearch 同期 401

- 事象: `ml.data.loaders.meili_sync` 実行時に `PATCH /indexes/properties/settings` が `401 Unauthorized`
- 直接原因:
  - Meilisearch 側は `allUsers` invoker を外し、ID token 必須
  - 一方で seed 同期はユーザー主体の token 経路で呼ばれ、呼び出し主体が `sa-api` と一致しないケースが発生
- 対応:
  - `meili_sync.py` に service account impersonation 指定を追加
  - `seed_minimal.py` から `sa-api` impersonation を強制して呼び出すよう変更
- 状態: **原因修正済み（`deploy-all` Step10 通過で再発なしを確認）**

---

## 確定している「できる / できない」

### できる（確定）

- 単発の運用・確認コマンド群
- 主要サービスの再デプロイ
- 学習ジョブ実行と訓練データ妥当性ゲート導入
- Meili同期の非同期応答揺れに対する耐性向上
- API+モデル同時監視付きのデプロイ進捗判定（`ops-deploy-monitor`）
- 3成分寄与必須ゲートと精度レポート（20ケース）運用

### まだ言い切れない（未確定）

- なし（未確定項目は Phase 5 のみ）
