"""Pipeline Inbound Adapter — train job entrypoint.

TBD: container.dataset.load() → core.preprocess → core.feature_engineering →
core.trainer.train → container.model_store.save → container.tracker.log_metrics。
Phase 1 の pipeline/training_job/main.py + pipeline/evaluation_job/main.py を統合。
"""


def main() -> None:
    raise NotImplementedError("Phase 2 skeleton: train_job TBD")


if __name__ == "__main__":
    main()
