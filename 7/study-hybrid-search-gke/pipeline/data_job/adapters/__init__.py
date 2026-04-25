"""Adapters for ``pipeline/data_job`` (re-export of the canonical KFP adapter)."""

from pipeline.training_job.adapters import KFPOrchestrator

__all__ = ["KFPOrchestrator"]
