# Demonstration guide (PowerShell, run from the repository root)

Prerequisites: stack running (README step 6) and a trained model.
Open: app http://localhost , Grafana http://localhost:3000 , Prometheus http://localhost:9090 , MLflow http://localhost:5000

## 1. Normal prediction
1. Open http://localhost, go to **Predict**, click **Load example**, press **Predict**.
2. Show the result (quality, model version, id). Open **History**: the row is saved in PostgreSQL.
3. Open **Model**: MAE / RMSE / R2 come from the real evaluation of the deployed model.

## 2. Invalid input
1. In **Predict**, press **Make alcohol invalid (demo)**, then **Predict**.
2. The API answers HTTP 422 with the reason; **History** shows a red `rejected` row with no prediction.
3. Grafana panel "Validation rejections" increases.
4. CLI alternative: `python -m scripts.simulate_traffic --mode invalid --count 3`

## 3. Drift alert
1. Normal traffic first (should NOT alert): `python -m scripts.simulate_traffic --mode normal --count 35`
2. Shifted traffic (valid values, different distribution): `python -m scripts.simulate_traffic --mode drift --count 35`
3. Open **Alerts**: a `DRIFT ALERT` row lists the drifted features (e.g. alcohol, total_sulfur_dioxide).
4. Explain: every request was accepted; the alert comes from comparing a batch of 30+ rows with the training data.
5. Grafana "Drift alerts" increases. Evidently report: `reports/drift/latest.html` inside the backend container.

If step 1 also raises an alert, say so honestly: a random sample of 30 rows can occasionally trip a statistical test. Check the `share_drifted` value and discuss the threshold (`DRIFT_SHARE_THRESHOLD`).

## 4. Failed CI test / failed quality gate
Option A - failing test:
1. In `featureguard/validation.py` change the `alcohol` range to `(5.0, 10.0)`.
2. Run `python -m pytest -q`: the tests fail. Push to Jenkins: the **Python tests** stage turns red and no image is built or deployed.
3. Revert the change.

Option B - failing quality gate:
1. In `params.yaml` set `min_r2: 0.99`.
2. Run `python -m ml.train`: prints `QUALITY GATE FAILED`, exit code 1, previous `models/` untouched, nothing registered in MLflow.
3. Revert the change.

## 5. Rollback
Kubernetes must be deployed (`deployment/kubernetes/deploy.ps1`).
1. `powershell -ExecutionPolicy Bypass -File deployment/kubernetes/rollback-demo.ps1`
2. The script deploys image tag `broken`, shows the rollout stalling while old pods keep serving, runs `kubectl rollout undo`, and prints the history.
3. Manual commands: `kubectl -n featureguard rollout history deployment/backend` and `kubectl -n featureguard rollout undo deployment/backend`.
4. Explain deployment rollback vs model-version rollback (docs/VIVA.md, question 16).
