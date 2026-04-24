# Phase 6 T5 — Cloud Monitoring Service + SLO + burn-rate AlertPolicy.
#
# Phase 5 already ships two log-based alert policies (5xx, p95 latency) via
# module.monitoring. Phase 6 adds *formal SLOs* on top of Cloud Run's built-in
# metrics (run.googleapis.com/request_count + request_latencies) so PMLE-style
# SLI / SLO / Error-Budget / Burn-Rate concepts are learnable against real
# telemetry from the same search-api service.
#
# Design:
#   * One google_monitoring_custom_service anchors both SLOs to the Cloud Run
#     service URI (telemetry.resource_name).
#   * Two google_monitoring_slo:
#       - availability (2xx/total ratio)
#       - latency (fraction of requests under latency_threshold_ms)
#   * Two google_monitoring_alert_policy per SLO (fast + slow burn) using the
#     select_slo_burn_rate() MQL helper. The default multipliers match the
#     Google SRE workbook "Alerting on SLOs" recommendations.
#
# The module takes notification_channel_ids as an input (list) so it can share
# the channel that module.monitoring already creates — no duplicate email
# channel resource here.

resource "google_monitoring_custom_service" "search_api" {
  project      = var.project_id
  service_id   = "${var.service_name}-${var.service_id_suffix}"
  display_name = "${var.service_name} (Phase 6 SLO anchor)"

  telemetry {
    resource_name = "//run.googleapis.com/projects/${var.project_id}/locations/${var.region}/services/${var.service_name}"
  }
}

# =========================================================================
# Availability SLO — 2xx / total on run.googleapis.com/request_count.
# =========================================================================

resource "google_monitoring_slo" "availability" {
  project      = var.project_id
  service      = google_monitoring_custom_service.search_api.service_id
  slo_id       = "availability-${replace(format("%.3f", var.availability_goal), ".", "p")}"
  display_name = "Availability ≥ ${format("%.1f%%", var.availability_goal * 100)} over ${var.rolling_period_days}d"

  goal                = var.availability_goal
  rolling_period_days = var.rolling_period_days

  request_based_sli {
    good_total_ratio {
      good_service_filter  = <<-EOT
        metric.type="run.googleapis.com/request_count"
        resource.type="cloud_run_revision"
        resource.label."service_name"="${var.service_name}"
        metric.label."response_code_class"="2xx"
      EOT
      total_service_filter = <<-EOT
        metric.type="run.googleapis.com/request_count"
        resource.type="cloud_run_revision"
        resource.label."service_name"="${var.service_name}"
      EOT
    }
  }
}

# =========================================================================
# Latency SLO — fraction of requests under latency_threshold_ms.
# Uses run.googleapis.com/request_latencies (DISTRIBUTION, unit=ms).
# =========================================================================

resource "google_monitoring_slo" "latency" {
  project      = var.project_id
  service      = google_monitoring_custom_service.search_api.service_id
  slo_id       = "latency-${var.latency_threshold_ms}ms-${replace(format("%.3f", var.latency_goal), ".", "p")}"
  display_name = "≥ ${format("%.0f%%", var.latency_goal * 100)} of requests < ${var.latency_threshold_ms}ms over ${var.rolling_period_days}d"

  goal                = var.latency_goal
  rolling_period_days = var.rolling_period_days

  request_based_sli {
    distribution_cut {
      distribution_filter = <<-EOT
        metric.type="run.googleapis.com/request_latencies"
        resource.type="cloud_run_revision"
        resource.label."service_name"="${var.service_name}"
      EOT
      range {
        max = var.latency_threshold_ms
      }
    }
  }
}

# =========================================================================
# Burn-rate alert policies — fast burn (2% of budget in 1h) + slow burn
# (10% of budget in 3d). Multipliers configurable via *_burn_threshold vars.
# =========================================================================

resource "google_monitoring_alert_policy" "availability_fast_burn" {
  project      = var.project_id
  display_name = "${var.service_name} availability SLO fast-burn (${var.fast_burn_threshold}x / 1h)"
  combiner     = "OR"

  conditions {
    display_name = "Fast burn"
    condition_threshold {
      filter          = "select_slo_burn_rate(\"${google_monitoring_slo.availability.name}\", \"3600s\")"
      duration        = "0s"
      comparison      = "COMPARISON_GT"
      threshold_value = var.fast_burn_threshold
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
      trigger { count = 1 }
    }
  }

  notification_channels = var.notification_channel_ids
}

resource "google_monitoring_alert_policy" "availability_slow_burn" {
  project      = var.project_id
  display_name = "${var.service_name} availability SLO slow-burn (${var.slow_burn_threshold}x / 3d)"
  combiner     = "OR"

  conditions {
    display_name = "Slow burn"
    condition_threshold {
      filter          = "select_slo_burn_rate(\"${google_monitoring_slo.availability.name}\", \"259200s\")"
      duration        = "0s"
      comparison      = "COMPARISON_GT"
      threshold_value = var.slow_burn_threshold
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
      trigger { count = 1 }
    }
  }

  notification_channels = var.notification_channel_ids
}

resource "google_monitoring_alert_policy" "latency_fast_burn" {
  project      = var.project_id
  display_name = "${var.service_name} latency SLO fast-burn (${var.fast_burn_threshold}x / 1h)"
  combiner     = "OR"

  conditions {
    display_name = "Fast burn"
    condition_threshold {
      filter          = "select_slo_burn_rate(\"${google_monitoring_slo.latency.name}\", \"3600s\")"
      duration        = "0s"
      comparison      = "COMPARISON_GT"
      threshold_value = var.fast_burn_threshold
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
      trigger { count = 1 }
    }
  }

  notification_channels = var.notification_channel_ids
}

resource "google_monitoring_alert_policy" "latency_slow_burn" {
  project      = var.project_id
  display_name = "${var.service_name} latency SLO slow-burn (${var.slow_burn_threshold}x / 3d)"
  combiner     = "OR"

  conditions {
    display_name = "Slow burn"
    condition_threshold {
      filter          = "select_slo_burn_rate(\"${google_monitoring_slo.latency.name}\", \"259200s\")"
      duration        = "0s"
      comparison      = "COMPARISON_GT"
      threshold_value = var.slow_burn_threshold
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
      trigger { count = 1 }
    }
  }

  notification_channels = var.notification_channel_ids
}
