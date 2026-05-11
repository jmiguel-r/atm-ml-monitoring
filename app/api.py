"""
FastAPI REST API for ATM ML Monitoring System.
8 endpoints covering status, detection, alerts, and reporting.
"""

from datetime import datetime
from typing import Optional
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from src.simulator import simulate_batch
from src.features import extract_features
from src.models import run_all_detectors
from src.alerts import AlertEngine, format_alert_for_display

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="ATM ML Monitoring API",
    description="Real-time anomaly detection for 10,000+ ATM fleet",
    version="1.0.0",
)

# Global state (in production: Redis / DB-backed)
_alert_engine = AlertEngine(dedup_window_minutes=15)
_last_report = None
_last_fleet = None

# ── Schemas ───────────────────────────────────────────────────────────────────

class BatchRequest(BaseModel):
    n_atms: int = 1000
    duration_minutes: int = 15
    inject_anomalies: bool = False

class AlertAckRequest(BaseModel):
    alert_id: str

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    """Health check."""
    return {
        "service": "ATM ML Monitoring",
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }


@app.get("/health", tags=["Health"])
def health():
    """Detailed health check with system state."""
    return {
        "status": "healthy",
        "last_batch_run": _last_report.batch_timestamp if _last_report else None,
        "active_alerts": len(_alert_engine.active_alerts()),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/batch/run", tags=["Detection"])
def run_batch(request: BatchRequest):
    """
    Run a detection batch over simulated ATM events.
    In production this would consume from a message queue or database.
    """
    global _last_report, _last_fleet

    fleet, events = simulate_batch(
        n_atms=request.n_atms,
        duration_minutes=request.duration_minutes,
        inject_anomalies=request.inject_anomalies,
    )
    _last_fleet = fleet

    features = extract_features(events, fleet, window_minutes=request.duration_minutes)
    report = run_all_detectors(features)
    _last_report = report

    alerts = _alert_engine.process(report, fleet_df=fleet)

    return {
        "batch_timestamp": report.batch_timestamp,
        "n_atms_evaluated": report.n_atms_evaluated,
        "n_anomalies_detected": report.n_anomalies_detected,
        "anomaly_rate": round(report.anomaly_rate, 4),
        "new_alerts": len(alerts),
        "alerts_summary": _alert_engine.summary(),
    }


@app.get("/alerts", tags=["Alerts"])
def get_alerts(
    severity: Optional[str] = Query(default=None, description="Filter by severity: CRITICAL, HIGH, LOW"),
    limit: int = Query(default=50, ge=1, le=500),
):
    """Return current active alerts, optionally filtered by severity."""
    alerts = _alert_engine.active_alerts(severity_filter=severity)[:limit]
    return {
        "count": len(alerts),
        "alerts": [
            {
                "alert_id": a.alert_id,
                "atm_id": a.atm_id,
                "region": a.region,
                "severity": a.severity,
                "detector": a.detector_name,
                "reason": a.reason,
                "score": a.score,
                "occurrences": a.occurrence_count,
                "created_at": a.created_at,
                "acknowledged": a.acknowledged,
            }
            for a in alerts
        ],
    }


@app.get("/alerts/summary", tags=["Alerts"])
def get_alerts_summary():
    """Return a high-level summary of current alert state."""
    return _alert_engine.summary()


@app.post("/alerts/acknowledge", tags=["Alerts"])
def acknowledge_alert(request: AlertAckRequest):
    """Acknowledge an alert by ID."""
    success = _alert_engine.acknowledge(request.alert_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Alert {request.alert_id} not found")
    return {"status": "acknowledged", "alert_id": request.alert_id}


@app.post("/alerts/resolve/{alert_id}", tags=["Alerts"])
def resolve_alert(alert_id: str):
    """Resolve an alert by ID."""
    success = _alert_engine.resolve(alert_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return {"status": "resolved", "alert_id": alert_id}


@app.get("/atm/{atm_id}/history", tags=["ATM"])
def get_atm_history(atm_id: str):
    """Return alert history for a specific ATM."""
    history = _alert_engine.atm_alert_history(atm_id)
    if not history:
        return {"atm_id": atm_id, "alert_count": 0, "alerts": []}
    return {
        "atm_id": atm_id,
        "alert_count": len(history),
        "alerts": [
            {
                "alert_id": a.alert_id,
                "severity": a.severity,
                "detector": a.detector_name,
                "reason": a.reason,
                "score": a.score,
                "created_at": a.created_at,
            }
            for a in history[-20:]  # last 20
        ],
    }


@app.get("/report/latest", tags=["Reporting"])
def get_latest_report():
    """Return summary of the most recent detection batch."""
    if _last_report is None:
        raise HTTPException(status_code=404, detail="No batch has been run yet. POST /batch/run first.")
    return {
        "batch_timestamp": _last_report.batch_timestamp,
        "n_atms_evaluated": _last_report.n_atms_evaluated,
        "n_anomalies_detected": _last_report.n_anomalies_detected,
        "anomaly_rate": round(_last_report.anomaly_rate, 4),
        "detector_breakdown": _detector_breakdown(_last_report),
    }


def _detector_breakdown(report) -> list[dict]:
    """Count anomalies per detector."""
    counts: dict[str, int] = {}
    for r in report.results:
        if r.is_anomaly:
            counts[r.detector_name] = counts.get(r.detector_name, 0) + 1
    return [{"detector": k, "anomalies": v} for k, v in sorted(counts.items())]
