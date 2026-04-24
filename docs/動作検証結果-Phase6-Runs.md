# Phase 6 検証ログ（Run 1-2）

更新日: 2026-04-24
対象: `6/study-hybrid-search-pmle`
参考: [動作検証結果.md](./動作検証結果.md) の Phase 6 セクション

---

## Run 1: 細かくトライアンドエラー方針での段階実行

**実施日**: 2026-04-24  
**方針**: 
- `deploy-all` は使わず、各 step を分解して個別 make target で回す
- エラー発生時は複数候補ログを仕込む
- 所要時間を記録
- **成功条件**: LightGBM + ME5 + MeiliSearch 3 成分すべてが寄与する hybrid 検索

### 変更 1: `ops-deploy-monitor` の汎用化

`scripts/local/deploy_monitor.py` を拡張:
- `argparse.REMAINDER` で任意コマンドを受け取り
- `--label` でラベル付け可
- ログは `logs/deploy-monitor/<UTC>-<label>-monitor.log` に保存

### 変更 2: 開始時点の GCP リソース棚卸し

Run 9 (destroy 後) の partial state:
- Cloud Run `search-api`: ✅ 起動中だが `/search` は 500
- Cloud Run `meili-search`: ✅ 起動中、`/health` → `available`
- BQ datasets: ✅ `mlops` / `feature_mart` / `predictions` 全て存在
- Vertex Model Registry: ✅ version 登録済
- **Vertex Endpoints**: ❌ **ゼロ件** — root cause
- GCS buckets: ⚠️ 存在するが中身は空（artifact 不在）
- Secret Manager: `doppler-service-token` / `wandb-api-key` のみ

### `/search` 500 の root cause

```
404 Endpoint projects/mlops-dev-a/locations/asia-northeast1/endpoints/property-encoder-endpoint is not found.
```

Search-api 側のコードは無傷、Vertex endpoint を再作成するだけで復旧する見込み。

### Run 1 実行順序と所要時間

| # | step | コマンド | 所要時間 | 結果 |
|---|---|---|---|---|
| a | baseline-lint | `make tf-validate` | 7.6s | ✅ |
| b | baseline-check | `make check` | 30.8s | ⚠️ 255 passed / 1 failed (既知 parity drift) |
| c | seed-test | `make seed-test` | 19.5s | ✅ BQ に 5 行 INSERT |
| d | train-smoke-persist | `make train-smoke-persist` | 17.7s | ✅ ndcg@10=0.9804 |
| e | encoder-assets-upload | encoder assets upload | ~60s | ✅ Phase 5 cache reuse |
| f | ranker-model-upload | `gsutil cp` model.txt | 1s | ✅ |
| g | encoder-endpoint-deploy | `setup_encoder_endpoint --apply` | **~22 min 34 sec** | ✅ |
| h | reranker-endpoint-deploy | reranker deploy (並列) | **~18 min 14 sec** | ✅ |
| i | meili-sync-job | `gcloud run jobs execute` | 26.5s | ✅ 5 件 upsert |
| j | ops-enable-search | search-api env 注入 | 28 sec | ✅ |
| k | ops-livez | health check | 3 sec | ✅ |
| l | ops-search-components (1) | 初回 | 8 sec | ❌ HTTP 500 (IAM drift) |
| m | IAM 応急処置 | `gcloud pubsub add-iam` | 2 sec | ✅ |
| n | ops-search-components (2) | 2 回目 | 6.2 sec | ✅ **PASS** 🎉 |
| o | ops-accuracy-report | 20 ケース | 49.9 sec | ✅ **全 1.0** |

### /search レスポンス例

クエリ: "新宿区西新宿 1LDK"

```
p001 final_rank=1 lexical_rank=1     semantic_rank=4  me5_score=0.0138 score=-0.0797
p002 final_rank=2 lexical_rank=10000 semantic_rank=1  me5_score=0.0525 score=-0.1062
p004 final_rank=3 lexical_rank=10000 semantic_rank=2  me5_score=0.0291 score=-0.1062
p005 final_rank=4 lexical_rank=10000 semantic_rank=3  me5_score=0.0144 score=-0.1062
```

- p001: Meilisearch + ME5 + LightGBM 全経路
- p002/p004/p005: semantic で候補化、reranker score 付

### Run 1 教訓

- **Phase 5 の 1.1 GB encoder cache reuse で encoder-assets-upload を 60 秒に圧縮**
- **Vertex Endpoint.deploy 並列化で 40-50 min → 22-23 min に圧縮**
- **destroy → restore を個別 script で実行可能** — deploy-all 不要
- **非対称な IAM drift ポイント** — `api_publish_feedback` だけ apply 済で `ranking_log` / `retrain` は未 apply
- **成功条件は `ops-search-components` で初めて確定** — `/livez` 200 では不十分

### Run 1 で作成した一時ファイル / 副産物

| 種別 | パス | 後始末 |
|---|---|---|
| 一時 python | `/tmp/phase6-deploy-reranker.py` | 恒久化するなら `scripts/local/setup/setup_reranker_endpoint.py` に昇格 |
| smoke モデル | `/tmp/hybrid-search-cloud-smoke-model.txt` | Run 2 以降は true train 出力を使用 |
| GCS artifact | `gs://mlops-dev-a-models/encoders/...` (1.04 GiB) | destroy 時に一括 wipe |
| Vertex 常時課金 | encoder/reranker endpoint (n1-standard-2) | 学習終了時 `make destroy-*` で coast-down |

### Run 1 宿題（未実施）

1. **IAM 部分 drift**: ranking-log / retrain publishers の TF 宣言 apply なぜ失敗したのかを追跡
2. **reranker registration スクリプト**: `register_model.py` を pipeline 不要で実行可能にする `setup_reranker_endpoint.py` 作成
3. **ops-monitor-lro profile**: Vertex Endpoint deploy の 15-20 min 沈黙で stall-warning がスパムする
4. **destroy-phase6-learning target**: 常時課金の endpoint + GCS 1 GB assets を一発 destroy
5. **Vertex Pipelines 真実行**: smoke 5.2 KiB では rerank score が均一。本物 Booster で差別化スコア実現

---

## Run 2: deploy-all / destroy-all / run-all の往復検証 (中断)

**実施日**: 2026-04-24 11:33-12:00 UTC  
**背景**: User 指示「phase06 の destroy-all, deploy-all, run-all 検証依頼」

### タイムライン

| # | 時刻 (UTC) | 操作 | rc | 所要 | 結果 |
|---|---|---|---|---|---|
| 1 | 11:33-11:34 | `make destroy-all` | 0 | **67 sec** | ✅ Endpoint 残存 bug 検出 |
| 2 | 11:35 | 手動 endpoint 掃除 | 0 | 6 sec | ✅ endpoint 2 本削除 |
| 3 | 11:35-11:40 | `make ops-deploy-monitor` (deploy-all) | 1 | 5 min | ❌ step 6/7 SLO 72h 制限違反 |
| 4 | — | `modules/slo/main.tf` 修正 | — | — | ✅ 259200s → 86400s |
| 5 | 11:46-11:54 | 2 回目 deploy-all | — | ~8 min | ⚠️ step 7 で `.cache` archive stall → **User 中断** |
| 6 | 11:54 | `terraform force-unlock` | 0 | — | ✅ stale lock 解除 |
| 7 | ~12:00 | destroy-all 再走行 (monitor 越し) | 2 | 途中 | ❌ monitor crash (stale build_id) |
| 8 | — | `deploy_monitor._build_describe` 修正 | — | — | ✅ |
| 9 | 12:00-12:01 | `make destroy-all` (5 回目) | 0 | **49 sec** | ✅ 完走 |

### 検出した Phase 6 固有バグ 3 件

**(B1) SLO module: burn-rate alert 窓が 72h で GCP 制限 (24h) 違反**

- `modules/slo/main.tf:127, 173` の `"259200s"` が GCP 上限超過
- 修正: `259200s` → `86400s`、display_name `/3d` → `/1d`
- tf-validate + tf-fmt PASS

**(B2) destroy-all の Vertex endpoint undeploy が display-name ↔ id で skip**

- Run 1 で `setup_encoder_endpoint.py` が作った endpoint は numeric id を resource name として持つ
- destroy-all は display-name で describe → NOT_FOUND → skip → endpoint 残存
- 応急処置: `gcloud ai endpoints undeploy-model + delete` で手動削除
- 恒久修正案: display_name → numeric id 解決を追加 (Run 3 宿題)

**(B3) destroy-all の PROTECTED_TABLE_TARGETS が Phase 6 新規テーブル未網羅**

- Phase 6 で追加された `properties_enriched` (T8) と `ranking_log_hourly_ctr` (T2) が抜けていた
- 結果 deletion_protection が false に落ちず destroy-all が fail
- 修正: 2 エントリ追加。結果: 5 回目 destroy-all が 49 秒でクリーン完走 ✅

**(B4) deploy_monitor の `_build_describe` が stale build_id で crash**

- 旧 session の build_id で `gcloud builds describe` が NOT_FOUND
- monitor が CalledProcessError で落ちるため wrap している destroy-all も中断
- 修正: `check=False` + `returncode != 0 → ("", "")`

### Run 2 成果

- **3 件の本番バグを顕在化**、3 件を恒久修正 (B1/B3/B4)
- destroy-all = **~50-70 秒**、deploy-all = **最低 5 分**
- **Run 3 で要対応**: B2 (undeploy display-name → numeric id)、`.gcloudignore` に `.cache/` 追加 (Run 2 B5)

### Run 2 の後始末

- User 指示「いったん中止」で BG deploy-all 停止
- `terraform force-unlock` で stale lock 解除
- 5 回目 destroy-all で B3 バグ修正してから走らせ、49 秒でクリーン完了
- 最終状態 = 「tfstate bucket + cloudbuild sources + vertex bucket のみ」の真っ新状態
