# AGENTS.md

## Purpose

Agent operating guide for this monorepo-style learning project.
Use this file for cross-phase behavior only; phase-specific details belong to each phase-local doc.

## Repository Shape

- This repository contains independent phases under `1/` through `7/`.
- Do not share implementation code across phases unless explicitly requested.
- Keep changes scoped to one phase whenever possible.

Primary navigation:
- [README.md](README.md)
- [CLAUDE.md](CLAUDE.md)
- [docs/README.md](docs/README.md)

## First Step For Any Task

1. Identify the target phase from the file path.
2. Read that phase's `CLAUDE.md` before editing code.
3. Prefer phase-local docs as source of truth when docs conflict.

Phase-local guides:
- [1/study-ml-foundations/CLAUDE.md](1/study-ml-foundations/CLAUDE.md)
- [2/study-ml-app-pipeline/CLAUDE.md](2/study-ml-app-pipeline/CLAUDE.md)
- [3/study-hybrid-search-local/CLAUDE.md](3/study-hybrid-search-local/CLAUDE.md)
- [4/study-hybrid-search-gcp/CLAUDE.md](4/study-hybrid-search-gcp/CLAUDE.md)
- [5/study-hybrid-search-vertex/CLAUDE.md](5/study-hybrid-search-vertex/CLAUDE.md)
- [6/study-hybrid-search-pmle/CLAUDE.md](6/study-hybrid-search-pmle/CLAUDE.md)
- [7/study-hybrid-search-gke/CLAUDE.md](7/study-hybrid-search-gke/CLAUDE.md)

## Command Conventions

- Start in the target phase directory before running `make`.
- Use `make help` first in each phase.
- Command vocabulary and phase support matrix: [docs/Makefile.md](docs/Makefile.md).

Validation expectations:
- Phase 1-2: usually `make test`.
- Phase 3: `make test` plus layer/pipeline checks when relevant.
- Phase 4-7: `make check` (lint/format/type/test equivalent).

## Non-Negotiable Constraints

- For phases 3-7, keep the hybrid-search foundation intact: LightGBM + multilingual-e5 + Meilisearch.
- Any replacement/removal of core retrieval/ranking components requires explicit user approval.
- Phase 6 keeps `/search` default behavior aligned with Phase 5; new PMLE features should be opt-in.

Canonical references:
- [README.md](README.md)
- [CLAUDE.md](CLAUDE.md)
- [docs/01_仕様と設計.md](docs/01_仕様と設計.md)
- [docs/03_実装カタログ.md](docs/03_実装カタログ.md)
- [docs/04_運用.md](docs/04_運用.md)
- [docs/05_Docker配置規約.md](docs/05_Docker配置規約.md)

## Documentation Rules

- Link to existing docs instead of duplicating long policy text.
- Treat root docs as navigation/hubs; treat phase-local docs as operational source of truth.
- Archive/history lives under [docs/archive/README.md](docs/archive/README.md).

## Guardrails

- Do not edit archive or legacy material unless asked.
- Do not perform broad multi-phase refactors by default.
- For root-level doc updates, keep terminology synchronized with phase docs.

## Existing Chat Customizations

- Custom agent: [.github/agents/gcp-mlops-theme-research.agent.md](.github/agents/gcp-mlops-theme-research.agent.md)
- Custom skill: [.github/skills/phase-doc-sync/SKILL.md](.github/skills/phase-doc-sync/SKILL.md)

Use them when tasks match their scope; otherwise follow this AGENTS guide and phase-local instructions.
