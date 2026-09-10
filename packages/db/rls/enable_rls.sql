-- =============================================================================
-- TrendRadar — enforce Row-Level Security (PREPARED, NOT YET APPLIED)
-- =============================================================================
-- Status: ready to apply when you go multi-tenant. See rls/README.md for the
-- full plan, the required app wiring, and apply/rollback steps.
--
-- Model: the WEB app connects as a restricted role `trendradar_web` (NOBYPASSRLS)
-- and sets `app.owner_id` per request (SET LOCAL). Policies scope every row to
-- that owner. The WORKER keeps its `postgres`/service role (it legitimately spans
-- all users) and bypasses RLS — do NOT point the worker at `trendradar_web`.
--
-- Idempotent: safe to re-run. Wrap in a single transaction when applying.
-- =============================================================================

-- 0. Restricted application role for the web path (password set out-of-band).
do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'trendradar_web') then
    create role trendradar_web login nosuperuser nobypassrls noinherit
      password 'CHANGE_ME';  -- set a real password, then use it in the web DATABASE_URL
  end if;
end $$;

grant usage on schema public to trendradar_web;

-- 1. Owner accessor — reads the per-request GUC set by the app (SET LOCAL app.owner_id).
--    `true` = missing_ok, so a connection that never set it yields NULL → sees no rows.
create or replace function public.current_owner() returns uuid
  language sql stable as $$ select nullif(current_setting('app.owner_id', true), '')::uuid $$;

-- 2. Drop the stray, incomplete legacy policies (they were inert under the bypass role).
drop policy if exists projects_owner_all  on public.projects;
drop policy if exists concepts_owner_read on public.concepts;

-- 3. Force RLS on every user-scoped table (FORCE = applies even to the table owner)
--    and grant the web role the privileges it needs (rows still filtered by policy).
do $$
declare t text;
  owned text[] := array[
    'projects','queries','videos','concepts','trends','peer_cache','credit_log','alerts','watchlist','llm_log',
    'scores','concept_members','trend_members','video_snapshots','analyses','video_embeddings'];
  global_read text[] := array['authors','trending_sounds'];
begin
  foreach t in array owned loop
    execute format('alter table public.%I enable row level security', t);
    execute format('alter table public.%I force  row level security', t);
    execute format('grant select, insert, update, delete on public.%I to trendradar_web', t);
  end loop;
  foreach t in array global_read loop
    execute format('alter table public.%I enable row level security', t);
    execute format('alter table public.%I force  row level security', t);
    execute format('grant select on public.%I to trendradar_web', t);
  end loop;
end $$;

-- 4. Policies. Owner reached three ways: direct owner_id, via project_id, via video→project.

-- 4a. projects — the root of ownership.
create policy p_projects on public.projects for all
  using (owner_id = public.current_owner())
  with check (owner_id = public.current_owner());

-- 4b. tables with a direct project_id.
do $$
declare t text;
  via_project text[] := array['queries','videos','concepts','trends','peer_cache','credit_log','alerts','watchlist','llm_log'];
begin
  foreach t in array via_project loop
    execute format($f$
      create policy p_%1$s on public.%1$I for all
        using (project_id in (select id from public.projects where owner_id = public.current_owner()))
        with check (project_id in (select id from public.projects where owner_id = public.current_owner()))
    $f$, t);
  end loop;
end $$;

-- 4c. tables scoped via video_id → videos.project_id → projects.owner_id.
do $$
declare t text;
  via_video text[] := array['scores','concept_members','trend_members','video_snapshots','analyses','video_embeddings'];
begin
  foreach t in array via_video loop
    execute format($f$
      create policy p_%1$s on public.%1$I for all
        using (video_id in (
          select v.id from public.videos v join public.projects p on p.id = v.project_id
          where p.owner_id = public.current_owner()))
        with check (video_id in (
          select v.id from public.videos v join public.projects p on p.id = v.project_id
          where p.owner_id = public.current_owner()))
    $f$, t);
  end loop;
end $$;

-- 4d. global tables — public reference data, readable by any authenticated owner.
create policy p_authors on public.authors for select using (true);
create policy p_trending_sounds on public.trending_sounds for select using (true);

-- Done. The worker (postgres/service role, rolbypassrls) is unaffected and keeps full access.
