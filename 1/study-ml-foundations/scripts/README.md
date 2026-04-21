# scripts

Phase 3/4 の構成に寄せるため、`local/` 配下に標準入口を用意しています。

- `local/setup/` : seed/train などの準備系
- `local/deploy/` : API 起動系
- `local/ops/` : ローカル運用系
- `local/sql/` : SQL 置き場（Phase 1 は現状未使用）

呼び出しは `scripts/local/*` を正とします。
