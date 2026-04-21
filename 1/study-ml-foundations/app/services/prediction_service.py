import numpy as np

from ml.common.utils.schema import MODEL_COLS
from ml.data.feature_engineering.feature_engineering import engineer_features_input
from ml.data.preprocess.preprocess import preprocess_input


def predict_price(booster, values: dict) -> float:
    transformed = preprocess_input(values)
    transformed = engineer_features_input(transformed)
    features = np.array([[transformed[col] for col in MODEL_COLS]])
    prediction = booster.predict(features)[0]
    return round(float(prediction), 4)
