-- =============================================================================
-- TrendRadar — roll back enforced RLS (undo enable_rls.sql)
-- =============================================================================
-- Point the web app's DATABASE_URL back to the postgres/service role BEFORE
-- running this, or the web app will lose access mid-rollback.
-- Idempotent; wrap in a single transaction.
-- =============================================================================

drop policy if exists p_authors on public.authors;
drop policy if exists p_trending_sounds on public.trending_sounds;
drop policy if exists p_projects on public.projects;

do $$
declare t text;
  owned text[] := array[
    'queries','videos','concepts','trends','peer_cache','credit_log','alerts','watchlist','llm_log',
    'scores','concept_members','trend_members','video_snapshots','analyses','video_embeddings'];
begin
  foreach t in array owned loop
    execute format('drop policy if exists p_%1$s on public.%1$I', t);
  end loop;
end $$;

-- Leave RLS enabled (Supabase default) but stop forcing it; revoke web grants.
do $$
declare t text;
  all_t text[] := array[
    'projects','queries','videos','concepts','trends','peer_cache','credit_log','alerts','watchlist','llm_log',
    'scores','concept_members','trend_members','video_snapshots','analyses','video_embeddings','authors','trending_sounds'];
begin
  foreach t in array all_t loop
    execute format('alter table public.%I no force row level security', t);
    execute format('revoke all on public.%I from trendradar_web', t);
  end loop;
end $$;

revoke usage on schema public from trendradar_web;
drop function if exists public.current_owner();
-- drop role trendradar_web;  -- uncomment once nothing connects as it
