"""Four fixed model families and validation-only decision settings."""

import hashlib
import pickle
import time
import warnings
import numpy as np
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor, RandomForestClassifier
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from .policy import PROFILE_NAMES, descriptors

ALGORITHMS = ("extra_trees", "random_forest", "pooled_forest", "mlp")


class Model:
    def __init__(self, algorithm, feature_names, estimator, failure=None):
        self.algorithm, self.feature_names = algorithm, feature_names
        self.estimator, self.failure = estimator, failure

    def predict(self, x):
        x = np.asarray(x, dtype=float)
        if self.algorithm == "pooled_forest":
            desc = np.asarray(descriptors()); n, k = len(x), len(desc)
            expanded = np.column_stack((np.repeat(x, k, axis=0), np.tile(desc, (n, 1))))
            mean = self.estimator.predict(expanded).reshape(n, k)
            classes = list(self.failure.classes_)
            failure = (self.failure.predict_proba(expanded)[:, classes.index(1)].reshape(n, k)
                       if 1 in classes else np.zeros_like(mean))
            return mean, np.zeros_like(mean), failure
        mean = self.estimator.predict(x)
        if self.algorithm in ("extra_trees", "random_forest"):
            std = np.std(np.asarray([tree.predict(x) for tree in self.estimator.estimators_]), axis=0)
        else: std = np.zeros_like(mean)
        return mean, std, np.zeros_like(mean)

    def choose(self, state, setting):
        mean, spread, failure = (a[0] for a in self.predict([[state[n] for n in self.feature_names]]))
        utility = mean-setting.get("disagreement", 0)*spread-setting.get("risk_penalty", 0)*failure
        index = int(np.argmax(utility))
        name = PROFILE_NAMES[index+1] if utility[index] > setting["threshold"] else "baseline"
        return name, {"mean": mean.tolist(), "spread": spread.tolist(), "failure": failure.tolist(),
                      "utility": utility.tolist()}


def settings(algorithm):
    for threshold in (0., .002, .005):
        penalties = (0., .5) if algorithm in ("extra_trees", "random_forest") else ((0., .1, .3) if algorithm == "pooled_forest" else (0.,))
        for penalty in penalties:
            yield {"threshold": threshold, "disagreement": penalty if algorithm in ("extra_trees", "random_forest") else 0.,
                   "risk_penalty": penalty if algorithm == "pooled_forest" else 0.}


def fit(algorithm, data):
    start = time.perf_counter(); x, y = np.asarray(data["x"]), np.asarray(data["y"])
    assert y.shape == (len(x), len(PROFILE_NAMES)-1)
    failure = None
    if algorithm == "extra_trees":
        estimator = ExtraTreesRegressor(n_estimators=400, max_depth=10, min_samples_leaf=5, n_jobs=1, random_state=37)
    elif algorithm == "random_forest":
        estimator = RandomForestRegressor(n_estimators=400, max_depth=10, min_samples_leaf=5, max_features=.8, n_jobs=1, random_state=37)
    elif algorithm == "pooled_forest":
        estimator = RandomForestRegressor(n_estimators=400, max_depth=12, min_samples_leaf=12, max_features=.8, n_jobs=1, random_state=37)
        failure = RandomForestClassifier(n_estimators=300, max_depth=12, min_samples_leaf=5,
                                         class_weight="balanced_subsample", n_jobs=1, random_state=37)
    elif algorithm == "mlp":
        estimator = TransformedTargetRegressor(
            regressor=make_pipeline(StandardScaler(), MLPRegressor(hidden_layer_sizes=(96, 48), activation="tanh",
                alpha=.02, learning_rate_init=.001, max_iter=800, early_stopping=True,
                validation_fraction=.15, n_iter_no_change=25, random_state=37)), transformer=StandardScaler())
    else: raise ValueError("unknown model family")
    with warnings.catch_warnings(record=True) as emitted:
        warnings.simplefilter("always")
        if failure is None:
            estimator.fit(x, y)
        else:
            desc = np.asarray(descriptors()); k = len(desc)
            expanded = np.column_stack((np.repeat(x, k, axis=0), np.tile(desc, (len(x), 1))))
            estimator.fit(expanded, y.ravel())
            failure.fit(expanded, 1-np.asarray(data["home_alive"], dtype=int).ravel())
    model = Model(algorithm, data["feature_names"], estimator, failure)
    prediction = model.predict(x)[0]; weights = pickle.dumps(model, protocol=5)
    return {"algorithm": algorithm, "weights": weights, "sha256": hashlib.sha256(weights).hexdigest(),
            "seconds": time.perf_counter()-start, "training_worlds": len(x), "features": x.shape[1],
            "training_mse": float(np.mean((prediction-y)**2)), "training_predictions": prediction.tolist(),
            "warnings": [str(w.message) for w in emitted], "parameters": repr(estimator.get_params(deep=True))}
