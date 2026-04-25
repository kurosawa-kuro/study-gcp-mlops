"""Adapters for ``pipeline/batch_serving_job`` (re-export of the canonical KFP adapter)."""

from pipeline.training_job.adapters import KFPOrchestrator

__all__ = ["KFPOrchestrator"]
