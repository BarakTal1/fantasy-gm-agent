# Yahoo Fantasy API access: application notes

Source: Yahoo's developer pages (`/developer/`, `/developer/docs/`, `/developer/access/`), read 2026-10-04.

## What Yahoo says about review

- Manual review with no stated timeline; volume affects speed.
- Access is **read-only** by default. Write access is not offered.
- Required form fields: product description, Yahoo Fantasy data needed, intended user base, estimated user count (Small <1,000 / Medium 1,000-100,000 / Large 100,000+), existing Client ID, notes.
- Reviewers check: what the product is, which specific data it needs, and whether access is limited to **personal or single-league use**.
- "Incomplete or insufficiently detailed submissions ... will be closed without further correspondence." Silence can mean a closed application, not a pending one.
- Developers may hold one account only. Usage Yahoo considers "excessive" is throttled.
- Apps must show "Fantasy data provided by Yahoo Fantasy" with links, plus the official logo unaltered.

## Likely reasons this one is still unconfirmed

1. The application was probably vague about user base and scope. A public portfolio app with sign-up looks like a Medium/Large product, which is harder to approve than a personal tool. Your friend's local app reads as personal use.
2. The UI previously said you could "connect your Yahoo league" after signing up, which implies multi-user access.
3. The app had no Yahoo attribution.
4. If the first submission was thin, it may have been closed silently. Check your email, including spam, and developer.yahoo.com/apps for the app's status.

## Changes made in the repo

- Added the "Fantasy data provided by Yahoo Fantasy" attribution (in-app footer and landing footer).
- Removed the "connect your Yahoo league soon" sign-up copy.

Logo: added unmodified at `frontend/public/yahoo-fantasy-logo.png` (white background chip in dark mode, never inverted or recolored).

## Suggested resubmission (personal, single-league, small)

- **Product:** A personal, read-only AI assistant for my own Yahoo NBA fantasy league. It reads my roster, free agents, league settings and pending trades, and recommends waiver pickups and trade evaluations. It never writes to Yahoo.
- **Data needed:** league settings, my team roster, free agents, league transactions/pending trades, and standings/matchups for league key `<YAHOO_LEAGUE_KEY>`. GET only.
- **User base:** Only me (one Yahoo account, one league). The public demo runs on static demo data, not Yahoo data.
- **Estimated users:** Small (<1,000); actually 1.
- **Notes:** Read-only access only. Data is cached in Postgres and refreshed on a schedule to keep request volume low. Yahoo attribution is shown in the app. Redirect URI is `oob`.

Do not create a second developer account or submit a duplicate if the first is still open; reply to the existing thread or edit that app instead.
