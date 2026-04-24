#!/usr/bin/env bash
# docker compose up の前に、Phase 2 が使うホストポートを占有しているコンテナを停止する。
#
# 対象ポート: 8000 (api) / 5432 (postgres) / 5050 (pgadmin) / 7700 (meilisearch) / 6379 (redis)
#
# - 自分のコンテナ (real-estate-*) は docker compose 側で扱うので対象外
# - それ以外のコンテナは停止に加えて強制削除し、固定 container_name 衝突も残さない
# - ホストプロセスがポートを掴んでいる場合はコンテナ起因ではないため警告のみ
#
# 使い方: `make ports-free` または直接 `./scripts/local/setup/free_ports.sh`
set -euo pipefail

PORTS=(8000 5432 5050 7700 6379)
OWN_NAME_PREFIX="real-estate-"

stop_conflicting_containers() {
  local port="$1"
  local stopped_any=0
  local entries
  entries="$(docker ps --format '{{.ID}}|{{.Names}}|{{.Ports}}' || true)"
  [ -z "$entries" ] && return 0

  while IFS='|' read -r cid name ports; do
    [ -z "$cid" ] && continue
    [[ "$ports" == *":${port}->"* ]] || continue
    if [[ "$name" == ${OWN_NAME_PREFIX}* ]]; then
      echo "[skip] port ${port}: own container '${name}' (docker compose が管理)"
      continue
    fi
    echo "[remove] port ${port}: removing '${name}' (${cid:0:12})"
    docker rm -f "$cid" >/dev/null
    stopped_any=1
  done <<< "$entries"
  return $stopped_any
}

check_host_port() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    local in_use
    in_use="$(ss -Htln "sport = :${port}" 2>/dev/null || true)"
    if [ -n "$in_use" ]; then
      echo "[warn] port ${port}: host process still listening (非 docker プロセス)。必要に応じて手動で停止してください"
      echo "       $(echo "$in_use" | head -1)"
    fi
  fi
}

for port in "${PORTS[@]}"; do
  stop_conflicting_containers "$port" || true
  check_host_port "$port"
done

echo "[done] ports checked: ${PORTS[*]}"
