# Phase 7 Port-Adapter-DI 移行ロードマップ (残作業のみ)

> **状態**: ✅ **移行完了**。Phase A〜G の全タスクは終了済 (Composition root 分離 / FastAPI Depends 化 / Port-Adapter ファイル分割 / fakes 分離 / Service 層抽出 / Handler 分割 / tests/fakes/ 整備 / `make check-layers` 自動化 / 関連 docs 更新)。
>
> 現行構造の説明は本ドキュメントには残さない。canonical な仕様は実装と test に集約:
> - 全体構造: `docs/01_仕様と設計.md §4` (Port / Adapter / DI 境界)
> - ディレクトリレイアウト: `docs/03_実装カタログ.md §2` (`app/services/protocols` / `app/services/adapters` / `app/services/fakes` / `app/container` / `app/api/handlers` / `app/api/mappers` / `ml/*/ports` / `ml/*/adapters` / `pipeline/*/ports`)
> - 境界違反検出: `scripts/ci/layers.py::DIRECTORY_RULES` + `make check-layers` (現状 53 files clean)
> - DI 配線: `app/composition_root.py::Container` + `ContainerBuilder.build()` (search / ml / infra builder 分割済 — Issue 1 解決)
>
> Phase 7 Run 2 で Vector Search / Agent Builder adapter を **削除** した結果、Issue 7 (plugin architecture for PMLE optional modules) は対象消失。

---

## 残作業 (改善タスク、運用熟成後に判断)

優先順は **observability 統一 > optional adapter helper**。残り 2 件は見送り判断 (理由は下表)。

### 現役タスク

| # | 旧 Issue | 優先 | 項目 | 判断材料 / 着手条件 |
|---|---|---|---|---|
| 1 | Issue 5 | 高 | **observability の Container 管理統一** | metrics (`prometheus-fastapi-instrumentator`) / tracing / structured logging の注入経路を Container 経由に揃える。現状 `app/main.py:_expose_prometheus()` で Instrumentator を register、`ml/common/logging::get_logger()` を adapter / service が直呼び、`api/middleware/request_logging.py` で request_id 発行と、3 経路に分散。tracing (Cloud Trace / OpenTelemetry) を入れる時点で必ず再線引きになるので、その手前で **`Container.observability` (Logger / Tracer / MeterProvider 入り)** を切り出すのが妥当。着手条件: tracing 導入の意思決定がある時 |
| 2 | Issue 2 | 中 | **optional adapter guard の helper 化** (旧 "adapter resolve 規約") | VS/AB 削除で backend 分岐 (`if backend == "vertex"`) は消滅。残っているのは `if not settings.enable_xxx: return None` → `try construct: ... except: logger.exception + return None` の **optional adapter guard 4 連発** (`build_encoder_client` / `build_reranker_client` / `build_rag_summarizer` / `build_popularity_scorer`)。これを `resolve_optional_adapter(name, enabled: bool, factory: Callable)` 型の helper にまとめる。着手条件: optional adapter が 5 個目以降に増えた時 (現状 4 個では helper 化しても短縮幅が小さい) |

### 見送り判断 (再検討トリガー付き)

| # | 旧 Issue | 判定 | 理由 / 再検討トリガー |
|---|---|---|---|
| 3 | Issue 4 | 見送り | **DI scope 明文化は不要**。現 Container は全 adapter が singleton + eager init で、`ContainerBuilder.build()` で一度生成 → frozen `Container` に格納する単一 scope。scope 表を書いても 1 行 ("all singleton, eager") で trivial。再検討トリガー: request-scoped state (per-request connection / per-request retry budget 等) を導入した時 |
| 4 | Issue 6 | 見送り | **Publisher / Query Port の facade 化はしない**。`RankingLogPublisher` / `FeedbackRecorder` / `PredictionPublisher` は ISP に沿った 1-method protocol で、`tests/fakes/` の noop 実装も短い。facade 化は call site と fake を曖昧にして得が薄い。再検討トリガー: Port が同種 5 個以上に増殖した時、または Publisher 群を共通 retry / batching 層で wrap する必要が出た時 |

いずれも「設計穴」ではなく「磨き込み」案件のため、Phase 7 主検証 (`/search` 3 成分 + `/rag` + `/search?explain=true`) には影響しない。

## 完了タスクの参照先

- 大規模リファクタの履歴は `docs/動作検証結果.md §第3部 大規模リファクタ Run` に時系列で記載 (2026-04-24 夜の方針転換 3 点 + Phase 7 = Phase 6 ベース再構築)。
- 各 Phase A〜G の個別チェックリストや「`make check` green / `319 passed` → `421 passed`」推移は git log + `動作検証結果.md` 参照。
