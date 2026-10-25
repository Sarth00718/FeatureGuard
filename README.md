# FeatureGuard - Red Wine Quality Prediction with Training-Serving Skew Detection

College MLOps project: React + FastAPI + PostgreSQL + Random Forest, with DVC, MLflow, Evidently, Nginx, Docker Compose, Jenkins, Prometheus/Grafana and Kubernetes.

Read first: `docs/ARCHITECTURE.md` (diagram and workflow), `docs/DEMO_GUIDE.md`, `docs/VIVA.md`.

## What was verified, and what was not
Verified while building (Linux sandbox, Python 3.12, Node 22):
* 23 Python tests pass in a clean virtualenv created from the pinned `requirements.txt` (validation, drift with both KS and Evidently engines, ML helpers, API with SQLite).
* `python -m ml.train` with MLflow logging and registry, `ml.evaluate`, and the failing quality gate (exit code 1, previous model untouched) all ran. This was done on a small SYNTHETIC dataset because the UCI site was not reachable from the sandbox. Those numbers mean nothing for wine quality; **run the pipeline on the real CSV and use your own results.**
* Frontend: `npm test` (3 tests) and `npm run build` pass. All YAML/JSON files parse.

NOT verified (no Docker, Kubernetes, Jenkins or Grafana in the sandbox): Docker image builds, Docker Compose startup, the MLflow image tag `ghcr.io/mlflow/mlflow:v2.16.2`, the Jenkins image and pipeline, Kubernetes manifests, Grafana dashboard rendering, the PowerShell scripts, and Evidently inside the Python 3.11 container. Expect to fix small issues there; the troubleshooting section lists the likely ones. Please do not tell faculty something works until you have run it.

## Layout
```
frontend/    React + Vite dashboard          backend/     FastAPI API (app/main.py)
ml/          train, evaluate, predict,       featureguard/ validation.py, drift_monitor.py
             preprocessing, validate_data
database/    init.sql (reference schema)     nginx/       nginx.conf + Dockerfile
monitoring/  prometheus.yml, Grafana         deployment/  docker-compose.yml, jenkins/, kubernetes/
tests/       pytest                          scripts/     simulate_traffic.py
dvc.yaml  params.yaml  Jenkinsfile  requirements.txt  .env.example
```

## Setup (Windows PowerShell)
Requirements: Python 3.11+, Node 20+, Git, Docker Desktop. Run everything from the repository root.

### 1. Python environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
If scripts are blocked: `Set-ExecutionPolicy -Scope Process Bypass`.

### 2. Dataset and DVC
```powershell
python ml/download_data.py          # or download winequality-red.csv manually into data/raw/
```
DVC is already initialised (`.dvcignore`, `dvc.yaml`, `data/raw/winequality-red.csv.dvc` are in the repo).
`data/raw/winequality-red.csv` is git-ignored; DVC tracks it via the `.dvc` pointer file.

### 3. Train (one command)
```powershell
python -m ml.train
```
Validates data, trains, prints MAE / RMSE / R2 on the test split, applies the quality gate in `params.yaml`, logs to MLflow, and writes `models/`. Exit code 1 means the gate failed.
Reproducible alternative with DVC: `dvc repro`. Re-check metrics anytime: `python -m ml.evaluate`.

MLflow: by default runs go to a local `mlflow.db` (view with `mlflow ui --backend-store-uri sqlite:///mlflow.db`). To use the Compose MLflow server: `$env:MLFLOW_TRACKING_URI="http://localhost:5000"` before training.

### 4. Tests
```powershell
python -m pytest -q
cd frontend; npm install; npm test; cd ..
```

### 5. Run with Docker Compose (required — PostgreSQL runs in Docker)
```powershell
Copy-Item .env.example .env        # then edit the passwords in .env
docker compose --env-file .env -f deployment/docker-compose.yml up -d --build
docker compose --env-file .env -f deployment/docker-compose.yml ps
```
The model must already be trained (step 3): it is copied into the backend image.
Open http://localhost (app), http://localhost/api/docs (API docs), http://localhost:3000 (Grafana), http://localhost:9090 (Prometheus), http://localhost:5000 (MLflow).
All API calls go through Nginx on port 80 — always use `http://localhost/api/...` not `localhost:8000`.
Stop: `docker compose --env-file .env -f deployment/docker-compose.yml down` (add `-v` to delete the data volumes).
Jenkins runs locally on your machine at http://localhost:8080.
Push this repo to GitHub and configure Jenkins with "Pipeline script from SCM" → your repo URL + `github-pat` credential + branch `*/main` + Script Path `Jenkinsfile`. Set Poll SCM trigger `H/5 * * * *`. See `STEP_BY_STEP_EXECUTION.txt` Phase 3-B and Phase 4 for the full walkthrough.

### 7. Kubernetes (Docker Desktop with Kubernetes enabled, or Minikube)
```powershell
# Build images
docker build -t featureguard-backend:1.0.0  -f backend/Dockerfile .
docker build -t featureguard-frontend:1.0.0 frontend
docker build -t featureguard-nginx:1.0.0    -f nginx/Dockerfile .

# Deploy
kubectl apply -f deployment/kubernetes/00-namespace-config.yaml
kubectl create configmap grafana-dashboards -n featureguard --from-file=monitoring/grafana/dashboards --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f deployment/kubernetes/10-postgres.yaml
kubectl apply -f deployment/kubernetes/20-backend.yaml
kubectl apply -f deployment/kubernetes/30-frontend.yaml
kubectl apply -f deployment/kubernetes/40-nginx.yaml
kubectl apply -f deployment/kubernetes/50-monitoring.yaml
kubectl -n featureguard set image deployment/backend  backend=featureguard-backend:1.0.0
kubectl -n featureguard set image deployment/frontend frontend=featureguard-frontend:1.0.0
kubectl -n featureguard rollout status deployment/backend  --timeout=180s
kubectl -n featureguard get pods
```
Rolling update: `kubectl -n featureguard set image deployment/backend backend=featureguard-backend:2.0.0`
Rollback: `kubectl -n featureguard rollout undo deployment/backend`
Tear down: `kubectl delete namespace featureguard`

## Configuration (environment variables)
| Variable | Meaning | Default |
|---|---|---|
| `POSTGRES_USER/PASSWORD/DB/HOST/PORT` | database connection (or set `DATABASE_URL`) | see `.env.example` |
| `MODEL_DIR` | folder with `model.joblib`, `metadata.json`, `reference.csv` | `models` |
| `DRIFT_ENGINE` | `evidently` or `ks` | `evidently` |
| `DRIFT_BATCH_SIZE` | accepted requests per drift check | 30 |
| `DRIFT_SHARE_THRESHOLD` | share of drifted features that triggers an alert | 0.3 |
| `MLFLOW_TRACKING_URI` | where training logs runs | local sqlite |
| `GRAFANA_USER/PASSWORD` | Grafana login | admin / see `.env` |

## Nginx routing
`nginx/nginx.conf`: `location /api/` uses `proxy_pass http://backend:8000/;`. The trailing slash removes `/api/`, so `/api/predict` reaches FastAPI as `/predict`. Everything else goes to the frontend container. Kubernetes uses the same rules with the same service names.

## Jenkins
Stages: Checkout, Install, Python tests, Frontend tests and build, Train and quality gate, Build images, Smoke test, Deploy, Verify health. Jenkins talks to Docker through the mounted `/var/run/docker.sock` (it uses the host's Docker daemon). Create two "Secret file" credentials in Jenkins: `featureguard-env` (your `.env`) and, for Kubernetes, `featureguard-kube` (kubeconfig). Nothing secret is in the repo. Create a Pipeline job from SCM pointing at this repository. The Deploy stages only run after every earlier stage passed; a failed quality gate stops the pipeline before any image is built.

## Troubleshooting
* **Backend container restarts / `/ready` returns 503:** the model is missing. Run `python -m ml.train`, rebuild (`up -d --build`).
* **`COPY models/ ... not found` during build:** same cause, `models/` does not exist yet.
* **`dvc repro` says data missing:** run `python ml/download_data.py` first.
* **Port 80/3000/5432 already in use:** set `HTTP_PORT` in `.env`, or stop the other program/stack.
* **Download fails:** get `winequality-red.csv` from https://archive.ics.uci.edu/dataset/186/wine+quality and put it in `data/raw/`.
* **MLflow image not found / training cannot reach MLflow:** unset `MLFLOW_TRACKING_URI` to use the local sqlite store, or check the image tag in the compose file.
* **Evidently import problems:** set `DRIFT_ENGINE=ks` (built-in fallback) and tell your faculty which engine you used.
* **Kubernetes pods `ImagePullBackOff`:** images are local. On Minikube run `minikube image load ...` (the script does this); on Docker Desktop make sure Kubernetes uses the Docker Desktop engine.
* **Grafana shows no data:** generate traffic (`python -m scripts.simulate_traffic`) and check http://localhost:9090/targets.
* **Windows line endings in shell scripts inside images:** none are used; ignore.

## Team split
Member 1: `frontend/`. Member 2: `backend/`, `database/`, `nginx/`. Member 3: `ml/`, `featureguard/`, `dvc.yaml`, `params.yaml`. Member 4: `deployment/`, `Jenkinsfile`, `monitoring/`. Everyone reads `docs/ARCHITECTURE.md` and can explain the request-to-prediction workflow.
