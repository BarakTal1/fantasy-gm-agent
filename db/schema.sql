CREATE TABLE IF NOT EXISTS league_config (
    league_key TEXT PRIMARY KEY,
    format     TEXT NOT NULL,               -- 'category' | 'points'
    categories JSONB NOT NULL DEFAULT '[]',  -- e.g. ["PTS","REB","AST",...]
    roster_slots JSONB NOT NULL DEFAULT '{}',
    cached_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS player_stat_snapshots (
    player_id  TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    stats      JSONB NOT NULL,               -- per-game or per-day stat map
    PRIMARY KEY (player_id, snapshot_date)
);

CREATE TABLE IF NOT EXISTS weekly_schedule (
    nba_team   TEXT NOT NULL,
    week       INTEGER NOT NULL,
    games_total INTEGER NOT NULL,
    games_remaining INTEGER NOT NULL,
    as_of_date DATE NOT NULL,
    PRIMARY KEY (nba_team, week)
);

CREATE TABLE IF NOT EXISTS oauth_tokens (
    id            INTEGER PRIMARY KEY DEFAULT 1,   -- single-user: one row
    access_token  TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at    TIMESTAMPTZ NOT NULL,
    CONSTRAINT single_row CHECK (id = 1)
);
