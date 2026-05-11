"""
ML Models for ATM anomaly detection.
6 specialized detectors covering different failure modes.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional
from sklearn.ensemble import IsolationForest
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler


@dataclass
class AnomalyResult:
    """Result from a single detector."""
    detector_name: str
    atm_id: str
    is_anomaly: bool
    score: float          # raw anomaly score (higher = more anomalous)
    confidence: float     # [0, 1]
    reason: str
    severity: str         # "LOW", "HIGH", "CRITICAL"


@dataclass
class DetectionReport:
    """Aggregated results for a batch."""
    batch_timestamp: str
    n_atms_evaluated: int
    n_anomalies_detected: int
    results: list[AnomalyResult] = field(default_factory=list)

    @property
    def anomaly_rate(self) -> float:
        return self.n_anomalies_detected / max(self.n_atms_evaluated, 1)

    def anomalies_df(self) -> pd.DataFrame:
        return pd.DataFrame([r.__dict__ for r in self.results if r.is_anomaly])


# ── Detector 1: Isolation Forest (general anomaly detection) ─────────────────

class IsolationForestDetector:
    """General-purpose anomaly detection using Isolation Forest."""

    FEATURES = [
        "tx_count", "error_rate", "amount_mean", "amount_std",
        "tx_velocity", "hw_error_rate", "offline_minutes",
        "overall_risk_score",
    ]
    NAME = "IsolationForest"

    def __init__(self, contamination: float = 0.05, n_estimators: int = 100):
        self.contamination = contamination
        self.model = IsolationForest(
            contamination=contamination,
            n_estimators=n_estimators,
            random_state=42,
        )
        self.scaler = StandardScaler()
        self._fitted = False

    def fit(self, features_df: pd.DataFrame) -> "IsolationForestDetector":
        X = self._prepare(features_df)
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)
        self._fitted = True
        return self

    def predict(self, features_df: pd.DataFrame) -> list[AnomalyResult]:
        if not self._fitted:
            self.fit(features_df)

        X = self._prepare(features_df)
        X_scaled = self.scaler.transform(X)
        scores = -self.model.score_samples(X_scaled)   # higher = more anomalous
        labels = self.model.predict(X_scaled)           # -1 = anomaly, 1 = normal

        results = []
        for i, (atm_id, row) in enumerate(features_df.iterrows()):
            is_anomaly = labels[i] == -1
            score = float(scores[i])
            confidence = min(1.0, score / 1.0)
            severity = _score_to_severity(score, thresholds=(0.55, 0.70))

            results.append(AnomalyResult(
                detector_name=self.NAME,
                atm_id=str(atm_id),
                is_anomaly=is_anomaly,
                score=round(score, 4),
                confidence=round(confidence, 4),
                reason=f"General anomaly pattern (IF score={score:.3f})",
                severity=severity,
            ))
        return results

    def _prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        cols = [c for c in self.FEATURES if c in df.columns]
        return df[cols].fillna(0)


# ── Detector 2: Z-Score (statistical threshold) ──────────────────────────────

class ZScoreDetector:
    """Detects ATMs with statistically unusual metrics (>3σ deviation)."""

    NAME = "ZScore"
    FEATURES = ["error_rate", "tx_velocity", "amount_mean", "hw_error_rate"]
    THRESHOLD = 2.5  # σ threshold for anomaly

    def __init__(self, threshold: float = 2.5):
        self.threshold = threshold
        self._stats: dict = {}

    def fit(self, features_df: pd.DataFrame) -> "ZScoreDetector":
        for col in self.FEATURES:
            if col in features_df.columns:
                self._stats[col] = {
                    "mean": features_df[col].mean(),
                    "std": features_df[col].std(),
                }
        return self

    def predict(self, features_df: pd.DataFrame) -> list[AnomalyResult]:
        if not self._stats:
            self.fit(features_df)

        results = []
        for atm_id, row in features_df.iterrows():
            max_z = 0.0
            worst_feature = ""
            for col in self.FEATURES:
                if col in self._stats and col in features_df.columns:
                    stat = self._stats[col]
                    if stat["std"] > 0:
                        z = abs((row[col] - stat["mean"]) / stat["std"])
                        if z > max_z:
                            max_z = z
                            worst_feature = col

            is_anomaly = max_z > self.threshold
            severity = _score_to_severity(max_z, thresholds=(self.threshold, self.threshold * 1.5))

            results.append(AnomalyResult(
                detector_name=self.NAME,
                atm_id=str(atm_id),
                is_anomaly=is_anomaly,
                score=round(max_z, 4),
                confidence=min(1.0, max_z / (self.threshold * 2)),
                reason=f"Statistical outlier on '{worst_feature}' (z={max_z:.2f}σ)" if is_anomaly else "Within normal range",
                severity=severity,
            ))
        return results


# ── Detector 3: DBSCAN (clustering — geographic/behavioral outliers) ─────────

class DBSCANDetector:
    """Clusters ATMs by behavior; points not in any cluster are anomalies."""

    NAME = "DBSCAN"
    FEATURES = ["tx_count_per_min", "error_rate", "hw_error_rate", "fraud_risk_score"]

    def __init__(self, eps: float = 0.5, min_samples: int = 5):
        self.eps = eps
        self.min_samples = min_samples
        self.scaler = StandardScaler()
        self._labels: Optional[np.ndarray] = None

    def predict(self, features_df: pd.DataFrame) -> list[AnomalyResult]:
        cols = [c for c in self.FEATURES if c in features_df.columns]
        X = features_df[cols].fillna(0).values
        X_scaled = self.scaler.fit_transform(X)

        db = DBSCAN(eps=self.eps, min_samples=self.min_samples)
        labels = db.fit_predict(X_scaled)
        self._labels = labels

        results = []
        for i, (atm_id, row) in enumerate(features_df.iterrows()):
            is_anomaly = labels[i] == -1  # -1 = noise / outlier in DBSCAN
            score = 1.0 if is_anomaly else 0.0

            results.append(AnomalyResult(
                detector_name=self.NAME,
                atm_id=str(atm_id),
                is_anomaly=is_anomaly,
                score=score,
                confidence=0.7 if is_anomaly else 0.0,
                reason="Behavioral outlier — no cluster match" if is_anomaly else "Normal cluster member",
                severity="HIGH" if is_anomaly else "LOW",
            ))
        return results


# ── Detector 4: Offline Detector ──────────────────────────────────────────────

class OfflineDetector:
    """Detects ATMs that are offline or have severe connectivity issues."""

    NAME = "OfflineDetector"

    def __init__(self, offline_threshold_minutes: float = 5.0, score_threshold: float = 0.3):
        self.offline_threshold = offline_threshold_minutes
        self.score_threshold = score_threshold

    def fit(self, features_df: pd.DataFrame) -> "OfflineDetector":
        return self  # stateless

    def predict(self, features_df: pd.DataFrame) -> list[AnomalyResult]:
        results = []
        for atm_id, row in features_df.iterrows():
            offline_min = row.get("offline_minutes", 0)
            connectivity = row.get("connectivity_score", 1.0)
            is_offline_flag = row.get("is_offline", 0)

            is_anomaly = (
                offline_min >= self.offline_threshold
                or connectivity < (1 - self.score_threshold)
                or bool(is_offline_flag)
            )

            score = max(
                offline_min / max(self.offline_threshold, 1),
                1 - connectivity,
            )
            score = min(1.0, score)
            severity = "CRITICAL" if offline_min > 30 else ("HIGH" if is_anomaly else "LOW")

            results.append(AnomalyResult(
                detector_name=self.NAME,
                atm_id=str(atm_id),
                is_anomaly=is_anomaly,
                score=round(score, 4),
                confidence=round(score, 4),
                reason=f"ATM offline {offline_min:.1f} min / connectivity={connectivity:.2f}" if is_anomaly else "Online",
                severity=severity,
            ))
        return results


# ── Detector 5: Fraud Detector ────────────────────────────────────────────────

class FraudDetector:
    """Detects skimming / rapid-succession fraud patterns."""

    NAME = "FraudDetector"

    def __init__(self, fraud_threshold: float = 0.6):
        self.fraud_threshold = fraud_threshold

    def fit(self, features_df: pd.DataFrame) -> "FraudDetector":
        return self

    def predict(self, features_df: pd.DataFrame) -> list[AnomalyResult]:
        results = []
        for atm_id, row in features_df.iterrows():
            fraud_score = row.get("fraud_risk_score", 0.0)
            velocity = row.get("tx_velocity", 0.0)
            amount_z = abs(row.get("amount_zscore", 0.0))

            is_anomaly = fraud_score >= self.fraud_threshold

            if velocity > 8:
                reason = f"High tx velocity ({velocity:.1f} tx/min) — possible skimming"
            elif amount_z > 2.5:
                reason = f"Unusual amounts (z={amount_z:.1f}σ) — possible fraud"
            elif is_anomaly:
                reason = f"Fraud risk score {fraud_score:.2f} above threshold"
            else:
                reason = "No fraud pattern detected"

            severity = "CRITICAL" if fraud_score > 0.8 else ("HIGH" if is_anomaly else "LOW")

            results.append(AnomalyResult(
                detector_name=self.NAME,
                atm_id=str(atm_id),
                is_anomaly=is_anomaly,
                score=round(fraud_score, 4),
                confidence=round(fraud_score, 4),
                reason=reason,
                severity=severity,
            ))
        return results


# ── Detector 6: Hardware Predictor ────────────────────────────────────────────

class HardwarePredictor:
    """Predicts imminent hardware failures based on error rates and trends."""

    NAME = "HardwarePredictor"

    def __init__(self, hw_risk_threshold: float = 0.4):
        self.hw_risk_threshold = hw_risk_threshold

    def fit(self, features_df: pd.DataFrame) -> "HardwarePredictor":
        return self

    def predict(self, features_df: pd.DataFrame) -> list[AnomalyResult]:
        results = []
        for atm_id, row in features_df.iterrows():
            hw_risk = row.get("hardware_risk_score", 0.0)
            hw_errors = row.get("hw_error_count", 0)
            hw_critical = row.get("hw_critical_count", 0)

            is_anomaly = hw_risk >= self.hw_risk_threshold or hw_critical > 0

            if hw_critical > 0:
                reason = f"Critical hardware failure detected ({hw_critical} critical events)"
            elif hw_errors > 3:
                reason = f"Multiple hardware errors ({hw_errors}) — maintenance needed"
            elif is_anomaly:
                reason = f"Hardware risk score {hw_risk:.2f} — predictive maintenance alert"
            else:
                reason = "Hardware within normal parameters"

            severity = "CRITICAL" if hw_critical > 0 else ("HIGH" if is_anomaly else "LOW")

            results.append(AnomalyResult(
                detector_name=self.NAME,
                atm_id=str(atm_id),
                is_anomaly=is_anomaly,
                score=round(hw_risk, 4),
                confidence=round(hw_risk, 4),
                reason=reason,
                severity=severity,
            ))
        return results


# ── Ensemble runner ───────────────────────────────────────────────────────────

def run_all_detectors(
    features_df: pd.DataFrame,
    batch_timestamp: Optional[str] = None,
) -> DetectionReport:
    """
    Run all 6 detectors on feature data and return a consolidated report.
    """
    if batch_timestamp is None:
        batch_timestamp = pd.Timestamp.now().isoformat()

    detectors = [
        IsolationForestDetector(),
        ZScoreDetector(),
        DBSCANDetector(),
        OfflineDetector(),
        FraudDetector(),
        HardwarePredictor(),
    ]

    all_results: list[AnomalyResult] = []
    anomaly_atms: set[str] = set()

    for detector in detectors:
        results = detector.predict(features_df)
        all_results.extend(results)
        for r in results:
            if r.is_anomaly:
                anomaly_atms.add(r.atm_id)

    return DetectionReport(
        batch_timestamp=batch_timestamp,
        n_atms_evaluated=len(features_df),
        n_anomalies_detected=len(anomaly_atms),
        results=all_results,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _score_to_severity(score: float, thresholds: tuple[float, float]) -> str:
    low_t, high_t = thresholds
    if score >= high_t:
        return "CRITICAL"
    elif score >= low_t:
        return "HIGH"
    return "LOW"
