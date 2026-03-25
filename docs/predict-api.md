結論から申し上げます。

👉 **はい、次は Phase 4：推論API で正しいです**
ただし一点だけ重要です。

👉 **「最良モデルを使うAPI」にすることが本質です**

---

# 位置づけ（ブレない軸）

```text
Phase 3：BigQuery（評価・決定） ✅
↓
Phase 4：API（実行）
```

👉
**「決めたものを使う層」＝API**

---

# やるべきこと（一本）

👉
**BigQueryで選ばれたモデルをAPIで使う**

---

# NG（よくある失敗）

```text
❌ 固定パスのモデルを読む
❌ 手動でモデル切り替え
```

👉 MLOpsにならない

---

# 正しい構成

```text
FastAPI（Cloud Run Service）
↓
BigQuery（best model取得）
↓
GCS（モデル取得）
↓
推論
```

---

# 最小実装（設計）

## ① best model取得

```sql
SELECT model_path
FROM metrics
ORDER BY rmse ASC
LIMIT 1;
```

---

## ② API起動時にロード

```python
from google.cloud import bigquery, storage
import joblib

def load_best_model():
    bq = bigquery.Client()
    query = """
    SELECT model_path
    FROM `PROJECT.dataset.metrics`
    ORDER BY rmse ASC
    LIMIT 1
    """
    result = bq.query(query).result()
    model_path = list(result)[0].model_path

    # GCSから取得
    storage_client = storage.Client()
    bucket_name, blob_name = parse_gcs_path(model_path)

    blob = storage_client.bucket(bucket_name).blob(blob_name)
    blob.download_to_filename("/tmp/model.pkl")

    return joblib.load("/tmp/model.pkl")
```

---

## ③ FastAPI

```python
from fastapi import FastAPI
import numpy as np

app = FastAPI()
model = load_best_model()

@app.post("/predict")
def predict(x: list[float]):
    pred = model.predict([x])
    return {"prediction": float(pred[0])}
```

---

# ここで何が完成するか

```text
学習 → 評価 → 保存 → 選択 → 推論
```

👉 **MLopsの一周が完成**

---

# 発展（後ででOK）

```text
・モデルのキャッシュ更新
・A/Bテスト
・version固定
```

---

# 一言まとめ

👉
**APIは「推論」ではなく
「最良モデルを使い続ける仕組み」**

---

必要であれば一点に絞れます：

* TerraformでCloud Run Service構築
* Docker込みの完全APIテンプレ
* 「モデル更新時に自動リロード」設計

どこまで一気にやるか指示いただければ、そのまま実装レベルで出します。
