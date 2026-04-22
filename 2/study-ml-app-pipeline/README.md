# study-ml-app-pipeline (Phase 2)

MLOps 学習 Phase 2 — **App (API 連携) / Pipeline (ジョブ分離) / Port-Adapter** を導入するデザインパターン Phase。題材は Phase 1 と同じカリフォルニア住宅価格予測（LightGBM 回帰）。

## Phase 2 の位置付け

Phase 1 → 2 → 3 → 4 → 5 の 5 フェーズ構成の 2 番目。

- Phase 1 (`1/study-ml-foundations/`) — ML 基礎（trainer / evaluation / preprocess / feature_engineering）
- **Phase 2 (本 repo)** — 同じ題材で App / Pipeline / Port-Adapter を導入
- Phase 3 (`3/study-hybrid-search-local/`) — 不動産ハイブリッド検索 Local。本 Phase の Port/Adapter 構造を引き継ぎ、adapter を Meilisearch / Redis / ME5 に差し替える
- Phase 4/5 — GCP / Vertex 化

## 学習ゴール

1. **FastAPI + lifespan による DI 配線** — グローバル状態なしで `app.state` にモデル / adapter を保持
2. **Inbound/Outbound Port** — HTTP / pipeline job は Inbound Adapter、DB / ファイル / tracker は Outbound Port + Adapter
3. **依存方向の制御** — `core → ports ← adapters` の方向性を崩さない
4. **Phase 3 への接続性** — Port 粒度を「実装依存しない pure-data」で切ることで adapter 差し替えの学びに繋がる

## 現状

**Skeleton phase**（2026-04-22）。詳細な設計意図と target layout は `CLAUDE.md` を参照。

## Commands（予定、未実装）

```bash
make build   # Docker イメージビルド
make seed    # PostgreSQL に California Housing 投入
make train   # LightGBM 学習
make serve   # FastAPI 起動 (:8000)
make test    # pytest
```
