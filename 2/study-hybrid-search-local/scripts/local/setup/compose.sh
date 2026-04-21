#!/usr/bin/env bash
# docker compose ラッパー — env/secret/credential.yaml を読み、
# キー名を大文字化して環境変数に export してから docker compose を起動する。
# 期待する YAML は flat な key: value のみ（ネスト・リスト非対応）。
#
# 使い方: Makefile から `$(DOCKER_COMPOSE) up -d` のように呼び出す。
set -euo pipefail
cd "$(dirname "$0")/.."

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
exec docker compose "$@"
