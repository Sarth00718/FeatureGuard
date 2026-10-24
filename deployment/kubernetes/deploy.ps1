# Deploy FeatureGuard to Docker Desktop Kubernetes / Minikube.  Run from the repository root:
#   powershell -ExecutionPolicy Bypass -File deployment/kubernetes/deploy.ps1 -Tag 1.0.0
# Prerequisite: the model is trained (models/ exists)  ->  python -m ml.train
param([string]$Tag = "1.0.0")
$ErrorActionPreference = "Stop"

if (-not (Test-Path "models/model.joblib")) { throw "models/model.joblib not found - run: python -m ml.train" }

Write-Host "Building images (tag $Tag)..."
docker build -t featureguard-backend:$Tag -f backend/Dockerfile .
docker build -t featureguard-frontend:$Tag frontend
# Minikube only: make the local images visible to the cluster
if ((kubectl config current-context) -match "minikube") {
  minikube image load featureguard-backend:$Tag
  minikube image load featureguard-frontend:$Tag
}

kubectl apply -f deployment/kubernetes/00-namespace-config.yaml
kubectl create configmap grafana-dashboards -n featureguard --from-file=monitoring/grafana/dashboards --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f deployment/kubernetes/

# Point the Deployments at the tag that was just built
kubectl -n featureguard set image deployment/backend backend=featureguard-backend:$Tag
kubectl -n featureguard set image deployment/frontend frontend=featureguard-frontend:$Tag
kubectl -n featureguard rollout status deployment/backend --timeout=180s
kubectl -n featureguard rollout status deployment/frontend --timeout=120s
kubectl -n featureguard get pods
Write-Host "Open http://localhost  (Docker Desktop)  or run: minikube service nginx -n featureguard"
