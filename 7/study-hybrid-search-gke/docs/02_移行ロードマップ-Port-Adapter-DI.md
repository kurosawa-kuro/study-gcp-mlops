# Phase 7 Port-Adapter-DI 移行ロードマップ

`docs/02_移行ロードマップ.md` の **DI / Port-Adapter 観点版**。Phase 6 から継承した Phase 7 のコードベースは、表面的に Port-Adapter パターンを採っているが、Hexagonal Architecture / Clean Architecture の厳格な観点で **致命的な不足**を抱えている。本ドキュメントはその不足を補うための段階別作業計画。

権威順位（[`docs/README.md §2`](README.md)）:

```
02_移行ロードマップ.md > 02_移行ロードマップ-Port-Adapter-DI.md ≥ 01_仕様と設計.md > README.md
```

本ドキュメントは `02_移行ロードマップ.md` (serving 層差し替えの権威) と独立に進行可能。中核検索の挙動を変えない範囲で進める。

---

## §0. なぜ必要か

Phase 6 自体が DI / Port-Adapter の設計として不完全だったため、Phase 6 をそのまま継承した Phase 7 もまた **同種の不足を抱えたまま** である。学習リポジトリとして Hexagonal/Clean Architecture を理解する目的に対して、現状は十分ではない。

### 致命的問題（実測）

| # | 問題 | 観測値 |
|---|---|---|
| 1 | composition root が main.py に埋込 | `app/main.py` **699 行**、`_build_*` factory **13 個**直書き |
| 2 | DI が素朴（FastAPI Depends 未使用） | handler が `request.app.state` に対して `getattr` で型不明アクセス |
| 3 | Adapter ファイルの肥大 | `adapters/candidate_retriever.py` **371 行**に 5 クラス、`kserve_prediction.py` **623 行**に encoder + reranker 同居 |
| 4 | Port ファイルに複数 Protocol 混在 | `protocols/candidate_retriever.py` に `Candidate` + `CandidateRetriever` + `FeedbackRecorder` + `RankingLogPublisher` の 4 つが同居 |
| 5 | Noop / fake が production adapter と同居 | `NoopRankingLogPublisher` 等が `adapters/` 直下 |
| 6 | Pipeline / ML 層に Port 概念なし | `pipeline/training_job/` `ml/training/` `ml/registry/` `ml/serving/` `ml/streaming/` が SDK 直叩き |
| 7 | layers.py が手動登録方式 | `RULES` に未登録のファイルは無検査（新ファイル時に手動追記必要） |
| 8 | 型安全性の欠落 | `filters: dict[str, Any]`、`tuple[str, int, float]` 等が Port API に貫通 |

---

## §1. 全体方針

### 1.0 現在地の整理

Phase 7 はもはや「DI 導入を試し始めた段階」ではない。以下が揃ったため、現状は **DI 導入期ではなく DI 運用期** と位置づける。

- `app/main.py` は HTTP entrypoint に縮退し、依存生成は `app/composition_root.py` の `ContainerBuilder` に集約済
- handler は `Depends(...)` 経由で `Container` / service を受け取り、`request.app.state` 直参照を廃止済
- `app/services/protocols/` に Port を分離し、複数 adapter (`KServe*`, `BigQuery*`, `Vertex*`, `Noop*`, `InMemory*`) が同じ Port を実装
- `SearchService` / `FeedbackService` / `RagService` が UseCase 層として成立
- `tests/fakes/` と `app/services/fakes/` が分離され、production noop と test double の責務が分かれている

この状態は、典型的な「route で依存を new する」「service が SDK を直叩きする」「mock 差し替えが困難」という導入前の状態を既に脱している。今後の主題は「DI を入れること」ではなく、**運用しやすい Container 境界と Port 粒度を保ちながら拡張すること**にある。

### 1.0.1 現時点の強み

- **Composition Root が明確**: `lifespan()` → `ContainerBuilder(settings).build()` → `app.state.container`
- **Port 分離が実運用に乗っている**: `EncoderClient`, `RerankerClient`, `CandidateRetriever`, `FeedbackRecorder`, `PopularityScorer`, `Generator`
- **差し替え実績がある**: KServe / BigQuery / Vertex / Noop / InMemory の複数実装が共存
- **Service 層が薄い HTTP handler から分離済**: handler は I/O、service は use case に寄せた
- **テストと相性が良い**: fake/stub/in-memory による差し替えが fixture レベルで機能している

### 1.0.2 まだ残る伸びしろ

- **ContainerBuilder の肥大化抑制**: factory が増え続ける場合、`search_container.py` / `ml_container.py` / `infra_container.py` のような分割を検討する
- **settings の整理**: `ApiSettings` / `TrainSettings` / `EmbedSettings` などが増えたら domain/feature 単位で package 化する
- **Port 粒度の統一**: Publisher 系や Query 系が増えすぎる場合は facade 化や責務再編を検討する
- **scope の明文化**: singleton/request scope の境界、metrics/tracing の DI 管理、feature flag ごとの adapter 切替を設計として固定する
- **plugin 化余地**: 今後の PMLE 機能追加で plugin architecture に寄せる選択肢がある

### 1.1 制約

- **トップレベルのフォルダ構成は変更しない**。`app/ ml/ pipeline/ scripts/ infra/ env/ monitoring/ docs/` は必須維持
- **[`docs/フォルダ-ファイル.md`](/home/ubuntu/repos/study-gcp-mlops/docs/フォルダ-ファイル.md) 準拠**。`ports/ adapters/ core/` は機能ディレクトリの**内側**に置く（`ml/` 直下は禁止）
- **MLOps 学習なので `pipeline/` を重視**
- 設計優先順位: **DI > Port-Adapter > Clean > Domain**
- Phase 6 のコードは参考にしない（同様の不足を抱えるため）

### 1.2 適用後の構造

```
app/                              # 既存。中の整理のみ
├── main.py                       # < 150 行 (HTTP entrypoint のみ)
├── composition_root.py           # NEW: Container + ContainerBuilder
├── domain/                       # NEW (P2): SearchFilters / Candidate
├── api/
│   ├── dependencies.py           # NEW: FastAPI Depends 解決
│   ├── handlers/                 # NEW: endpoint 1 file 1 handler
│   ├── mappers/                  # NEW: domain ↔ schema 変換
│   ├── middleware/               # 既存
│   └── routes/                   # 既存
├── services/
│   ├── protocols/                # 既存。1 Protocol 1 file 化
│   ├── adapters/                 # 既存。1 Adapter 1 file 化
│   ├── fakes/                    # NEW: Noop / InMemory
│   ├── search_service.py         # NEW
│   ├── feedback_service.py       # NEW
│   ├── rag_service.py            # NEW
│   └── retrain_policy.py         # 既存
└── schemas/                      # 既存

ml/                               # 機能別。各機能 dir 内に ports/ adapters/
├── common/                       # 既存
├── data/                         # 既存
├── training/
│   ├── ports/                    # NEW: RankerTrainer, RankerModel
│   ├── adapters/                 # NEW: LightGBMTrainer, LightGBMModel
│   └── trainer.py                # 既存（薄くする）
├── evaluation/                   # 既存（pure logic、Port 化不要）
├── registry/
│   ├── ports/                    # NEW: ModelRegistry
│   └── adapters/                 # NEW: VertexModelRegistry
├── serving/
│   ├── ports/                    # NEW: PredictorService
│   └── adapters/                 # NEW: KServePredictor
└── streaming/
    ├── ports/                    # NEW: StreamProcessor
    └── adapters/                 # NEW: DataflowStreamProcessor

pipeline/                         # <verb>_job 命名は維持
├── data_job/
│   ├── ports/                    # NEW
│   └── adapters/                 # NEW
├── training_job/
│   ├── ports/                    # NEW: PipelineOrchestrator
│   ├── adapters/                 # NEW: KFPOrchestrator
│   └── components/               # 既存（adapter 経由で呼ばれる側に）
├── batch_serving_job/            # 既存（同パターン）
├── evaluation_job/               # 既存（同パターン）
└── workflow/                     # 既存
```

### 1.3 禁止事項

- `app/` 直下に `composition_root.py` `domain/` 以外の新規ディレクトリ追加（単一ファイルは可）
- `ml/` 直下への `ports/ adapters/ core/` 配置（Phase 2 の例外形を再現しない）
- 新たな top-level ディレクトリの追加

---

## §2. 段階別作業計画

### Phase A — DI 整備（最優先・P0）

**ゴール**: composition root を `main.py` から分離。FastAPI Depends 化。テスト時の DI override 容易化。

#### A-1. Composition root 分離

- 作成: `app/composition_root.py`
  - `Container` dataclass（全 adapter / service の immutable 集合）
  - `ContainerBuilder` クラス（`ApiSettings → Container`）
  - 既存 `app/main.py:67-328` の `_build_*` factory **13 個**を全て移動
- 修正: `app/main.py`
  - `lifespan()` は `ContainerBuilder(settings).build()` を呼んで `app.state.container` に格納するだけ
  - 目標行数: < 150 行（現在 699 行）

#### A-2. FastAPI Depends 化

- 作成: `app/api/dependencies.py`
  - `get_container(request) -> Container`
  - `get_search_service(...) -> SearchService` 等
  - `get_request_id(request) -> str`
- 修正: 全 endpoint handler を `Depends(...)` 注入に置換、`request.app.state` の `getattr` を全廃

#### A-3. テスト fixture 整備

- 修正: `tests/conftest.py`
  - `test_container` fixture: 全 adapter を fake/stub に置換した Container
  - `test_app` fixture: `test_container` を inject した FastAPI app
  - `TestClient` を `test_app` ベースに切替（環境変数 monkeypatch 廃止）

#### A-4. SDK client lifecycle を composition root に集約

- 修正: `GeminiGenerator._model()`、`VertexVectorSearchSemantic._matching_engine()` 等の lazy init を廃止
- composition root で `vertexai.init()` / `bigquery.Client()` 等を 1 回呼び、adapter コンストラクタに client を注入

**Phase A 成功条件**:

- `app/main.py` < 150 行
- handler から `getattr(request.app.state, ...)` が消滅
- `pytest tests/unit` が環境変数なしで動く

---

### Phase B — Port-Adapter 整備（P0）

**ゴール**: 1 Port 1 file、1 Adapter 1 file。fake を分離。型安全化。

#### B-1. Protocol ファイル分割

- `app/services/protocols/candidate_retriever.py` (58行) を 4 ファイルに:
  - `candidate.py` — `Candidate` dataclass
  - `candidate_retriever.py` — `CandidateRetriever` のみ
  - `feedback_recorder.py` — `FeedbackRecorder` のみ
  - `ranking_log_publisher.py` — `RankingLogPublisher` のみ
- 全 Protocol に **detailed docstring**（目的・semantics・failure mode・実装一覧）

#### B-2. Adapter ファイル分割

- `app/services/adapters/candidate_retriever.py` (371行) を 3 ファイルに:
  - `bigquery_candidate_retriever.py`
  - `pubsub_ranking_log_publisher.py`
  - `pubsub_feedback_recorder.py`
- `app/services/adapters/kserve_prediction.py` (623行) を 2 ファイルに:
  - `kserve_encoder.py`
  - `kserve_reranker.py`
- `app/services/adapters/semantic_search.py` を 2 ファイルに:
  - `bigquery_semantic_search.py`
  - `vertex_vector_search_semantic.py`

#### B-3. fakes/ 分離

- 作成: `app/services/fakes/`
  - `noop_ranking_log_publisher.py` / `noop_feedback_recorder.py` / `noop_lexical_search.py` / `noop_cache_store.py`
  - `in_memory_cache_store.py`
- 修正: `app/services/adapters/__init__.py` から fake 系を export 削除
- 作成: `app/services/fakes/__init__.py` で fake のみ export

#### B-4. 型安全化

- 作成: `app/domain/search.py`（Phase E と合流）
  - `SearchFilters` を `TypedDict(total=False)` で定義
- 作成: `app/services/protocols/_types.py`
  - `SemanticResult = NamedTuple("SemanticResult", property_id=str, rank=int, similarity=float)`
  - `LexicalResult = NamedTuple("LexicalResult", property_id=str, rank=int)`
- 修正: 各 Port / adapter / service / handler で `dict[str, Any]` を `SearchFilters` に置換、無名 tuple を NamedTuple に置換

**Phase B 成功条件**:

- `app/services/protocols/` の各ファイルが 1 Protocol（dataclass 例外あり）
- `app/services/adapters/` の各ファイルが 1 Adapter
- `from app.services.adapters import Noop*` で import エラー
- `make check-layers` が green

---

### Phase C — Pipeline / ML Port 化（P0、MLOps 重視）

**ゴール**: pipeline/ ml/ の主要機能で Port-Adapter を成立させる。SDK 直叩きを adapter に隔離。

[`docs/フォルダ-ファイル.md`](/home/ubuntu/repos/study-gcp-mlops/docs/フォルダ-ファイル.md) 準拠で**機能ディレクトリの内側**に `ports/ adapters/` を置く。

#### C-1. ml/training/

- 作成: `ml/training/ports/`
  - `ranker_trainer.py` — `RankerTrainer(Protocol)`
  - `ranker_model.py` — `RankerModel(Protocol)`
- 作成: `ml/training/adapters/`
  - `lightgbm_trainer.py` — `LightGBMRankerTrainer`, `LightGBMModel`
- 修正: `ml/training/trainer.py` を pure orchestration に
- 修正: `scripts/ci/layers.py` で `ml/training/trainer.py` から `lightgbm` import 禁止

#### C-2. ml/registry/

- 作成: `ml/registry/ports/model_registry.py` — `ModelRegistry(Protocol)`
- 作成: `ml/registry/adapters/vertex_model_registry.py`
- 修正: `scripts/deploy/kserve_models.py` 等から `aiplatform` 直叩きを `ModelRegistry` 経由に

#### C-3. ml/serving/

- 作成: `ml/serving/ports/predictor.py` — `PredictorService(Protocol)`
- 作成: `ml/serving/adapters/kserve_predictor.py`
- 既存 `ml/serving/encoder.py` `ml/serving/reranker.py`: KServe container の entrypoint としてそのまま残置（Port 化対象は client 側 = `app/services/adapters/kserve_*`）

#### C-4. ml/streaming/

- 作成: `ml/streaming/ports/stream_processor.py` — `StreamProcessor(Protocol)`
- 作成: `ml/streaming/adapters/dataflow_processor.py`
- 既存 `ml/streaming/container/` のロジックを adapter 内に整理

#### C-5. pipeline/<verb>_job/

- 作成: `pipeline/training_job/ports/`
  - `pipeline_orchestrator.py` — `PipelineOrchestrator(Protocol)`
  - `pipeline_component.py` — `PipelineComponent(Protocol)`
- 作成: `pipeline/training_job/adapters/kfp_orchestrator.py`
- 修正: `pipeline/training_job/main.py` を `PipelineOrchestrator` Protocol 経由に
- 同パターンを `data_job/` `evaluation_job/` `batch_serving_job/` に複製

**Phase C 成功条件**:

- `ml/training/trainer.py` から `lightgbm` import 消滅
- `pipeline/training_job/main.py` から `kfp.dsl` import 消滅
- `make check-layers` が `ml/training/trainer.py` `pipeline/*/main.py` を含めて green

---

### Phase D — Service 層抽出 (Clean 寄り、P1)

**ゴール**: API handler から business logic を service へ。1 handler < 40 行。

#### D-1. Service クラス化

- 作成: `app/services/search_service.py` — `SearchService.search(SearchInput) -> SearchOutput`
- 作成: `app/services/feedback_service.py` — `FeedbackService.record(...)`
- 作成: `app/services/rag_service.py` — `RagService.summarize(...)`（既存 `RagSummarizer` を昇格）

#### D-2. Handler 分割

- 作成: `app/api/handlers/`
  - `search_handler.py` — `/search`
  - `rag_handler.py` — `/rag`
  - `feedback_handler.py` — `/feedback`
  - `health_handler.py` — `/livez` `/readyz` `/healthz`
  - `retrain_handler.py` — `/jobs/check-retrain`
- 各 handler は **40 行以下**、Pydantic schema ↔ domain mapping だけ

#### D-3. Mapper 層

- 作成: `app/api/mappers/search_mapper.py`
  - `to_search_response(domain: SearchOutput) -> SearchResponse`
  - `to_search_input(req: SearchRequest) -> SearchInput`

**Phase D 成功条件**:

- `app/api/handlers/*.py` の各ファイルが 40 行以下
- `app/main.py` < 100 行
- `app/services/ranking.py` は薄い helper のみ残す or `search_service.py` に吸収

---

### Phase E — Domain（最低優先、P2）

**ゴール**: 値オブジェクト・entity の最低限の整理（深追いしない）。

#### E-1. Domain ディレクトリ

- 作成: `app/domain/`
  - `candidate.py` — `Candidate`, `RankedCandidate`
  - `search.py` — `SearchFilters`, `SearchInput`, `SearchOutput`, `SearchResultItem`（domain 版）

**作らないもの**（user 優先順位最低のため）:

- 価格・面積・住所等の Value Object（`Rent`, `Area`, `Address`）
- Entity (Property)
- Domain exception

**Phase E 成功条件**:

- `Candidate` の参照元が `app/domain/candidate.py` 一箇所
- API schema (`app/schemas/search.py::SearchResultItem`) と domain (`app/domain/search.py::SearchResultItem`) が分離

---

### Phase F — テスト・CI 整備（P1）

#### F-1. テストダブル整備

- 作成: `tests/fakes/`
  - `stub_encoder_client.py` — `StubEncoderClient`（固定 embedding）
  - `mock_reranker_client.py` — `MockRerankerClient`（呼び出し記録 + 決定的スコア）
  - `in_memory_ranking_log_publisher.py` / `in_memory_feedback_recorder.py`
  - `in_memory_semantic_search.py` / `in_memory_lexical_search.py`

`app/services/fakes/` (Phase B-3) は production noop、`tests/fakes/` は test stub と分業。

#### F-2. layers.py 自動化

- 修正: `scripts/ci/layers.py`
  - `DIRECTORY_RULES: dict[str, frozenset[str]]` を新設
  - `find_rules_for_file(rel_path)`: file 単位 → directory 単位の順で fallback
  - `app/` `ml/` `pipeline/` 配下を rglob して全 `.py` を対象に走査
- 既存 `RULES` のうち `DIRECTORY_RULES` でカバーされるエントリは整理

**DIRECTORY_RULES の最低エントリ**:

```python
DIRECTORY_RULES = {
    "app/services/protocols/": ADAPTER_BANS,
    "app/services/": ADAPTER_BANS,                # adapters/ fakes/ 以外
    "app/domain/": ADAPTER_BANS | {"lightgbm"},
    "app/api/handlers/": ADAPTER_BANS,
    "app/api/mappers/": ADAPTER_BANS,
    "ml/training/ports/": ADAPTER_BANS | {"lightgbm"},
    "ml/registry/ports/": ADAPTER_BANS,
    "ml/serving/ports/": ADAPTER_BANS,
    "ml/streaming/ports/": ADAPTER_BANS,
    "pipeline/data_job/ports/": ADAPTER_BANS | {"kfp"},
    "pipeline/training_job/ports/": ADAPTER_BANS | {"kfp"},
    "pipeline/evaluation_job/ports/": ADAPTER_BANS | {"kfp"},
    "pipeline/batch_serving_job/ports/": ADAPTER_BANS | {"kfp"},
}
```

#### F-3. unit / integration テスト追加

- handler の HTTP テストを `test_container` 経由で書き換え
- service レベルのテストを Protocol mock で書く
- pipeline / ml の Port 化分はテストを最低 1 件ずつ追加

**Phase F 成功条件**:

- `make check` (`ruff` + `mypy --strict` + `pytest`) green
- `make check-layers` が新ファイル追加時も自動検出（手動 RULES 追記不要）

---

### Phase G — ドキュメント整備（P2、最終工程）

#### G-1. 本ロードマップを完了済み Phase ✅ で更新

#### G-2. `docs/01_仕様と設計.md` § Port-Adapter-DI 章追加

- 設計テーゼ: なぜ Port-Adapter なのか
- `app/services/{protocols,adapters,fakes}` の責務
- `ml/<feature>/{ports,adapters}` の責務
- `pipeline/<job>/{ports,adapters}` の責務
- `Container` / DI フローの図解（mermaid）

#### G-3. `docs/03_実装カタログ.md` Port/Adapter テーブル更新

- 全 Port × 全 Adapter の対応表
- どの環境変数 / feature flag で adapter が選択されるか
- fake の用途（development / test）

#### G-4. CLAUDE.md の Port/Adapter 境界指針更新

- 「Phase 6 から継承」を削除
- Container 経由 DI ルールを追記

---

## §3. 検証方法

各 Phase 完了時:

```bash
make check          # ruff + ruff format --check + mypy --strict + pytest
make check-layers   # AST で Port-Adapter 境界違反検出
make train-smoke    # 合成データで LightGBM LambdaRank 学習 (GCP 認証不要)
make api-dev        # ローカル uvicorn (ENABLE_SEARCH=false) で Container 動作確認
```

全 Phase 完了後の **E2E** 検証:

```bash
make tf-bootstrap
make deploy-all
make verify-all
make ops-slo-status
make destroy-all
```

**Port-Adapter-DI 成立を示す独自検査** (Phase F に組み込み):

```bash
# Container 経由 DI のみで動作することを確認
grep -RE "request\.app\.state\.\w+" app/api/handlers/ && echo "VIOLATION"

# Adapter ファイルが 1 file 1 class
for f in app/services/adapters/*.py; do
  count=$(grep -c "^class " "$f")
  [ "$count" -gt 1 ] && echo "VIOLATION: $f has $count classes"
done

# Port ファイルが 1 file 1 Protocol (dataclass 例外あり)
for f in app/services/protocols/*.py; do
  count=$(grep -cE "^class \w+\(Protocol\)" "$f")
  [ "$count" -gt 1 ] && echo "VIOLATION: $f has $count Protocols"
done
```

---

## §4. 推奨実行順

1. **Phase A** (DI 整備) — 全 Phase の基盤、まず main.py を < 150 行に
2. **Phase B** (Port-Adapter 整備) — file 分割で Phase D/E の前提を作る
3. **Phase C** (Pipeline/ML Port 化) — MLOps 学習の核心、並行で C-1〜C-5 を分担可
4. **Phase D** (Service 層抽出)
5. **Phase E** (Domain) — 軽量に
6. **Phase F** (テスト/CI) — Phase A〜E 各々で随伴して進めるが、最後に網羅検証
7. **Phase G** (ドキュメント)

各 Phase は独立 PR にして、`make check` + `make check-layers` を merge gate にする。

---

## §5. 進捗

| Phase | 状態 | メモ |
|---|---|---|
| A-1 Composition root 分離 | ✅ | `app/composition_root.py` (Container + ContainerBuilder)。main.py 699 → 67 行 |
| A-2 FastAPI Depends 化 | ✅ | `app/api/dependencies.py`、handler は全 Depends 化。`request.app.state.getattr` 全廃 |
| A-3 テスト fixture | ✅ | `tests/conftest.py` (root) に `fake_settings` / `fake_container_factory` / `fake_container` / `fake_app` / `fake_client` を新設。各 adapter 用 fixture (`fake_encoder` / `fake_reranker` / `fake_candidate_retriever` / `fake_ranking_log_publisher` / `fake_feedback_recorder` / `fake_search_cache` / `fake_retrain_queries` / `fake_retrain_publisher`) も提供 |
| A-4 SDK lifecycle 集約 | ✅ | `GeminiGenerator.prepare()` / `VertexVectorSearchSemantic.prepare()` を新設し composition root から eager init。BQ client は ``ContainerBuilder._bigquery()`` で共有 (CandidateRetriever / SemanticSearch / RetrainQueries / PopularityScorer 全部) |
| A 検証 | TODO | テスト・検証は別日 |
| B-1 Protocol 分割 | ✅ | `candidate_retriever.py` を 3 Port + Domain Model 移送に分割 |
| B-2 Adapter 分割 | ✅ | `kserve_prediction.py` を `_kserve_common.py` + `kserve_encoder.py` + `kserve_reranker.py` に。`candidate_retriever.py` を `_pubsub_diagnostics.py` + `bigquery_candidate_retriever.py` + `pubsub_ranking_log_publisher.py` + `pubsub_feedback_recorder.py` に。`semantic_search.py` を `bigquery_semantic_search.py` + `vertex_vector_search_semantic.py` に。旧 file は thin re-export shim で backward compat 維持 |
| B-3 fakes/ 分離 | ✅ | `app/services/fakes/` 5 file。adapters/__init__.py から fake 系 export を transitional re-export 化 |
| B-4 型安全化 | ✅ | `app/services/protocols/_types.py` に `LexicalResult` / `SemanticResult` NamedTuple 新設。`LexicalSearchPort` / `SemanticSearchPort` / `CandidateRetriever` を `SearchFilters` (TypedDict) + NamedTuple 戻り値型に。`MeilisearchLexical` / `BigQuerySemanticSearch` / `VertexVectorSearchSemantic` / `AgentBuilderLexicalRetriever` adapter を NamedTuple 構築側に更新 |
| C-1 ml/training/ Port | ✅ | `ports/{ranker_trainer,ranker_model}.py` + `adapters/lightgbm_trainer.py`。`trainer.py` の orchestration 移行は別タスク |
| C-2 ml/registry/ Port | ✅ | `ports/model_registry.py` + `adapters/vertex_model_registry.py` |
| C-3 ml/serving/ Port | ✅ | `ports/predictor_service.py` + `adapters/kserve_predictor.py` (client-side)。server-side encoder/reranker.py はそのまま |
| C-4 ml/streaming/ Port | ✅ | `ports/stream_processor.py` + `adapters/dataflow_processor.py` |
| C-5 pipeline/<job>/ Port | ✅ | training_job が canonical (Port + KFPOrchestrator)、他 3 job は re-export |
| D-1 Service クラス化 | ✅ | `SearchService` / `FeedbackService` / `RagService` 新設、Container に統合 |
| D-2 Handler 分割 | ✅ | `app/api/handlers/` に 6 router (各 < 40 行) |
| D-3 Mapper 層 | ✅ | `app/api/mappers/search_mapper.py` |
| E-1 app/domain/ | ✅ | `Candidate` / `RankedCandidate` / `SearchFilters` / `SearchInput` / `SearchOutput` / `SearchResultItem` |
| F-1 tests/fakes/ | ✅ | 12 件の test double を `tests/fakes/` に配置 (`StubEncoderClient` / `MockRerankerClient` / `InMemoryCandidateRetriever` / `InMemoryRankingLogPublisher` / `InMemoryFeedbackRecorder` / `InMemoryLexicalSearch` / `InMemorySemanticSearch` / `StubPopularityScorer` / `StubGenerator` / `StubRetrainQueries` / `MockPredictionPublisher` / `InMemoryCacheStore`)。命名規約 (`Stub*` 固定 / `Mock*` 呼び出し記録 / `InMemory*` 状態あり) を `__init__.py` で明文化 |
| F-2 layers.py 自動化 | ✅ | `DIRECTORY_RULES` + `EXCLUSIONS` + `find_rules_for_file` + `discover_files` を実装。Port / Domain / Service / Handler / Mapper / Fake / `ml/<feature>/ports/` / `pipeline/<job>/ports/` を directory rule で網羅。`composition_root.py` / `app/main.py` / `tests/` は EXCLUSIONS。test_import_boundaries.py を `discover_files()` ベースに更新。`make check-layers` = **51 files clean** |
| F-3 テスト追加 | ✅ | service 層 / handler HTTP / mapper / ml / pipeline で計 9 file 追加 (test_search_service / test_feedback_service / test_rag_service / test_search_handler_http / test_feedback_handler_http / test_health_handler / test_search_mapper / test_lightgbm_trainer_adapter / test_kfp_orchestrator)。実行は別日 (user 指示) |
| G-1 本ドキュメント更新 | ✅ | 進捗反映済 |
| G-2 01_仕様と設計.md 更新 | ✅ | §4 を Port-Adapter-DI 章に書き換え |
| G-3 03_実装カタログ.md 更新 | ✅ | §2.6 を新構造で書き直し、§2.3 / §2.4 に ports/adapters の新規行追加 |
| G-4 CLAUDE.md 更新 | ✅ | "Port / Adapter / DI 境界と make check" を Container DI ベースに改訂 |
