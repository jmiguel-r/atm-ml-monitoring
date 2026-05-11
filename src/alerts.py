"""
Alert Engine for ATM Monitoring System.
Handles deduplication, severity classification, and alert history.
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict

from src.models import AnomalyResult, DetectionReport


SEVERITY_PRIORITY = {"CRITICAL": 3, "HIGH": 2, "LOW": 1}


@dataclass
class Alert:
    """A deduplicated, enriched alert ready for notification."""
    alert_id: str
    atm_id: str
    region: str
    severity: str
    detector_name: str
    reason: str
    score: float
    created_at: str
    updated_at: str
    occurrence_count: int = 1
    acknowledged: bool = False
    resolved: bool = False


class AlertEngine:
    """
    Processes DetectionReports into deduplicated Alerts.

    Features:
    - Deduplication: same (atm_id, detector, severity) within a cooldown window
      is treated as the same alert (occurrence_count increases).
    - Trend tracking: tracks alert history per ATM for escalation.
    - Priority queue: CRITICAL alerts surfaced first.
    """

    def __init__(
        self,
        dedup_window_minutes: int = 15,
        max_history: int = 1000,
    ):
        self.dedup_window = timedelta(minutes=dedup_window_minutes)
        self.max_history = max_history
        self._active_alerts: dict[str, Alert] = {}      # alert_id → Alert
        self._atm_history: dict[str, list[Alert]] = defaultdict(list)  # atm_id → [Alert]

    def process(
        self,
        report: DetectionReport,
        fleet_df=None,  # optional: pd.DataFrame with atm metadata
    ) -> list[Alert]:
        """
        Process a DetectionReport and return new/updated alerts.
        Only anomalies with severity HIGH or CRITICAL are surfaced.
        """
        now = datetime.utcnow()
        new_alerts: list[Alert] = []

        # Filter to real anomalies only
        anomalies = [r for r in report.results if r.is_anomaly and r.severity in ("HIGH", "CRITICAL")]

        for result in anomalies:
            region = self._get_region(result.atm_id, fleet_df)
            alert_key = self._make_key(result)

            existing = self._active_alerts.get(alert_key)

            if existing and not existing.resolved:
                # Deduplicate — update occurrence and timestamp
                existing.occurrence_count += 1
                existing.updated_at = now.isoformat()
                new_alerts.append(existing)
            else:
                # New alert
                alert = Alert(
                    alert_id=alert_key,
                    atm_id=result.atm_id,
                    region=region,
                    severity=result.severity,
                    detector_name=result.detector_name,
                    reason=result.reason,
                    score=result.score,
                    created_at=now.isoformat(),
                    updated_at=now.isoformat(),
                    occurrence_count=1,
                )
                self._active_alerts[alert_key] = alert
                self._atm_history[result.atm_id].append(alert)
                new_alerts.append(alert)

        # Sort by severity priority (CRITICAL first), then score
        new_alerts.sort(
            key=lambda a: (SEVERITY_PRIORITY.get(a.severity, 0), a.score),
            reverse=True,
        )

        # Trim history
        for atm_id in self._atm_history:
            if len(self._atm_history[atm_id]) > self.max_history:
                self._atm_history[atm_id] = self._atm_history[atm_id][-self.max_history:]

        return new_alerts

    def acknowledge(self, alert_id: str) -> bool:
        """Mark an alert as acknowledged."""
        if alert_id in self._active_alerts:
            self._active_alerts[alert_id].acknowledged = True
            return True
        return False

    def resolve(self, alert_id: str) -> bool:
        """Mark an alert as resolved (clears dedup window)."""
        if alert_id in self._active_alerts:
            self._active_alerts[alert_id].resolved = True
            return True
        return False

    def active_alerts(self, severity_filter: Optional[str] = None) -> list[Alert]:
        """Return all active (non-resolved) alerts, optionally filtered by severity."""
        alerts = [a for a in self._active_alerts.values() if not a.resolved]
        if severity_filter:
            alerts = [a for a in alerts if a.severity == severity_filter]
        return sorted(alerts, key=lambda a: SEVERITY_PRIORITY.get(a.severity, 0), reverse=True)

    def atm_alert_history(self, atm_id: str) -> list[Alert]:
        """Return alert history for a specific ATM."""
        return self._atm_history.get(atm_id, [])

    def summary(self) -> dict:
        """Return a summary of current alert state."""
        active = self.active_alerts()
        return {
            "total_active": len(active),
            "critical": len([a for a in active if a.severity == "CRITICAL"]),
            "high": len([a for a in active if a.severity == "HIGH"]),
            "low": len([a for a in active if a.severity == "LOW"]),
            "top_atms": self._top_atms(active, n=5),
        }

    def _top_atms(self, alerts: list[Alert], n: int = 5) -> list[dict]:
        """Return the ATMs with the most alerts."""
        counts: dict[str, int] = defaultdict(int)
        for a in alerts:
            counts[a.atm_id] += 1
        top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:n]
        return [{"atm_id": atm_id, "alert_count": count} for atm_id, count in top]

    @staticmethod
    def _make_key(result: AnomalyResult) -> str:
        """Create a stable dedup key from anomaly result."""
        raw = f"{result.atm_id}|{result.detector_name}|{result.severity}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    @staticmethod
    def _get_region(atm_id: str, fleet_df) -> str:
        if fleet_df is not None and "atm_id" in fleet_df.columns:
            row = fleet_df[fleet_df["atm_id"] == atm_id]
            if len(row) > 0:
                return row.iloc[0].get("region", "UNKNOWN")
        return "UNKNOWN"


def format_alert_for_display(alert: Alert) -> str:
    """Format an alert as a human-readable string."""
    icon = {"CRITICAL": "🔴", "HIGH": "🟠", "LOW": "🟡"}.get(alert.severity, "⚪")
    return (
        f"{icon} [{alert.severity}] {alert.atm_id} | {alert.detector_name}\n"
        f"   {alert.reason}\n"
        f"   Score: {alert.score:.3f} | Region: {alert.region} | "
        f"Occurrences: {alert.occurrence_count}"
    )
