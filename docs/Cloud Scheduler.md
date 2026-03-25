# Cloud Scheduler + 監視 + Discord通知 設計書

## 概要

```
Cloud Scheduler (cron)
  ↓ 定期実行
Cloud Run Job (ml-batch)
  ↓ ログ書き出し
GCS (mlops-dev-a-data/logs/)

＋

監視スクリプト (gcloud CLI)
  ↓ 失敗検知
Discord通知 (Webhook)
```

---

## 1. Cloud Scheduler → Cloud Run Job

### 仕組み

Cloud Schedulerがcronスケジュールで Cloud Run Job を実行する。
HTTPリクエストではなく、Cloud Run Jobs APIを直接呼び出す。

### 必要なAPI

```bash
gcloud services enable cloudscheduler.googleapis.com --project=mlops-dev-a
```

### gcloud CLIでの作成例

```bash
gcloud scheduler jobs create http ml-batch-schedule \
  --location=asia-northeast1 \
  --schedule="0 9 * * *" \
  --time-zone="Asia/Tokyo" \
  --uri="https://asia-northeast1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/mlops-dev-a/jobs/ml-batch:run" \
  --http-method=POST \
  --oauth-service-account-email=941178142366-compute@developer.gserviceaccount.com
```

### Terraform定義

```hcl
resource "google_cloud_scheduler_job" "ml_batch_schedule" {
  name      = "ml-batch-schedule"
  region    = var.region
  schedule  = "0 9 * * *"    # 毎日9:00 JST
  time_zone = "Asia/Tokyo"

  http_target {
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/ml-batch:run"
    http_method = "POST"

    oauth_token {
      service_account_email = "${data.google_project.current.number}-compute@developer.gserviceaccount.com"
    }
  }

  depends_on = [google_cloud_run_v2_job.ml_batch]
}
```

### IAM要件

Cloud Schedulerのサービスアカウントに以下が必要:

| ロール | 対象 | 用途 |
|--------|------|------|
| roles/run.invoker | Cloud Run Job | Job実行権限 |

```bash
gcloud run jobs add-iam-policy-binding ml-batch \
  --region=asia-northeast1 \
  --member="serviceAccount:941178142366-compute@developer.gserviceaccount.com" \
  --role="roles/run.invoker"
```

---

## 2. 監視スクリプト (gcloud CLI)

### 目的

Cloud Run Job の実行結果を監視し、失敗時にDiscordへ通知する。

### 監視方法

```bash
# 最新の実行結果を取得
gcloud run jobs executions list \
  --job=ml-batch \
  --region=asia-northeast1 \
  --limit=1 \
  --format="json"
```

レスポンス例:
```json
{
  "status": {
    "completionTime": "2026-03-26T00:00:30Z",
    "conditions": [
      {
        "type": "Completed",
        "status": "True"
      }
    ],
    "runningCount": 0,
    "succeededCount": 1,
    "failedCount": 0
  }
}
```

### 判定ロジック

| 条件 | 判定 |
|------|------|
| succeededCount >= 1, failedCount == 0 | 成功 |
| failedCount >= 1 | 失敗 → Discord通知 |
| completionTimeが一定時間以上前 | 未実行 → Discord通知 |

### スクリプト設計 (Python)

```
scripts/monitor_batch.py

1. gcloud run jobs executions list で最新実行を取得
2. 成功/失敗/未実行を判定
3. 失敗 or 未実行 → Discord Webhook へ POST
4. 成功 → 何もしない（or オプションで通知）
```

### 実行方法の選択肢

| 方式 | メリット | デメリット |
|------|---------|-----------|
| ローカルcron | シンプル | マシン依存 |
| Cloud Scheduler + Cloud Function | フルマネージド | 追加コスト・複雑 |
| Cloud Scheduler + 別のCloud Run Job | 統一的 | やや冗長 |

推奨: まずローカルcronで開始、必要に応じてCloud化

---

## 3. Discord通知

### セットアップ

1. Discordサーバーのチャンネル設定 → Webhook URLを取得
2. 環境変数 `DISCORD_WEBHOOK_URL` に設定

### Discord Webhook の特徴

- Slack と違いApp作成不要（チャンネル設定からすぐ作れる）
- ペイロード形式が異なる（`content` フィールド）
- Embed で構造化メッセージも可能

### 通知フォーマット

失敗時:
```json
{
  "embeds": [
    {
      "title": "Cloud Run Job 実行失敗",
      "color": 15158332,
      "fields": [
        { "name": "Job", "value": "`ml-batch`", "inline": true },
        { "name": "ステータス", "value": "FAILED", "inline": true },
        { "name": "コンソール", "value": "[GCPで確認](https://console.cloud.google.com/run/jobs/details/asia-northeast1/ml-batch?project=mlops-dev-a)" }
      ]
    }
  ]
}
```

成功時（オプション）:
```json
{
  "embeds": [
    {
      "title": "Cloud Run Job 実行成功",
      "color": 3066993,
      "fields": [
        { "name": "Job", "value": "`ml-batch`", "inline": true },
        { "name": "ステータス", "value": "SUCCESS", "inline": true }
      ]
    }
  ]
}
```

色コード: 赤=15158332 (0xE74C3C)、緑=3066993 (0x2ECC71)

### Python実装イメージ

```python
import json
import os
import urllib.request


def notify_discord(embeds: list[dict]) -> None:
    webhook_url = os.environ["DISCORD_WEBHOOK_URL"]
    payload = json.dumps({"embeds": embeds}).encode()
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req)
```

標準ライブラリのみで実装可能（requests不要）。

---

## 4. 実装時の変更対象

| ファイル | 内容 |
|---------|------|
| `terraform/cloud_scheduler.tf` | 新規: Scheduler定義 |
| `terraform/iam.tf` | 追加: run.invoker権限 |
| `makefiles/gcp.mk` | 追加: cloudscheduler.googleapis.com |
| `scripts/monitor_batch.py` | 新規: 監視 + Discord通知 |
| `.env` | 新規: DISCORD_WEBHOOK_URL |

### 必要なAPI追加

```
cloudscheduler.googleapis.com
```

---

## 5. スケジュール設計

| 項目 | 値 |
|------|-----|
| バッチ実行 | 毎日 09:00 JST |
| 監視チェック | 毎日 09:30 JST（バッチ完了後） |
| タイムゾーン | Asia/Tokyo |

cron式:
- バッチ: `0 9 * * *`
- 監視: `30 9 * * *`

---

## 6. 注意事項

- Cloud Scheduler は無料枠あり（3ジョブ/月）
- Discord Webhook URLは `.env` で管理し、gitにコミットしない（.gitignoreに `.env` 登録済み）
- 監視スクリプトはGCSへの書き込み権限不要（読み取りのみ）
- Cloud Run Job のタイムアウト（デフォルト10分）を考慮してスケジュール間隔を設定
- Discord Webhook のレートリミット: 30リクエスト/分
