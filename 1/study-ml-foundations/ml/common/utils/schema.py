"""プロジェクト共通の特徴量・ターゲット定義."""

FEATURE_COLS = [
    "MedInc",
    "HouseAge",
    "AveRooms",
    "AveBedrms",
    "Population",
    "AveOccup",
    "Latitude",
    "Longitude",
]

ENGINEERED_COLS = [
    "BedroomRatio",
    "RoomsPerPerson",
]

MODEL_COLS = FEATURE_COLS + ENGINEERED_COLS

TARGET_COL = "Price"
