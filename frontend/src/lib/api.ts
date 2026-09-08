import { API_BASE } from "./config";

export interface Player {
  player_id: string;
  name: string;
  nba_team: string;
  positions?: string[];
  stats: Record<string, number>;
}

export interface Team {
  team_key: string;
  name: string;
  players: Player[];
}

export async function getLeagueInfo() {
  const r = await fetch(`${API_BASE}/league/info`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json() as Promise<{ name: string; format: string; format_label: string }>;
}

export async function getDashboard() {
  const r = await fetch(`${API_BASE}/analytics/dashboard`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function getTeams() {
  const r = await fetch(`${API_BASE}/league/teams`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json() as Promise<{ my_team_key: string; teams: Team[] }>;
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
