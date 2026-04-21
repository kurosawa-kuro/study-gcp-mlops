from app.services.prediction_service import predict_price


class Predictor:
    def __init__(self, booster) -> None:
        self.booster = booster

    def predict(self, values: dict) -> float:
        return predict_price(self.booster, values)
