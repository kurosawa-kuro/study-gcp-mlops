# === Terraform ===
TF_DIR := terraform

.PHONY: tf-init tf-plan tf-apply tf-apply-repo tf-destroy tf-fmt tf-validate

tf-init:
	cd $(TF_DIR) && terraform init -input=false

tf-plan: tf-init
	cd $(TF_DIR) && terraform plan

tf-apply-repo: tf-init
	cd $(TF_DIR) && terraform apply -auto-approve \
	  -target=google_artifact_registry_repository.myrepo

tf-apply: tf-init
	cd $(TF_DIR) && terraform apply -auto-approve

tf-destroy: tf-init
	cd $(TF_DIR) && terraform destroy

tf-fmt:
	cd $(TF_DIR) && terraform fmt -recursive

tf-validate: tf-init
	cd $(TF_DIR) && terraform validate
