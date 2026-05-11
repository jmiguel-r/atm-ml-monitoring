"""
Feature engineering for ATM monitoring.
Generates 24 features per ATM from raw event data.
"""

import numpy as np
import pandas as pd
from typing import Optional


# Features produced by this module
FEATURE_COLUMNS = [
    # Transaction volume
    "tx_count", "tx_count_per_min",
    # Transaction success
    "error_rate", "consecutive_errors",
    # Amount statistics
    "amount_mean", "amount_std", "amount_max", "amount_zscore",
    # Speed / velocity
    "tx_velocity", "inter_tx_seconds_mean",
    # Hardware health
    "hw_error_count", "hw_critical_count", "hw_error_rate",
    # Connectivity
    "offline_minutes", "is_offline", "connectivity_score",
    # Time-based
    "hour_of_day", "is_business_hours", "is_weekend",
    # Rolling z-scores
    "tx_count_zscore", "error_rate_zscore",
    # Composite risk scores
    "hardware_risk_score", "fraud_risk_score", "overall_risk_score",
]


def extract_features(
    events: pd.DataFrame,
    fleet: pd.DataFrame,
    window_minutes: int = 15,
    reference_stats: Optional[dict] = None,
) -> pd.DataFrame:
    """
    Compute 24 features per ATM from a batch of raw events.

    Args:
        events: Raw event DataFrame from simulator.
        fleet: Fleet metadata DataFrame.
        window_minutes: Duration of the batch window.
        reference_stats: Optional dict with historical mean/std per ATM for z-scores.

    Returns:
        DataFrame indexed by atm_id with FEATURE_COLUMNS.
    """
    atm_ids = fleet["atm_id"].tolist()
    feature_rows = []

    tx_events = events[events["event_type"] == "transaction"].copy()
    hw_events = events[events["event_type"] == "hardware"].copy()
    conn_events = events[events["event_type"] == "connectivity"].copy()

    for atm_id in atm_ids:
        atm_tx = tx_events[tx_events["atm_id"] == atm_id]
        atm_hw = hw_events[hw_events["atm_id"] == atm_id]
        atm_conn = conn_events[conn_events["atm_id"] == atm_id]
        atm_meta = fleet[fleet["atm_id"] == atm_id].iloc[0]

        # ── Transaction features ──────────────────────────────────────────────
        tx_count = len(atm_tx)
        tx_count_per_min = tx_count / max(window_minutes, 1)
        errors = atm_tx[~atm_tx["success"]]
        error_rate = len(errors) / max(tx_count, 1)

        # Consecutive errors (worst streak)
        consecutive_errors = _max_consecutive_errors(atm_tx)

        # Amount statistics (withdrawals only)
        withdrawals = atm_tx[atm_tx["tx_type"] == "withdrawal"]["amount"]
        amount_mean = withdrawals.mean() if len(withdrawals) > 0 else 0.0
        amount_std = withdrawals.std() if len(withdrawals) > 1 else 0.0
        amount_max = withdrawals.max() if len(withdrawals) > 0 else 0.0

        # Amount z-score (how unusual is the mean amount?)
        if reference_stats and atm_id in reference_stats:
            ref = reference_stats[atm_id]
            amount_zscore = _zscore(amount_mean, ref.get("amount_mean_mean", amount_mean), ref.get("amount_mean_std", 1.0))
            tx_count_zscore = _zscore(tx_count, ref.get("tx_count_mean", tx_count), ref.get("tx_count_std", 1.0))
            error_rate_zscore = _zscore(error_rate, ref.get("error_rate_mean", error_rate), ref.get("error_rate_std", 0.01))
        else:
            amount_zscore = 0.0
            tx_count_zscore = 0.0
            error_rate_zscore = 0.0

        # Transaction velocity (tx per minute, fraud indicator)
        if tx_count >= 2 and len(atm_tx) >= 2:
            sorted_tx = atm_tx["timestamp"].sort_values()
            time_span = (sorted_tx.iloc[-1] - sorted_tx.iloc[0]).total_seconds() / 60.0
            tx_velocity = tx_count / max(time_span, 0.1)
            inter_tx_seconds = sorted_tx.diff().dt.total_seconds().dropna().mean() if len(sorted_tx) > 1 else 999.0
        else:
            tx_velocity = tx_count_per_min
            inter_tx_seconds = 999.0

        # ── Hardware features ─────────────────────────────────────────────────
        hw_error_count = len(atm_hw[~atm_hw["success"]])
        hw_critical_count = len(atm_hw[atm_hw.get("hw_status", pd.Series(["ok"] * len(atm_hw))).isin(["critical"])]) if "hw_status" in atm_hw.columns else 0
        hw_error_rate = hw_error_count / max(len(atm_hw), 1)

        # ── Connectivity features ─────────────────────────────────────────────
        if len(atm_conn) > 0 and "minutes_offline" in atm_conn.columns:
            offline_minutes = atm_conn["minutes_offline"].sum()
            is_offline = int(offline_minutes > 0)
        else:
            offline_minutes = 0.0
            is_offline = 0

        connectivity_score = max(0.0, 1.0 - (offline_minutes / max(window_minutes, 1)))

        # ── Time-based features ───────────────────────────────────────────────
        if len(atm_tx) > 0:
            ref_time = atm_tx["timestamp"].max()
        else:
            ref_time = pd.Timestamp.now()

        hour_of_day = ref_time.hour
        is_business_hours = int(9 <= hour_of_day <= 18)
        is_weekend = int(ref_time.weekday() >= 5)

        # ── Composite risk scores ─────────────────────────────────────────────
        hardware_risk_score = min(1.0, hw_error_rate * 5 + hw_critical_count * 0.3)
        fraud_risk_score = _compute_fraud_risk(tx_velocity, amount_zscore, tx_count, inter_tx_seconds)
        overall_risk_score = (
            0.3 * error_rate
            + 0.25 * hardware_risk_score
            + 0.25 * fraud_risk_score
            + 0.2 * (1 - connectivity_score)
        )

        feature_rows.append({
            "atm_id": atm_id,
            "region": atm_meta["region"],
            "age_years": atm_meta["age_years"],
            # Transaction
            "tx_count": tx_count,
            "tx_count_per_min": round(tx_count_per_min, 4),
            "error_rate": round(error_rate, 4),
            "consecutive_errors": consecutive_errors,
            "amount_mean": round(float(amount_mean), 2),
            "amount_std": round(float(amount_std), 2) if not np.isnan(amount_std) else 0.0,
            "amount_max": round(float(amount_max), 2),
            "amount_zscore": round(amount_zscore, 4),
            "tx_velocity": round(tx_velocity, 4),
            "inter_tx_seconds_mean": round(inter_tx_seconds, 2),
            # Hardware
            "hw_error_count": hw_error_count,
            "hw_critical_count": hw_critical_count,
            "hw_error_rate": round(hw_error_rate, 4),
            # Connectivity
            "offline_minutes": round(offline_minutes, 2),
            "is_offline": is_offline,
            "connectivity_score": round(connectivity_score, 4),
            # Time
            "hour_of_day": hour_of_day,
            "is_business_hours": is_business_hours,
            "is_weekend": is_weekend,
            # Z-scores
            "tx_count_zscore": round(tx_count_zscore, 4),
            "error_rate_zscore": round(error_rate_zscore, 4),
            # Composite
            "hardware_risk_score": round(hardware_risk_score, 4),
            "fraud_risk_score": round(fraud_risk_score, 4),
            "overall_risk_score": round(overall_risk_score, 4),
        })

    return pd.DataFrame(feature_rows).set_index("atm_id")


# ── Internal helpers ──────────────────────────────────────────────────────────

def _max_consecutive_errors(atm_tx: pd.DataFrame) -> int:
    """Return the longest streak of consecutive failed transactions."""
    if len(atm_tx) == 0:
        return 0
    successes = atm_tx.sort_values("timestamp")["success"].tolist()
    max_streak = streak = 0
    for s in successes:
        if not s:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    return max_streak


def _zscore(value: float, mean: float, std: float) -> float:
    """Safe z-score calculation."""
    if std == 0:
        return 0.0
    return (value - mean) / std


def _compute_fraud_risk(
    tx_velocity: float,
    amount_zscore: float,
    tx_count: int,
    inter_tx_seconds: float,
) -> float:
    """
    Heuristic fraud risk score [0, 1].
    High velocity + unusual amounts + low inter-tx time = high risk.
    """
    velocity_score = min(1.0, tx_velocity / 10.0)        # >10 tx/min is suspicious
    amount_score = min(1.0, abs(amount_zscore) / 3.0)    # >3σ is suspicious
    speed_score = max(0.0, 1.0 - inter_tx_seconds / 60.0)  # <1 min between tx is suspicious
    volume_score = min(1.0, tx_count / 50.0)              # >50 tx in window is suspicious

    return round(
        0.35 * velocity_score
        + 0.25 * amount_score
        + 0.25 * speed_score
        + 0.15 * volume_score,
        4,
    )
