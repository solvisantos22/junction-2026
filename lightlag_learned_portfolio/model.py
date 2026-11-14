"""Three pinned classical regression models for strategy reward differences."""

import hashlib
import pickle
import time

import numpy as np
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .policy import PROFILE_NAMES

ALGORITHMS = ("extra_trees", "hist_boost", "ridge")


def fit(algorithm, data):
    start = time.perf_counter()
    x, y = np.asarray(data["x"], dtype=float), np.asarray(data["y"], dtype=float)
    assert len(x) == len(y) and y.shape[1] == len(PROFILE_NAMES) - 1
    if algorithm == "extra_trees":
        model = ExtraTreesRegressor(n_estimators=400, max_depth=8, min_samples_leaf=6, n_jobs=1, random_state=17)
    elif algorithm == "hist_boost":
        model = MultiOutputRegressor(HistGradientBoostingRegressor(max_iter=160, max_leaf_nodes=7,
                    min_samples_leaf=12, l2_regularization=5., learning_rate=.05, random_state=17), n_jobs=1)
    elif algorithm == "ridge":
        model = make_pipeline(StandardScaler(), Ridge(alpha=50.))
    else:
        raise ValueError("unknown algorithm")
    model.fit(x, y)
    model.feature_names_ = data["feature_names"]
    prediction = model.predict(x)
    weights = pickle.dumps(model, protocol=5)
    return {"algorithm": algorithm, "weights": weights, "sha256": hashlib.sha256(weights).hexdigest(),
            "seconds": time.perf_counter() - start, "training_rows": len(x), "features": x.shape[1],
            "train_mse": float(np.mean((prediction-y)**2)), "train_predictions": prediction.tolist(),
            "hyperparameters": model.get_params(deep=False).__repr__()}
