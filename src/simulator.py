"""
ATM Event Simulator — generates realistic events for 10,000+ ATMs.
Covers transactions, hardware, connectivity, and system events.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random
from typing import Optional

# Reproducibility
SEED = 42
np.random.seed(SEED)
random.seed(SEED)

# ATM regions for geographic distribution
REGIONS = ["CDMX", "GDL", "MTY", "QRO", "PUE", "MER", "TIJ", "CUN", "HMO", "VER"]

# Hardware components that can fail
HARDWARE_COMPONENTS = ["card_reader", "cash_dispenser", "receipt_printer", "keypad", "camera", "network_card"]

# Transaction types
TX_TYPES = ["withdrawal", "deposit", "balance_inquiry", "transfer", "payment"]

# Error codes
ERROR_CODES = {
    "card_reader": ["E001", "E002", "E003"],
    "cash_dispenser": ["E010", "E011", "E012", "E013"],
    "receipt_printer": ["E020", "E021"],
    "keypad": ["E030"],
    "camera": ["E040"],
    "network_card": ["E050", "E051"],
    "transaction": ["T001", "T002", "T003", "T004"],
}


def generate_atm_fleet(n_atms: int = 10_000) -> pd.DataFrame:
    """Generate a fleet of ATMs with realistic metadata."""
    np.random.seed(SEED)
    atm_ids = [f"ATM_{str(i).zfill(6)}" for i in range(1, n_atms + 1)]
    regions = np.random.choice(REGIONS, size=n_atms)
    install_years = np.random.randint(2010, 2023, size=n_atms)
    models = np.random.choice(["NCR-6622", "Diebold-DN200", "Nautilus-NH2700", "Wincor-ProCash"], size=n_atms)

    fleet = pd.DataFrame({
        "atm_id": atm_ids,
        "region": regions,
        "install_year": install_years,
        "model": models,
        "age_years": 2024 - install_years,
    })
    return fleet


def simulate_transactions(
    fleet: pd.DataFrame,
    start_time: datetime,
    duration_minutes: int = 15,
    base_tps: float = 0.5,  # transactions per ATM per minute
) -> pd.DataFrame:
    """Simulate transaction events across the fleet."""
    events = []
    end_time = start_time + timedelta(minutes=duration_minutes)

    for _, atm in fleet.iterrows():
        atm_id = atm["atm_id"]
        age_factor = 1 + (atm["age_years"] * 0.02)  # older ATMs slightly more error-prone

        # Number of transactions in this window
        n_tx = np.random.poisson(base_tps * duration_minutes)

        for _ in range(n_tx):
            ts = start_time + timedelta(seconds=random.uniform(0, duration_minutes * 60))
            hour = ts.hour

            # Business hours effect
            if 9 <= hour <= 18:
                amount = np.random.lognormal(mean=5.5, sigma=0.8)  # higher amounts during day
            else:
                amount = np.random.lognormal(mean=4.5, sigma=1.0)

            amount = round(min(amount, 10_000), 2)
            tx_type = random.choices(TX_TYPES, weights=[0.6, 0.1, 0.2, 0.05, 0.05])[0]

            # Error probability increases with age
            error_prob = 0.02 * age_factor
            success = random.random() > error_prob
            error_code = None

            if not success:
                if tx_type == "withdrawal":
                    error_code = random.choice(ERROR_CODES["cash_dispenser"])
                else:
                    error_code = random.choice(ERROR_CODES["transaction"])

            events.append({
                "timestamp": ts,
                "atm_id": atm_id,
                "region": atm["region"],
                "event_type": "transaction",
                "tx_type": tx_type,
                "amount": amount if tx_type in ["withdrawal", "deposit"] else 0,
                "success": success,
                "error_code": error_code,
                "component": None,
                "duration_ms": int(np.random.exponential(scale=3000)) if success else int(np.random.exponential(scale=8000)),
            })

    return pd.DataFrame(events)


def simulate_hardware_events(
    fleet: pd.DataFrame,
    start_time: datetime,
    duration_minutes: int = 15,
    anomaly_rate: float = 0.005,
) -> pd.DataFrame:
    """Simulate hardware status events."""
    events = []
    end_time = start_time + timedelta(minutes=duration_minutes)

    for _, atm in fleet.iterrows():
        atm_id = atm["atm_id"]
        age_factor = 1 + (atm["age_years"] * 0.05)

        for component in HARDWARE_COMPONENTS:
            # Each component sends a heartbeat
            ts = start_time + timedelta(seconds=random.uniform(0, duration_minutes * 60))
            failure_prob = anomaly_rate * age_factor

            status = "ok"
            error_code = None

            if random.random() < failure_prob:
                status = random.choice(["warning", "error", "critical"])
                if component in ERROR_CODES:
                    error_code = random.choice(ERROR_CODES[component])

            events.append({
                "timestamp": ts,
                "atm_id": atm_id,
                "region": atm["region"],
                "event_type": "hardware",
                "tx_type": None,
                "amount": 0,
                "success": status == "ok",
                "error_code": error_code,
                "component": component,
                "duration_ms": 0,
                "hw_status": status,
            })

    return pd.DataFrame(events)


def simulate_connectivity_events(
    fleet: pd.DataFrame,
    start_time: datetime,
    duration_minutes: int = 15,
    offline_rate: float = 0.003,
) -> pd.DataFrame:
    """Simulate ATM connectivity (online/offline) events."""
    events = []

    for _, atm in fleet.iterrows():
        atm_id = atm["atm_id"]

        # Each ATM sends a heartbeat
        ts = start_time + timedelta(seconds=random.uniform(0, duration_minutes * 60))
        is_offline = random.random() < offline_rate
        minutes_offline = np.random.exponential(scale=30) if is_offline else 0

        events.append({
            "timestamp": ts,
            "atm_id": atm_id,
            "region": atm["region"],
            "event_type": "connectivity",
            "tx_type": None,
            "amount": 0,
            "success": not is_offline,
            "error_code": "E050" if is_offline else None,
            "component": "network_card",
            "duration_ms": int(minutes_offline * 60_000),
            "minutes_offline": round(minutes_offline, 1),
        })

    return pd.DataFrame(events)


def simulate_batch(
    n_atms: int = 10_000,
    start_time: Optional[datetime] = None,
    duration_minutes: int = 15,
    inject_anomalies: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run a full simulation batch.
    Returns (fleet_df, events_df).
    """
    if start_time is None:
        start_time = datetime.now().replace(second=0, microsecond=0)

    fleet = generate_atm_fleet(n_atms)

    tx_events = simulate_transactions(fleet, start_time, duration_minutes)
    hw_events = simulate_hardware_events(fleet, start_time, duration_minutes)
    conn_events = simulate_connectivity_events(fleet, start_time, duration_minutes)

    # Optionally inject known anomalies for testing
    if inject_anomalies:
        fleet, tx_events = _inject_anomalies(fleet, tx_events, start_time)

    events = pd.concat([tx_events, hw_events, conn_events], ignore_index=True)
    events = events.sort_values("timestamp").reset_index(drop=True)

    return fleet, events


def _inject_anomalies(
    fleet: pd.DataFrame,
    tx_events: pd.DataFrame,
    start_time: datetime,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Inject known anomalies into a random subset of ATMs."""
    anomaly_atms = fleet.sample(n=min(50, len(fleet)), random_state=SEED)["atm_id"].tolist()

    extra_events = []
    for atm_id in anomaly_atms[:25]:
        # Fraud pattern: many small transactions in rapid succession
        for i in range(20):
            ts = start_time + timedelta(seconds=i * 15)
            extra_events.append({
                "timestamp": ts,
                "atm_id": atm_id,
                "region": fleet[fleet["atm_id"] == atm_id]["region"].values[0],
                "event_type": "transaction",
                "tx_type": "withdrawal",
                "amount": random.uniform(100, 500),
                "success": True,
                "error_code": None,
                "component": None,
                "duration_ms": 2000,
            })

    if extra_events:
        extra_df = pd.DataFrame(extra_events)
        tx_events = pd.concat([tx_events, extra_df], ignore_index=True)

    return fleet, tx_events
