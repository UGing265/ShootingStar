"""Model training, probability calibration, and versioned artifact persistence."""

import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler


class CalibratedLogisticRegressionModel:
    """Logistic Regression classifier with strictly separated Platt scaling calibration."""

    def __init__(self, c_reg: float = 1.0, random_state: int = 42):
        self.c_reg = c_reg
        self.random_state = random_state
        self.scaler = StandardScaler()
        self.base_model = LogisticRegression(
            C=self.c_reg,
            solver="lbfgs",
            random_state=self.random_state,
            max_iter=1000,
        )
        self.calibrator: Optional[LogisticRegression] = None

    def fit_and_calibrate(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_calib: np.ndarray,
        y_calib: np.ndarray,
    ) -> None:
        """Trains base classifier on train set, then calibrates on separate calibration set.
        
        Scaler is fitted strictly on X_train to prevent normalization leakage.
        Calibration uses Platt scaling: 1D sigmoid fit on decision values of the calibration set.
        """
        X_train_scaled = self.scaler.fit_transform(X_train)
        self.base_model.fit(X_train_scaled, y_train)

        # Calibrate probabilities on the dedicated calibration window via Platt scaling
        X_calib_scaled = self.scaler.transform(X_calib)
        z_calib = self.base_model.decision_function(X_calib_scaled).reshape(-1, 1)

        # Ensure both classes are present in calibration set for calibration fit
        unique_classes = np.unique(y_calib)
        if len(unique_classes) >= 2:
            self.calibrator = LogisticRegression(C=1.0, random_state=self.random_state, max_iter=500)
            self.calibrator.fit(z_calib, y_calib)
        else:
            self.calibrator = None

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Returns calibrated probability distribution [P(DOWN), P(UP)]."""
        X_scaled = self.scaler.transform(X)
        if self.calibrator is not None:
            z = self.base_model.decision_function(X_scaled).reshape(-1, 1)
            return self.calibrator.predict_proba(z)
        # Fallback to uncalibrated base model probabilities if calibration set lacked both classes
        return self.base_model.predict_proba(X_scaled)

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Returns binary directional prediction (0 for DOWN, 1 for UP)."""
        proba = self.predict_proba(X)
        return np.argmax(proba, axis=1)

    def save_artifact(self, model_dir: Path, experiment_id: str) -> Tuple[Path, str]:
        """Saves versioned artifact using joblib and returns (file_path, sha256_hash)."""
        model_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "experiment_id": experiment_id,
            "scaler": self.scaler,
            "base_model": self.base_model,
            "calibrator": self.calibrator,
            "c_reg": self.c_reg,
            "random_state": self.random_state,
        }

        temp_path = model_dir / f"temp_{experiment_id}.joblib"
        joblib.dump(payload, temp_path)

        file_bytes = temp_path.read_bytes()
        sha256_hash = hashlib.sha256(file_bytes).hexdigest()

        final_path = model_dir / f"{experiment_id}_{sha256_hash[:10]}.joblib"
        if final_path.exists():
            temp_path.unlink()
        else:
            temp_path.rename(final_path)

        return final_path, sha256_hash

    @classmethod
    def load_artifact(cls, path: Path) -> "CalibratedLogisticRegressionModel":
        payload = joblib.load(path)
        instance = cls(c_reg=payload["c_reg"], random_state=payload["random_state"])
        instance.scaler = payload["scaler"]
        instance.base_model = payload["base_model"]
        instance.calibrator = payload.get("calibrator")
        return instance
