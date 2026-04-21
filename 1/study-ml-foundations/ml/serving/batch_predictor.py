import pandas as pd

from ml.common.utils.schema import FEATURE_COLS
from ml.serving.predictor import Predictor


class BatchPredictor:
    def __init__(self, predictor: Predictor) -> None:
        self.predictor = predictor

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for _, row in df.iterrows():
            values = {col: float(row[col]) for col in FEATURE_COLS}
            rows.append(self.predictor.predict(values))
        out = df.copy()
        out["predicted_price"] = rows
        return out
