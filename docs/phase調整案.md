# study-gcp-mlops

MLOps 学習用の 6 フェーズ構成リポジトリ（+ Optional Phase 7）。  
**全フェーズを単一の親 Git リポジトリで管理**し、Phase ごとに学習対象を段階的に広げる。

---

## 全体方針

- Phase 1 は **ML 基礎に集中**（学習・評価・保存）
- Phase 2 は **App / Pipeline / Port-Adapter** を導入
- Phase 3-5 は不動産検索ドメインで **Local -> GCP -> Vertex AI** へ展開
- Phase 6 は **Phase 5 と同じ不動産ハイブリッド検索ドメインを題材として維持**し、PMLE 試験範囲の追加技術を実コードへ統合して学ぶ
- Phase 7 は **Optional / Advanced**。Phase 5 の serving 層を GKE + KServe に置き換える Draft
- Phase 3/4/5/7 は **LightGBM + multilingual-e5 + Meilisearch のハイブリッド構成を必須**
- Phase 間のコードは原則共有しない（教材としての独立性を優先）
- 各 Phase の正本は phase 配下ドキュメント（ルート README は全体ナビゲーション）
- 設計思想（Port/Adapter、core-ports-adapters 層構造、依存方向）は一貫させ、**adapter 実装だけ差し替える**
- W&B はクライアント調整により現時点では教材対象外（必要時 optional 再導入）
- 実験履歴・評価結果は Phase ごとに軽量管理し、Phase4以降は GCP / Vertex 標準機能へ移行する
- モデル成果物の正本管理は **GCS -> Vertex Model Registry** へ段階移行する
- Looker Studio は本教材対象外とする

---

## Phase 一覧

| Phase | ディレクトリ | テーマ | 主な学習ポイント | 主な技術 | 実行方式 |
|---|---|---|---|---|---|
| 1 | `1/study-ml-foundations/` | ML 基礎（回帰） | preprocess / feature engineering / training / evaluation / artifact 出力（model.pkl / metrics.json / params.yaml） | LightGBM, PostgreSQL | Docker Compose |
| 2 | `2/study-ml-app-pipeline/` | App + Pipeline + Port/Adapter | FastAPI lifespan DI, `core -> ports <- adapters`, predictor 経由推論、seed/train/predict job 分離 | FastAPI, LightGBM, PostgreSQL | Docker Compose |
| 3 | `3/study-hybrid-search-local/` | 不動産ハイブリッド検索（Local） | lexical + semantic + rerank、LambdaRank、Port/Adapter 実践 | Meilisearch, multilingual-e5, LightGBM LambdaRank, Redis | uv + Docker Compose |
| 4 | `4/study-hybrid-search-cloud/` | 不動産ハイブリッド検索（GCP） | GCP マネージドサービス化、RRF、再学習ループ、IaC/CI | Cloud Run, GCS, BigQuery, Cloud Logging, Terraform, WIF | uv + クラウド実行基盤 |
| 5 | `5/study-hybrid-search-vertex/` | Vertex AI 標準 MLOps 差分移行 | Vertex Pipelines / Endpoint / Model Registry / Monitoring への adapter 差し替え | Vertex AI, Vertex Pipelines, Endpoint, Model Registry, Monitoring | uv + Vertex AI |
| 6 | `6/study-gcp-ml-engineer-cert/` | GCP PMLE 追加技術ラボ | PMLE 範囲の追加技術を adapter / 副経路 / 追加エンドポイント / Terraform として統合。default flag では Phase 5 挙動維持 | BQML / Dataflow / Vector Search / Monitoring SLO / Gemini RAG / Agent Builder（補助: Explainable AI / Vizier / Feature Group / Model Garden） | uv + Vertex AI + Terraform |
| 7 | `7/study-hybrid-search-gke/` | GKE/KServe 差分移行（Draft） | serving 層を GKE + KServe へ置換し、Phase 5 の学習/データ基盤を維持 | GKE, KServe, Gateway API, Workload Identity | uv + GKE/KServe |

---

## 全 Phase 共通ツール（横断的に登場）

| ツール | 役割 | 初登場 | 本格活用 |
|---|---|---|---|
| JSON / CSV metrics | ローカル評価結果・run履歴保存 | Phase 1 | Phase 1-3 |
| Git commit hash | 再現性管理 | Phase 1 | 全 Phase |
| pytest | 全 Phase 共通のテストランナー | Phase 1 | 全 Phase |
| Git | 親リポで全 Phase を単一管理 | 開始時点 | 全 Phase |
| pydantic-settings (YAML) | 設定とシークレットの分離 | Phase 1 | 全 Phase |
| Docker / Docker Compose | ローカル実行基盤 | Phase 1 | Phase 1-3 |
| uv | Python 依存管理 | Phase 3 | Phase 3-7 |

---

## 学習順（推奨）

1. `1/study-ml-foundations`
2. `2/study-ml-app-pipeline`
3. `3/study-hybrid-search-local`
4. `4/study-hybrid-search-cloud`
5. `5/study-hybrid-search-vertex`
6. `6/study-gcp-ml-engineer-cert`
7. `7/study-hybrid-search-gke`

---

## 学習運用フロー

### Phase1〜3

```text
model.pkl
metrics.json
params.yaml
runs/20260424_001/

はい。**この調整はかなり良い判断です。**
クライアント許可が取れたなら、今の学習ロードマップは **W&B前提設計をやめて、GCP/Vertexネイティブ寄りに整理** できます。

---

# 一点結論

**W&B一旦除外を正式反映し、Phase1〜3を軽量化、Phase4〜5をGCP/Vertex標準構成へ寄せるべきです。**

---

# READMEへ反映すべき変更計画

---

## ① 全体方針に追記

追加：

```md
- W&B はクライアント調整により現時点では教材対象外とし、必要時に再導入可能な optional 扱いとする
- 実験履歴・評価結果は Phase ごとに軽量管理し、Phase4以降は GCP / Vertex 標準機能へ移行する
- モデル成果物の正本管理は GCS → Vertex Model Registry へ段階移行する
```



---

## ② 全Phase共通ツールからW&B削除

現状：

```md
| W&B | 実験管理（metrics / artifact tracking） | Phase 1 | Phase 1 以降 |
```

削除。

代替追加：

```md
| JSON / CSV metrics | ローカル評価結果・run履歴保存 | Phase 1 | Phase 1-3 |
| Git commit hash | 再現性管理 | Phase 1 | 全 Phase |
```

---

## ③ Phase1修正（軽量化）

現状：

```md
artifact 管理
```

変更：

```md
artifact 出力（model.pkl / metrics.json / params.yaml）
```

---

## ④ Phase4修正（GCP本流化）

現状：

```md
Cloud Run, BigQuery, Dataform, Terraform, WIF
```

変更推奨：

```md
Cloud Run, GCS, BigQuery, Cloud Logging, Terraform, WIF
```

理由：

* W&B削除後は GCS が重要度上昇
* Dataformより先にGCS明記した方が実務的

---

## ⑤ Phase5修正（Vertex主軸明確化）

現状：

```md
Vertex AI, KFP, Endpoint, Feature Group, Vizier
```

変更：

```md
Vertex AI, Vertex Pipelines, Endpoint, Model Registry, Monitoring
```

理由：

W&B抜けた分、Vertex標準MLOps感を強める。

---

## ⑥ Phase6整理

現状：

補助技術が混在。

変更：

```md
BQML / Dataflow / Vector Search / Monitoring SLO / Gemini RAG / Agent Builder
(補助: Explainable AI / Vizier / Feature Group / Model Garden)
```

---

# 学習運用フロー（修正版）

## Phase1〜3

```text
model.pkl
metrics.json
params.yaml
runs/20260424_001/
```

## Phase4

```text
GCS bucket:
models/
reports/
artifacts/
```

評価結果：

BigQuery table

## Phase5

```text
Vertex Model Registry
Vertex Pipelines metadata
Endpoint deploy history
```

---

# あなた向け実務価値

この変更後は面接でも強いです。

> W&B使ってました

より

> W&BなしでもGCP/Vertex標準機能でMLOps構成できます

の方が強いです。

---

# 最終反映版のPhase役割

| Phase | 役割                   |
| ----- | -------------------- |
| 1     | ML基礎 + ローカル成果物管理     |
| 2     | API / Job / DI       |
| 3     | Search / Ranking     |
| 4     | GCP Serverless MLOps |
| 5     | Vertex標準MLOps        |
| 6     | PMLE追加技術             |
| 7     | GKE/KServe           |

---

# 最終結論

**W&B除外は後退ではなく、むしろ教材として純化です。**
あなたの主戦場はGCP/Vertexなので、ここへ寄せた方が強いです。


整理方針、かなり明確です。**今の情報で設計思想を一本化できます。**

## 一点結論

あなたのロードマップは今後、

**W&B = 実験・評価のトレーサビリティ基盤**
**GCS / Vertex Registry = モデル成果物の正本管理**
**Looker Studio = 不採用**

この3点で明確に切り分けるべきです。

---

# まず誤解を解く（重要）

多くの現場で W&B は

* メトリクス可視化
* モデル保存
* artifact置き場

まで全部使います。

しかしあなたのクライアント文脈では違う。

## 今回の定義

### W&Bの役割

* 学習run履歴
* 実験条件比較
* 精度変化追跡
* 誰がいつ何を試したか
* 再現性監査

### モデル正本管理

* GCS
* Vertex AI Model Registry

これで分離。

---

# 具体的にREADMEで変えるべき点

---

## ① W&B説明文修正

現状：

```md
W&B | 実験管理（metrics / artifact tracking）
```

変更：

```md
W&B | 実験評価・run履歴・再現性トレーサビリティ
```

または

```md
W&B | 実験比較 / metric可視化 / run lineage
```

※ artifact tracking を消す



---

## ② モデル保存の主語を分離

Phase1〜2 現状：

```md
artifact 管理
```

曖昧です。

変更：

```md
artifact出力（ローカル/GCS）
```

Phase5以降：

```md
Model Registry による版管理・昇格
```

---

## ③ Phase5 の価値を上げる

現状：

```md
Vertex Pipelines/Endpoints/Registry/Monitoring
```

このままで良いですが、Registryの意味を明示。

変更：

```md
Vertex Pipelines / Endpoint / Model Registry / Monitoring
（モデル正本管理へ移行）
```

---

## ④ Looker Studio削除

話題に出ていないなら削除正解です。

今後も BigQuery可視化が必要なら、

* Cloud Monitoring Dashboard
* W&B dashboard
* Grafana（必要時）

で十分。

LookerはBI組織が必要な時だけ。

---

# あなた向けベスト設計（重要）

## Phase1

* LightGBM学習
* W&B run logging
* model.pkl ローカル保存

## Phase4

* Cloud Run job
* GCS model export
* W&B metric tracking

## Phase5

* Vertex Pipeline
* Vertex Model Registry昇格
* W&B実験比較

これがかなり実務的。

---

# なぜこの分離が強いか

面接・案件で説明しやすい。

> W&Bでモデル管理してます

より弱い。

強いのは：

> 実験履歴はW&B、モデル正本はVertex Registry、実ファイルはGCSです

これは設計理解者です。

---

# READMEに追加すべき思想文

```md
- W&B は実験評価・run履歴・再現性管理に利用する
- モデル成果物の正本管理は GCS / Vertex Model Registry を利用する
- 可視化は W&B / Cloud Monitoring を主とし、Looker Studio は本教材対象外とする
```

---

# 最終結論

**W&Bを“何でも屋”にせず、評価トレーサビリティ専任に落とす。
モデル格納はGCS→成熟後Vertex Registry。
Lookerは削除。**

この整理はかなりプロっぽいです。


了解です。前提を踏まえると、重心はこうです。

**MLOps育成なら、Phase1〜2は MLflow なしで正解**です。
ここは「MLを作る力」ではなく、**ML成果物を扱う最低限の理解**に絞るべきです。

## 修正版の寄せ方

| 要素                           |                  移動先 | 理由                   |
| ---------------------------- | -------------------: | -------------------- |
| MLflow / Experiment Tracking |     Phase4 or Phase5 | 運用・比較・履歴管理の文脈で出す方が自然 |
| Pub/Sub                      |                   削除 | 実案件で使わないなら不要         |
| Vizier                       | Phase6補助 or Appendix | MLOps育成では優先度低い       |
| Feature Group                | Phase6補助 or Appendix | 実務で使う確度が低いなら後回し      |
| Explainable AI               |             Phase6補助 | PMLE範囲・説明責任として軽く扱う   |
| Model Garden                 |             Phase6補助 | 実装主軸ではなく拡張知識で十分      |

## Phase5の主軸はこれで良いです

| Phase | 主役                                                  |
| ----- | --------------------------------------------------- |
| 5     | Vertex Pipelines / Endpoint / Registry / Monitoring |
| 6     | PMLE範囲の追加技術を副経路として統合                                |
| 7     | GKE/KServe差分移行                                      |

特に Phase5 は、
**「Cloud Run中心のMLOpsをVertex標準部品に差し替える」**
に絞った方が強いです。

## Phase6の扱い

Phase6は「本流」ではなく、

**PMLE試験範囲をPhase5コードに追加実装する検証ラボ**

で良いです。

つまり、

* `/search` default は壊さない
* 追加エンドポイント
* 追加adapter
* 追加Terraform
* feature flag
* optional path

として分離するのが正解です。

## 最終バランス

| Phase | 役割                            |
| ----- | ----------------------------- |
| 1     | ML成果物の最低理解                    |
| 2     | API / job / DI / Port-Adapter |
| 3     | 検索・ランキング・評価                   |
| 4     | GCP Cloud Run MLOps           |
| 5     | Vertex標準MLOps                 |
| 6     | PMLE追加技術ラボ                    |
| 7     | GKE/KServe運用差分                |

**一点結論：Phase1〜2を汚さず、MLflow・Vizier・Feature Group・Explainable AI・Model Gardenは後半の“運用/資格/補助”側へ逃がすのが最適です。**

はい。**一旦外すとかなり軽くなります。**
特に Phase1〜2 は軽くなります。

## W&Bを外すと消える負荷

* APIキー管理
* login / entity / project 設定
* `.env` / Secret 管理
* オンライン送信
* 失敗時の切り分け
* チーム/権限まわり
* artifact運用の曖昧さ

## 代わりに使う技術

### Phase1〜2

**JSON / CSV / ローカルファイル保存**で十分です。

```text
metrics.json
params.json
model.pkl
evaluation_report.json
```

技術としては：

| 用途       | 代替                              |
| -------- | ------------------------------- |
| metric保存 | JSON / CSV                      |
| model保存  | local filesystem                |
| 実験履歴     | run_id付きディレクトリ                  |
| 可視化      | README表 / notebook / matplotlib |
| 再現性      | config.yaml + git commit hash   |

---

### Phase4

ここからGCPなので、

| 用途     | 技術                   |
| ------ | -------------------- |
| モデル格納  | GCS                  |
| 評価結果保存 | BigQuery             |
| 実行ログ   | Cloud Logging        |
| 監視     | Cloud Monitoring     |
| CI/CD  | GitHub Actions + WIF |
| IaC    | Terraform            |

---

### Phase5

Vertexに寄せるなら、

| 用途         | 技術                            |
| ---------- | ----------------------------- |
| Pipeline履歴 | Vertex AI Pipelines           |
| モデル正本      | Vertex Model Registry         |
| 推論         | Vertex Endpoint               |
| モデル監視      | Vertex AI Model Monitoring    |
| 実験比較       | Vertex Experiments / Metadata |

---

## README上の修正案

W&Bを一旦外すなら、全Phase共通ツールから削除して、こう書くのが良いです。

```md
| JSON/CSV metrics | ローカル評価結果・run履歴の保存 | Phase 1 | Phase 1-3 |
| GCS | モデル成果物・評価成果物の格納 | Phase 4 | Phase 4以降 |
| BigQuery | 評価結果の蓄積・比較 | Phase 4 | Phase 4以降 |
| Vertex Model Registry | モデル正本管理・昇格 | Phase 5 | Phase 5以降 |
| Vertex AI Pipelines / Metadata | Pipeline実行履歴・再現性管理 | Phase 5 | Phase 5以降 |
```

## 結論

**W&Bを外すなら、Phase1〜3は「JSON/CSV + run_idディレクトリ」で十分。
Phase4でGCS/BigQuery、Phase5でVertex Registry/Pipelinesに進化させるのが自然です。**

一番軽い構成はこれです。
