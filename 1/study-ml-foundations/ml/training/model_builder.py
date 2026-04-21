def build_training_params() -> dict:
    return {
        "objective": "regression",
        "metric": "rmse",
        "learning_rate": 0.05,
        "num_leaves": 31,
        "verbosity": -1,
    }
