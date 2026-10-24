# Viva questions and answers

**1. What problem does FeatureGuard solve?**
A model is trained on one data distribution but serves another. FeatureGuard rejects impossible inputs per request and watches batches of real inputs for distribution drift, so the team notices when the model may be operating outside what it learned.

**2. Difference between feature validation and drift detection?**
Validation checks one request against hard rules (fields, types, ranges) and rejects it. Drift detection compares a batch of many requests with the training data using statistical tests; it only raises an alert. One request cannot prove drift.

**3. Why not block requests when drift is detected?**
A distribution shift does not make each individual request invalid, and the model may still predict well. Blocking would cause an outage; an alert lets humans decide whether to retrain.

**4. Training-serving skew vs data drift?**
Skew: the features seen at serving differ from training because of a pipeline inconsistency (different columns, units, preprocessing). Our schema check guards this. Drift: the real world changes over time. Our batch check monitors this. This project covers both, with separate mechanisms.

**5. Why Random Forest?**
Strong baseline on small tabular data, needs little tuning, easy to explain. No GPU or deep learning needed.

**6. Which metrics and what do they mean?**
MAE: average absolute error in quality points. RMSE: like MAE but punishes big errors more. R2: share of variance explained (1 is perfect). All are computed on a held-out test split, never on training data.

**7. How is the train/test split reproducible?**
A fixed `random_state` in `params.yaml`, used by both training and `ml.evaluate`.

**8. What does DVC do here?**
It versions the dataset (`dvc add`) and defines the pipeline in `dvc.yaml`, so `dvc repro` reruns only the stages whose data, code or params changed.

**9. What does MLflow do here?**
It records every training run (params, metrics, model) and holds a model registry. Only models that pass the quality gate are registered.

**10. What is the quality gate?**
Thresholds in `params.yaml` (`min_r2`, `max_rmse`). If the new model is worse, training exits with code 1, nothing is saved or registered, and Jenkins stops before building or deploying.

**11. Why is training separate from the API?**
Training is slow and batch-oriented; serving must be fast and stable. The API only loads a saved model file.

**12. Why PostgreSQL?**
Predictions and drift results must survive restarts and be queryable for the history page and for batching drift checks. A Docker volume (and a PVC in Kubernetes) keeps the data.

**13. What does Nginx do?**
Single entry point: `/` goes to the frontend container, `/api/` goes to FastAPI with the prefix removed. The browser needs only one address and no CORS setup.

**14. Which Prometheus metrics do you expose?**
Prediction requests, failures, validation rejections, drift checks and alerts, request latency histogram, app up, model loaded.

**15. Liveness vs readiness probe?**
Liveness (`/health`) says the process is alive; failing it restarts the pod. Readiness (`/ready`) says it can serve (database and model available); failing it removes the pod from the Service without restarting it.

**16. Deployment rollback vs model rollback?**
Deployment rollback (`kubectl rollout undo`) returns to the previous container image. In this project the approved model is baked into the image, so it also returns the model that shipped with it. Model rollback in the ML sense means choosing an earlier registered version in MLflow, then re-training/re-exporting and rebuilding the image; it is a deliberate ML decision, not a Kubernetes feature.

**17. Does Kubernetes roll back automatically?**
No. With `maxUnavailable: 0` a broken new pod never becomes Ready, so old pods keep serving, but the rollout just stalls. We then roll back explicitly (`rollout undo`), and the Jenkinsfile does this when `rollout status` times out.

**18. Why does CI run tests before building images?**
Fail fast and cheaply: no image is built from code that fails tests or from a model that fails the gate.

**19. How do secrets stay out of the repo?**
`.env` is git-ignored (only `.env.example` is committed); Kubernetes uses a Secret; Jenkins uses stored credentials.

**20. Limitations?**
Drift state is computed from the database, so several replicas can occasionally check the same batch; the model is small and the dataset describes only one wine type; Jenkins and MLflow are not deployed in Kubernetes.
