# Deploying TrendRadar

Two hosts: **web** (Next.js → Vercel) and **worker** (FastAPI + cron → Render via `render.yaml`).
Both talk to the **same Supabase Postgres**. Do the steps in order.

## 1. Worker + cron → Render (Blueprint)
1. In the Render dashboard → **New → Blueprint**, connect this repo. Render reads [`render.yaml`](render.yaml) and creates two things:
   - `trendradar-worker` (web service — the refresh API)
   - `trendradar-trending-sounds` (daily cron — Trending Songs)
2. Set the `sync: false` env vars (they're intentionally not in the repo):
   - `DATABASE_URL` — Supabase **session pooler** connection string
   - `SCRAPECREATORS_API_KEY`, `OPENAI_API_KEY`
   - `WORKER_SECRET` — **generate a strong random value; you'll paste the SAME value into Vercel** (step 2)
3. After deploy, note the worker URL (e.g. `https://trendradar-worker.onrender.com`) and check `GET /health` returns `{"status":"ok"}`.

## 2. Web → Vercel
1. **New Project** → import this repo → set **Root Directory = `apps/web`**.
2. Environment Variables (see [`apps/web/.env.example`](apps/web/.env.example)):
   - `DATABASE_URL` (same Supabase DB)
   - `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
   - `OPENAI_API_KEY`
   - `WORKER_URL` = the Render worker URL from step 1
   - `WORKER_SECRET` = **the same value you set on Render**
3. Deploy.

## 3. Supabase auth (do this or login breaks on the live domain)
In the Supabase dashboard → **Authentication → URL Configuration**, add the Vercel domain to **Site URL** and **Redirect URLs** (e.g. `https://your-app.vercel.app/**`).

## 4. Verify
- Log in on the Vercel domain.
- Open a project → **Refresh** → the worker should accept it (202) and `project.status` flips to `ready` when done.
- `/sounds` shows the Trending Songs chart (cron populates it daily; run `refresh_trending_sounds.py` once manually to seed immediately).

---

### Notes / known gaps
- **Auth on the worker:** the refresh endpoint requires the `X-Worker-Secret` header when `WORKER_SECRET` is set (prod). Unset = open (local dev only).
- **DB migrations:** the journal is now **reconciled** with the live DB — all three migrations (`0000`–`0002`) are recorded in `drizzle.__drizzle_migrations`, so `drizzle-kit migrate` is a clean no-op (the historical unguarded `0002` is marked applied and won't replay). Going forward, use the normal flow: edit `packages/db/src/schema.ts` → `pnpm --filter @trendradar/db generate` → review the SQL → `migrate`. If you ever hand-apply a change, immediately record it in `drizzle.__drizzle_migrations` (hash = `sha256` of the migration file) so the journal stays in sync. Schema source of truth: `packages/db/src/schema.ts`.
- **RLS:** row-level security is **not** enforced in Postgres yet — user isolation is app-level (`ownerId` filters), which is fine for a single-owner/internal tool. A **complete, reviewed migration is prepared** in [`packages/db/rls/`](packages/db/rls/README.md) (restricted web role + owner-scoping policies + the app-wiring guide, validated against the live schema). Apply it before opening to untrusted multi-tenant users. The old inert/incomplete policies have been removed so the DB state isn't misleading.
