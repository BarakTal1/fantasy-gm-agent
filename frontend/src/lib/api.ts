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

// Every request sends the session cookie so signed-in users get their own
// settings (and the API can stay demo-browsable when there's no cookie).
const CREDS: RequestInit = { credentials: "include" };

async function jget(path: string) {
  const r = await fetch(`${API_BASE}${path}`, CREDS);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function getLeagueInfo() {
  return jget("/league/info") as Promise<{ name: string; format: string; format_label: string }>;
}

export async function getDashboard() {
  return jget("/analytics/dashboard");
}

export async function getTeams() {
  return jget("/league/teams") as Promise<{ my_team_key: string; teams: Team[] }>;
}

export async function analyzeTrade(give: string[], get: string[]) {
  const r = await fetch(`${API_BASE}/trade/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ give, get }),
    ...CREDS,
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// --- Weekday coverage ---
export interface WeekdayCoverage { day: string; count: number; weak: boolean }
export async function getWeekdays() {
  return jget("/analytics/weekdays") as Promise<{ days: WeekdayCoverage[] }>;
}

// --- Trade history ---
export interface TradedPlayer {
  player_id: string; name: string; nba_team: string;
  before: Record<string, number>; after: Record<string, number>;
}
export interface HistoricTrade {
  date: string; with_team: string; gave: TradedPlayer[]; got: TradedPlayer[];
}
export async function getTradeHistory() {
  return jget("/trades/history") as Promise<{ trades: HistoricTrade[] }>;
}

// --- Auth ---
export interface AuthUser { email: string; league_format: string }

async function authPost(path: string, body?: object) {
  const r = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
    ...CREDS,
  });
  if (!r.ok) {
    let detail = `HTTP ${r.status}`;
    try { detail = (await r.json()).detail ?? detail; } catch { /* ignore */ }
    throw new Error(detail);
  }
  return r.json();
}

export async function register(email: string, password: string) {
  return authPost("/auth/register", { email, password }) as Promise<AuthUser>;
}
export async function login(email: string, password: string) {
  return authPost("/auth/login", { email, password }) as Promise<AuthUser>;
}
export async function logout() {
  return authPost("/auth/logout");
}
export async function getMe() {
  const r = await fetch(`${API_BASE}/auth/me`, CREDS);
  if (r.status === 401) return null;
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json() as Promise<AuthUser>;
}
export async function updateSettings(league_format: string) {
  const r = await fetch(`${API_BASE}/settings`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ league_format }),
    ...CREDS,
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json() as Promise<{ league_format: string }>;
}
