以下に「そのまま docs に貼れるレベル」で整理します。
（冗長性を削り、実装判断に直結する形に圧縮しています）

---

# BigQuery連携方針（study-gcp MLOps）

## 1. 結論

👉 **次の一手は BigQuery 連携で確定**

理由：

👉 **評価を“分析可能なデータ”として蓄積するため**

---

## 2. 現状の限界

### 現在

```text
GCS
├── models/  ← OK
└── logs/    ← OK
```

👉 しかし

```text
比較・意思決定ができない
```

---

### 問題の本質

```text
logs/json を人が読むだけ
```

👉 **人間依存**

---

## 3. BigQuery導入の役割

```text
metrics table
↓
SQL
↓
最良モデル決定
```

👉 **機械的に意思決定可能**

---

## 4. MLflowとの役割分担（重要）

### MLflow

```text
・実験ログ
・詳細トレース
・run単位の確認
```

👉 探索ツール

---

### BigQuery

```text
・全履歴横断
・SQL集計
・ランキング
```

👉 **意思決定ツール**

---

### 本質

```text
MLflow：良さそう
BigQuery：最強が確定
```

---

## 5. 最小実装（これだけやる）

### テーブル

```sql
CREATE TABLE metrics (
  run_id STRING,
  timestamp TIMESTAMP,
  rmse FLOAT64,
  mae FLOAT64,
  model_path STRING
);
```

---

### Python追加

```python
from google.cloud import bigquery

def insert_metrics(row):
    client = bigquery.Client()
    table_id = "PROJECT_ID.dataset.metrics"

    errors = client.insert_rows_json(table_id, [row])
    if errors:
        raise Exception(errors)
```

---

### pipeline最後

```python
insert_metrics({
    "run_id": run_id,
    "timestamp": datetime.utcnow().isoformat(),
    "rmse": rmse,
    "mae": mae,
    "model_path": model_path
})
```

---

## 6. 得られる効果

```sql
SELECT *
FROM metrics
ORDER BY rmse ASC
LIMIT 1;
```

👉 **最良モデルが一発で決まる**

---

## 7. データ責務の分離（重要設計）

### GCS

```text
・raw
・processed
・models
・logs
```

👉 保存（安い）

---

### BigQuery

```text
・metrics
・features（将来）
・predictions（将来）
```

👉 分析（DWH）

---

### 原則

```text
GCS：全部保存
BigQuery：必要な要約だけ
```

---

## 8. NGパターン

```text
❌ 全データをBigQuery
❌ モデル保存
❌ ログ全文投入
```

👉 コスト増 + 設計崩壊

---

## 9. コスト認識

### ストレージ

```text
約 $0.02 / GB / 月
→ 実質無視可能
```

---

### クエリ

```text
$5 / TB
→ metrics規模ならほぼ0円
```

---

### 注意点

```sql
SELECT * FROM 巨大テーブル ← NG
```

---

## 10. アーキテクチャ（更新後）

```text
Cloud Run Job
↓
MLflow（詳細ログ）
↓
GCS（モデル・ログ）
↓
BigQuery（評価） ← NEW
```

---

## 11. ロードマップ上の位置

```text
Phase 1：Cloud Run Job + GCS ✅
Phase 2：MLflow ✅
Phase 3：BigQuery ← 今ここ
Phase 4：API
Phase 5：Vertex AI
```

---

## 12. 次の具体アクション

```text
① BigQuery dataset + table 作成
② insert_metrics 実装
③ best model SQL 確認
```

---

## 13. 一言まとめ

👉
**MLflowでは「選べない」
BigQueryで「決める」**

---

必要であれば次は一点に絞れます：

* TerraformでBigQuery完全定義
* best model自動選択ロジック（API連携）
* GCS→BQパイプライン設計

どこを深掘りするか指示いただければ、そのまま実装レベルまで落とします。
