# API Module

FastAPI ベースの公開入口。検索 API とフィードバック API を公開する。

## Responsibilities

- `main.py`: FastAPI アプリ生成と router 登録
- `routes/search.py`: 検索条件を受け取り、検索実行結果を返す
- `routes/feedback.py`: click / favorite / inquiry のフィードバックを受け取り反映する

## Routes

- `GET /health`: ヘルスチェック
- `GET /search`: Meilisearch + ME5 + LightGBM rerank による検索
- feedback route: 検索結果に対する行動ログ反映

## Dependency Flow

- `routes/search.py` → `src.search.query_builder`
- `routes/search.py` → `src.search.search_service`
- `routes/feedback.py` → `src.infra.repositories.engagement`

## Notes

- 検索 backend 障害時は `502 Search backend unavailable` を返す
- `/search` は `candidate_limit` で Meili 候補数、`limit` で最終返却件数を制御する
