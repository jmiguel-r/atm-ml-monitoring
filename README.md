# 🏧 ATM ML Monitoring System

> **Production-ready ML anomaly detection platform for 10,000+ ATMs**  
> Real-time detection · 6 ensemble ML detectors · REST API · Interactive dashboard · Kubernetes-ready

[![CI/CD](https://github.com/jmiguel-r/atm-ml-monitoring/actions/workflows/ci.yml/badge.svg)](https://github.com/jmiguel-r/atm-ml-monitoring/actions)
[![Tests](https://img.shields.io/badge/Tests-39%2F39%20passing-brightgreen)](./tests/)
[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green.svg)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-interactive-FF4B4B.svg)](https://streamlit.io)
[![Docker](https://img.shields.io/badge/Docker-multi%2Dcontainer-2496ED.svg)](https://docker.com)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-HPA%2Dready-326CE5.svg)](https://kubernetes.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                             │
│         10,000+ ATMs  ·  Transactions  ·  Hardware  ·  Network  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                      DATA PIPELINE                              │
│    Event Simulator  ·  Feature Engineering  ·  Parquet Storage  │
│         24 features per ATM  ·  Batch every 5-15 min           │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                       ML DETECTORS                              │
│  ┌──────────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  Isolation Forest │  │  Z-Score     │  │  DBSCAN Cluster   │  │
│  └──────────────────┘  └──────────────┘  └───────────────────┘  │
│  ┌──────────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  Offline Detect  │  │  Fraud Detect│  │  Hardware Predict │  │
│  └──────────────────┘  └──────────────┘  └───────────────────┘  │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                        OUTPUTS                                  │
│   FastAPI (8 endpoints)  ·  Streamlit Dashboard  ·  Alert Engine │
│       CRITICAL / HIGH / LOW  ·  Dedup  ·  Trend Tracking        │
└──────────────────────────────┬──────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────┐
│                    INFRASTRUCTURE                               │
│          Docker  ·  Kubernetes (HPA 2-10 pods)  ·  GitHub CI/CD │
└─────────────────────────────────────────────────────────────────┘
```

---

## ✨ Features

| Feature | Details |
|---|---|
| **Scale** | Simulates 10,000+ ATMs generating real-time events |
| **Anomaly types** | Failed transactions, hardware faults, disconnections, fraud patterns, unusual amounts, long idle time |
| **6 ML detectors** | Isolation Forest, Z-Score, DBSCAN, Offline Detector, Fraud Detector, Hardware Predictor |
| **24 features per ATM** | Rolling stats, z-scores, velocity, hardware health, connectivity score |
| **Alert engine** | Deduplication, severity levels (CRITICAL/HIGH/LOW), trend history |
| **REST API** | 8 FastAPI endpoints — batch trigger, alert management, ATM history |
| **Dashboard** | Streamlit with 5 tabs: live alerts, regional view, detector analysis, map, trend |
| **Infrastructure** | Docker, Kubernetes HPA (auto-scale 2-10 pods), GitHub Actions CI/CD |

---

## 🚀 Quick Start

### Option 1: Docker Compose (Recommended — 3 commands)

```bash
git clone https://github.com/jmiguel-r/atm-ml-monitoring.git
cd atm-ml-monitoring
docker compose up --build
```

Then open:
- **API docs:** http://localhost:8000/docs
- **Dashboard:** http://localhost:8501

### Option 2: Local Python

```bash
git clone https://github.com/jmiguel-r/atm-ml-monitoring.git
cd atm-ml-monitoring
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python scripts/run_batch.py --n-atms 1000 --inject-anomalies
```

### Option 3: Step-by-Step (3 terminals)

**Terminal 1 — API:**
```bash
uvicorn app.api:app --reload
```

**Terminal 2 — Dashboard:**
```bash
streamlit run app/dashboard.py
```

**Terminal 3 — Batch runner:**
```bash
python scripts/run_batch.py --n-atms 2000 --inject-anomalies --verbose
```

---

## 📊 Usage

### REST API (FastAPI)
Access interactive docs at http://localhost:8000/docs

```bash
# Trigger a detection batch
curl -X POST http://localhost:8000/batch/run \
  -H "Content-Type: application/json" \
  -d '{"n_atms": 1000, "inject_anomalies": true}'

# Get active alerts
curl http://localhost:8000/alerts?severity=CRITICAL

# Get ATM history
curl http://localhost:8000/atm/ATM_000001/history
```

### Streamlit Dashboard
Visit http://localhost:8501

- **🚨 Live Alerts** — Filterable table of active alerts
- **🗺️ Regional View** — Risk distribution by region (Mexico)
- **🤖 Detector Analysis** — Anomalies per detector + feature distributions
- **📍 ATM Map** — Interactive map with risk heatmap
- **📈 Trend** — Box plots and top 20 highest-risk ATMs

---

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | System health check |
| `POST` | `/batch/run` | Trigger a detection batch |
| `GET` | `/alerts` | List active alerts (filterable) |
| `GET` | `/alerts/summary` | Alert counts by severity |
| `POST` | `/alerts/acknowledge` | Acknowledge an alert |
| `POST` | `/alerts/resolve/{id}` | Resolve an alert |
| `GET` | `/atm/{id}/history` | Alert history for one ATM |
| `GET` | `/report/latest` | Last batch summary + detector breakdown |

---

## 🤖 ML Detectors

### 1. Isolation Forest
General-purpose anomaly detection. Trained on 8 features including error rate, transaction velocity, hardware health, and overall risk score. Flags ATMs in the top 5% anomaly percentile.

### 2. Z-Score Detector
Statistical outlier detection. Flags any ATM where a key metric exceeds 2.5σ from the fleet mean. Fast and interpretable — clearly explains which feature triggered the alert.

### 3. DBSCAN Clustering
Behavioral clustering. ATMs that don't fit any cluster (-1 label) are flagged as outliers. Captures unusual combinations of metrics that other detectors might miss.

### 4. Offline Detector
Connectivity monitoring. Flags ATMs offline >5 minutes or with connectivity score <0.7. CRITICAL severity for >30 minutes offline.

### 5. Fraud Detector
Skimming and rapid-succession fraud patterns. Combines transaction velocity, inter-transaction timing, amount z-scores, and volume. Flags score ≥0.6.

### 6. Hardware Predictor
Predictive maintenance. Uses hardware error counts and critical event flags to predict imminent failures before they cause outages.

---

## 📊 Feature Engineering (24 features)

```
Transaction:   tx_count, tx_count_per_min, error_rate, consecutive_errors
               amount_mean, amount_std, amount_max, amount_zscore
               tx_velocity, inter_tx_seconds_mean

Hardware:      hw_error_count, hw_critical_count, hw_error_rate

Connectivity:  offline_minutes, is_offline, connectivity_score

Time:          hour_of_day, is_business_hours, is_weekend

Z-scores:      tx_count_zscore, error_rate_zscore

Composite:     hardware_risk_score, fraud_risk_score, overall_risk_score
```

---

## 🧪 Tests

```bash
pytest tests/ -v --cov=src
```

35 unit tests covering all modules — simulator, features, all 6 detectors, alert engine.

---

## 🚢 Deployment

### Cloud Deployment (AWS / GCP / Azure)

#### AWS ECS (Elastic Container Service)

1. **Build and push image:**
```bash
aws ecr create-repository --repository-name atm-ml-monitoring
aws ecr get-login-password | docker login --username AWS --password-stdin YOUR_ACCOUNT.dkr.ecr.REGION.amazonaws.com
docker build -t atm-ml-monitoring .
docker tag atm-ml-monitoring:latest YOUR_ACCOUNT.dkr.ecr.REGION.amazonaws.com/atm-ml-monitoring:latest
docker push YOUR_ACCOUNT.dkr.ecr.REGION.amazonaws.com/atm-ml-monitoring:latest
```

2. **Deploy with Terraform:**
See `infra/terraform/` for IaC templates (ECS task definitions, ALB, RDS for PostgreSQL).

3. **Access:**
- API: `https://api-atm-monitoring.youromain.com`
- Dashboard: `https://dashboard-atm-monitoring.yourdomain.com`

#### Google Cloud Run

```bash
# Build and push
gcloud builds submit --tag gcr.io/YOUR_PROJECT/atm-ml-monitoring

# Deploy API
gcloud run deploy atm-api \
  --image gcr.io/YOUR_PROJECT/atm-ml-monitoring \
  --port 8000 \
  --memory 1Gi \
  --cpu 1

# Deploy Dashboard
gcloud run deploy atm-dashboard \
  --image gcr.io/YOUR_PROJECT/atm-ml-monitoring \
  --port 8501 \
  --memory 2Gi \
  --cpu 2 \
  --command streamlit \
  --args "run,app/dashboard.py"
```

#### Kubernetes (Self-hosted or managed)

```bash
# Using provided k8s config
kubectl apply -f k8s/deployment.yaml

# Check status
kubectl get pods -l app=atm-monitoring
kubectl logs -f deployment/atm-monitoring-api
```

### Production Checklist

- [ ] Database: PostgreSQL for alert history (not in-memory)
- [ ] Cache: Redis for alert deduplication across pods
- [ ] Secrets: Use Cloud Secrets Manager (AWS Secrets, GCP Secret Manager)
- [ ] Monitoring: Prometheus + Grafana (Prometheus config in `monitoring/`)
- [ ] Logging: CloudWatch (AWS) or Cloud Logging (GCP)
- [ ] CI/CD: GitHub Actions automatically tests and deploys on push
- [ ] Load balancing: ALB (AWS) or Cloud Load Balancer (GCP)
- [ ] Auto-scaling: HPA configured for 2-10 pods based on CPU/memory

---

## 🏗️ Project Structure

```
atm-ml-monitoring/
├── src/
│   ├── simulator.py      # ATM event generator (10k+ devices)
│   ├── features.py       # 24-feature engineering pipeline
│   ├── models.py         # 6 ML anomaly detectors
│   └── alerts.py         # Alert engine: dedup, severity, history
├── app/
│   ├── api.py            # FastAPI — 8 REST endpoints
│   └── dashboard.py      # Streamlit — 5-tab monitoring dashboard
├── scripts/
│   └── run_batch.py      # CLI batch runner
├── tests/
│   └── test_atm_monitoring.py  # 35 unit tests
├── k8s/
│   └── deployment.yaml   # Kubernetes + HPA config
├── .github/workflows/
│   └── ci.yml            # GitHub Actions CI/CD
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## 🛠️ Tech Stack

- **ML**: scikit-learn (Isolation Forest, DBSCAN), NumPy, Pandas
- **API**: FastAPI, Uvicorn, Pydantic
- **Dashboard**: Streamlit, Plotly
- **Infrastructure**: Docker, Kubernetes, GitHub Actions
- **Testing**: pytest, pytest-cov

---

## 📄 License

MIT — free to use for portfolio and commercial projects.
