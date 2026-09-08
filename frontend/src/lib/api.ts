import { API_BASE } from "./config";

export async function getDashboard() {
  const r = await fetch(`${API_BASE}/analytics/dashboard`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function analyzeTrade(give: string[], get: string[]) {
  const r = await fetch(`${API_BASE}/trade/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ give, get }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}
