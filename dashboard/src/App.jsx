import { useEffect, useMemo, useState } from "react";
import { apiGet, login, runFailover } from "./api";

const REFRESH_MS = 5000;

export default function App() {
  const [token, setToken] = useState(localStorage.getItem("dr_token") || "");
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin12345");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const [status, setStatus] = useState(null);
  const [failovers, setFailovers] = useState([]);
  const [metrics, setMetrics] = useState(null);
  const [services, setServices] = useState([]);

  useEffect(() => {
    if (!token) {
      return;
    }

    let canceled = false;

    async function load() {
      try {
        const [statusData, failoverData, metricData, serviceData] = await Promise.all([
          apiGet("/api/v1/observability/system-status", token),
          apiGet("/api/v1/observability/failovers", token),
          apiGet("/api/v1/observability/metrics/recovery", token),
          apiGet("/api/v1/services", token),
        ]);

        if (!canceled) {
          setStatus(statusData);
          setFailovers(failoverData);
          setMetrics(metricData);
          setServices(serviceData);
          setError("");
        }
      } catch (err) {
        if (!canceled) {
          setError(err.message);
        }
      }
    }

    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => {
      canceled = true;
      clearInterval(timer);
    };
  }, [token]);

  async function onLogin(e) {
    e.preventDefault();
    setLoading(true);
    try {
      const data = await login(username, password);
      setToken(data.access_token);
      localStorage.setItem("dr_token", data.access_token);
      setError("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    setToken("");
    localStorage.removeItem("dr_token");
    setStatus(null);
    setFailovers([]);
    setMetrics(null);
    setServices([]);
  }

  async function manualFailover() {
    if (!token) {
      return;
    }
    try {
      await runFailover(token);
    } catch (err) {
      setError(err.message);
    }
  }

  const serviceGroups = useMemo(() => {
    return services.reduce((acc, service) => {
      if (!acc[service.region]) {
        acc[service.region] = [];
      }
      acc[service.region].push(service);
      return acc;
    }, {});
  }, [services]);

  if (!token) {
    return (
      <main className="layout center">
        <section className="panel auth">
          <h1>Cloud DR Dashboard</h1>
          <p className="muted">Authenticate to monitor failover, backups, and recovery posture.</p>
          <form onSubmit={onLogin} className="form">
            <label>
              Username
              <input value={username} onChange={(e) => setUsername(e.target.value)} />
            </label>
            <label>
              Password
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
            <button disabled={loading}>{loading ? "Signing in..." : "Sign in"}</button>
          </form>
          {error && <p className="error">{error}</p>}
        </section>
      </main>
    );
  }

  return (
    <main className="layout">
      <header className="topbar">
        <h1>Cloud DR Dashboard</h1>
        <div className="topbar-actions">
          <button onClick={manualFailover}>Manual Failover</button>
          <button className="ghost" onClick={logout}>
            Logout
          </button>
        </div>
      </header>

      {error && <p className="error">{error}</p>}

      <section className="grid two">
        <article className="panel">
          <h2>Region State</h2>
          <div className="region-row">
            <div className="region-card active">
              <h3>Active</h3>
              <p>{status?.active_region || "-"}</p>
            </div>
            <div className="region-card standby">
              <h3>Standby</h3>
              <p>{status?.standby_region || "-"}</p>
            </div>
          </div>
        </article>

        <article className="panel">
          <h2>Recovery Metrics</h2>
          <ul className="stat-list">
            <li>
              <span>Completed Workflows</span>
              <strong>{metrics?.completed_workflows ?? "-"}</strong>
            </li>
            <li>
              <span>Average RTO (seconds)</span>
              <strong>{metrics?.avg_rto_seconds?.toFixed?.(2) ?? "-"}</strong>
            </li>
            <li>
              <span>Average RPO (seconds)</span>
              <strong>{metrics?.avg_rpo_seconds?.toFixed?.(2) ?? "-"}</strong>
            </li>
          </ul>
        </article>
      </section>

      <section className="grid two">
        <article className="panel">
          <h2>Services by Region</h2>
          <div className="service-grid">
            {Object.entries(serviceGroups).map(([region, items]) => (
              <div key={region} className="service-column">
                <h3>{region}</h3>
                {items.map((service) => (
                  <div key={service.id} className={`service-chip ${service.status.toLowerCase()}`}>
                    <span>{service.name}</span>
                    <strong>{service.status}</strong>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <h2>Failover Timeline</h2>
          <div className="timeline">
            {failovers.length === 0 && <p className="muted">No failover events yet.</p>}
            {failovers.slice(0, 8).map((event) => (
              <div key={event.id} className="timeline-item">
                <p>
                  <strong>{event.from_region}</strong> to <strong>{event.to_region}</strong>
                </p>
                <p className="muted">{event.reason}</p>
                <time>{new Date(event.created_at).toLocaleString()}</time>
              </div>
            ))}
          </div>
        </article>
      </section>
    </main>
  );
}
