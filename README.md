# TrendRadar

UGC trend-intelligence: find short-form videos that genuinely outperform, decode *why*, and
turn recurring winning patterns into shoot-ready content briefs for a client. See `plans/` for the
full design (PLAN, SPEC, DATABASE_SCHEMA, API_CONTRACTS, ROADMAP) and `plans/PHASE0_FINDINGS.md`
for the validated approach (canonical).

## Monorepo layout

```
packages/db     Drizzle schema + migrations (@trendradar/db)  ← built, verified
worker/         Python pipeline (ingest → intent → score → hook → cluster → adapt)
                worker/scratch/ = Phase 0 spike (throwaway, working)
apps/web        Next.js dashboard (concept cards + scripts)   ← next
```

## Setup

Requires Node ≥20 + pnpm. Install: `pnpm install`.

### Database (Supabase Postgres)
1. Create a Supabase project, copy its connection string.
2. Put it in `packages/db/.env` as `DATABASE_URL=postgresql://...` (session pooler).
3. Generate/apply schema:
   ```bash
   pnpm db:generate   # emit SQL migration from packages/db/src/schema.ts
   pnpm db:migrate    # apply to the database
   ```

The schema is the single source of truth (`packages/db/src/schema.ts`); the Python worker reads/writes
the same tables but never declares them.

## Status

- Phase 0 — DONE (validated pipeline, see PHASE0_FINDINGS.md).
- Phase 1 — in progress: `packages/db` schema done (15 tables, migration verified); worker + web next.
