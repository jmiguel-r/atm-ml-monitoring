"""
Batch runner script — runs a detection cycle and prints results.
Usage: python scripts/run_batch.py [--n-atms 1000] [--inject-anomalies]
"""

import argparse
from datetime import datetime

from src.simulator import simulate_batch
from src.features import extract_features
from src.models import run_all_detectors
from src.alerts import AlertEngine, format_alert_for_display


def main():
    parser = argparse.ArgumentParser(description="ATM ML Monitoring — Batch Runner")
    parser.add_argument("--n-atms", type=int, default=1000, help="Number of ATMs to simulate")
    parser.add_argument("--duration", type=int, default=15, help="Batch window in minutes")
    parser.add_argument("--inject-anomalies", action="store_true", help="Inject known anomalies")
    parser.add_argument("--verbose", action="store_true", help="Show all alerts")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"ATM ML Monitoring — Batch Run")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"ATMs: {args.n_atms:,} | Window: {args.duration} min | Anomalies injected: {args.inject_anomalies}")
    print(f"{'='*60}\n")

    # 1. Simulate
    print("📡 Simulating ATM events...")
    fleet, events = simulate_batch(
        n_atms=args.n_atms,
        duration_minutes=args.duration,
        inject_anomalies=args.inject_anomalies,
    )
    print(f"   Generated {len(events):,} events across {args.n_atms:,} ATMs\n")

    # 2. Feature extraction
    print("🔧 Extracting features...")
    features = extract_features(events, fleet, window_minutes=args.duration)
    print(f"   Computed {len(features.columns)} features for {len(features):,} ATMs\n")

    # 3. Run detectors
    print("🤖 Running ML detectors...")
    report = run_all_detectors(features)
    print(f"   Evaluated {report.n_atms_evaluated:,} ATMs")
    print(f"   Anomalies detected: {report.n_anomalies_detected} ({report.anomaly_rate:.1%})\n")

    # Detector breakdown
    detector_counts: dict[str, int] = {}
    for r in report.results:
        if r.is_anomaly:
            detector_counts[r.detector_name] = detector_counts.get(r.detector_name, 0) + 1

    print("   Breakdown by detector:")
    for det, count in sorted(detector_counts.items(), key=lambda x: -x[1]):
        print(f"     {det:25s} → {count:4d} anomalies")

    # 4. Alerts
    print("\n🚨 Processing alerts...")
    engine = AlertEngine()
    alerts = engine.process(report, fleet_df=fleet)
    summary = engine.summary()

    print(f"   Active alerts: {summary['total_active']}")
    print(f"   🔴 CRITICAL: {summary['critical']}")
    print(f"   🟠 HIGH:     {summary['high']}")
    print(f"   🟡 LOW:      {summary['low']}")

    if alerts:
        print(f"\n{'─'*60}")
        n_show = len(alerts) if args.verbose else min(10, len(alerts))
        print(f"Top {n_show} alerts:\n")
        for alert in alerts[:n_show]:
            print(format_alert_for_display(alert))
            print()

        if not args.verbose and len(alerts) > 10:
            print(f"  ... and {len(alerts) - 10} more. Use --verbose to see all.")

    print(f"\n{'='*60}")
    print("✅ Batch complete.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
