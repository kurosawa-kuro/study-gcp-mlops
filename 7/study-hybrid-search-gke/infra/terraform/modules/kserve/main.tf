# =========================================================================
# KServe installation on GKE Autopilot
#
# 注意: このモジュールは kubernetes / helm プロバイダを使う。環境側
# (`infra/terraform/environments/<env>/provider.tf`) で GKE cluster
# endpoint + WI token を引いた provider 設定を渡すこと。
#
# 2 段階 apply を推奨: 初回は `-target=module.gke` でクラスタを作り、
# 次に全体 apply で KServe を入れる。
# =========================================================================

# ----- Namespaces -----
resource "kubernetes_namespace" "search" {
  metadata {
    name = var.search_namespace
  }
}

resource "kubernetes_namespace" "inference" {
  metadata {
    name = var.inference_namespace
  }
}

# ----- KSA with Workload Identity annotation -----
resource "kubernetes_service_account" "api" {
  metadata {
    name      = var.ksa_names.api
    namespace = kubernetes_namespace.search.metadata[0].name
    annotations = {
      "iam.gke.io/gcp-service-account" = var.service_accounts.api.email
    }
  }
}

resource "kubernetes_service_account" "encoder" {
  metadata {
    name      = var.ksa_names.encoder
    namespace = kubernetes_namespace.inference.metadata[0].name
    annotations = {
      "iam.gke.io/gcp-service-account" = var.service_accounts.endpoint_encoder.email
    }
  }
}

resource "kubernetes_service_account" "reranker" {
  metadata {
    name      = var.ksa_names.reranker
    namespace = kubernetes_namespace.inference.metadata[0].name
    annotations = {
      "iam.gke.io/gcp-service-account" = var.service_accounts.endpoint_reranker.email
    }
  }
}

# ----- cert-manager (KServe 前提) -----
resource "helm_release" "cert_manager" {
  name             = "cert-manager"
  namespace        = "cert-manager"
  create_namespace = true
  repository       = "https://charts.jetstack.io"
  chart            = "cert-manager"
  version          = var.cert_manager_version

  set {
    name  = "installCRDs"
    value = "true"
  }
}

# ----- KServe (RawDeployment mode — Knative 非依存) -----
#
# Phase 6 は Knative Serving を載せない RawDeployment (K8s Deployment +
# HPA + Gateway API) を採用。Autopilot の互換性と 0→N スケールに
# 依存しない前提のため。
# -------------------------------------------------------------------------
resource "helm_release" "kserve_crd" {
  name             = "kserve-crd"
  namespace        = "kserve"
  create_namespace = true
  repository       = "oci://ghcr.io/kserve/charts"
  chart            = "kserve-crd"
  version          = var.kserve_version

  depends_on = [helm_release.cert_manager]
}

resource "helm_release" "kserve" {
  name             = "kserve"
  namespace        = "kserve"
  create_namespace = false
  repository       = "oci://ghcr.io/kserve/charts"
  chart            = "kserve"
  version          = var.kserve_version

  set {
    name  = "kserve.controller.deploymentMode"
    value = "RawDeployment"
  }

  # RawDeployment では Gateway API を直接扱う
  set {
    name  = "kserve.controller.gateway.ingressGateway.enableGatewayApi"
    value = "true"
  }

  depends_on = [
    helm_release.kserve_crd,
    helm_release.cert_manager,
  ]
}
