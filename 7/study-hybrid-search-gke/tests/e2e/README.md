# E2E Tests

`tests/e2e/` は現状 placeholder で、pytest ベースの実 E2E はまだ持たない。

- 実運用に近い総合確認は `make run-all-core` が担う
- デプロイ後の smoke は `make run-all` / `make verify-all` から辿る
- このディレクトリに pytest を追加する場合は、ローカル完結ではなく GCP / GKE / KServe を前提にする理由を README に追記する
