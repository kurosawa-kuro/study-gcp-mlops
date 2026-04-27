# scripts/

Makefile から呼ばれる補助 script の置き場。**Makefile は原則 1 行で対応 script を呼ぶだけ** にし、手続き的なロジックは全て `scripts/` 側に外出しする。

---

## 言語選択ルール (最優先)

> **原則 script は Python**。
> 但し、**文字列展開が全くない / 単純なコマンド羅列のみ** であれば shell script を許可。
> 結果として shell script は自然に皆無になる設計。

「文字列展開」の定義 (これらが 1 つでもあれば Python へ寄せる):

- 変数を文字列に埋め込む (`"foo-${VAR}-bar"` / `f"..."` / `printf`)
- JSON / YAML を組み立てる (`jq -n` / heredoc / format string)
- 条件分岐 / ループ / 関数定義
- パイプの中で `sed` / `awk` / `cut` で整形
- 外部コマンドの出力を変数にキャプチャして再利用 (`X=$(...)` の二段以上)
- パス計算 (`$(dirname ...)` / `realpath` / `Path(...).resolve()` 等)

Shell が許される具体例 (これだけ):

```bash
#!/usr/bin/env bash
set -euo pipefail
gcloud services enable serviceusage.googleapis.com bigquery.googleapis.com ...
```

```bash
#!/usr/bin/env bash
terraform -chdir=infra fmt -check -diff
```

これ以上のことをしたくなったら **Python に書き換える**。

---

## ディレクトリ構成

責務 (lifecycle stage) ごとにサブフォルダを切る。新規 script は **必ずどれかに属する**形で追加する。

```
scripts/
  README.md                          ← 本ファイル
  _common.py                         ← 共通 helper
  ci/                                ← 静的検査・境界チェック (layers.py / sync_dataform.py)
  setup/                             ← doctor / terraform bootstrap / pipeline setup / local_hybrid
  deploy/                            ← api_gke / kserve_models / monitor 等の deploy 系
  ops/                               ← livez/search/ranking/feedback/promote 等の運用コマンド
  bqml/                              ← BQML モデル学習 (Phase 6 T1)
  enrichment/                        ← 旧 Phase 6 T8 用ディレクトリ名の残骸。Phase 7 では未使用
  sql/                               ← BQ クエリ (`bq query < scripts/sql/X.sql`)
```

サブフォルダの役割境界:

| folder | 含めるもの | 含めないもの |
|---|---|---|
| `setup/` | 1 回だけ叩く / 開発環境前提を整える系。local hybrid stack 起動 helper もここ | 反復実行する run/ops |
| `deploy/` | image を build して Cloud Run revision を作る | runtime の HTTP 検査 (それは ops/) |
| `config/` | committed yaml/json から派生ファイルを生成 | 値そのものの変更 (それは env/config/setting.yaml) |
| `checks/` | repo 構造 / 命名 / 境界 / 静的解析 | 実行時の HTTP / DB 検査 (それは ops/) |
| `ops/` | デプロイ後の API / Job への HTTP / RPC 検査 | 構造検査 (それは checks/ や tests/) |
| `sql/` | 1 ファイル 1 SQL、`bq query` で叩く | Python ロジック |

`tests/` 側も同じ責務分割: `tests/arch/` (boundary tests) / `tests/parity/` (cross-file invariants) / `tests/infra/` (terraform / table / workflow shape)。

---

## Makefile 側の規約

- ターゲットは **1 行で script を呼ぶだけ** (`uv run python scripts/X.py` / `bash scripts/X.sh` / `bq query --project_id=$(PROJECT_ID) < scripts/sql/X.sql`)。
- Makefile に inline shell / heredoc / SQL define ブロックを書かない (出てきたら `scripts/` に移動)。
- ターゲット名と script ファイル名は対応させる (`make ops-livez` → `scripts/ops/livez.py`)。
- export している基本変数は `PROJECT_ID` / `REGION` / `API_SERVICE` / `ARTIFACT_REPO` / `VERTEX_LOCATION` / `PIPELINE_ROOT_BUCKET` / `PIPELINE_TEMPLATE_GCS_PATH`。script 側はこれらを env から受け取り、未指定時の既定値は `env/config/setting.yaml` から読む。
- 非秘密値は **`env/config/setting.yaml` が single source of truth**。Make は awk で、Python は `scripts/_common.py` と `ml.common.config.BaseAppSettings` でその yaml を読む。yaml を編集すれば両者に反映される (どちらか一方をハードコードで上書きしないこと)。
- 秘密値は **`env/secret/credential.yaml` または環境変数**。script 側では `scripts/_common.py::secret()`、app/ML 側では `BaseAppSettings` が読む。

---

## Python script の規約

| 項目 | 約束 |
|---|---|
| 実行コマンド | `uv run python scripts/X.py` (project の `.venv` を使う) |
| shebang | 任意 (uv 経由実行が前提なので付けても付けなくても可) |
| 構造 | `def main() -> int:` + `if __name__ == "__main__": raise SystemExit(main())` |
| 引数 | env var を **第一**、`argparse` を補助。`os.environ.get("PROJECT_ID", "mlops-dev-a")` のように既定値を持つ |
| 認証 | `subprocess.run(["gcloud", "auth", "print-identity-token"], ...)` で OIDC を取る (Cloud Run は `--no-allow-unauthenticated`) |
| 外部依存 | 標準ライブラリ (`urllib.request` / `subprocess` / `json`) を優先。requests / httpx 等の追加依存は持ち込まない |
| 終了コード | 成功 0、失敗 非 0 |
| 出力 | stdout に結果、エラーは stderr。最終行のサマリは 1 行 (例: `posted=3`) |
| Lint | `make check` の ruff / mypy 対象に入る (`pyproject.toml` の include に `scripts/**/*.py` が入っている前提) |

---

## Shell script (例外的に許される場合) の規約

例外で .sh を書く場合は以下を守る:

| 項目 | 約束 |
|---|---|
| shebang | `#!/usr/bin/env bash` |
| 安全フラグ | 先頭で `set -euo pipefail` |
| 行数 | **目安 5 行以内** (それ超は Python へ) |
| 文字列展開 | 一切しない (`${X}` 埋め込み、heredoc、$(...)、jq -n 全て不可) |
| 引数 | 位置引数を取らない |
| 実行権限 | `chmod +x` で committする |

---

## SQL ファイルの規約

- 1 ファイル 1 SQL。先頭コメントに **何のためのクエリか + 参照テーブルのスキーマ位置** (`infra/terraform/modules/data/main.tf::training_runs` 等) を書く。
- リテラル `mlops-dev-a` / `asia-northeast1` を直書きしてよい (本リポは単一プロジェクト前提、CLAUDE.md 非負制約)。
- 旧 California 残骸 (`predictions_log` / `metrics.rmse` / `validate_data_skew.sql`) を参照しない — schema は `infra/terraform/modules/data/main.tf` を権威とする。

---

## 新規 script を追加するとき

1. **言語を決める**: 文字列展開が 1 つでもあれば Python、ゼロなら shell。
2. **置き場所を決める**:
   - 開発環境セットアップ / Terraform → `scripts/setup/X.py`
   - local dev stack 起動 → `scripts/setup/local_hybrid.py`
   - デプロイ系 (Cloud Build → GKE rollout / KServe patch 等) → `scripts/deploy/X.py`
   - デプロイ後の運用 / API smoke → `scripts/ops/X.py`
   - BQ クエリだけ → `scripts/sql/X.sql`
3. 上記言語別規約に従って書く。
4. `Makefile` に対応するターゲットを **1 行で** 追加 (`X: ## description\n\tuv run python scripts/.../X.py`)。
5. `.PHONY` リストにターゲット名を追加。
6. `make help` に説明文が出ることを確認。

## 何を置かないか

- **本番ロジック**: `app/` / `ml/{data,training,serving,common}/` / `pipeline/` に置く。`scripts/` は thin wrapper のみ。
- **テスト**: `tests/` / `app/tests/` / `common/tests/` / `ml/{embed,train,serve,sync}/tests/` に置く。
- **使い捨ての一回 migration スクリプト**: 完了後に削除する (リポに残さない)。
- **別リポからのコピー**: そのまま置かない。本リポの API スキーマ・命名・依存に合わせて書き直すか削除する。

---

## 現在の状態 (2026-04-27 時点)

旧 shell 群は全て Python 化完了。`setup/` / `deploy/` / `ops/` / `ci/` / `bqml/` + `sql/` を主系統として使い、共通 helper は `scripts/_common.py` に集約している。local hybrid 起動は `scripts/setup/local_hybrid.py` が担当し、**非秘密値は `env/config/setting.yaml`、秘密値は `env/secret/credential.yaml` / Secret Manager** に責務分離した。Makefile からは `uv run python -m scripts.<folder>.<module>` で呼び出す。
