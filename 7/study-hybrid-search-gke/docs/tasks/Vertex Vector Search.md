## 結論

**「persistent stack に GCS embedding archive + Index Endpoint だけ destroy / Index は維持」のハイブリッド構成が最適解。deploy 時間を 27分 → 10-12分 に短縮しつつ、維持コストを ¥約30/月 に抑え込めます。**

ポイントは **「Index は無料で残せる、Index Endpoint(replica)が課金される」** という Vector Search の課金構造を突くこと。ここが鍵です。

---

## 理由## 重要な発見:課金構造の非対称性

公式情報から以下が確定しました:

```text
[課金されるもの]
- Index Endpoint に deploy された Index の replica × node-hour
  → 1 replica × $0.38/hour = ¥1,460/日 (24h放置)

[課金されないもの]
- Undeployed Index (作成済みだが endpoint に deploy されていない)
- Index Endpoint 自体(空の状態)
```

これは「You pay for each model deployed to an endpoint, even if no prediction is made. You must undeploy your model to stop incurring further charges. Models that are not deployed or have failed to deploy are not charged.」と「a cost for building or updating indexes. This cost is the same as the indexing costs for Vector Search, number of examples * number of dimensions * 4 bytes per float * $3.00 per GB. When you deploy to an endpoint, you are billed per node hour for each node in your endpoint.」から確認できます。

つまり **Index は build 後に保持しても課金されない、deploy(replica起動)した瞬間から課金される**。これが鍵。

---

## 最適解:3層永続化アーキテクチャ

```text
[Layer 1: 完全永続(persistent stack)]
  GCS bucket: gs://embeddings-archive/
    - prevent_destroy = true
    - 維持コスト: ¥3-30/月 (data sizeによる)
  
  ※ Index自体は永続化対象外。再build可能
  
[Layer 2: 半永続(vector_search stack - 別管理)]
  Vertex Vector Search Index (build済み、未deploy)
    - 維持コスト: ¥0/月 (undeployed)
    - destroy-all では消さない
  
  Vertex Index Endpoint (空)
    - 維持コスト: ¥0/月 (deployedIndexが無ければ)
    - destroy-all では消さない
  
[Layer 3: 使い捨て(core stack)]
  Deployed Index (Index → Endpoint への deploy)
    - 課金対象: ¥1,460/日 (1 replica)
    - destroy-all で必ず undeploy
```

### deploy-all の所要時間

```text
[初回] (Layer 1-3 全て新規)
  GCS upload:           1-2 min
  Index build:          5-15 min
  Endpoint 作成:         10-15 min
  Index → Endpoint:     10-15 min  ← deploy
  ─────────────────────────────
  合計: 26-47 min

[2回目以降] (Layer 1-2 が永続化済み)
  Index → Endpoint:     10-15 min  ← deploy のみ
  ─────────────────────────────
  合計: 10-15 min  ★ 60% 短縮
```

`deploy_index()` だけで済むので、**27分 → 10-15分** に短縮されます。

### destroy-all の所要時間

```text
undeploy index from endpoint: 10-30 min (Google 側 cleanup)
※ Index と Endpoint は残す
```

---

## 維持コスト試算

```text
[永続化コスト]
GCS embedding archive:    
  100 MB → ¥0.3/月
  1 GB   → ¥3/月
  10 GB  → ¥30/月

Undeployed Index:         ¥0/月 (公式: charges only when deployed)
Empty Index Endpoint:     ¥0/月 (replica 0)
Feature Online Store:     使う日のみ ¥182/3h
─────────────────────────────────
月額維持コスト: ¥3〜¥30/月
```

**「課金地獄」の構造的回避**が達成されます。

---

## 有力シナリオ

### シナリオA: 3層分離(推奨・確度85%)

```text
persistent stack:    GCS embedding archive
vector_search stack: Index (build済), Endpoint (空)
core stack:          Deployed Index, Feature Store, GKE, etc

deploy-all (core):   10-15 min
destroy-all (core):  undeploy + 通常destroy
維持コスト:           ¥3-30/月
学習機会:             毎回 deploy/undeploy で実機学習
```

### シナリオB: 2層分離(代替・確度10%)

```text
persistent stack:    GCS embedding archive
core stack:          Index/Endpoint も含む全て

deploy-all:          27 min(Index buildが毎回)
維持コスト:           ¥3-30/月
学習機会:             Index build を毎回見られる
```

シナリオA の方が時間効率は圧倒的に良い。

### シナリオC: stack 統合(非推奨・確度5%)

毎回 27分 + 維持コスト ¥0 だが、Toshifumiさんの本来の問題(deploy 時間短縮)を解決しない。

---

## 破綻条件

### シナリオA が破綻する条件

```text
1. Index Endpoint に "stale" な deployedIndex が残る
   → 課金継続。undeploy 確認が必須
   
2. Embedding model のバージョンを変更
   → 既存 Index の embedding と次元/分布が不整合
   → Index 再 build 必要(27分の出戻り)
   
3. Vector Search の major upgrade (1.0 → 2.0 等)
   → 構造変更、移行作業発生
   
4. 数ヶ月使わない場合の Google 側 GC
   → 公式に明記されていないが、念の為 monthly health check 推奨
```

### Undeploy 漏れ検知の自動化が必須

```text
最大のリスク = undeploy 忘れ
1 replica 残存 = ¥1,460/日 = ¥44,000/月

対策:
- Cloud Scheduler で 4h 後の強制 undeploy
- Billing Budget Alert: 日次 ¥3,000
- destroy-all script で必ず undeploy 確認
```

---

## 実務・行動への影響

### Terraform stack 構造

```text
infra/terraform/
├── stacks/
│   ├── persistent/         # 維持(課金あり、GCSのみ)
│   │   ├── main.tf
│   │   └── outputs.tf      # → embedding archive bucket name
│   ├── vector_search/      # 維持(課金ゼロ)
│   │   ├── main.tf         # Index, IndexEndpoint
│   │   └── outputs.tf      # → index_id, endpoint_id
│   └── core/               # 使い捨て(課金あり)
│       ├── main.tf         # GKE, Composer, Feature Store, etc
│       └── deployed_index.tf  # Index → Endpoint への deploy
└── modules/
    ├── vector_search_index/
    ├── vector_search_endpoint/
    ├── deployed_index/      # ← core stack だけが使う
    └── ...
```

### Terraform 実装の要点

```hcl
# stacks/vector_search/main.tf
resource "google_vertex_ai_index" "main" {
  display_name        = "search-index-v1"
  region              = "asia-northeast1"
  
  metadata {
    contents_delta_uri = "gs://${var.embedding_bucket}/v1.0/"
    config {
      dimensions          = 768
      shard_size          = "SHARD_SIZE_SMALL"
      distance_measure_type = "DOT_PRODUCT_DISTANCE"
      algorithm_config {
        tree_ah_config {
          leaf_node_embedding_count    = 500
          leaf_nodes_to_search_percent = 7
        }
      }
    }
  }
  
  index_update_method = "BATCH_UPDATE"
  
  lifecycle {
    prevent_destroy = true  # ← destroy-all から保護
  }
}

resource "google_vertex_ai_index_endpoint" "main" {
  display_name = "search-endpoint-v1"
  region       = "asia-northeast1"
  
  public_endpoint_enabled = true
  
  lifecycle {
    prevent_destroy = true  # ← 空の Endpoint は無料
  }
}
```

```hcl
# stacks/core/deployed_index.tf
data "terraform_remote_state" "vector_search" {
  backend = "gcs"
  config = {
    bucket = "tfstate-bucket"
    prefix = "vector_search"
  }
}

resource "google_vertex_ai_index_endpoint_deployed_index" "main" {
  index_endpoint = data.terraform_remote_state.vector_search.outputs.endpoint_id
  index          = data.terraform_remote_state.vector_search.outputs.index_id
  deployed_index_id = "deployed_v1"
  
  automatic_resources {
    min_replica_count = 1
    max_replica_count = 1
  }
  
  # ← prevent_destroy しない。core stack の destroy で消える
}
```

### Makefile

```makefile
# 永続部分(初回のみ)
deploy-persistent:
	cd infra/terraform/stacks/persistent && terraform apply -auto-approve

# Vector Search 構造(数ヶ月に1回)
deploy-vector-search:
	cd infra/terraform/stacks/vector_search && terraform apply -auto-approve

# 日常 verify(deploy = 10-15分)
deploy-core:
	cd infra/terraform/stacks/core && terraform apply -auto-approve

# 日常 destroy(undeploy のみ)
destroy-core:
	cd infra/terraform/stacks/core && terraform destroy -auto-approve

# 学習サイクル
verify-cycle: deploy-core run-tests destroy-core

# 完全クリーンアップ(月1)
destroy-all:
	$(MAKE) destroy-core
	cd infra/terraform/stacks/vector_search && terraform destroy -auto-approve
	# persistent stack は手動でのみ destroy
```

### Vector Search 学習の確保

```text
[初回] 全 stack を deploy → Index build 27分 を実機学習
       PMLE 試験範囲を1回触る
       
[2回目以降] core stack のみ deploy → 10-15分で起動
            毎回 deploy/undeploy のサイクルを学習
            replica の課金構造を肌で理解
            
[月1回] Index 再 build を実施
        embedding 更新、index 構造変更を学習
```

**「Index build 27分」は1回経験すれば PMLE 学習として十分**。毎回繰り返す必要はない。

---

## 最終判断

**3層永続化アーキテクチャを採用。**

```text
✅ 学習目的達成: Vector Search 全要素を実機学習可能
✅ deploy 時間: 27分 → 10-15分(60%短縮)
✅ 維持コスト: ¥3-30/月(課金地獄回避)
✅ Undeploy 自動化で人的ミス防御
```

特に重要なのは、**「Index 自体は無料で残せる」という Vector Search の課金構造を活用すること**。これは多くの記事で見落とされている本質的な事実です。Toshifumiさんの「努力の余白を奪わない、構造的にフリーライドを排除する」という方針にも合致します(構造で課金事故を防ぐ設計)。

### 実装ロードマップ

```text
[今日 v3 done 後] 既存構造を確認、stack 分離計画レビュー
[今週 PR 1] persistent stack 作成 + GCS embedding archive
[今週 PR 2] vector_search stack 分離 (Index, Endpoint を引き越し)
[来週 PR 3] core stack の deployed_index を remote_state 参照に変更
[来週 PR 4] Makefile 整備、Cloud Scheduler 自動 undeploy
[2週後 PR 5] Billing Budget Alert + 監視ダッシュボード
```

これでメモリにある「Phase 7 6-PR migration」と整合する形で実装できます。**Toshifumiさんの目的(Vector Search 学習維持 + deploy 高速化 + 課金地獄回避)が3つとも構造的に達成される唯一の解**です。