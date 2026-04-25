# Phase 7 Port-Adapter-DI 移行ロードマップ (残作業のみ)

> **状態**: ✅ **移行完了**。Phase A〜G の全タスクは終了済 (Composition root 分離 / FastAPI Depends 化 / Port-Adapter ファイル分割 / noop adapter 分離 / Service 層抽出 / Handler 分割 / tests/fakes/ 整備 / `make check-layers` 自動化 / 関連 docs 更新)。
>
> 現行構造の説明は本ドキュメントには残さない。canonical な仕様は実装と test に集約:
> - 全体構造: `docs/01_仕様と設計.md §4` (Port / Adapter / DI 境界)
> - ディレクトリレイアウト: `docs/03_実装カタログ.md §2` (`app/services/protocols` / `app/services/adapters` / `app/services/noop_adapters` / `app/container` / `app/api/handlers` / `app/api/mappers` / `ml/*/ports` / `ml/*/adapters` / `pipeline/*/ports`)
> - 境界違反検出: `scripts/ci/layers.py::DIRECTORY_RULES` + `make check-layers` (現状 53 files clean)
> - DI 配線: `app/composition_root.py::Container` + `ContainerBuilder.build()` (search / ml / infra builder 分割済 — Issue 1 解決)
>
> Phase 7 Run 2 で Vector Search / Agent Builder adapter を **削除** した結果、Issue 7 (plugin architecture for PMLE optional modules) は対象消失。

---

## 残作業 (改善タスク、運用熟成後に判断)

### 対応済み

| # | 旧 Issue | 項目 | 反映先 |
|---|---|---|---|
| 1 | Issue 5 | ✅ **observability の Container 管理統一** | `app/observability.py::Observability` (frozen dataclass、`service_name` + `logger_factory` + `expose_prometheus()`) を新設。`Container.observability` field 追加、`ContainerBuilder(settings, observability=...)` で外部注入可。`app/main.py` から `_expose_prometheus` / module-global `Counter` / `Histogram` を撤去し `observability.expose_prometheus(app)` 呼び出しに統一。`tests/conftest.py` の `fake_container_factory` も新 field を default 値で埋める。tracing 導入時は `Observability` に `tracer` field を足すだけで Container 全体に伝搬する seam が出来た |
| 2 | Issue 2 | ✅ **optional adapter guard の helper 化** | `app/container/_optional_adapter.py::resolve_optional_adapter[T]()` 新設 (PEP 695 generics)。`enabled=False` で `None`、`factory()` 例外時は `logger.exception("Failed to initialize %s", name)` + `None`。`MlBuilder.build_rag_summarizer` / `build_popularity_scorer` を helper 経由に refactor。`SearchBuilder.build_encoder_client` / `build_reranker_client` は tuple 返却 + URL 空文字 warn の追加分岐があり helper に押し込むと逆に読みにくいので原形維持 (理由は helper module docstring に記載) |

検証: `make check` 全 PASS (ruff / fmt / mypy strict / pytest 409 passed) + `make check-layers` clean。

### 見送り判断 (再検討トリガー付き)

| # | 旧 Issue | 判定 | 理由 / 再検討トリガー |
|---|---|---|---|
| 3 | Issue 4 | 見送り | **DI scope 明文化は不要**。現 Container は全 adapter が singleton + eager init で、`ContainerBuilder.build()` で一度生成 → frozen `Container` に格納する単一 scope。scope 表を書いても 1 行 ("all singleton, eager") で trivial。再検討トリガー: request-scoped state (per-request connection / per-request retry budget 等) を導入した時 |
| 4 | Issue 6 | 見送り | **Publisher / Query Port の facade 化はしない**。`RankingLogPublisher` / `FeedbackRecorder` / `PredictionPublisher` は ISP に沿った 1-method protocol で、`tests/fakes/` の noop 実装も短い。facade 化は call site と fake を曖昧にして得が薄い。再検討トリガー: Port が同種 5 個以上に増殖した時、または Publisher 群を共通 retry / batching 層で wrap する必要が出た時 |

## 完了タスクの参照先

- 大規模リファクタの履歴は `docs/動作検証結果.md §第3部 大規模リファクタ Run` に時系列で記載 (2026-04-24 夜の方針転換 3 点 + Phase 7 = Phase 6 ベース再構築)。
- 各 Phase A〜G の個別チェックリストや「`make check` green / `319 passed` → `421 passed`」推移は git log + `動作検証結果.md` 参照。
