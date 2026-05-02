# E2E Tests

`tests/e2e/` は **opt-in live acceptance gate** を置く場所。

- 常時 CI で回す structural / workflow contract は `tests/integration/` に置く
- ここは GCP / GKE / KServe を前提にする **破壊的または高コスト** な acceptance のみ
- `test_phase7_acceptance_gate.py` は `destroy-all -> deploy-all -> canonical ConfigMap -> ops-search-components -> VVS -> FOS -> feedback -> ranking -> accuracy`
  を 1 本で叩く opt-in gate。`RUN_LIVE_GCP_ACCEPTANCE=1` が無ければ skip する
- 実運用に近い総合確認コマンドは引き続き `make run-all-core` / `make run-all` が担う
