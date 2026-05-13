# 💰 ATM ML Monitoring — Detailed Cost Analysis

## Executive Summary

| Platform | Monthly Cost (est.) | Best For |
|---|---|---|
| **AWS ECS** | $190-360 | Established companies, complex workflows |
| **Google Cloud Run** | $180-295 | Startups, variable load, simplicity |
| **Kubernetes (self-hosted)** | $500+ | High scale, multiple services |

---

## AWS ECS + CloudFormation Detailed Breakdown

### Infrastructure Components

#### 1. ECS Fargate Compute

**Configuration:**
- 2-10 tasks (auto-scaling based on CPU)
- 1-2 vCPU per task
- 2-4 GB memory per task
- On-demand pricing (no reserved instances)

**Calculation:**

```
Baseline: 2 tasks running 24/7
  = 2 tasks × 1 vCPU × $0.04560/vCPU-hour
  = $0.0912/hour
  = $0.0912 × 730 hours/month
  = $66.58/month (vCPU)

Memory: 2 tasks × 3 GB × $0.00504/GB-hour
  = $0.03024/hour
  = $0.03024 × 730
  = $22.08/month (memory)

Baseline monthly: $88.66

Peak hours (10 tasks, 10% of month = 73 hours):
  = 8 additional tasks × 1 vCPU × $0.04560 × 73
  = $26.63/month

Total ECS Compute: $88.66 + $26.63 = $115.29/month
```

**Savings opportunity:** Use 1-year reserved instances → 30% discount = ~$81/month

#### 2. Application Load Balancer (ALB)

**Pricing:**
```
Hourly charge: $0.0225/hour × 730 hours = $16.43/month
LCU (Load Balancer Capacity Units):
  - Processed bytes: ~100 GB/month × $0.006/GB = $0.60
  - New connections: ~100k/month × $0.000006 = $0.60
  - Active connections: ~100 × $0.0000022 = $0.22

ALB total: $16.43 + $1.42 = $17.85/month
```

#### 3. RDS PostgreSQL (Database)

**Baseline (db.t3.micro — free tier first 12 months):**
```
db.t3.micro: $0.017/hour × 730 hours = $12.41/month
Storage: 100 GB × $0.115/GB-month = $11.50/month
Backups: 35-day retention = ~$3.45/month

Total RDS (paid): $27.36/month
(Free tier year 1 = ~$0/month)
```

#### 4. ElastiCache Redis (Caching)

**Baseline (cache.t3.micro — 0.5 GB):**
```
Node cost: $0.017/hour × 730 hours = $12.41/month
Data transfer (out): 10 GB × $0.02/GB = $0.20/month

Total ElastiCache: $12.61/month
```

#### 5. CloudWatch & Monitoring

**Logs:**
```
Log ingestion: 1 GB/month × $0.50 = $0.50
Log storage: 1 GB × $0.03/GB-month = $0.03

Metrics:
  - Custom metrics: 10 × $0.30 = $3.00
  - Alarms: 5 × $0.10 = $0.50

Total CloudWatch: $4.03/month
```

#### 6. Data Transfer

**Internet egress:**
```
Outbound data: 50 GB/month × $0.09/GB = $4.50
Internal (free): Within region = $0.00

Total Data Transfer: $4.50/month
```

#### 7. ECR (Container Registry)

**Storage:**
```
Storage: 5 GB × $0.10/GB-month = $0.50/month
Requests: Negligible

Total ECR: $0.50/month
```

### AWS Total Cost Breakdown

```
┌─────────────────────────────────────────┐
│        AWS Monthly Cost Summary          │
├─────────────────────────────────────────┤
│ ECS Fargate Compute      $115.29        │
│ Load Balancer             $17.85        │
│ RDS PostgreSQL            $27.36        │  ← Year 2+
│ ElastiCache Redis         $12.61        │
│ CloudWatch & Logs          $4.03        │
│ Data Transfer              $4.50        │
│ ECR Registry               $0.50        │
├─────────────────────────────────────────┤
│ YEAR 1 (with free tier)   $162.14       │
│ YEAR 2+ (full pricing)    $182.14       │
├─────────────────────────────────────────┤
│ With Reserved Instances:   $150-160     │
│ (30% discount on compute)               │
└─────────────────────────────────────────┘
```

---

## Google Cloud Platform Detailed Breakdown

### Infrastructure Components

#### 1. Cloud Run (Container Runtime)

**API Service:**
```
Configuration: 2 vCPU, 2 GB memory
Pricing: Pay per request + computation time

Requests: 1M requests/month
  = 1M requests × $0.40/million = $0.40

Computation: 1M requests × avg 2 seconds × 2 vCPU
  = 2M vCPU-seconds / 3600 = 555.56 vCPU-hours
  = 555.56 × $0.000024 = $0.013
  
Memory: 555.56 hours × 2 GB × $0.00001667/GB-hour = $0.0185

API Service Total: $0.43/month
```

**Dashboard Service:**
```
Similar to API (fewer requests, more idle time)
Estimated: $0.30/month
```

**Total Cloud Run: $0.73/month**

#### 2. Cloud SQL (PostgreSQL)

**Pricing:**
```
db-custom-2-8192 (2 vCPU, 8 GB):
  - Instance: $0.1265/hour × 730 = $92.35/month
  - Storage: 100 GB × $0.17/GB = $17.00/month
  - Backups: Included in pricing

Total Cloud SQL: $109.35/month
```

#### 3. Memorystore (Redis)

**Pricing:**
```
Standard tier, 1 GB capacity:
  - Instance: $0.156/GB-day × 30 days × 1 GB = $4.68/month
  - Data transfer (out of VPC): $0.00 (internal)

Total Memorystore: $4.68/month
```

#### 4. Cloud Load Balancer

**Pricing:**
```
Network Load Balancer:
  - Per forwarding rule: $0.025/hour × 730 = $18.25
  - Per GB: 50 GB × $0.006 = $0.30

Total Load Balancer: $18.55/month
```

#### 5. Cloud Logging

**Pricing:**
```
Log ingestion: 1 GB/month (included in free tier)
Log storage: Free (first 30 days)

Total Logging: $0/month
```

#### 6. Cloud Monitoring

**Pricing:**
```
Metrics: 150 custom metrics × $0.2574 = $38.61/month
API calls: Included

Total Monitoring: $38.61/month
```

#### 7. Artifact Registry

**Pricing:**
```
Storage: 10 GB × $0.10/GB-month = $1.00
Data egress: Included in Cloud Run

Total Artifact Registry: $1.00/month
```

#### 8. Data Transfer

**Egress:**
```
Outbound: 50 GB/month × $0.12/GB = $6.00
Internal: Free

Total Data Transfer: $6.00/month
```

### GCP Total Cost Breakdown

```
┌─────────────────────────────────────────┐
│        GCP Monthly Cost Summary          │
├─────────────────────────────────────────┤
│ Cloud Run Services         $0.73        │
│ Cloud SQL PostgreSQL      $109.35       │
│ Memorystore Redis          $4.68        │
│ Cloud Load Balancer       $18.55        │
│ Cloud Logging              $0.00        │
│ Cloud Monitoring          $38.61        │
│ Artifact Registry          $1.00        │
│ Data Transfer              $6.00        │
├─────────────────────────────────────────┤
│ TOTAL MONTHLY             $178.92       │
│ TOTAL YEARLY            $2,147.04       │
└─────────────────────────────────────────┘
```

**Note:** GCP often has promotional credits ($300 free tier for new accounts).

---

## Kubernetes (Self-Hosted) Cost Analysis

### Infrastructure Requirements

**Cluster Setup (AWS EC2 example):**

```
Master Nodes:
  - 3 × t3.medium: $0.0416/hour × 730 = $91.09/month × 3 = $273.27

Worker Nodes (for ATM monitoring):
  - 3 × t3.large: $0.0832/hour × 730 = $60.74/month × 3 = $182.22

Load Balancer (Network LB):
  = $18.25/month

Storage (EBS):
  - 100 GB × $0.10/GB-month = $10.00

Data Transfer:
  = $6.00/month

Total K8s Infrastructure: $490.74/month
```

### Added Operational Costs

```
Logging/Monitoring:
  - Prometheus + Grafana: $0 (open source)
  - Cloud-native logging: $10-50/month

Backups:
  - Managed backups: $20-50/month

Support:
  - Kubernetes expertise/on-call: $500-2000/month

Total with operations: $1,000-2,500/month
```

---

## Cost Comparison Matrix

```
Scale               AWS ECS         GCP Cloud Run    K8s Self-Hosted
─────────────────────────────────────────────────────────────────────
1,000 ATMs/month    $180/mo         $179/mo          $500+/mo
10,000 ATMs/month   $280/mo         $250/mo          $1,000+/mo
100,000 ATMs/month  $800/mo         $600/mo          $3,000+/mo

Reserve instances   -30% on compute  No savings       -40% on compute
Auto-scaling ready  ✓               ✓                ✓
Managed service     ✓               ✓ (best)         ✗
Learning curve      Medium          Low              Steep
```

---

## Cost Optimization Strategies

### 1. Reserved Instances / Commitments

**AWS:**
```
1-year all upfront: -31% on compute + storage
3-year all upfront: -40% on compute + storage
Savings: ~$50-60/month
```

**GCP:**
```
1-year commitment: -25% on Cloud SQL
3-year commitment: -52% on Cloud SQL
Savings: ~$25-30/month
```

### 2. Auto-Scaling Tuning

**Current configuration:**
- Scale from 2-10 pods based on 70% CPU threshold
- This keeps costs low during off-hours

**Optimization:**
```
Off-peak (8PM-8AM): Scale to 1 pod
Peak (9AM-5PM): Scale to 5-10 pods
Savings: ~$60/month (40% less compute)
```

### 3. Database Optimization

**Current:** db.t3.micro → db.t4g.micro (graviton, -45% cost)
```
Savings: ~$15/month
```

**Connection pooling:** RDS Proxy
```
Cost: $0.015/hour × 730 = $10.95/month
Benefit: Reduced RDS load, better performance
Net: +$10.95/month (worth it for scale)
```

### 4. Caching Strategy

**Current:** Redis for alert deduplication

**Optimize with local cache:**
- Replace Redis with in-memory cache in API pods
- Reduce ElastiCache costs: $0 (down from $12.61/month)
- Trade-off: Dedup works per-pod, not cluster-wide
- Not recommended for production

### 5. Data Transfer Optimization

**Current:** 50 GB/month egress
**Optimize:**
- Use VPC endpoints (free internal transfer)
- CloudFront CDN (for dashboard static assets): +$5/month, saves $40
- Compress API responses (gzip): saves 60% on egress
- Total savings: $20-30/month

---

## Total Cost Projections (1 Year)

### AWS ECS

```
Year 1 (with free tier):
  Monthly: $162-182
  Yearly:  $1,944-2,184

Year 2+ (full pricing):
  Monthly: $182-202
  Yearly:  $2,184-2,424

With optimizations (reserved instances, caching):
  Monthly: $120-140
  Yearly:  $1,440-1,680
```

### Google Cloud Run

```
Year 1:
  Monthly: $179-199
  Yearly:  $2,148-2,388
  (minus $300 free tier credit: $1,848-2,088)

Year 2+:
  Monthly: $179-199
  Yearly:  $2,148-2,388

With commitments + optimizations:
  Monthly: $140-160
  Yearly:  $1,680-1,920
```

---

## Cost Monitoring & Alerts

### AWS

```bash
# Set up cost anomaly detection
aws ce create-anomaly-monitor \
  --anomaly-monitor '{
    "MonitorName": "atm-monitoring",
    "MonitorType": "DIMENSIONAL",
    "MonitorDimension": "SERVICE"
  }'

# Get current spending
aws ce get-cost-and-usage \
  --time-period Start=2026-01-01,End=2026-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost
```

### GCP

```bash
# Get billing data
gcloud billing accounts list
gcloud billing accounts get-iam-policy BILLING_ACCOUNT_ID

# Set up budget alerts
gcloud billing budgets create \
  --billing-account=BILLING_ACCOUNT_ID \
  --display-name="ATM Monitoring Monthly Budget" \
  --budget-amount=200 \
  --threshold-rule=percent=50 \
  --threshold-rule=percent=100
```

---

## Break-Even Analysis

**When does Cloud Run become cheaper than ECS?**

```
Cloud Run: $179/month (fixed)
ECS: $115 (compute) + $18 (LB) + $27 (DB) = $160/month (baseline)

→ Cloud Run becomes more expensive at scale
→ ECS is better for stable, predictable workloads
→ GCP better for variable, bursty workloads
```

---

## Recommendation

| Use Case | Best Choice | Monthly Cost |
|---|---|---|
| **Startup (MVP)** | GCP Cloud Run | $180 |
| **Growing startup** | AWS ECS | $160 |
| **Enterprise (10k+ ATMs)** | AWS ECS (reserved) | $120 |
| **Multi-region** | AWS ECS + AWS GCP | $400+ |

---

## Cost Reduction Roadmap

```
Month 1: Deploy baseline ($180/month)
  ↓
Month 2: Add reserved instances (-30%)
  ↓ $180 → $126/month
Month 3: Optimize caching & data transfer (-15%)
  ↓ $126 → $107/month
Month 6: Add auto-scaling schedule (-20%)
  ↓ $107 → $86/month
Month 12: Re-evaluate with real usage patterns

Target by Month 12: <$100/month
```

---

## Questions?

- Need RI calculator? → aws.amazon.com/ec2/pricing/reserved-instances
- Need GCP commitment discount? → cloud.google.com/pricing
- Need cost optimization audit? → Run `./deploy.sh` and enable CloudWatch/Cloud Monitoring
