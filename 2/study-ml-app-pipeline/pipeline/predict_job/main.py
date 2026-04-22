"""Pipeline Inbound Adapter — batch predict job entrypoint.

TBD: container.model_store.load(run_id) → core.trainer.predict(frame) → 結果を
container.dataset.write(predictions) に書き出す。Phase 1 の
pipeline/batch_serving_job/main.py 相当を Port 呼び出し化。
"""


def main() -> None:
    raise NotImplementedError("Phase 2 skeleton: predict_job TBD")


if __name__ == "__main__":
    main()
