#!/bin/bash
# Annotex Kind Deployment Script
# Deploys the application to a local Kind cluster for development/testing
#
# Usage:
#   ./scripts/kind-deploy.sh          # Full deployment (creates cluster)
#   ./scripts/kind-deploy.sh --skip-cluster  # Skip cluster creation (redeploy only)
#   ./scripts/kind-deploy.sh --delete  # Delete the cluster

set -e

# Configuration
CLUSTER_NAME="annotex"
NAMESPACE="annotex"
IMAGE_NAME="annotex"
IMAGE_TAG="latest"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! command -v kind &> /dev/null; then
        log_error "Kind is not installed. Install with: brew install kind"
        exit 1
    fi

    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed. Install with: brew install kubectl"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running. Please start Docker."
        exit 1
    fi

    log_info "All prerequisites met."
}

# Delete cluster
delete_cluster() {
    log_info "Deleting Kind cluster '${CLUSTER_NAME}'..."
    kind delete cluster --name "${CLUSTER_NAME}" 2>/dev/null || true
    log_info "Cluster deleted."
}

# Create Kind cluster
create_cluster() {
    # Check if cluster already exists
    if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
        log_warn "Cluster '${CLUSTER_NAME}' already exists."
        read -p "Delete and recreate? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            delete_cluster
        else
            log_info "Using existing cluster."
            kubectl cluster-info --context "kind-${CLUSTER_NAME}"
            return
        fi
    fi

    log_info "Creating Kind cluster '${CLUSTER_NAME}'..."
    kind create cluster --name "${CLUSTER_NAME}" --config k8s/kind/cluster-config.yml

    log_info "Waiting for node to be ready..."
    kubectl wait --for=condition=ready node --all --timeout=120s

    log_info "Cluster created successfully."
}

# Build Docker image
build_image() {
    log_info "Building Docker image '${IMAGE_NAME}:${IMAGE_TAG}'..."
    docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" .
    log_info "Image built successfully."
}

# Load image into Kind
load_image() {
    log_info "Loading image into Kind cluster..."
    kind load docker-image "${IMAGE_NAME}:${IMAGE_TAG}" --name "${CLUSTER_NAME}"
    log_info "Image loaded successfully."
}

# Deploy infrastructure (PostgreSQL, Redis)
deploy_infrastructure() {
    log_info "Creating namespace '${NAMESPACE}'..."
    kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

    log_info "Deploying PostgreSQL..."
    kubectl apply -f k8s/kind/postgres.yml -n "${NAMESPACE}"

    log_info "Deploying Redis..."
    kubectl apply -f k8s/kind/redis.yml -n "${NAMESPACE}"

    log_info "Waiting for PostgreSQL to be ready..."
    kubectl wait --for=condition=ready pod -l app=postgres -n "${NAMESPACE}" --timeout=120s

    log_info "Waiting for Redis to be ready..."
    kubectl wait --for=condition=ready pod -l app=redis -n "${NAMESPACE}" --timeout=120s

    log_info "Infrastructure deployed successfully."
}

# Deploy configuration
deploy_config() {
    log_info "Deploying ConfigMap..."
    kubectl apply -f k8s/configmap.yml -n "${NAMESPACE}"

    log_info "Creating Secrets..."
    kubectl create secret generic annotex-secrets \
        --from-literal=DATABASE_URL="postgresql+asyncpg://postgres:postgres@postgres:5432/annotex" \
        --from-literal=REDIS_URL="redis://redis:6379/0" \
        --from-literal=SECRET_KEY="kind-dev-secret-key-not-for-production" \
        --dry-run=client -o yaml | kubectl apply -f - -n "${NAMESPACE}"

    log_info "Configuration deployed successfully."
}

# Deploy application
deploy_application() {
    log_info "Preparing deployment manifest..."

    # Replace image placeholder with actual image and fix imagePullPolicy for Kind
    sed "s|DOCKER_IMAGE_PLACEHOLDER:IMAGE_TAG_PLACEHOLDER|${IMAGE_NAME}:${IMAGE_TAG}|g; s|imagePullPolicy: Always|imagePullPolicy: IfNotPresent|g" \
        k8s/deployment.yml > /tmp/annotex-deployment-kind.yml

    log_info "Deploying application..."
    kubectl apply -f /tmp/annotex-deployment-kind.yml -n "${NAMESPACE}"
    kubectl apply -f k8s/kind/service.yml -n "${NAMESPACE}"

    log_info "Waiting for API deployment to be ready..."
    kubectl rollout status deployment/annotex-api -n "${NAMESPACE}" --timeout=300s

    log_info "Waiting for Worker deployment to be ready..."
    kubectl rollout status deployment/annotex-worker -n "${NAMESPACE}" --timeout=300s || log_warn "Worker deployment may take longer due to ML model loading."

    log_info "Application deployed successfully."
}

# Verify deployment
verify_deployment() {
    log_info "Verifying deployment..."

    echo ""
    echo "=== Deployments ==="
    kubectl get deployments -n "${NAMESPACE}"

    echo ""
    echo "=== Pods ==="
    kubectl get pods -n "${NAMESPACE}"

    echo ""
    echo "=== Services ==="
    kubectl get services -n "${NAMESPACE}"

    echo ""
    log_info "Checking API health..."

    # Give the service a moment to be ready
    sleep 5

    if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
        log_info "API is healthy!"
    else
        log_warn "API health check failed. The pods may still be starting."
        log_info "Check pod status with: kubectl get pods -n ${NAMESPACE}"
        log_info "Check pod logs with: kubectl logs -l app=annotex -n ${NAMESPACE}"
    fi
}

# Print access information
print_access_info() {
    echo ""
    echo "============================================"
    echo "  Annotex Kind Deployment Complete!"
    echo "============================================"
    echo ""
    echo "Access the application:"
    echo "  - API:     http://localhost:8080"
    echo "  - Docs:    http://localhost:8080/docs"
    echo "  - Health:  http://localhost:8080/health"
    echo ""
    echo "Useful commands:"
    echo "  kubectl get pods -n ${NAMESPACE}           # List pods"
    echo "  kubectl logs -l app=annotex -n ${NAMESPACE} # View logs"
    echo "  kubectl exec -it deploy/postgres -n ${NAMESPACE} -- psql -U postgres annotex"
    echo ""
    echo "To delete the cluster:"
    echo "  kind delete cluster --name ${CLUSTER_NAME}"
    echo "  # or: ./scripts/kind-deploy.sh --delete"
    echo ""
}

# Main execution
main() {
    cd "$(dirname "$0")/.."  # Change to project root

    case "${1:-}" in
        --delete)
            delete_cluster
            exit 0
            ;;
        --skip-cluster)
            check_prerequisites
            build_image
            load_image
            deploy_infrastructure
            deploy_config
            deploy_application
            verify_deployment
            print_access_info
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --skip-cluster  Skip cluster creation (redeploy app only)"
            echo "  --delete        Delete the Kind cluster"
            echo "  --help, -h      Show this help message"
            echo ""
            exit 0
            ;;
        *)
            check_prerequisites
            create_cluster
            build_image
            load_image
            deploy_infrastructure
            deploy_config
            deploy_application
            verify_deployment
            print_access_info
            ;;
    esac
}

main "$@"
