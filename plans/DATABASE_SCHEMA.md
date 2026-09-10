# DATABASE_SCHEMA.md — TrendRadar

> Postgres (Supabase) via Drizzle. `packages/db` owns this; the Python worker reads/writes the same tables but never declares them.
> The load-bearing decision: **`videos` = identity (one row), `video_snapshots` = metrics over time (append-only, many rows)**. Velocity, momentum, and the entire trend engine come from snapshots.

---

## 1. Conventions

- All ids: `uuid` default `gen_random_uuid()`, except external platform ids which are stored as `text` (`videos.video_id`, `authors.handle`).
- Timestamps: `timestamptz`, stored UTC, displayed IST/local in the app.
- Counts: `bigint` (view counts exceed int range), nullable when the source doesn't provide them (never faked to 0).
- Money/credits: `numeric` where fractional; credits are `integer`.
- Every table: `created_at timestamptz not null default now()`; mutable tables add `updated_at`.
- **RLS-ready:** tables that will be user/workspace scoped carry `workspace_id uuid` from day one (single workspace now; RLS enabled when multi-workspace lands). Not enforced in MVP, present in schema.
- Soft delete only where user-facing (`niches`, `queries`, `watchlist`, `briefs`) via `deleted_at`; ingestion/derived tables hard-delete via retention jobs.

---

## 2. Enums

```sql
platform      : 'tiktok' | 'reels'
query_type    : 'hashtag' | 'keyword' | 'sound' | 'account'
content_type  : 'pitch' | 'education' | 'other'   -- from the intent filter; keep 'pitch'
lane          : 'rising' | 'proven'               -- rising-now vs proven-playbook
confidence    : 'high' | 'medium' | 'emerging'    -- concept evidence strength
lifecycle     : 'emerging' | 'growing' | 'mature' | 'declining'
score_flag    : 'ok' | 'approximated' | 'no_baseline' | 'noise'  -- 'noise' = below follower floor
trend_type    : 'sound' | 'format' | 'hook'
trend_status  : 'rising' | 'peak' | 'declining'
alert_type    : 'breakout' | 'trend_rising' | 'competitor' | 'saturation'
llm_task      : 'hook_extract' | 'style_vision' | 'structure' | 'ambiguous_retry'
analysis_status : 'pending' | 'done' | 'failed'
credit_call   : 'trending' | 'profile' | 'video' | 'search'
```

> **Live-schema note (code is source of truth — `packages/db/src/enums.ts`):** the shipped `credit_call` enum is `search | video_detail | author_videos | transcript`; Reels calls reuse these (`search` for reels-search, `author_videos` for the profile/baseline call, `video_detail` for post-detail). When audio expansion (§4.0 source #3) ships, add a **`song`** value for `fetch_song_videos`. `query_type` already includes **`account`** (competitor/niche seeds) and **`sound`** (audio-expansion seeds) — no new type needed. Keep enum edits additive; never rename an in-use value.

---

## 3. Tables

### 3.1 `niches` → shipped as `projects`
A tracked space we produce content for. **In code this table is `projects`** (one per onboarded business). Live columns beyond the below: `owner_id` (auth.users — owner-scoped reads/RLS), `product_url`, `product_description`, `audience`, `job_to_be_done`, `region` (**user-set, never inferred — §SPEC 2.4**), `status`, `last_refreshed_at`, `last_run_credits`.

| col | type | notes |
|---|---|---|
| id | uuid pk | |
| workspace_id | uuid | RLS-ready |
| owner_id | uuid | Supabase `auth.users.id`; all reads scoped to this |
| name | text not null | "IN ecom sellers", "US SaaS" |
| product | text | which of our products this feeds (ecombox/gymos/…) |
| platforms | platform[] not null | which platforms to ingest for this niche |
| created_at / updated_at / deleted_at | timestamptz | |

**Onboarding v2 (SPEC §2.4) capture** — AI pre-fills from the pasted URL, user edits:
- **seed keywords, competitor accounts, own accounts, audio seeds** → rows in `queries` (types `keyword` / `account` / `sound`; own accounts flagged `is_own`, §3.2).
- **competitor websites + own product URL** → project columns (`product_url`; add `competitor_urls text[]` when built) — used by the onboarding LLM for context, not by the worker's search.
- **top-performing content** (optional) → stored as `queries(type='account', is_own=true)` members or a light `own_winners` list; feeds adaptation + de-dup.

### 3.2 `queries`
Seed inputs that drive ingestion for a niche.

| col | type | notes |
|---|---|---|
| id | uuid pk | |
| niche_id | uuid fk → niches | |
| platform | platform not null | |
| type | query_type not null | hashtag / keyword / sound / account |
| value | text not null | `#amazonseller`, `amazon seller india`, an audio_id, a handle |
| is_own | boolean not null default false | for `type='account'`: the client's OWN account — mine for current style + **exclude from recommendations**, don't treat as a discovery win |
| active | boolean not null default true | pause without deleting |
| last_run_at | timestamptz | |
| created_at / deleted_at | timestamptz | |

Unique: `(niche_id, platform, type, value)`. Discovery (SPEC §4.0) reads these: `type='keyword'` → search, `type='account'` (competitor/niche, `is_own=false`) → account mining, `type='sound'` → audio expansion. Competitor accounts are **additive seeds, never a filter**.

### 3.2b `intent_cache`
The intent-filter verdict per **(project, external video_id)**. Intent is context-dependent (a video is a pitch for one business, off-goal for another) so it's keyed by project, not global. Cached so re-runs are stable — the classifier is non-deterministic, so we classify each video **once** and reuse the verdict.

| col | type | notes |
|---|---|---|
| id | uuid pk | |
| project_id | uuid fk → projects | |
| platform | platform not null | |
| video_id | text not null | external id (set *before* the video is persisted, so keyed by the external id, not our uuid) |
| is_pitch | boolean not null | |
| created_at | timestamptz | |

Unique: `(project_id, platform, video_id)`. (Hook analyses are cached similarly — `_rank_and_hook` reuses an existing `analyses` row instead of re-running vision, which also sidesteps expiring CDN URLs. Derived `scores` are cleared and rewritten each run, unlike append-only `video_snapshots`.)

### 3.3 `authors`
A creator account. One per `(platform, handle)`.

| col | type | notes |
|---|---|---|
| id | uuid pk | |
| platform | platform not null | |
| handle | text not null | |
| is_verified | boolean | |
| follower_count | bigint | from profile lookup; nullable |
| baseline_median_views | bigint | median of ~10 recent videos' views (author-videos endpoint). **THE account baseline — primary scoring input.** |
| last_profiled_at | timestamptz | when we last spent a profile credit |
| created_at / updated_at | timestamptz | |

Unique: `(platform, handle)`.

### 3.4 `videos`
Identity row — one per unique video. **Metrics are NOT here.**

| col | type | notes |
|---|---|---|
| id | uuid pk | |
| platform | platform not null | |
| video_id | text not null | external id |
| author_id | uuid fk → authors | |
| niche_id | uuid fk → niches | first niche it was discovered under |
| caption | text | |
| duration_s | integer | video length in seconds — scoring normalizer |
| content_type | content_type | from the intent filter (pitch/education/other); we keep 'pitch' |
| audio_id | text | music/sound id — trend signal |
| audio_title | text | |
| url | text not null | |
| taken_at | timestamptz | when posted |
| first_seen_at | timestamptz not null default now() | when we first ingested it |
| raw_payload | jsonb not null | untouched vendor JSON, for reprocessing |
| created_at | timestamptz | |

Unique: `(platform, video_id)` — the dedupe key.
Indexes: `(niche_id)`, `(author_id)`, `(audio_id)`, `(platform, taken_at)`.

### 3.5 `video_snapshots`  ← the time-series heart
Append-only. One row per video per ingestion/re-poll.

| col | type | notes |
|---|---|---|
| id | uuid pk | |
| video_id | uuid fk → videos | |
| captured_at | timestamptz not null default now() | |
| view_count | bigint | |
| like_count | bigint | |
| comment_count | bigint | |
| share_count | bigint | TikTok fills it; **Instagram always null** unless the DataSource is the Apify reel-scraper |
| save_count | bigint | TikTok fills it (collect_count); **Instagram always null** — ScrapeCreators never exposes IG saves |
| play_count | bigint | |

Index: `(video_id, captured_at desc)`. **Never updated in place.** Velocity = diff of two latest rows.

### 3.6 `scores`
Computed selection output (Layer 1). Latest score per video, plus history if re-scored.

| col | type | notes |
|---|---|---|
| id | uuid pk | |
| video_id | uuid fk → videos | |
| strategy | text not null | 'tiktok' \| 'reels' + weights version |
| account_outperformance | numeric | views ÷ author.baseline_median_views. **PRIMARY signal.** null if no baseline |
| save_rate | numeric | saves ÷ views (weighted highest — watch-time proxy) |
| share_rate | numeric | shares ÷ views (weighted highest — watch-time proxy) |
| like_rate | numeric | likes ÷ views |
| comment_rate | numeric | comments ÷ views |
| velocity | numeric | views ÷ age_days — single-snapshot proxy (true velocity needs time-series, Phase 3) |
| niche_spike | numeric | a rate (e.g. save-rate) ÷ the niche-sample median — cheaper cross-check |
| duration_s | integer | normalizer (copied from video) |
| age_days | numeric | normalizer |
| composite | numeric not null | the ranking number |
| flag | score_flag not null default 'ok' | ok / no_baseline / noise |
| computed_at | timestamptz not null default now() | |

**Never rank by raw views.** Follower count is only a floor (~1,000 followers): below it, ratios are `noise`, never the denominator.

Index: `(video_id, computed_at desc)`, `(composite desc)` for ranking. A view `latest_scores` exposes the newest score per video.

### 3.7 `analyses`
Layer 2 output — **outliers only**, cached by video.

| col | type | notes |
|---|---|---|
| id | uuid pk | |
| video_id | uuid fk → videos | unique |
| status | analysis_status not null default 'pending' | |
| hook_text | text | the exact hook line |
| hook_type | text | question / POV / bold-claim / curiosity-gap / … |
| emotional_driver | text | |
| format | text | talking-head / green-screen / demo / … |
| structure | text | hook→problem→solution, listicle, … |
| replication_score | integer | 0–100 |
| transcript | text | opening-window transcript (full only if computed) |
| onscreen_text | text | OCR output |
| representative_video_id | uuid fk → videos | set if tags inherited from a cluster rep |
| provider | text | which LLMProvider |
| model | text | which model |
| prompt_version | text | for A/B of prompts |
| created_at / updated_at | timestamptz | |

Unique: `(video_id)`.

### 3.8 `concepts`  ← the core deliverable
Recurring concepts — winners clustered into repeatable formulas. The actionable unit is "this concept works across N creators," not "here are 6 videos."

| col | type | notes |
|---|---|---|
| id | uuid pk | |
| niche_id | uuid fk → niches | |
| lane | lane not null | rising / proven |
| name | text not null | human label for the concept |
| pattern | text | the repeatable formula |
| n_videos | integer | evidence count |
| n_creators | integer | distinct creators (recurrence = credibility) |
| median_outperformance | numeric | median account-baseline outperformance across members |
| niche_spike | numeric | e.g. save-rate spike vs niche median |
| confidence | confidence not null | high (≥5 videos, ≥4 creators) / medium / emerging |
| lifecycle | lifecycle not null | emerging / growing / mature / declining (growing/declining need time-series, Phase 3) |
| adapted_hook | text | rewritten hook for the client |
| format | text | talking-head / green-screen / demo / … |
| length_s | integer | recommended shoot length |
| test_target | text | what the client should test |
| script | jsonb | timecoded beats (shoot-ready) |
| created_at / updated_at | timestamptz | |

Index: `(niche_id, lane)`, `(niche_id, confidence)`.

### 3.9 `concept_members`
Join: which videos back which concept.

| col | type | notes |
|---|---|---|
| concept_id | uuid fk → concepts | |
| video_id | uuid fk → videos | |

PK: `(concept_id, video_id)`.

### 3.10 `trends`
Layer 3 clusters (Phase 3). **Also backs the global Trending Songs tab (SPEC §4.5):** `type='sound'`, `key=audio_id`. That tab aggregates `videos.audio_id` across the owner's projects (bottom-up), filterable by **region** via the owning project's `region`; per-sound metrics (usage, median outperformance, rising/mature) may be materialized here or computed live from `videos`+`scores`.

| col | type | notes |
|---|---|---|
| id | uuid pk | |
| niche_id | uuid fk → niches | |
| type | trend_type not null | sound / format / hook |
| key | text not null | audio_id, cluster label, or hook embedding centroid id |
| label | text | human-readable ("'POV: the app knows' hook") |
| status | trend_status not null | rising / peak / declining |
| growth_rate | numeric | slope of member-winner count over time |
| member_count | integer | current winners in cluster |
| first_detected_at | timestamptz | |
| updated_at | timestamptz | |

Index: `(niche_id, status)`, `(niche_id, type, key)`.

### 3.11 `trend_members`
Join: which videos belong to which trend cluster over time.

| col | type | notes |
|---|---|---|
| trend_id | uuid fk → trends | |
| video_id | uuid fk → videos | |
| added_at | timestamptz not null default now() | |

PK: `(trend_id, video_id)`.

### 3.12 `alerts`
Track surface events (Phase 3).

| col | type | notes |
|---|---|---|
| id | uuid pk | |
| niche_id | uuid fk → niches | |
| type | alert_type not null | breakout / trend_rising / competitor / saturation |
| payload | jsonb not null | video ref, counts, deltas — enough to render the card |
| read | boolean not null default false | |
| created_at | timestamptz | |

Index: `(niche_id, created_at desc)`, `(read)`.

### 3.13 `watchlist`
Accounts we follow within a niche.

| col | type | notes |
|---|---|---|
| id | uuid pk | |
| niche_id | uuid fk → niches | |
| author_id | uuid fk → authors | |
| created_at / deleted_at | timestamptz | |

Unique: `(niche_id, author_id)`.

### 3.14 `briefs`
Saved content briefs (Phase 2+).

| col | type | notes |
|---|---|---|
| id | uuid pk | |
| niche_id | uuid fk → niches | |
| angle | text | |
| hook | text | |
| script | text | |
| backing_video_ids | uuid[] | the outliers this is built from |
| trend_id | uuid fk → trends | the wave it rides, if any |
| created_at / updated_at / deleted_at | timestamptz | |

### 3.15 `credit_log`  ← cost discipline
Every `DataSource` call. Non-negotiable.

| col | type | notes |
|---|---|---|
| id | uuid pk | |
| source | text not null | 'scrapecreators' / 'apify' / … |
| call | credit_call not null | trending / profile / video / search |
| credits | integer not null | credits charged |
| result_count | integer | rows returned |
| niche_id | uuid fk → niches | nullable |
| created_at | timestamptz not null default now() | |

Index: `(created_at)`, `(source, created_at)`. Powers the burn-rate tile.

### 3.16 `llm_log` (optional, Phase 2)
Mirror of credit_log for LLM spend — provider, model, task, tokens in/out, batch flag, cost estimate. Same rationale: know the burn.

---

## 4. Key relationships

```
niches 1─* queries
niches 1─* videos *─1 authors
videos 1─* video_snapshots        (time-series)
videos 1─* scores                 (latest via view)
videos 1─1 analyses               (outliers only)
niches 1─* concepts *─* videos    (via concept_members — the core deliverable)
niches 1─* trends *─* videos      (via trend_members)
niches 1─* alerts
niches 1─* watchlist *─1 authors
niches 1─* briefs
```

---

## 5. Retention & size control (bootstrapped)

- `video_snapshots` grows fastest. Retention: keep full-resolution snapshots for 90 days; beyond that, downsample to daily and prune intra-day rows (a rollup job). Trends only need daily granularity historically.
- `videos.raw_payload` (jsonb) is heavy — keep for 30 days, then null it (analysis is already extracted).
- Source video files are **never** stored in Postgres or Storage beyond transient processing (§SPEC 4/9).

---

## 6. Indexes summary (ranking/query hot paths)

- `videos (platform, video_id)` unique — dedupe.
- `video_snapshots (video_id, captured_at desc)` — velocity.
- `scores (composite desc)` + `latest_scores` view — the breakout table.
- `concepts (niche_id, lane)` — concept board (rising vs proven).
- `videos (audio_id)` — sound-trend grouping.
- `trends (niche_id, status)` — trends board.
- `alerts (niche_id, created_at desc)` — alerts feed.
- `credit_log (created_at)` — burn rate.

---

**End of DATABASE_SCHEMA.md** — full Drizzle DDL generated from these tables in `packages/db/schema.ts`.
