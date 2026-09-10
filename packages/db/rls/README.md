# Row-Level Security (prepared — not yet enforced)

Today TrendRadar isolates users at the **app layer** (`ownerId` filters in every query).
That's fine while you're the sole owner. Before onboarding untrusted multi-tenant users,
enforce isolation in Postgres too, so a missed `.where(ownerId …)` can't leak data.

## Why it isn't just "enable RLS"
RLS is already *enabled* on all tables (Supabase default), but **inert**: the web app and
worker both connect as `postgres`, which has `rolbypassrls = true`. And the user's Supabase
JWT never reaches Drizzle (data goes over a raw `DATABASE_URL`, not the Supabase client), so
`auth.uid()` is unavailable. Enforcement therefore needs three things, all provided here:

1. A **restricted web role** (`trendradar_web`, `NOBYPASSRLS`) — [`enable_rls.sql`](enable_rls.sql).
2. The app **passing the owner id per request** via a GUC (`SET LOCAL app.owner_id`).
3. **Owner-scoping policies** on every table (direct `owner_id`, via `project_id`, or via `video→project`) — [`enable_rls.sql`](enable_rls.sql).

The **worker keeps the `postgres`/service role** — it legitimately spans all users (it runs
per-project jobs). Do **not** point the worker at `trendradar_web`.

## Enforce it (when going multi-tenant)
1. **Apply the SQL** in one transaction (review it first):
   ```bash
   psql "$ADMIN_DATABASE_URL" -1 -f packages/db/rls/enable_rls.sql
   ```
   Then set a real password on the role:
   ```sql
   alter role trendradar_web password '<strong-secret>';
   ```
2. **Wire the app** — set the owner GUC at the start of every request's transaction. Add a
   helper in `packages/db` and route web reads/writes through it:
   ```ts
   // packages/db/src/index.ts
   import { sql } from "drizzle-orm";
   export async function withOwner<T>(ownerId: string, fn: (tx: Db) => Promise<T>): Promise<T> {
     return getDb().transaction(async (tx) => {
       await tx.execute(sql`select set_config('app.owner_id', ${ownerId}, true)`); // true = LOCAL to tx
       return fn(tx as unknown as Db);
     });
   }
   ```
   In the web app, replace direct `db()` calls in user-facing paths with
   `withOwner(uid, (tx) => tx.select()…)`. Keep the existing `ownerId` filters — defence in depth.
3. **Point the web `DATABASE_URL` at `trendradar_web`** (not `postgres`). Leave the worker's
   `DATABASE_URL` on the service role.
4. **Enforce transaction pooling caveat:** `SET LOCAL` only holds inside a transaction, so every
   RLS-scoped query must run through `withOwner`. If you use Supabase's transaction pooler
   (port 6543), that's fine; just never run a scoped query outside the wrapper.

## Test before trusting it
```sql
-- as trendradar_web, with no owner set → sees nothing
set role trendradar_web;
select set_config('app.owner_id', '', true);
select count(*) from projects;                     -- expect 0
-- with a real owner → sees only their rows
select set_config('app.owner_id', '<some-owner-uuid>', true);
select count(*) from projects;                     -- expect only that owner's
reset role;
```
Verify a second owner's uuid sees a disjoint set, and that the worker (postgres) still sees all.

## Roll back
Point the web `DATABASE_URL` back to `postgres` first, then:
```bash
psql "$ADMIN_DATABASE_URL" -1 -f packages/db/rls/disable_rls.sql
```

## Grants note
`enable_rls.sql` grants the web role CRUD on owned tables + SELECT on the global tables
(`authors`, `trending_sounds`). If the web app's write surface grows, widen grants accordingly;
worker-written tables the web only reads can be tightened to SELECT-only later.
