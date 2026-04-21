#!/usr/bin/env bash
source "$(dirname "$0")/core.sh"

step "Cleaning"
# PostgreSQL ボリュームも含めて削除
docker compose down --remove-orphans --volumes 2>/dev/null || true

# Docker が root で作成したファイルをコンテナ経由で削除
if [ -d models ] || [ -d src/ml/wandb ]; then
  docker run --rm \
    -v "$(pwd)/models:/work/models" \
    -v "$(pwd)/src/ml:/work/ml" \
    alpine sh -c "rm -rf /work/models/* /work/ml/wandb" 2>/dev/null || true
fi

echo "Done."
