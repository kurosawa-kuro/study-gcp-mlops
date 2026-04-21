def build_prediction_response(price: float) -> dict:
    return {"predicted_price": round(float(price), 4)}
