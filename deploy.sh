#!/bin/bash

##############################################################################
# ATM ML Monitoring — Automated AWS Deployment Script
# 
# Usage:
#   ./deploy.sh aws         # Deploy to AWS ECS
#   ./deploy.sh gcp         # Deploy to Google Cloud Run
#   ./deploy.sh k8s         # Deploy to Kubernetes
#
# Prerequisites:
#   - AWS CLI / gcloud CLI / kubectl installed
#   - Docker installed
#   - Credentials configured (aws configure / gcloud auth login)
##############################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="atm-ml-monitoring"
DOCKER_IMAGE="$PROJECT_NAME:latest"
AWS_REGION="${AWS_REGION:-us-east-1}"
GCP_REGION="${GCP_REGION:-us-central1}"
ENVIRONMENT="${ENVIRONMENT:-prod}"

##############################################################################
# Helper Functions
##############################################################################

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

check_command() {
    if ! command -v $1 &> /dev/null; then
        log_error "$1 is not installed. Please install it first."
    fi
}

##############################################################################
# AWS Deployment Functions
##############################################################################

aws_deploy() {
    log_info "Starting AWS ECS deployment..."
    
    # Validate prerequisites
    check_command aws
    check_command docker
    
    # Get AWS account ID
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    ECR_REPO="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$PROJECT_NAME"
    
    log_info "AWS Account: $AWS_ACCOUNT_ID"
    log_info "ECR Repository: $ECR_REPO"
    
    # Step 1: Create ECR repository (if not exists)
    log_info "Step 1: Checking ECR repository..."
    if ! aws ecr describe-repositories --repository-names $PROJECT_NAME --region $AWS_REGION &> /dev/null; then
        log_warning "ECR repository doesn't exist. Creating..."
        aws ecr create-repository \
            --repository-name $PROJECT_NAME \
            --region $AWS_REGION
        log_success "ECR repository created"
    else
        log_success "ECR repository exists"
    fi
    
    # Step 2: Login to ECR
    log_info "Step 2: Logging in to ECR..."
    aws ecr get-login-password --region $AWS_REGION | \
        docker login --username AWS --password-stdin $ECR_REPO
    log_success "Logged in to ECR"
    
    # Step 3: Build Docker image
    log_info "Step 3: Building Docker image..."
    docker build -t $DOCKER_IMAGE .
    log_success "Docker image built"
    
    # Step 4: Tag image
    log_info "Step 4: Tagging image..."
    docker tag $DOCKER_IMAGE $ECR_REPO:latest
    docker tag $DOCKER_IMAGE $ECR_REPO:$(date +%Y%m%d-%H%M%S)
    log_success "Image tagged"
    
    # Step 5: Push to ECR
    log_info "Step 5: Pushing image to ECR..."
    docker push $ECR_REPO:latest
    log_success "Image pushed to ECR"
    
    # Step 6: Deploy with CloudFormation
    log_info "Step 6: Deploying with CloudFormation..."
    
    STACK_NAME="$PROJECT_NAME-$ENVIRONMENT"
    
    # Check if stack exists
    if aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_REGION &> /dev/null; then
        log_info "Stack exists. Updating..."
        aws cloudformation update-stack \
            --stack-name $STACK_NAME \
            --template-body file://infra/aws-cloudformation.yml \
            --parameters \
                ParameterKey=EnvironmentName,ParameterValue=$ENVIRONMENT \
                ParameterKey=ContainerImage,ParameterValue=$ECR_REPO:latest \
                ParameterKey=DesiredCount,ParameterValue=2 \
            --capabilities CAPABILITY_NAMED_IAM \
            --region $AWS_REGION
    else
        log_info "Stack doesn't exist. Creating..."
        aws cloudformation create-stack \
            --stack-name $STACK_NAME \
            --template-body file://infra/aws-cloudformation.yml \
            --parameters \
                ParameterKey=EnvironmentName,ParameterValue=$ENVIRONMENT \
                ParameterKey=ContainerImage,ParameterValue=$ECR_REPO:latest \
                ParameterKey=DesiredCount,ParameterValue=2 \
            --capabilities CAPABILITY_NAMED_IAM \
            --region $AWS_REGION
    fi
    
    log_info "Waiting for stack operation to complete..."
    aws cloudformation wait stack-create-complete \
        --stack-name $STACK_NAME \
        --region $AWS_REGION || \
    aws cloudformation wait stack-update-complete \
        --stack-name $STACK_NAME \
        --region $AWS_REGION
    
    log_success "Stack deployment complete"
    
    # Step 7: Get outputs
    log_info "Step 7: Retrieving endpoints..."
    OUTPUTS=$(aws cloudformation describe-stacks \
        --stack-name $STACK_NAME \
        --region $AWS_REGION \
        --query 'Stacks[0].Outputs')
    
    log_success "AWS Deployment Complete!"
    echo ""
    echo "=== Deployment Outputs ==="
    echo "$OUTPUTS" | jq -r '.[] | "\(.OutputKey): \(.OutputValue)"'
    echo ""
    echo "API Docs:  $(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="ApiEndpoint") | .OutputValue')"
    echo "Dashboard: $(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="DashboardEndpoint") | .OutputValue')"
}

##############################################################################
# GCP Deployment Functions
##############################################################################

gcp_deploy() {
    log_info "Starting Google Cloud Run deployment..."
    
    # Validate prerequisites
    check_command gcloud
    check_command docker
    
    # Get project ID
    PROJECT_ID=$(gcloud config get-value project)
    log_info "GCP Project: $PROJECT_ID"
    
    # Step 1: Enable services
    log_info "Step 1: Enabling required services..."
    gcloud services enable run.googleapis.com
    gcloud services enable artifactregistry.googleapis.com
    gcloud services enable cloudbuild.googleapis.com
    log_success "Services enabled"
    
    # Step 2: Create Artifact Registry repo (if not exists)
    log_info "Step 2: Setting up Artifact Registry..."
    if ! gcloud artifacts repositories describe $PROJECT_NAME --location=$GCP_REGION &> /dev/null; then
        log_warning "Repository doesn't exist. Creating..."
        gcloud artifacts repositories create $PROJECT_NAME \
            --repository-format=docker \
            --location=$GCP_REGION \
            --description="ATM ML Monitoring System"
        log_success "Repository created"
    else
        log_success "Repository exists"
    fi
    
    # Step 3: Build and push image
    log_info "Step 3: Building and pushing image..."
    gcloud builds submit \
        --region=$GCP_REGION \
        --tag $GCP_REGION-docker.pkg.dev/$PROJECT_ID/$PROJECT_NAME/$PROJECT_NAME:latest
    log_success "Image built and pushed"
    
    # Step 4: Deploy API service
    log_info "Step 4: Deploying API service..."
    gcloud run deploy atm-api \
        --image $GCP_REGION-docker.pkg.dev/$PROJECT_ID/$PROJECT_NAME/$PROJECT_NAME:latest \
        --platform managed \
        --region $GCP_REGION \
        --port 8000 \
        --memory 2Gi \
        --cpu 2 \
        --allow-unauthenticated \
        --set-env-vars PYTHONPATH=/app \
        --timeout 900
    log_success "API service deployed"
    
    # Step 5: Deploy Dashboard service
    log_info "Step 5: Deploying Dashboard service..."
    gcloud run deploy atm-dashboard \
        --image $GCP_REGION-docker.pkg.dev/$PROJECT_ID/$PROJECT_NAME/$PROJECT_NAME:latest \
        --platform managed \
        --region $GCP_REGION \
        --port 8501 \
        --memory 2Gi \
        --cpu 2 \
        --allow-unauthenticated \
        --timeout 900 \
        --command streamlit \
        --args "run,app/dashboard.py,--server.port=8501,--server.address=0.0.0.0"
    log_success "Dashboard service deployed"
    
    # Step 6: Get service URLs
    log_info "Step 6: Retrieving service URLs..."
    API_URL=$(gcloud run services describe atm-api --region=$GCP_REGION --format='value(status.url)')
    DASHBOARD_URL=$(gcloud run services describe atm-dashboard --region=$GCP_REGION --format='value(status.url)')
    
    log_success "GCP Deployment Complete!"
    echo ""
    echo "=== Service URLs ==="
    echo "API Docs:  $API_URL/docs"
    echo "Dashboard: $DASHBOARD_URL"
}

##############################################################################
# Kubernetes Deployment Functions
##############################################################################

k8s_deploy() {
    log_info "Starting Kubernetes deployment..."
    
    # Validate prerequisites
    check_command kubectl
    check_command docker
    
    # Step 1: Build and push image
    log_info "Step 1: Building Docker image..."
    REGISTRY="${REGISTRY:-your-registry}"
    docker build -t $DOCKER_IMAGE .
    docker tag $DOCKER_IMAGE $REGISTRY/$PROJECT_NAME:latest
    docker tag $DOCKER_IMAGE $REGISTRY/$PROJECT_NAME:$(date +%Y%m%d-%H%M%S)
    log_success "Docker image built"
    
    log_info "Step 2: Pushing image to registry..."
    docker push $REGISTRY/$PROJECT_NAME:latest
    log_success "Image pushed"
    
    # Step 2: Create namespace
    log_info "Step 3: Creating namespace..."
    kubectl create namespace $PROJECT_NAME --dry-run=client -o yaml | kubectl apply -f -
    log_success "Namespace ready"
    
    # Step 3: Update deployment image
    log_info "Step 4: Updating deployment image..."
    sed "s|atm-ml-monitoring:latest|$REGISTRY/$PROJECT_NAME:latest|g" k8s/deployment.yaml > /tmp/deployment-updated.yaml
    
    # Step 4: Apply deployment
    log_info "Step 5: Applying Kubernetes manifests..."
    kubectl apply -f /tmp/deployment-updated.yaml -n $PROJECT_NAME
    log_success "Manifests applied"
    
    # Step 5: Wait for rollout
    log_info "Step 6: Waiting for rollout..."
    kubectl rollout status deployment/atm-monitoring-api -n $PROJECT_NAME --timeout=5m
    log_success "Rollout complete"
    
    # Step 6: Get service info
    log_info "Step 7: Retrieving service information..."
    log_success "Kubernetes Deployment Complete!"
    echo ""
    echo "=== Service Information ==="
    kubectl get svc -n $PROJECT_NAME
    echo ""
    echo "To access services locally:"
    echo "  kubectl port-forward svc/atm-monitoring-api-svc 8000:80 -n $PROJECT_NAME"
    echo "  kubectl port-forward svc/atm-monitoring-dashboard-svc 8501:80 -n $PROJECT_NAME"
}

##############################################################################
# Main Menu
##############################################################################

show_usage() {
    echo "Usage: $0 {aws|gcp|k8s}"
    echo ""
    echo "Options:"
    echo "  aws      - Deploy to AWS ECS with CloudFormation"
    echo "  gcp      - Deploy to Google Cloud Run"
    echo "  k8s      - Deploy to Kubernetes cluster"
    echo ""
    echo "Environment variables:"
    echo "  AWS_REGION     - AWS region (default: us-east-1)"
    echo "  GCP_REGION     - GCP region (default: us-central1)"
    echo "  ENVIRONMENT    - Environment name (default: prod)"
    echo "  REGISTRY       - Docker registry for K8s (default: your-registry)"
}

if [ $# -eq 0 ]; then
    show_usage
    exit 1
fi

case "$1" in
    aws)
        aws_deploy
        ;;
    gcp)
        gcp_deploy
        ;;
    k8s)
        k8s_deploy
        ;;
    *)
        log_error "Unknown option: $1"
        show_usage
        exit 1
        ;;
esac
