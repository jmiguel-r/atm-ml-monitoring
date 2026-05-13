# 🚢 ATM ML Monitoring — Production Deployment Guide

## AWS Deployment (ECS + CloudFormation)

### Prerequisites
```bash
# Install AWS CLI
brew install awscli

# Configure credentials
aws configure
# Enter: Access Key ID, Secret Access Key, Region, Output format
```

### Step 1: Create ECR Repository

```bash
aws ecr create-repository --repository-name atm-ml-monitoring --region us-east-1
```

### Step 2: Build and Push Docker Image

```bash
# Get login token
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Build image
docker build -t atm-ml-monitoring:latest .

# Tag image
docker tag atm-ml-monitoring:latest YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/atm-ml-monitoring:latest

# Push to ECR
docker push YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/atm-ml-monitoring:latest
```

### Step 3: Deploy with CloudFormation

```bash
# Validate template
aws cloudformation validate-template \
  --template-body file://infra/aws-cloudformation.yml

# Create stack
aws cloudformation create-stack \
  --stack-name atm-ml-monitoring-prod \
  --template-body file://infra/aws-cloudformation.yml \
  --parameters \
    ParameterKey=EnvironmentName,ParameterValue=prod \
    ParameterKey=ContainerImage,ParameterValue=YOUR_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/atm-ml-monitoring:latest \
    ParameterKey=DesiredCount,ParameterValue=2 \
  --capabilities CAPABILITY_NAMED_IAM

# Monitor stack creation
aws cloudformation wait stack-create-complete --stack-name atm-ml-monitoring-prod

# Get outputs
aws cloudformation describe-stacks \
  --stack-name atm-ml-monitoring-prod \
  --query 'Stacks[0].Outputs'
```

### Step 4: Access Your Deployment

```bash
# Get the load balancer DNS
ALB_DNS=$(aws cloudformation describe-stacks \
  --stack-name atm-ml-monitoring-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`LoadBalancerDNS`].OutputValue' \
  --output text)

# Access API
open http://$ALB_DNS:8000/docs

# Access Dashboard
open http://$ALB_DNS:8501
```

---

## Google Cloud Deployment (Cloud Run)

### Prerequisites

```bash
# Install gcloud CLI
brew install google-cloud-sdk

# Authenticate
gcloud auth login

# Set project
gcloud config set project YOUR_PROJECT_ID

# Enable services
gcloud services enable run.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable cloudbuild.googleapis.com
```

### Step 1: Create Artifact Registry

```bash
gcloud artifacts repositories create atm-ml-monitoring \
  --repository-format=docker \
  --location=us-central1 \
  --description="ATM ML Monitoring System"
```

### Step 2: Build and Push Image

```bash
# Build with Cloud Build
gcloud builds submit --region=us-central1 \
  --tag us-central1-docker.pkg.dev/YOUR_PROJECT_ID/atm-ml-monitoring/atm-api:latest

# Or build locally and push
docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT_ID/atm-ml-monitoring/atm-api:latest .
docker push us-central1-docker.pkg.dev/YOUR_PROJECT_ID/atm-ml-monitoring/atm-api:latest
```

### Step 3: Deploy API Service

```bash
gcloud run deploy atm-api \
  --image us-central1-docker.pkg.dev/YOUR_PROJECT_ID/atm-ml-monitoring/atm-api:latest \
  --platform managed \
  --region us-central1 \
  --port 8000 \
  --memory 2Gi \
  --cpu 2 \
  --allow-unauthenticated \
  --set-env-vars PYTHONPATH=/app
```

### Step 4: Deploy Dashboard Service

```bash
gcloud run deploy atm-dashboard \
  --image us-central1-docker.pkg.dev/YOUR_PROJECT_ID/atm-ml-monitoring/atm-api:latest \
  --platform managed \
  --region us-central1 \
  --port 8501 \
  --memory 2Gi \
  --cpu 2 \
  --allow-unauthenticated \
  --command streamlit \
  --args "run,app/dashboard.py,--server.port=8501,--server.address=0.0.0.0"
```

### Step 5: Get Service URLs

```bash
# API endpoint
gcloud run services describe atm-api --region us-central1 --format='value(status.url)'

# Dashboard endpoint
gcloud run services describe atm-dashboard --region us-central1 --format='value(status.url)'
```

---

## Kubernetes Deployment (Self-Hosted)

### Prerequisites

```bash
# Install kubectl
brew install kubectl

# Set kubeconfig
export KUBECONFIG=path/to/kubeconfig.yaml
```

### Step 1: Build and Push Image

```bash
docker build -t your-registry/atm-ml-monitoring:latest .
docker push your-registry/atm-ml-monitoring:latest

# Update k8s/deployment.yaml with your image
sed -i 's|atm-monitoring:latest|your-registry/atm-ml-monitoring:latest|g' k8s/deployment.yaml
```

### Step 2: Deploy

```bash
# Create namespace
kubectl create namespace atm-monitoring

# Apply deployment
kubectl apply -f k8s/deployment.yaml -n atm-monitoring

# Check status
kubectl get pods -n atm-monitoring
kubectl get svc -n atm-monitoring

# Get LoadBalancer IP/DNS
kubectl get svc atm-monitoring-api-svc -n atm-monitoring
```

### Step 3: Monitor

```bash
# View logs
kubectl logs -f deployment/atm-monitoring-api -n atm-monitoring

# Port-forward (local testing)
kubectl port-forward svc/atm-monitoring-api-svc 8000:80 -n atm-monitoring
# Now access http://localhost:8000/docs
```

---

## Production Checklist

- [ ] **Database Setup**
  - [ ] Create RDS PostgreSQL (AWS) or Cloud SQL (GCP)
  - [ ] Update `requirements.txt` to include psycopg2-binary
  - [ ] Migrate alert storage to database (not in-memory)

- [ ] **Caching**
  - [ ] Set up ElastiCache Redis (AWS) or Memorystore (GCP)
  - [ ] Use for alert deduplication across pods

- [ ] **Secrets Management**
  - [ ] Store database passwords in AWS Secrets Manager / GCP Secret Manager
  - [ ] Reference in CloudFormation / deployment templates

- [ ] **Monitoring & Logging**
  - [ ] CloudWatch (AWS) or Cloud Logging (GCP)
  - [ ] Prometheus metrics enabled
  - [ ] Grafana dashboards configured

- [ ] **DNS & SSL**
  - [ ] Register domain
  - [ ] Create SSL certificate (ACM for AWS, Google-managed for GCP)
  - [ ] Configure HTTPS in ALB / Cloud Load Balancer

- [ ] **Backup & Disaster Recovery**
  - [ ] Enable RDS automated backups (35 days retention)
  - [ ] Test restore procedures
  - [ ] Document runbooks

- [ ] **Performance Tuning**
  - [ ] Set appropriate resource limits (CPU, memory)
  - [ ] Configure auto-scaling thresholds
  - [ ] Test under load (k6, JMeter)

- [ ] **Security**
  - [ ] Enable WAF (Web Application Firewall)
  - [ ] Run vulnerability scans on images
  - [ ] Enable VPC Flow Logs
  - [ ] Implement rate limiting on API

---

## Monitoring & Alerting

### CloudWatch Metrics (AWS)

```bash
# Create dashboard
aws cloudwatch put-dashboard \
  --dashboard-name atm-monitoring \
  --dashboard-body file://monitoring/cloudwatch-dashboard.json
```

### Alerts

CPU > 80% for 10 minutes → Scale up
Memory > 85% → Alert ops team
API latency > 5s (p95) → Investigate

---

## Cost Estimation

### AWS (Monthly)

- ECS Fargate: ~$100-200 (2-10 tasks, 1-2 vCPU each)
- RDS PostgreSQL: ~$50-100 (db.t3.micro)
- ElastiCache Redis: ~$15-30
- ALB: ~$20
- Data transfer: ~$5-10
- **Total: ~$190-360/month**

### GCP (Monthly)

- Cloud Run (2 services): ~$100-150
- Cloud SQL: ~$50-100
- Memorystore: ~$15-30
- Cloud Load Balancer: ~$15
- **Total: ~$180-295/month**

---

## Troubleshooting

### ECS Tasks failing to start

```bash
# Check logs
aws logs tail /ecs/atm-ml-monitoring --follow

# Check task definition
aws ecs describe-tasks --cluster atm-monitoring-cluster --tasks TASK_ARN
```

### Cloud Run service timing out

```bash
# Increase timeout
gcloud run services update atm-api --timeout 900
```

### Kubernetes pods stuck in pending

```bash
kubectl describe pod POD_NAME -n atm-monitoring
kubectl get events -n atm-monitoring
```

---

## Rollback Procedures

### AWS CloudFormation

```bash
aws cloudformation cancel-update-stack --stack-name atm-ml-monitoring-prod
# or
aws cloudformation update-stack --stack-name atm-ml-monitoring-prod \
  --use-previous-template
```

### GCP Cloud Run

```bash
# List revisions
gcloud run services describe atm-api --region us-central1

# Route traffic to previous revision
gcloud run services update-traffic atm-api --to-revisions REVISION_NAME=100 --region us-central1
```

---

## Support & Questions

For issues with deployment:
1. Check logs: `kubectl logs` / CloudWatch / Cloud Logging
2. Verify image: `docker run -it IMAGE /bin/bash`
3. Test locally first: `docker compose up`
4. Open GitHub issue with logs attached
