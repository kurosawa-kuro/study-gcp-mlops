"""Ports for ``pipeline/data_job``.

Phase C-5: re-exports the canonical orchestration Ports defined in
``pipeline/training_job/ports`` so all four ``<verb>_job`` packages
share one Protocol surface. Job-specific Ports (e.g. data-quality
gates) belong here as separate modules — none yet.
"""

from pipeline.training_job.ports import (
    PipelineComponent,
    PipelineComponentRef,
    PipelineConfig,
    PipelineOrchestrator,
)

__all__ = [
    "PipelineComponent",
    "PipelineComponentRef",
    "PipelineConfig",
    "PipelineOrchestrator",
]
