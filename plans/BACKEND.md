# BACKEND.md — TrendRadar

> The backend (Python worker) + how the frontend talks to it, deploy, auth, env, cost. Decided 2026-09-08.
> Complements API_CONTRACTS.md §B (pipeline job contracts). This doc = the operational shape around those jobs.

---

## 1. Roles

- **Frontend (Next.js, TypeScript)** — dashboard + onboarding. Reads the DB server-side via Drizzle for initial render. Subscribes to live updates via Supabase Realtime (client). Never scrapes, never calls the LLM for the pipeline, never holds a spending key that reaches the browser.
- **Backend (Python worker)** — the engine. Holds all secrets. Runs the whole pipeline (ingest → intent → score → hook → cluster → adapt), does every external call and every DB write for pipeline data.

The DB is the only contract between them.

---

## 2. Backend = Python + thin FastAPI

Language: **Python** (I/O-bound workload; you know Python). FastAPI is a **thin trigger layer**, not where the work lives.

```
worker/
  api.py            FastAPI: POST /projects/{id}/refresh, GET /health   (triggers only)
  run.py            CLI entrypoint for a full refresh (used by api + manual/cron)
  pipeline/         ingest · filter · intent · score · hook · cluster · adapt
  sources/          DataSource impls: scrapecreators.py, apify.py
  llm/              OpenAI calls (intent, hook_vision, hook_extract, cluster, adapt)
  scoring/          per-platform ScoringStrategy (tiktok, reels)
  db.py             Postgres access (same schema as packages/db)
  config.py         env + credit caps + weights
  .env.local        secrets (see §7)
```

- **FastAPI** receives a refresh trigger, starts the run in a **background task**, returns immediately (`202 {run_id}`). The browser doesn't wait.
- **The pipeline** is plain Python modules — callable by `api.py` and by `run.py`.
- **At scale (later):** put a job queue (Redis + RQ, or a DB-backed queue) behind the API so runs don't block a web worker. Not needed for MVP.

Concurrency: within a run, external calls go through **rate-limited async pools** (respect ScrapeCreators/OpenAI limits) with **retry-once + backoff**. Analysis/vision run on **outliers only**.

---

## 3. Refresh model — manual button (no cron for now)

Render's hobby/free tier has no reliable cron, so **refresh is a manual button** per project.

- Button → frontend calls `POST /projects/{id}/refresh` → backend sets project `status = running`, runs the pipeline, writes concepts, sets `status = ready` (or `failed`).
- The UI shows **"last refreshed N hours ago"** (from `projects.last_refreshed_at`) so you know when to click.
- Cron/daily auto-refresh is a later add (Render paid tier or Supabase pg_cron).

New `projects` columns for this: `status` (`idle|running|ready|failed`), `last_refreshed_at`, `last_run_credits`.

---

## 4. Live updates — Supabase Realtime (#2)

No polling. The frontend subscribes to changes and updates the lanes live.

- **Initial render:** server-side Drizzle (current concepts).
- **Live:** `supabase-js` client subscribes to `concepts` + `projects` (status) for the open project → new concept rows and `status` flips push to the browser instantly.
- Requires **Realtime enabled** on those two tables and **RLS** on (Realtime respects RLS).

---

## 5. Auth + RLS

- **Auth:** Supabase Auth, **email + password** (single operator for now). Middleware gates all app routes.
- **RLS:** enabled on all tables. MVP policy: an **authenticated** user can read/write; anonymous denied. This makes the public anon key safe (it can do nothing without a logged-in session).
- Only two public values ship to the browser: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`. Everything with spending power / full DB access stays server-side.

---

## 6. Video handling on Render (ephemeral)

The `hook` step downloads a ~3s clip to extract frames.

- Write to the server's **`/tmp`** (ephemeral), extract frames, **delete immediately** — per video, never persisted (matches the legal posture; Render wipes disk on restart anyway).
- Concurrency is capped so temp files don't accumulate.
- Download is SSRF-guarded (scheme check, reject private/reserved IPs, no redirects, timeout, size cap).

---

## 7. Env — 2 files, all secrets server-side

Files are named `.env.local` (host policy blocks the exact name `.env` for our tooling; `.env.local` is loaded identically).

**`apps/web/.env.local`** (frontend)
```
DATABASE_URL=                       # server-side (Drizzle reads)
OPENAI_API_KEY=                     # server-side (onboarding)
ONBOARDING_MODEL=gpt-5-mini
NEXT_PUBLIC_SUPABASE_URL=           # public (Realtime client)
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=   # public (safe with RLS)
```

**`worker/.env.local`** (backend)
```
DATABASE_URL=
OPENAI_API_KEY=
ONBOARDING_MODEL=gpt-5-mini
SCRAPECREATORS_API_KEY=
APIFY_API_KEY=
```

`DATABASE_URL` + `OPENAI_API_KEY` appear in both because both the app and worker need them. drizzle migrations read `worker/.env.local`.

---

## 8. Cost & credit ceilings

**1 credit = 1 ScrapeCreators request.** Each of these costs 1:
- `search` (per page)
- `fetch_video_detail` (IG views/followers)
- `fetch_author_videos` (account baseline)
- `fetch_transcript`

**Per full project refresh** ≈ search pages + baseline lookups (per candidate) + transcripts (per outlier). Single-niche estimate: ~5 + ~20 + ~10 = **~35 credits**.

**OpenAI** is separate (token-based $, not credits) — cheap because LLM/vision run on outliers only. Tracked in `llm_log`.

**Ceilings (enforced via `credit_log`):**
- **Per-run cap** — default **40 credits/run**. Before each ScrapeCreators call, the worker sums the run's spend; if the next call would exceed the cap, it stops the run cleanly and marks it `capped`.
- **Monthly cap** — a global backstop across all projects.
- Both live in `config.py`; tune after the first real run.

The manual-refresh model already bounds spend: one click = one capped run.

---

## 9. Deploy

- **Frontend:** Vercel.
- **Backend (FastAPI + pipeline):** Render (web service; free tier sleeps ~15 min idle → first refresh has a cold start, then runs).
- **DB + Auth + Realtime:** Supabase.
- Variable cost = ScrapeCreators credits + OpenAI tokens. Fixed cost ≈ small (Render/Supabase tiers).

---

## 10. Frontend ↔ backend flow (end to end)

```
Onboard: paste URL → Next server action reads site + OpenAI → proposes profile + seeds → Create project (Drizzle insert)
Refresh: click → POST /projects/{id}/refresh → backend runs pipeline (capped) → writes concepts, sets status
Live:    supabase-js subscription → lanes fill in + "ready" as the worker writes
Read:    concept card → detail (adapted hook, shoot-ready script, winning-video links)
```

---

## 11. Open / later

- Cron auto-refresh (paid tier) — replaces the manual button when volume justifies it.
- Job queue (Redis/RQ) — when concurrent runs need to not block the API.
- Multi-workspace + per-client RLS — when it stops being single-operator.

---

**End of BACKEND.md** — review, then build.
