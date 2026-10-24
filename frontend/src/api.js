// All calls go through /api (Nginx in Docker/K8s, Vite proxy in dev).
const BASE = "/api";

async function request(path, options) {
  const res = await fetch(BASE + path, options);
  let body = null;
  try { body = await res.json(); } catch { /* not JSON */ }
  if (!res.ok) {
    const err = new Error((body && body.detail && (body.detail.message || body.detail)) || res.statusText);
    err.status = res.status;
    err.errors = body && body.detail && body.detail.errors;
    throw err;
  }
  return body;
}

export const api = {
  health: () => request("/health"),
  summary: () => request("/summary"),
  modelMetrics: () => request("/model/metrics"),
  predictions: (limit = 50) => request(`/predictions?limit=${limit}`),
  driftAlerts: (onlyDrift = false) => request(`/drift/alerts?only_drift=${onlyDrift}`),
  driftCheck: () => request("/drift/check", { method: "POST" }),
  predict: (payload) =>
    request("/predict", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }),
};
