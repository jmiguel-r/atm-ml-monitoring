"""
Streamlit Dashboard for ATM ML Monitoring System.
5 tabs: Live Alerts, Regional View, Detector Analysis, ATM Map, Trend.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

from src.simulator import simulate_batch, REGIONS
from src.features import extract_features
from src.models import run_all_detectors
from src.alerts import AlertEngine, format_alert_for_display

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="ATM ML Monitoring",
    page_icon="🏧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("⚙️ Simulation Controls")
n_atms = st.sidebar.slider("Number of ATMs", min_value=100, max_value=10_000, value=1_000, step=100)
duration = st.sidebar.slider("Batch window (min)", min_value=5, max_value=60, value=15)
inject_anomalies = st.sidebar.checkbox("Inject known anomalies", value=True)

if st.sidebar.button("▶ Run Detection Batch", type="primary"):
    with st.spinner(f"Simulating {n_atms:,} ATMs..."):
        fleet, events = simulate_batch(
            n_atms=n_atms,
            duration_minutes=duration,
            inject_anomalies=inject_anomalies,
        )
        features = extract_features(events, fleet, window_minutes=duration)
        report = run_all_detectors(features)
        engine = AlertEngine()
        alerts = engine.process(report, fleet_df=fleet)

        st.session_state["fleet"] = fleet
        st.session_state["features"] = features
        st.session_state["report"] = report
        st.session_state["alerts"] = alerts
        st.session_state["engine"] = engine
        st.session_state["last_run"] = datetime.now().strftime("%H:%M:%S")

# ── Main area ─────────────────────────────────────────────────────────────────
st.title("🏧 ATM ML Monitoring Dashboard")

if "report" not in st.session_state:
    st.info("👈 Configure parameters and click **Run Detection Batch** to start.")
    st.stop()

report = st.session_state["report"]
features = st.session_state["features"]
fleet = st.session_state["fleet"]
alerts = st.session_state["alerts"]
engine = st.session_state["engine"]
summary = engine.summary()

# ── KPI strip ─────────────────────────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("ATMs Monitored", f"{report.n_atms_evaluated:,}")
col2.metric("Anomalies Detected", report.n_anomalies_detected)
col3.metric("🔴 CRITICAL", summary["critical"])
col4.metric("🟠 HIGH", summary["high"])
col5.metric("Anomaly Rate", f"{report.anomaly_rate:.1%}")

st.caption(f"Last batch: {st.session_state.get('last_run', '—')}")
st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🚨 Live Alerts", "🗺️ Regional View", "🤖 Detector Analysis", "📍 ATM Map", "📈 Trend"
])

# ── Tab 1: Live Alerts ────────────────────────────────────────────────────────
with tab1:
    st.subheader("Active Alerts")

    severity_filter = st.selectbox("Filter by severity", ["ALL", "CRITICAL", "HIGH", "LOW"])
    filtered = alerts if severity_filter == "ALL" else [a for a in alerts if a.severity == severity_filter]

    if not filtered:
        st.success("✅ No alerts match the current filter.")
    else:
        rows = [{
            "Severity": a.severity,
            "ATM ID": a.atm_id,
            "Region": a.region,
            "Detector": a.detector_name,
            "Reason": a.reason,
            "Score": f"{a.score:.3f}",
            "Occurrences": a.occurrence_count,
        } for a in filtered[:100]]

        df_alerts = pd.DataFrame(rows)

        def color_severity(val):
            colors = {"CRITICAL": "background-color: #ff4444; color: white",
                      "HIGH": "background-color: #ff8800; color: white",
                      "LOW": "background-color: #ffcc00"}
            return colors.get(val, "")

        st.dataframe(
            df_alerts.style.applymap(color_severity, subset=["Severity"]),
            use_container_width=True,
            height=400,
        )


# ── Tab 2: Regional View ──────────────────────────────────────────────────────
with tab2:
    st.subheader("Alert Distribution by Region")

    region_data = features.reset_index().merge(fleet[["atm_id", "region"]], on="atm_id", how="left")
    region_data["region"] = region_data.get("region_x", region_data.get("region", "UNKNOWN"))

    region_summary = region_data.groupby("region").agg(
        atm_count=("atm_id", "count"),
        avg_error_rate=("error_rate", "mean"),
        avg_risk=("overall_risk_score", "mean"),
        avg_hw_risk=("hardware_risk_score", "mean"),
    ).reset_index()

    fig = px.bar(
        region_summary,
        x="region",
        y="avg_risk",
        color="avg_risk",
        color_continuous_scale="RdYlGn_r",
        title="Average Risk Score by Region",
        labels={"avg_risk": "Avg Risk Score", "region": "Region"},
    )
    st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        fig2 = px.bar(region_summary, x="region", y="avg_error_rate",
                      title="Avg Transaction Error Rate by Region")
        st.plotly_chart(fig2, use_container_width=True)
    with col_b:
        fig3 = px.bar(region_summary, x="region", y="atm_count",
                      title="ATM Count by Region")
        st.plotly_chart(fig3, use_container_width=True)


# ── Tab 3: Detector Analysis ──────────────────────────────────────────────────
with tab3:
    st.subheader("Anomalies Detected per Model")

    detector_counts: dict[str, int] = {}
    for r in report.results:
        if r.is_anomaly:
            detector_counts[r.detector_name] = detector_counts.get(r.detector_name, 0) + 1

    df_det = pd.DataFrame(list(detector_counts.items()), columns=["Detector", "Anomalies"])
    df_det = df_det.sort_values("Anomalies", ascending=False)

    fig4 = px.bar(df_det, x="Detector", y="Anomalies", color="Anomalies",
                  color_continuous_scale="Reds", title="Anomalies per Detector")
    st.plotly_chart(fig4, use_container_width=True)

    st.subheader("Feature Distributions")
    feat_col = st.selectbox("Feature to plot", ["overall_risk_score", "error_rate",
                                                 "fraud_risk_score", "hardware_risk_score",
                                                 "tx_velocity", "offline_minutes"])
    if feat_col in features.columns:
        fig5 = px.histogram(features, x=feat_col, nbins=50, title=f"Distribution: {feat_col}")
        st.plotly_chart(fig5, use_container_width=True)


# ── Tab 4: ATM Map ────────────────────────────────────────────────────────────
with tab4:
    st.subheader("ATM Risk Map (Simulated Coordinates)")

    # Simulate geographic coordinates per region
    REGION_COORDS = {
        "CDMX": (19.43, -99.13), "GDL": (20.66, -103.35), "MTY": (25.67, -100.31),
        "QRO": (20.59, -100.39), "PUE": (19.04, -98.20), "MER": (20.97, -89.62),
        "TIJ": (32.52, -117.04), "CUN": (21.16, -86.85), "HMO": (29.10, -110.96),
        "VER": (19.18, -96.14),
    }

    map_data = features.reset_index()
    map_data["lat"] = map_data.get("region", "CDMX").map(lambda r: REGION_COORDS.get(r, (19.43, -99.13))[0] + np.random.uniform(-0.5, 0.5))
    map_data["lon"] = map_data.get("region", "CDMX").map(lambda r: REGION_COORDS.get(r, (19.43, -99.13))[1] + np.random.uniform(-0.5, 0.5))

    fig6 = px.scatter_mapbox(
        map_data,
        lat="lat", lon="lon",
        color="overall_risk_score",
        color_continuous_scale="RdYlGn_r",
        size="overall_risk_score",
        hover_name="atm_id",
        hover_data={"error_rate": True, "fraud_risk_score": True},
        mapbox_style="open-street-map",
        zoom=4, center={"lat": 23.0, "lon": -102.0},
        title="ATM Risk Distribution — Mexico",
        height=500,
    )
    st.plotly_chart(fig6, use_container_width=True)


# ── Tab 5: Trend ──────────────────────────────────────────────────────────────
with tab5:
    st.subheader("Risk Score Distribution")

    fig7 = px.box(features, y="overall_risk_score", title="Overall Risk Score Distribution")
    st.plotly_chart(fig7, use_container_width=True)

    st.subheader("Top 20 Highest-Risk ATMs")
    top20 = features.nlargest(20, "overall_risk_score")[
        ["overall_risk_score", "error_rate", "fraud_risk_score", "hardware_risk_score", "offline_minutes"]
    ].reset_index()
    st.dataframe(top20, use_container_width=True)
