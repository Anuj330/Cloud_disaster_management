const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function login(username, password) {
  const body = new URLSearchParams();
  body.set("username", username);
  body.set("password", password);

  const res = await fetch(`${API_BASE}/api/v1/auth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) {
    throw new Error("Authentication failed");
  }
  return res.json();
}

export async function apiGet(path, token) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error(`Request failed: ${path}`);
  }
  return res.json();
}

export async function runFailover(token) {
  const res = await fetch(`${API_BASE}/api/v1/dr/failover?reason=Manual%20dashboard%20failover`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error("Failover request failed");
  }
  return res.json();
}
