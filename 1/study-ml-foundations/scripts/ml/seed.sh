#!/usr/bin/env bash
source "$(dirname "$0")/../core.sh"

step "Seeding PostgreSQL"
docker compose run --rm --build seed
