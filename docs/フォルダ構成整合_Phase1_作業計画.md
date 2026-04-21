# フォルダ構成整合 — Phase 1 作業計画（未実行）

**作成日**: 2026-04-21
**対象**: `1/study-ml-foundations/`
**軸**: `4/study-hybrid-search-vertex/`
**状態**: 🔴 **未実行**（permission check で実行前停止、User の override 確認待ち）

---

## 1. 経緯と User 要望

### User 要望（2026-04-21）

> できるだけ同じフォルダ構成にしたい
> 少なくともトップディレクトリは同じフォルダ名
> 4/study-hybrid-search-vertex を軸にして 1 を調整依頼

### 既存設計ドキュメントとの関係

先行の `フォルダ構成整合_作業設計.md` §5.4 では **Phase 1 の src 再編は skip** と記載していた:

> **Phase 1 の src 再編**
> - `src/ml/{pipeline,trainer,evaluation}/` は教材の章立てと 1:1。再編は教材の全面書き直しを意味する
> - Phase 4 の `app/common/jobs/pipelines` とは設計思想が違う

**本計画はこの推奨を意図的に override する**。User が明示的に Phase 1 の整合を要求したため。

---

## 2. 実行可否の決定待ち事項（Blocker）

実行前に以下 2 点の User 確認が必要:

1. **教材のコードパス参照まで直すスコープでよいか**
   - `docs/教育資料/01_スライド.md` / `docs/教育資料/制作メモ/02_スライド要約.md` 内のコードサンプル冒頭のパスコメント（`# src/ml/pipeline/preprocess.py（抜粋）` 等）も新パスに更新するか
2. **撮影済デモ動画（もしあれば）内のパス参照は放置してよいか**
   - 教材テキストは更新できても、収録済のナレーションやスクリーンキャプチャに映る `src/ml/...` は巻き戻せない

上記 2 点が解決するまで本計画は **実行しない**。

---

## 3. 最終的な目標構造

### Before（現状）

```
1/study-ml-foundations/
├── CLAUDE.md / Makefile / README.md
├── Dockerfile.api / Dockerfile.trainer / docker-compose.yml
├── pyproject.toml
├── data/                  ← 保持
├── models/                ← 保持
├── docs/                  ← 保持
├── env/{config,secret}/   ← 保持
├── scripts/{api,ml}/      ← 保持
├── src/
│   ├── api/               ★ 移動対象
│   ├── ml/                ★ 移動対象
│   └── share/             ★ 移動対象
└── tests/                 ← 保持
```

### After（Phase 4 整合後）

```
1/study-ml-foundations/
├── CLAUDE.md / Makefile / README.md
├── Dockerfile.api / Dockerfile.trainer / docker-compose.yml
├── pyproject.toml
├── app/                   ★ 新規（← src/api/）
├── common/                ★ 新規（← src/share/）
├── jobs/                  ★ 新規
│   └── ml/                ★ 新規（← src/ml/、ml/ 階層は教材互換性のため保持）
│       ├── pipeline/
│       ├── trainer/
│       └── evaluation/
├── data/                  ← 保持（Phase 1 固有）
├── models/                ← 保持（Phase 1 固有）
├── docs/                  ← 保持
├── env/                   ← 保持
├── scripts/               ← 保持
└── tests/                 ← 保持（分割せず top-level のまま）
```

### Phase 4 との top-level dir 名対応表

| Phase 4 | Phase 1 After | 備考 |
|---|---|---|
| `app/` | `app/` | ✓ 一致（中身は Phase 1 は flat、Phase 4 は `app/src/app/` 2 段ネスト） |
| `common/` | `common/` | ✓ 一致（同上） |
| `jobs/` | `jobs/` | ✓ 一致（同上） |
| `pipelines/` | — | Phase 4 固有（Vertex KFP）、Phase 1 に不要 |
| `functions/` | — | Phase 4 固有（Cloud Function）、Phase 1 に不要 |
| `definitions/` | — | Phase 4 固有（Dataform）、Phase 1 に不要 |
| `infra/` | — | Phase 4 固有（Terraform）、Phase 1 に不要 |
| `monitoring/` | — | Phase 4 固有、Phase 1 に不要 |
| `docs/` / `env/` / `scripts/` / `tests/` | 既に一致 | — |
| — | `data/` / `models/` | Phase 1 固有（Docker volume / artifact versioning 教材用途） |

---

## 4. 作業ステップ（順序固定、Makefile 連動）

### Step 1: ディレクトリ作成と移動

```bash
cd /home/ubuntu/repos/study-gcp-mlops/1/study-ml-foundations

mkdir -p app jobs common

mv src/api/* app/
mv src/api/.* app/ 2>/dev/null  # dotfiles があれば
mv src/ml jobs/ml
mv src/share/* common/
mv src/share/.* common/ 2>/dev/null

rm -rf src/__pycache__
rmdir src/
```

### Step 2: Python import の全面 rewrite

以下 3 系統を全 Python ファイルで rewrite:

| Before | After |
|---|---|
| `from api.xxx` / `import api.xxx` | `from app.xxx` / `import app.xxx` |
| `from ml.xxx` / `import ml.xxx` | `from jobs.ml.xxx` / `import jobs.ml.xxx` |
| `from share.xxx` / `import share.xxx` | `from common.xxx` / `import common.xxx` |
| `from share import X` | `from common import X` |

**対象ファイル**（`src/` 内 + `tests/` 内、移動後のパスで列挙）:

```
app/main.py                (← src/api/main.py)
app/config.py              (← src/api/config.py)
jobs/ml/pipeline/main.py
jobs/ml/pipeline/config.py
jobs/ml/pipeline/repository.py
jobs/ml/pipeline/preprocess.py
jobs/ml/pipeline/feature_engineering.py
jobs/ml/pipeline/seed.py
jobs/ml/trainer/train.py
jobs/ml/evaluation/config.py
jobs/ml/evaluation/metrics.py
jobs/ml/evaluation/tracking.py
common/__init__.py
common/config.py
common/logging.py
common/schema.py
common/run_id.py

tests/api/test_api.py
tests/ml/test_evaluation.py
tests/ml/test_pipeline.py
tests/ml/test_trainer.py
tests/conftest.py (あれば)
```

### Step 3: `pyproject.toml` 更新

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]   # ← ["src"] から変更
```

### Step 4: `Dockerfile.api` 更新

```dockerfile
# Before:
# COPY src/ src/
# ENV PYTHONPATH=src
# CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

# After:
COPY app/ app/
COPY common/ common/
ENV PYTHONPATH=/app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Step 5: `Dockerfile.trainer` 更新

```dockerfile
# Before:
# COPY src/ src/
# ENV PYTHONPATH=src
# CMD ["python", "-m", "ml.pipeline.main"]

# After:
COPY jobs/ jobs/
COPY common/ common/
ENV PYTHONPATH=/app
CMD ["python", "-m", "jobs.ml.pipeline.main"]
```

### Step 6: `docker-compose.yml` 更新

```yaml
# Before:
#   seed:
#     command: ["python", "-m", "ml.pipeline.seed"]

# After:
  seed:
    command: ["python", "-m", "jobs.ml.pipeline.seed"]
```

### Step 7: `scripts/clean.sh` 更新

```bash
# Before:
# if [ -d models ] || [ -d src/ml/wandb ]; then
#   docker run --rm \
#     -v "$(pwd)/models:/work/models" \
#     -v "$(pwd)/src/ml:/work/ml" \
#     alpine sh -c "rm -rf /work/models/* /work/ml/wandb" 2>/dev/null || true
# fi

# After:
if [ -d models ] || [ -d jobs/ml/wandb ]; then
  docker run --rm \
    -v "$(pwd)/models:/work/models" \
    -v "$(pwd)/jobs/ml:/work/ml" \
    alpine sh -c "rm -rf /work/models/* /work/ml/wandb" 2>/dev/null || true
fi
```

### Step 8: ドキュメント更新

#### `README.md`（L48-52 の path 表を更新）

```markdown
| `app/`              | FastAPI 推論 API + Jinja2 フロントエンド |
| `jobs/ml/pipeline/` | データパイプライン + オーケストレーション (エントリーポイント) |
| `jobs/ml/trainer/`  | LightGBM 学習アルゴリズム |
| `jobs/ml/evaluation/` | 精度評価 (RMSE, R²) + W&B 実験ログ |
| `common/`           | 共通定義 (特徴量カラム, 設定ベースクラス, ロギング, Run ID 生成) |
```

#### `CLAUDE.md`

- 「Architecture」節のフロー図を新パスに書き換え
- 「Source Layout」節を新ツリーで書き直し:

```
app/                 推論API
├── main.py
├── config.py
├── templates/
├── static/

common/              共通
├── __init__.py
├── config.py
├── logging.py
├── schema.py
└── run_id.py

jobs/
└── ml/
    ├── pipeline/    データパイプライン + オーケストレーション
    ├── trainer/     学習アルゴリズム
    └── evaluation/  評価・実験ログ

tests/
├── api/             app のテスト
└── ml/              jobs のテスト
```

- `CMD ["python", "-m", "ml.pipeline.main"]` の記述を `jobs.ml.pipeline.main` に

#### `docs/01_仕様と設計.md`

- L23-32 のパッケージ構成図を新ツリーに
- L136 の `src/ml/trainer/train.py` → `jobs/ml/trainer/train.py`

#### `docs/03_実装カタログ.md`

L7, L16, L27, L33, L41 の 5 セクション見出しを更新:

```
### common/ — 共通定義              （← src/share/）
### jobs/ml/pipeline/ — データパイプライン + オーケストレーション
### jobs/ml/trainer/ — 学習アルゴリズム
### jobs/ml/evaluation/ — 評価・実験ログ
### app/ — 推論 API                 （← src/api/）
```

#### `docs/04_運用.md`

- L77, L82, L87 の `src/ml/...` → `jobs/ml/...`

#### `docs/教育資料/01_スライド.md`

- L208 のコードコメント `# src/ml/pipeline/preprocess.py（抜粋）` → `# jobs/ml/pipeline/preprocess.py（抜粋）`

#### `docs/教育資料/制作メモ/02_スライド要約.md`

- L130 の同様コメント

---

## 5. 検証ステップ（実行後に必ず走らせる）

```bash
cd /home/ubuntu/repos/study-gcp-mlops/1/study-ml-foundations

# 1. 旧パスが消えたことを確認
grep -rn "from api\|from ml\|from share\|import api\|import ml\b\|import share\b" . \
  --include="*.py" 2>&1 | grep -v "\.venv\|__pycache__" | \
  (! grep -q . && echo "OK: no stale imports" || echo "FAIL: stale imports found")

grep -rn "src/" . --include="*.md" --include="*.yml" --include="*.sh" \
  --include="Dockerfile*" --include="Makefile" 2>&1 | grep -v "\.venv\|\.git" | \
  (! grep -q . && echo "OK: no src/ refs" || echo "FAIL: src/ refs found")

# 2. Python で import が通るか
PYTHONPATH=. python -c "from app.main import app; print('app ok')"
PYTHONPATH=. python -c "from common.config import BaseAppSettings; print('common ok')"
PYTHONPATH=. python -c "from jobs.ml.pipeline.config import Settings; print('jobs ok')"

# 3. テストが走るか
make test

# 4. Docker ビルドが通るか
make build

# 5. E2E 疎通
make seed
make train
make serve &
curl http://localhost:8000/health
```

---

## 6. ロールバック戦略

Phase 1 は独立 Git リポジトリ（`1/study-ml-foundations/.git/`）。作業は必ず feature branch で実施:

```bash
cd /home/ubuntu/repos/study-gcp-mlops/1/study-ml-foundations
git checkout -b refactor/top-level-align-with-phase4
# ...作業...
# NG なら:
git checkout -
git branch -D refactor/top-level-align-with-phase4
```

---

## 7. リスク・懸念

| リスク | 深刻度 | 緩和策 |
|---|---|---|
| 教材の説明と実コードパスが食い違う（更新漏れ） | 高 | §8 チェックリスト全消化 |
| 撮影済デモ動画 / スクリーンショットのパスが古くなる | 中 | 動画は再撮影必要。画像は注釈を追記 |
| import path 変更で `wandb.init(project=...)` のパス依存が壊れる | 低 | W&B は project 名ベースなので影響小 |
| `pyproject.toml` 変更で `uv` / `pip` インストールが壊れる | 低 | Phase 1 は `pyproject.toml` を package 定義に使っていない（pytest のみ）ため影響小 |
| `from api.*` を他リポから import している箇所がある | 確認要 | Phase 1 は独立プロジェクト、外部依存は無いはず |

---

## 8. 完了チェックリスト

### ファイル移動
- [ ] `src/api/*` → `app/*`
- [ ] `src/ml/` → `jobs/ml/`
- [ ] `src/share/*` → `common/*`
- [ ] `src/` 削除

### Python
- [ ] 全 `.py` ファイルの `from api|ml|share` import を rewrite
- [ ] `pyproject.toml` pythonpath 更新

### Docker / compose
- [ ] `Dockerfile.api` の COPY / PYTHONPATH / CMD 更新
- [ ] `Dockerfile.trainer` の COPY / PYTHONPATH / CMD 更新
- [ ] `docker-compose.yml` の `seed` コマンド更新

### Scripts
- [ ] `scripts/clean.sh` の `src/ml/wandb` パス更新
- [ ] `scripts/ml/seed.sh` / `scripts/ml/train.sh` / `scripts/api/serve.sh` は影響なし（docker compose 経由）

### ドキュメント
- [ ] `README.md` L48-52 の path 表
- [ ] `CLAUDE.md` の Architecture + Source Layout 節
- [ ] `docs/01_仕様と設計.md` のパッケージ構成図 + L136
- [ ] `docs/03_実装カタログ.md` の 5 セクション見出し
- [ ] `docs/04_運用.md` の wandb 手順
- [ ] `docs/教育資料/01_スライド.md` L208
- [ ] `docs/教育資料/制作メモ/02_スライド要約.md` L130

### 検証
- [ ] `grep` で stale ref が 0 件
- [ ] `make test` PASS
- [ ] `make build` 成功
- [ ] `make seed && make train` で `models/latest/` が生成される
- [ ] `make serve` → `curl /health` 200
- [ ] 先行の `フォルダ構成整合_作業設計.md` §5.4 の「Phase 1 は対象外」記述を修正

---

## 9. 先行ドキュメントとの整合

本計画実行時に、`docs/フォルダ構成整合_作業設計.md` §5.4 の以下を修正する必要がある:

> Phase 1 は **フォルダ構成整合の対象外に近い**。教育資料 / env 配置は既に Phase 4 と同形。src/scripts/tests の大きな再編は教育用途に対して ROI が低い。

→

> Phase 1 は 2026-04-21 の User 要望により top-level 整合を実施（別計画 `フォルダ構成整合_Phase1_作業計画.md`）。

---

## 10. 参考

- 先行設計ドキュメント: `docs/フォルダ構成整合_作業設計.md`
- Phase 4 構造の詳細: 同 §2「Phase 4 基準構成（axis）」
