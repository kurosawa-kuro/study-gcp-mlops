import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error


def build_model(n_estimators: int = 100, max_depth: int = 10, random_state: int = 42) -> RandomForestRegressor:
    return RandomForestRegressor(
        n_estimators=n_estimators,
        max_depth=max_depth,
        random_state=random_state,
    )


def train(model: RandomForestRegressor, X_train: pd.DataFrame, y_train: pd.Series) -> RandomForestRegressor:
    model.fit(X_train, y_train)
    return model


def evaluate(model: RandomForestRegressor, X_test: pd.DataFrame, y_test: pd.Series) -> dict:
    y_pred = model.predict(X_test)
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    mae = float(mean_absolute_error(y_test, y_pred))
    return {"rmse": rmse, "mae": mae}
