"""Baseline models and non-short Spot trade accounting."""

from dataclasses import dataclass
from typing import Dict, List, Protocol
import numpy as np


@dataclass(frozen=True)
class BaselineMetrics:
    name: str
    sample_count: int
    accuracy: float
    precision_up: float
    recall_up: float
    spot_mean_return_per_signal: float
    spot_cumulative_return: float
    up_predictions_count: int
    down_predictions_count: int


class BaselineStrategy(Protocol):
    name: str

    def fit(self, y_train: np.ndarray) -> None:
        ...

    def predict(self, X: np.ndarray) -> np.ndarray:
        ...


class AlwaysUpBaseline:
    name = "Always_UP"

    def fit(self, y_train: np.ndarray) -> None:
        pass

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.ones(len(X), dtype=int)


class AlwaysDownBaseline:
    name = "Always_DOWN"

    def fit(self, y_train: np.ndarray) -> None:
        pass

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.zeros(len(X), dtype=int)


class MajorityClassBaseline:
    name = "Majority_Class"

    def __init__(self):
        self.majority_class = 1

    def fit(self, y_train: np.ndarray) -> None:
        if len(y_train) > 0:
            up_count = np.sum(y_train == 1)
            down_count = np.sum(y_train == 0)
            self.majority_class = 1 if up_count >= down_count else 0

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.full(len(X), self.majority_class, dtype=int)


class SimpleMomentumBaseline:
    name = "Simple_Momentum"

    def fit(self, y_train: np.ndarray) -> None:
        pass

    def predict(self, X: np.ndarray) -> np.ndarray:
        # Assumes feature 0 is ret_1 (1-bar return)
        if X.shape[1] > 0:
            return np.where(X[:, 0] > 0, 1, 0)
        return np.ones(len(X), dtype=int)


class BaselineEvaluator:
    """Evaluates prediction accuracy and Spot trading accounting.
    
    INVARIANT: Spot trading has no shorting. DOWN prediction stands aside in cash (0.0 return).
    """

    @staticmethod
    def evaluate(
        strategy: BaselineStrategy,
        X_test: np.ndarray,
        y_test: np.ndarray,  # 1 for UP, 0 for DOWN
        returns_test: np.ndarray,  # 30-minute forward return for each sample
    ) -> BaselineMetrics:
        preds = strategy.predict(X_test)
        n = len(y_test)

        if n == 0:
            return BaselineMetrics(
                name=strategy.name,
                sample_count=0,
                accuracy=0.0,
                precision_up=0.0,
                recall_up=0.0,
                spot_mean_return_per_signal=0.0,
                spot_cumulative_return=0.0,
                up_predictions_count=0,
                down_predictions_count=0,
            )

        acc = float(np.mean(preds == y_test))

        tp = np.sum((preds == 1) & (y_test == 1))
        fp = np.sum((preds == 1) & (y_test == 0))
        fn = np.sum((preds == 0) & (y_test == 1))

        precision_up = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        recall_up = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0

        # Spot trade accounting:
        # If predict UP (1): realize return_30m
        # If predict DOWN (0): stand aside in cash (realize 0.0 return)
        spot_realized_returns = np.where(preds == 1, returns_test, 0.0)
        mean_ret = float(np.mean(spot_realized_returns))
        cum_ret = float(np.sum(spot_realized_returns))

        return BaselineMetrics(
            name=strategy.name,
            sample_count=n,
            accuracy=acc,
            precision_up=precision_up,
            recall_up=recall_up,
            spot_mean_return_per_signal=mean_ret,
            spot_cumulative_return=cum_ret,
            up_predictions_count=int(np.sum(preds == 1)),
            down_predictions_count=int(np.sum(preds == 0)),
        )
