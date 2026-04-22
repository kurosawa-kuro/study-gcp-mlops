from fastapi import APIRouter, Request

from app.schemas.predict import PredictRequest
from app.services.prediction_service import predict_price

router = APIRouter()


@router.post("/predict")
def predict(request: Request, req: PredictRequest):
    booster = request.app.state.booster
    price = predict_price(booster, req.model_dump())
    return {"predicted_price": price}


@router.get("/health")
def health():
    return {"status": "ok"}
