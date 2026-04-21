#!/usr/bin/env bash
source "$(dirname "$0")/../core.sh"

step "Training"
docker compose run --rm --build trainer
