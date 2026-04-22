"""Dataset outbound port."""

from typing import Protocol

import pandas as pd


class DatasetReader(Protocol):
    def load(self, split: str) -> pd.DataFrame: ...
    def write(self, split: str, frame: pd.DataFrame) -> None: ...
    def write_predictions(self, run_id: str, frame: pd.DataFrame) -> None: ...
