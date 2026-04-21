#!/usr/bin/env bash
source "$(dirname "$0")/../core.sh"

step "Starting API server on port 8000"
docker compose up --build api
