"""Outbound Port (Protocol) 定義のみ。外部 SDK 非依存。

TBD: Phase 1 の ml/data/loaders, ml/registry を参照し以下を定義する予定。
- DatasetReader: load(split: str) -> pd.DataFrame
- ModelStore: save(run_id, model) / load(run_id) -> Booster
- ExperimentTracker: log_metrics(run_id, metrics) / finish()
"""
