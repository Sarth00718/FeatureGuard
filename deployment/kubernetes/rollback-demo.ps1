# Rollback demonstration: deploy a deliberately broken release, watch it fail, roll back.
#   powershell -ExecutionPolicy Bypass -File deployment/kubernetes/rollback-demo.ps1
$ErrorActionPreference = "Continue"
$ns = "featureguard"

Write-Host "`n1) Current rollout history (good version should be revision 1+)"
kubectl -n $ns rollout history deployment/backend

Write-Host "`n2) Deploying a BROKEN release (image tag that does not exist)"
kubectl -n $ns set image deployment/backend backend=featureguard-backend:broken
kubectl -n $ns rollout status deployment/backend --timeout=40s
if ($LASTEXITCODE -ne 0) {
  Write-Host "`n3) Rollout did not become ready. Because maxUnavailable=0 the old pods are STILL serving traffic."
  kubectl -n $ns get pods -l app=backend
  Write-Host "`n4) Rolling back to the previous working revision"
  kubectl -n $ns rollout undo deployment/backend
  kubectl -n $ns rollout status deployment/backend --timeout=120s
}
Write-Host "`n5) History after rollback"
kubectl -n $ns rollout history deployment/backend
kubectl -n $ns get pods -l app=backend
