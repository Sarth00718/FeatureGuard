import React, { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import { FIELDS, exampleValues, toPayload } from "./features.js";

const TABS = ["Dashboard", "Predict", "History", "Model", "Alerts", "Health"];

function useLoader(fn, deps = [], refreshMs = 0) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const load = useCallback(async () => {
    try { setState({ data: await fn(), error: null, loading: false }); }
    catch (e) { setState({ data: null, error: e.message, loading: false }); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => {
    load();
    if (refreshMs) { const t = setInterval(load, refreshMs); return () => clearInterval(t); }
  }, [load, refreshMs]);
  return { ...state, reload: load };
}

const Card = ({ title, value, hint }) => (
  <div className="card"><div className="card-title">{title}</div><div className="card-value">{value}</div>{hint && <div className="hint">{hint}</div>}</div>
);
const Err = ({ msg }) => msg ? <div className="error">Could not load data: {msg}</div> : null;

function Dashboard() {
  const s = useLoader(api.summary, [], 10000);
  const m = useLoader(api.modelMetrics, [], 30000);
  return (
    <section>
      <h2>Overview</h2>
      <Err msg={s.error} />
      {s.data && (
        <div className="grid">
          <Card title="Total requests" value={s.data.total_requests} />
          <Card title="Accepted" value={s.data.accepted} />
          <Card title="Rejected by validation" value={s.data.rejected} />
          <Card title="Drift alerts" value={s.data.drift_alerts} hint={`Checked every ${s.data.drift_batch_size} accepted requests`} />
        </div>
      )}
      <h2>Deployed model</h2>
      <Err msg={m.error} />
      {m.data && <p>Version <b>{m.data.model_version}</b>, trained {new Date(m.data.trained_at).toLocaleString()}. See the <b>Model</b> tab for its quality metrics.</p>}
    </section>
  );
}

function Predict() {
  const [values, setValues] = useState(exampleValues());
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true); setResult(null); setError(null);
    try { setResult(await api.predict(toPayload(values))); }
    catch (err) { setError(err); }
    finally { setBusy(false); }
  }
  return (
    <section>
      <h2>Predict wine quality</h2>
      <form onSubmit={submit} className="form">
        {FIELDS.map((f) => (
          <label key={f.name}>{f.label}
            <input value={values[f.name]} step={f.step} inputMode="decimal"
              onChange={(e) => setValues({ ...values, [f.name]: e.target.value })} />
          </label>
        ))}
        <div className="actions">
          <button type="submit" disabled={busy}>{busy ? "Predicting..." : "Predict"}</button>
          <button type="button" className="secondary" onClick={() => setValues(exampleValues())}>Load example</button>
          <button type="button" className="secondary" onClick={() => setValues({ ...values, alcohol: "99" })}>Make alcohol invalid (demo)</button>
        </div>
      </form>
      {result && <div className="success">Predicted quality: <b>{result.predicted_quality}</b> (about {result.rounded_quality} / 10) - model v{result.model_version}, saved as #{result.id}</div>}
      {error && (
        <div className="error"><b>Request rejected ({error.status || "network"}):</b> {error.message}
          {error.errors && <ul>{error.errors.map((x, i) => <li key={i}>{x}</li>)}</ul>}</div>
      )}
    </section>
  );
}

function History() {
  const h = useLoader(api.predictions, [], 10000);
  return (
    <section>
      <h2>Prediction history <button className="secondary small" onClick={h.reload}>Refresh</button></h2>
      <Err msg={h.error} />
      {h.data && h.data.length === 0 && <p>No predictions yet.</p>}
      {h.data && h.data.length > 0 && (
        <div className="table-wrap"><table>
          <thead><tr><th>#</th><th>Time</th><th>Status</th><th>Quality</th><th>Model</th><th>Alcohol</th><th>pH</th><th>Notes</th></tr></thead>
          <tbody>{h.data.map((p) => (
            <tr key={p.id} className={p.validation_status === "rejected" ? "row-bad" : ""}>
              <td>{p.id}</td><td>{new Date(p.created_at).toLocaleString()}</td><td>{p.validation_status}</td>
              <td>{p.predicted_quality == null ? "-" : p.predicted_quality.toFixed(2)}</td><td>{p.model_version}</td>
              <td>{String(p.features.alcohol ?? "")}</td><td>{String(p.features.ph ?? "")}</td>
              <td>{p.validation_errors ? p.validation_errors.join("; ") : ""}</td>
            </tr>))}</tbody>
        </table></div>
      )}
    </section>
  );
}

function Model() {
  const m = useLoader(api.modelMetrics);
  return (
    <section>
      <h2>Model performance</h2>
      <Err msg={m.error} />
      {m.data && (<>
        <div className="grid">
          <Card title="MAE" value={m.data.metrics.mae.toFixed(3)} hint="lower is better" />
          <Card title="RMSE" value={m.data.metrics.rmse.toFixed(3)} hint="lower is better" />
          <Card title="R squared" value={m.data.metrics.r2.toFixed(3)} hint="higher is better" />
        </div>
        <p className="hint">Offline evaluation of model v{m.data.model_version} on its {m.data.evaluated_on}. These are model-quality metrics measured at training time, not live traffic metrics (those are in Grafana).</p>
      </>)}
    </section>
  );
}

function Alerts() {
  const [onlyDrift, setOnlyDrift] = useState(false);
  const a = useLoader(() => api.driftAlerts(onlyDrift), [onlyDrift], 10000);
  const [msg, setMsg] = useState(null);
  async function runNow() {
    try { const r = await api.driftCheck(); setMsg(r.drift_detected ? "Drift detected in the checked batch." : "Batch checked: no drift detected."); a.reload(); }
    catch (e) { setMsg(e.message); }
  }
  return (
    <section>
      <h2>Feature drift alerts</h2>
      <p className="hint">Drift is judged on a batch of accepted requests compared with the training data, never on one request. Alerts are recorded and shown here; they do not block predictions.</p>
      <div className="actions">
        <button onClick={runNow}>Check recent requests now</button>
        <label className="inline"><input type="checkbox" checked={onlyDrift} onChange={(e) => setOnlyDrift(e.target.checked)} /> only show alerts</label>
      </div>
      {msg && <div className="info">{msg}</div>}
      <Err msg={a.error} />
      {a.data && a.data.length === 0 && <p>No drift checks recorded yet.</p>}
      {a.data && a.data.map((x) => (
        <div key={x.id} className={x.drift_detected ? "alert bad" : "alert ok"}>
          <b>{x.drift_detected ? "DRIFT ALERT" : "No drift"}</b> - {new Date(x.created_at).toLocaleString()} - batch of {x.batch_size}, {(x.share_drifted * 100).toFixed(0)}% of features drifted ({x.engine})
          {x.drifted_features.length > 0 && <div>Drifted: {x.drifted_features.join(", ")}</div>}
        </div>
      ))}
    </section>
  );
}

function Health() {
  const h = useLoader(api.health, [], 5000);
  const dot = (ok) => <span className={ok ? "dot ok" : "dot bad"} />;
  return (
    <section>
      <h2>Service health</h2>
      {h.error && <div className="error">API unreachable: {h.error}</div>}
      {h.data && (
        <div className="grid">
          <Card title="API" value={<>{dot(h.data.api === "ok")} {h.data.api}</>} />
          <Card title="Database" value={<>{dot(h.data.database === "ok")} {h.data.database}</>} />
          <Card title="Model" value={<>{dot(h.data.model === "loaded")} {h.data.model}</>} hint={h.data.model_version ? `version ${h.data.model_version}` : ""} />
        </div>
      )}
      <p className="hint">If this page loaded through Nginx, the frontend and the reverse proxy are working too.</p>
    </section>
  );
}

export default function App() {
  const [tab, setTab] = useState("Dashboard");
  const Page = { Dashboard, Predict, History, Model, Alerts, Health }[tab];
  return (
    <div className="app">
      <header><h1>FeatureGuard</h1><span>Red wine quality prediction with feature validation and drift monitoring</span></header>
      <nav>{TABS.map((t) => <button key={t} className={t === tab ? "active" : ""} onClick={() => setTab(t)}>{t}</button>)}</nav>
      <main><Page /></main>
    </div>
  );
}
