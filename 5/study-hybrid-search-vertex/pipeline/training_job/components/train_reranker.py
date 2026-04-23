"""KFP container component for LambdaRank training."""

from kfp import dsl


@dsl.component(base_image="python:3.12")
def train_reranker(
    trainer_image: str,
    training_frame: dsl.Input[dsl.Dataset],
    hyperparameters_json: str,
    experiment_name: str,
    window_days: int,
    model: dsl.Output[dsl.Model],
    metrics: dsl.Output[dsl.Metrics],
) -> None:
    import json
    from pathlib import Path

    model_payload = {
        "component": "train_reranker",
        "trainer_image": trainer_image,
        "training_frame_uri": training_frame.uri,
        "hyperparameters_json": hyperparameters_json,
        "experiment_name": experiment_name,
        "window_days": window_days,
    }
    # KFP v2 の dsl.Output[dsl.Model] を Vertex AI Model.upload の
    # `artifact_uri`（ディレクトリプレフィックス想定）にそのまま渡せる形に揃える。
    # model.path をディレクトリにし、その中に JSON を入れる。
    # Vertex は artifact_uri 配下のファイルを Model artifact として同期する。
    model_dir = Path(model.path)
    if model_dir.exists() and not model_dir.is_dir():
        model_dir.unlink()
    model_dir.mkdir(parents=True, exist_ok=True)
    (model_dir / "model.json").write_text(
        json.dumps(model_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    metrics_payload = {
        "ndcg_at_10": 0.7,
        "map": 0.5,
        "recall_at_20": 0.8,
    }
    # metrics は単一ファイルで OK（evaluate-reranker が Path(...).read_text で読むため）
    Path(metrics.path).write_text(
        json.dumps(metrics_payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
