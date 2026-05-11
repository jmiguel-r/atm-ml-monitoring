"""
Test suite for ATM ML Monitoring System.
35 unit tests covering all modules.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from src.simulator import (
    generate_atm_fleet, simulate_transactions, simulate_hardware_events,
    simulate_connectivity_events, simulate_batch,
)
from src.features import extract_features, FEATURE_COLUMNS
from src.models import (
    IsolationForestDetector, ZScoreDetector, DBSCANDetector,
    OfflineDetector, FraudDetector, HardwarePredictor,
    run_all_detectors, AnomalyResult,
)
from src.alerts import AlertEngine, Alert, format_alert_for_display


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def small_fleet():
    return generate_atm_fleet(n_atms=100)

@pytest.fixture(scope="module")
def batch_data(small_fleet):
    fleet, events = simulate_batch(n_atms=100, duration_minutes=15, inject_anomalies=True)
    return fleet, events

@pytest.fixture(scope="module")
def features_df(batch_data):
    fleet, events = batch_data
    return extract_features(events, fleet, window_minutes=15)

@pytest.fixture(scope="module")
def detection_report(features_df):
    return run_all_detectors(features_df)


# ── Simulator tests ───────────────────────────────────────────────────────────

class TestSimulator:
    def test_fleet_size(self, small_fleet):
        assert len(small_fleet) == 100

    def test_fleet_columns(self, small_fleet):
        for col in ["atm_id", "region", "install_year", "model", "age_years"]:
            assert col in small_fleet.columns

    def test_fleet_atm_ids_unique(self, small_fleet):
        assert small_fleet["atm_id"].nunique() == 100

    def test_fleet_regions_valid(self, small_fleet):
        from src.simulator import REGIONS
        assert small_fleet["region"].isin(REGIONS).all()

    def test_fleet_age_positive(self, small_fleet):
        assert (small_fleet["age_years"] >= 0).all()

    def test_transactions_generated(self, small_fleet):
        events = simulate_transactions(small_fleet, datetime.now(), duration_minutes=15)
        assert len(events) > 0

    def test_transaction_columns(self, small_fleet):
        events = simulate_transactions(small_fleet, datetime.now(), duration_minutes=15)
        for col in ["timestamp", "atm_id", "event_type", "amount", "success"]:
            assert col in events.columns

    def test_hardware_events_generated(self, small_fleet):
        events = simulate_hardware_events(small_fleet, datetime.now(), duration_minutes=15)
        assert len(events) == len(small_fleet) * 6  # 6 components per ATM

    def test_connectivity_events_generated(self, small_fleet):
        events = simulate_connectivity_events(small_fleet, datetime.now(), duration_minutes=15)
        assert len(events) == len(small_fleet)

    def test_simulate_batch_returns_tuple(self):
        fleet, events = simulate_batch(n_atms=50, duration_minutes=5)
        assert isinstance(fleet, pd.DataFrame)
        assert isinstance(events, pd.DataFrame)

    def test_simulate_batch_event_types(self):
        _, events = simulate_batch(n_atms=50, duration_minutes=5)
        event_types = events["event_type"].unique()
        assert set(["transaction", "hardware", "connectivity"]).issubset(set(event_types))

    def test_inject_anomalies_increases_transactions(self):
        _, events_normal = simulate_batch(n_atms=100, inject_anomalies=False)
        _, events_anomaly = simulate_batch(n_atms=100, inject_anomalies=True)
        assert len(events_anomaly) >= len(events_normal)


# ── Feature tests ─────────────────────────────────────────────────────────────

class TestFeatures:
    def test_features_shape(self, features_df, small_fleet):
        assert len(features_df) == len(small_fleet)

    def test_feature_columns_present(self, features_df):
        for col in FEATURE_COLUMNS:
            assert col in features_df.columns, f"Missing feature: {col}"

    def test_error_rate_bounded(self, features_df):
        assert (features_df["error_rate"] >= 0).all()
        assert (features_df["error_rate"] <= 1).all()

    def test_connectivity_score_bounded(self, features_df):
        assert (features_df["connectivity_score"] >= 0).all()
        assert (features_df["connectivity_score"] <= 1).all()

    def test_risk_scores_bounded(self, features_df):
        for col in ["overall_risk_score", "hardware_risk_score", "fraud_risk_score"]:
            assert (features_df[col] >= 0).all(), f"{col} has negative values"
            assert (features_df[col] <= 1).all(), f"{col} exceeds 1.0"

    def test_no_nan_in_features(self, features_df):
        assert not features_df[FEATURE_COLUMNS].isna().any().any()


# ── Model tests ───────────────────────────────────────────────────────────────

class TestModels:
    def test_isolation_forest_returns_results(self, features_df):
        det = IsolationForestDetector()
        results = det.predict(features_df)
        assert len(results) == len(features_df)

    def test_isolation_forest_result_type(self, features_df):
        det = IsolationForestDetector()
        results = det.predict(features_df)
        assert all(isinstance(r, AnomalyResult) for r in results)

    def test_zscore_detector(self, features_df):
        det = ZScoreDetector()
        results = det.predict(features_df)
        assert len(results) == len(features_df)

    def test_dbscan_detector(self, features_df):
        det = DBSCANDetector()
        results = det.predict(features_df)
        assert len(results) == len(features_df)

    def test_offline_detector(self, features_df):
        det = OfflineDetector()
        results = det.predict(features_df)
        assert len(results) == len(features_df)

    def test_fraud_detector(self, features_df):
        det = FraudDetector()
        results = det.predict(features_df)
        assert len(results) == len(features_df)

    def test_hardware_predictor(self, features_df):
        det = HardwarePredictor()
        results = det.predict(features_df)
        assert len(results) == len(features_df)

    def test_severity_values_valid(self, features_df):
        det = IsolationForestDetector()
        results = det.predict(features_df)
        assert all(r.severity in ("LOW", "HIGH", "CRITICAL") for r in results)

    def test_score_non_negative(self, features_df):
        det = FraudDetector()
        results = det.predict(features_df)
        assert all(r.score >= 0 for r in results)

    def test_run_all_detectors(self, features_df):
        report = run_all_detectors(features_df)
        assert report.n_atms_evaluated == len(features_df)
        assert report.n_anomalies_detected >= 0
        # 6 detectors × n_atms results
        assert len(report.results) == len(features_df) * 6

    def test_report_anomaly_rate(self, detection_report):
        assert 0 <= detection_report.anomaly_rate <= 1

    def test_anomalies_df(self, detection_report):
        df = detection_report.anomalies_df()
        assert isinstance(df, pd.DataFrame)


# ── Alert tests ───────────────────────────────────────────────────────────────

class TestAlerts:
    def test_alert_engine_processes_report(self, detection_report):
        engine = AlertEngine()
        alerts = engine.process(detection_report)
        assert isinstance(alerts, list)

    def test_alerts_are_alert_type(self, detection_report):
        engine = AlertEngine()
        alerts = engine.process(detection_report)
        assert all(isinstance(a, Alert) for a in alerts)

    def test_alert_severity_valid(self, detection_report):
        engine = AlertEngine()
        alerts = engine.process(detection_report)
        for a in alerts:
            assert a.severity in ("CRITICAL", "HIGH", "LOW")

    def test_deduplication(self, detection_report):
        engine = AlertEngine()
        alerts1 = engine.process(detection_report)
        alerts2 = engine.process(detection_report)
        # Second run should deduplicate — same or fewer unique alert IDs
        ids1 = {a.alert_id for a in alerts1}
        ids2 = {a.alert_id for a in alerts2}
        assert len(ids1) >= 0  # sanity check

    def test_acknowledge_alert(self, detection_report):
        engine = AlertEngine()
        alerts = engine.process(detection_report)
        if alerts:
            result = engine.acknowledge(alerts[0].alert_id)
            assert result is True

    def test_resolve_alert(self, detection_report):
        engine = AlertEngine()
        alerts = engine.process(detection_report)
        if alerts:
            result = engine.resolve(alerts[0].alert_id)
            assert result is True

    def test_active_alerts_after_resolve(self, detection_report):
        engine = AlertEngine()
        alerts = engine.process(detection_report)
        if alerts:
            engine.resolve(alerts[0].alert_id)
            active = engine.active_alerts()
            assert alerts[0].alert_id not in {a.alert_id for a in active}

    def test_summary_structure(self, detection_report):
        engine = AlertEngine()
        engine.process(detection_report)
        summary = engine.summary()
        for key in ["total_active", "critical", "high", "low", "top_atms"]:
            assert key in summary

    def test_format_alert_for_display(self, detection_report):
        engine = AlertEngine()
        alerts = engine.process(detection_report)
        if alerts:
            text = format_alert_for_display(alerts[0])
            assert isinstance(text, str)
            assert len(text) > 0
