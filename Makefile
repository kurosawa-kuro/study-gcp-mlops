# === 共通設定 ===
PROJECT_ID := mlops-dev-a
REGION := asia-northeast1
REPO := mlops-dev-a-docker
TAG := latest
BUCKET := mlops-dev-a-data
IMAGE_BASE := $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(REPO)

include makefiles/gcp.mk
include makefiles/terraform.mk
include makefiles/batch.mk
include makefiles/api.mk

# === 統合コマンド ===
.PHONY: deploy reset test help

deploy: batch-deploy api-deploy  ## 全体デプロイ（インフラ + batch + API）

test: batch-test api-test  ## 全テスト一括実行

reset:  ## 全リソース削除 & ローカルクリーン
	python3 scripts/reset_all.py

help:  ## コマンド一覧表示
	@echo "=== Setup ==="
	@echo "  make gcp-setup          GCP初回セットアップ一括"
	@echo "  make gcp-setup-apis     API有効化"
	@echo "  make gcp-setup-sa       Terraform SA権限付与"
	@echo "  make gcp-setup-docker   Docker認証設定"
	@echo ""
	@echo "=== Terraform ==="
	@echo "  make tf-init            初期化"
	@echo "  make tf-plan            差分確認"
	@echo "  make tf-apply           全リソース反映"
	@echo "  make tf-apply-repo      Artifact Registryのみ反映"
	@echo "  make tf-destroy         全リソース削除"
	@echo "  make tf-fmt             フォーマット"
	@echo "  make tf-validate        構文チェック"
	@echo ""
	@echo "=== Batch (ML学習パイプライン) ==="
	@echo "  make batch-test         テスト実行"
	@echo "  make batch-run-local    ローカルでML学習実行"
	@echo "  make batch-build        Dockerイメージビルド"
	@echo "  make batch-push         ビルド & push"
	@echo "  make batch-deploy       冪等デプロイ（repo→push→job）"
	@echo "  make batch-run          Cloud Run Job実行"
	@echo "  make batch-logs         実行履歴確認"
	@echo "  make batch-monitor      監視 + Discord通知"
	@echo "  make batch-drift        モデルドリフト検知"
	@echo "  make batch-ui           MLflow UI起動"
	@echo ""
	@echo "=== API (推論サービス) ==="
	@echo "  make api-test           APIテスト実行"
	@echo "  make api-build          APIイメージビルド"
	@echo "  make api-push           APIイメージ push"
	@echo "  make api-deploy         API冪等デプロイ"
	@echo "  make api-logs           APIログ確認"
	@echo "  make api-url            APIのURL表示"
	@echo "  make api-monitor        API健全性チェック"
	@echo ""
	@echo "=== 統合 ==="
	@echo "  make deploy             全体デプロイ（batch + API）"
	@echo "  make test               全テスト一括実行"
	@echo "  make reset              全リソース削除 & クリーン"
