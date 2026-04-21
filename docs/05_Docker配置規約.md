# Docker 配置規約（Phase1-4 共通）

この文書は `study-gcp-mlops` 全体で Dockerfile の配置・命名・役割を統一するための規約。

## 1. 目的

- Phase 間で Dockerfile の配置ゆれをなくす
- 「どこに何の Dockerfile があるか」を即判別できるようにする
- CI/CD の参照先を固定し、移行時の参照切れを防ぐ

## 2. 標準ディレクトリ

- **Service 用**: `infra/run/services/<service_name>/Dockerfile`
- **Job 用**: `infra/run/jobs/<job_name>/Dockerfile`

`<service_name>` / `<job_name>` はスネークケースで管理し、実リソース名との対応を文書化する。

## 3. 命名規則

- Dockerfile 名は原則 **`Dockerfile` 固定**
- `Dockerfile.api` / `Dockerfile.trainer` のような接尾辞付き命名は **legacy 扱い**

## 4. Phase ごとの運用方針

- **Phase4**: 完全準拠（`infra/run/services/*/Dockerfile`, `infra/run/jobs/*/Dockerfile`）
- **Phase3**: API は準拠済（`infra/run/services/search_api/Dockerfile`）。Job は `infra/run/jobs/*.Dockerfile` から `<job_name>/Dockerfile` へ段階移行対象
- **Phase2**: 準拠済（`infra/run/services/search_api/Dockerfile`）
- **Phase1**: 互換維持のため legacy 許容（`Dockerfile.api`, `Dockerfile.trainer`）

## 5. CI/CD 参照ルール

- workflow / cloudbuild は必ず `infra/run/**/Dockerfile` を参照する
- legacy 参照（`app/Dockerfile`, `Dockerfile.*`）が残る場合は、移行期限を docs に明記する

## 6. 最低限の Dockerfile 要件

- `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1` を設定
- 非 root 実行（可能な範囲で）
- 実行エントリーポイントは `CMD` で明示
- 依存解決は lock / requirements と整合させる

## 7. チェック運用

リポジトリルートで以下を実行:

```bash
python3 tools/check_docker_layout.py
```

このチェックは以下を検証する:

- Phase2/3/4 の required Dockerfile が規約パスに存在すること
- 定義外の `.Dockerfile` 接尾辞ファイルが紛れ込んでいないこと

## 8. 今後の移行ターゲット

- Phase3 jobs: `infra/run/jobs/embedding/Dockerfile` / `training.Dockerfile` → `infra/run/jobs/<job_name>/Dockerfile`
- Phase1: `Dockerfile.api`, `Dockerfile.trainer` は学習用 legacy として維持（削除しない）
