#!/usr/bin/env bash
# 共通設定 — 各スクリプトから source して使う
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[1]}")/.."

step() {
  echo "=== $1 ==="
}

# env/secret/credential.yaml を読み込み、大文字のキー名で環境変数に export する。
# docker-compose が postgres コンテナ等へ渡す ${POSTGRES_PASSWORD} 等の補間元になる。
# 期待する YAML は「flat key: value」のみ（ネスト・リスト非対応）。
load_credentials() {
  local yaml="env/secret/credential.yaml"
  [ -f "$yaml" ] || return 0
  local key val line
  while IFS= read -r line || [ -n "$line" ]; do
    [[ "$line" =~ ^[[:space:]]*$ ]] && continue
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*):[[:space:]]*(.*)$ ]]; then
      key="${BASH_REMATCH[1]}"
      val="${BASH_REMATCH[2]}"
      val="${val%%#*}"
      val="${val#"${val%%[![:space:]]*}"}"
      val="${val%"${val##*[![:space:]]}"}"
      [[ "$val" =~ ^\"(.*)\"$ ]] && val="${BASH_REMATCH[1]}"
      [[ "$val" =~ ^\'(.*)\'$ ]] && val="${BASH_REMATCH[1]}"
      export "${key^^}=$val"
    fi
  done < "$yaml"
}

load_credentials
