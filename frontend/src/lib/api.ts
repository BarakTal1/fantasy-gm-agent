import { API_BASE } from "./config";

export interface Player {
  player_id: string;
  name: string;
  nba_team: string;
  positions?: string[];
  stats: Record<string, number>;
  image_url?: string | null;
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

// --- Weekday coverage --- (served inside /analytics/waivers)
export interface WeekdayCoverage { day: string; count: number; weak: boolean; heavy: boolean }

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

// --- Full league-settings editor ---
export interface LeagueConfig {
  name: string;
  format: "category" | "points";
  categories: string[];
  point_weights: Record<string, number>;
  roster_slots: Record<string, number>;
  source: "manual" | "demo";
  yahoo_connected: boolean;
  options: { categories: string[]; point_stats: string[]; positions: string[] };
}
export interface LeagueConfigInput {
  name: string;
  format: "category" | "points";
  categories: string[];
  point_weights: Record<string, number>;
  roster_slots: Record<string, number>;
}

async function jsend(path: string, method: string, body: object) {
  const r = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    ...CREDS,
  });
  if (!r.ok) {
    let detail = `HTTP ${r.status}`;
    try { detail = (await r.json()).detail ?? detail; } catch { /* ignore */ }
    throw new Error(detail);
  }
  return r.json();
}

export async function getLeagueConfig() {
  return jget("/settings/league") as Promise<LeagueConfig>;
}
export async function saveLeagueConfig(cfg: LeagueConfigInput) {
  return jsend("/settings/league", "PUT", cfg) as Promise<LeagueConfig>;
}
export async function syncLeagueFromYahoo() {
  return jsend("/settings/league/sync-yahoo", "POST", {}) as Promise<LeagueConfig>;
}

// --- Analytics (subject-scoped) ---
export interface CategoryProfile { [cat: string]: { you: number; league_avg: number } }
export interface BuySellRow {
  player_id: string; name: string; nba_team: string;
  signal: "buy_low" | "sell_high"; strength: number;
  efficiency_delta: number | null; volume_delta: number; confidence: number;
  drivers: string[];
}
export interface RecommendedPickup {
  player_id: string; name: string; nba_team: string; games: number; score: number;
  drop: { player_id: string; name: string; value: number } | null;
}

export interface RosterOutlookRow {
  player_id: string; name: string; nba_team: string; image_url?: string | null;
  positions: string[];
  games: number; form: "buy_low" | "sell_high" | "neutral";
  projected?: Record<string, number>; projected_points?: number;
}
export interface BestPlayer {
  player_id: string; name: string; nba_team: string; positions: string[];
  image_url?: string | null; value: number;
}
export interface PositionStrength {
  position: string; count: number; total_value: number; avg_value: number;
}
export interface PositionBalance {
  position: string; eligible: number; required: number | null; thin: boolean;
}
export async function getMyTeamAnalytics() {
  return jget("/analytics/my-team") as Promise<{
    format: "category" | "points";
    roster: RosterOutlookRow[];
    best_player: BestPlayer | null;
    position_strengths: PositionStrength[];
    positional_balance: PositionBalance[];
    category_profile?: CategoryProfile;
  }>;
}
export interface TeamTarget {
  nba_team: string; weak_days: string[];
  free_agents: { player_id: string; name: string; nba_team: string; image_url?: string | null }[];
}
export async function getWaiversAnalytics() {
  return jget("/analytics/waivers") as Promise<{
    format: "category" | "points";
    schedule: Record<string, number>;
    recommended_pickups: RecommendedPickup[];
    streaming_board?: { player_id: string; name: string; nba_team: string;
                        games: number; projected: Record<string, number>; score: number }[];
    points_value_board?: { player_id: string; name: string; nba_team: string;
                           games: number; projected_points: number }[];
    weekdays: WeekdayCoverage[];
    teams_to_target: TeamTarget[];
  }>;
}
export interface TeamStatRow {
  team_key: string; name: string; players: number; games_week: number;
  stats: Record<string, number>;
}
export async function getLeagueAnalytics() {
  return jget("/analytics/league") as Promise<{
    format: "category" | "points";
    teams: Team[]; my_team_key: string;
    team_stats: TeamStatRow[];
    category_profile?: CategoryProfile;
    buy_low_sell_high: BuySellRow[];
  }>;
}

// --- Trades: received + suggestions ---
export interface ReceivedOffer {
  from_team: string; date: string; note: string;
  they_give: Player[]; they_want: Player[];
}
export async function getReceivedTrades() {
  return jget("/trades/received") as Promise<{ offers: ReceivedOffer[] }>;
}
export interface TradeSuggestion {
  with_team: string; give: Player[]; get: Player[];
  targeted_categories: string[]; fairness_gap: number; need_fit: number;
}
export async function getTradeSuggestions() {
  return jget("/trades/suggestions") as Promise<{
    format: "category" | "points"; suggestions: TradeSuggestion[];
  }>;
}
