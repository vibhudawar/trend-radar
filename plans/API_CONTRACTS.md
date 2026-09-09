# API_CONTRACTS.md — TrendRadar

> Three contract surfaces: (A) the web app's server actions + read API, (B) the Python worker's job contracts, (C) the `DataSource` / `LLMProvider` / `ScoringStrategy` interfaces.
> Zod (TS) and Pydantic (Python) mirror the same shapes. Derived from DATABASE_SCHEMA.md.

---

## A. Web app (Next.js)

Reads: Server Components (Drizzle) for pages; `/api/v1/*` for client-side polling/filtering. Writes: Server Actions.

### A.1 Read API (`/api/v1`)

| Method · Path | Purpose | Query / Body | Returns |
|---|---|---|---|
| GET `/api/v1/niches` | list niches | — | `Niche[]` |
| GET `/api/v1/niches/:id/breakouts` | ranked outliers (by account-baseline outperformance, not raw views) | `platform?, lane?=rising\|proven, minOutlier?, sinceHours?, sort?, page` | `BreakoutRow[]` + page meta |
| GET `/api/v1/niches/:id/concepts` | recurring concept cards per lane | `lane=rising\|proven` | `ConceptCard[]` (name, pattern, confidence, lifecycle, evidence counts, median outperformance) |
| GET `/api/v1/concepts/:id` | full concept | — | `ConceptDetail` (adapted hook, script, test target, winning-video links/examples w/ per-video outperformance) |
| GET `/api/v1/videos/:id` | video detail | — | `VideoDetail` (video + snapshots + latest score + analysis) |
| GET `/api/v1/videos/:id/snapshots` | metric time-series | — | `Snapshot[]` |
| GET `/api/v1/niches/:id/trends` | trends board | `status?, type?` | `Trend[]` |
| GET `/api/v1/niches/:id/alerts` | alerts feed | `unreadOnly?, page` | `Alert[]` |
| GET `/api/v1/niches/:id/credits` | burn rate | `range=7d\|30d` | `{ byDay, total, bySource }` |

All list endpoints paginate (`page`, `pageSize`, default 25) and always filter by `niche_id`.

### A.2 Server Actions (writes)

```ts
createNiche(input: { name; product?; platforms: Platform[] }) -> Niche
addQuery(input: { nicheId; platform; type; value }) -> Query
toggleQuery(input: { queryId; active }) -> Query
addToWatchlist(input: { nicheId; authorId }) -> WatchlistItem
removeFromWatchlist(input: { id }) -> void
saveBrief(input: { nicheId; angle; hook; script?; backingVideoIds; trendId? }) -> Brief
markAlertRead(input: { alertId }) -> void
requestReanalyze(input: { videoId }) -> { queued: true }   // enqueues a worker job; guarded to outliers only
```

Every action validates input with a Zod schema (§A.4), checks the row belongs to the workspace, returns the created/updated row.

### A.3 Zod contract examples

```ts
export const zPlatform = z.enum(["tiktok", "reels"]);
export const zQueryType = z.enum(["hashtag", "keyword", "sound", "account"]);

export const zBreakoutRow = z.object({
  videoId: z.string().uuid(),
  platform: zPlatform,
  authorHandle: z.string(),
  thumbnailUrl: z.string().url().nullable(),
  outlierMultiplier: z.number().nullable(),
  engagementRate: z.number().nullable(),
  viewVelocity: z.number().nullable(),
  views: z.number().nullable(),
  ageHours: z.number(),
  composite: z.number(),
  flag: z.enum(["ok", "approximated", "no_baseline"]),
});
```

### A.4 Auth (minimal, internal)

- Single team. Supabase Auth email/password; one workspace. Middleware gates all `/api/v1` and app routes.
- RLS declared but permissive-to-workspace now; tightened when multi-workspace lands.

---

## B. Python worker — job contracts

Jobs are idempotent, triggered by cron (Supabase pg_cron → an HTTP trigger or a Render cron). Each job logs credits/LLM spend. No job serves the browser.

The validated pipeline (PHASE0_FINDINGS §1, SPEC §4) runs in **TWO LANES per niche** — `rising` (recency-filtered + accelerating) and `proven` (all-time, no recency filter) — surfaced separately. Analysis (hook/cluster/adapt) runs **only on outliers**. Every external call retries once with backoff; `intent`, `hook`, and `analysis` results are cached by `video_id`.

### B.1 `ingest`

```
ingest(project_id, platform, lane) :                     # discovery = deduped union of 3 sources (SPEC §4.0)
  raws  = DataSource.search(platform, q)          for q in seed_keywords      # source #1
  raws += DataSource.fetch_author_videos(platform, h) for h in accounts       # source #2: competitor/niche accounts
  raws += DataSource.fetch_song_videos(platform, a)   for a in hot_audio_ids  # source #3: audio expansion
  for r in dedupe(raws, on=(platform, video_id)):        # + credit_log each call
    if not passes_filters(r): continue                   # recency (taken_at, rising lane only) / language-region / min-view floor
    author = upsert_author(r)
    video  = upsert_video(r)                             # on (platform, video_id)
    append_snapshot(video, r)                            # NEVER overwrite
  mark query.last_run_at
```

- **Discovery is the deduped union of 3 additive sources** (SPEC §4.0): keyword search, account mining (competitor/niche accounts from onboarding — additive, never a filter), audio expansion. Dedupe on `(platform, video_id)`.
- Filters decide *relevance* before any LLM spend: recency (`taken_at`, rising lane), language/region (user-set market, §2.4), min-view floor.
- **Credit efficiency:** account mining returns many videos + the baseline per call; cache `fetch_video_detail`/`fetch_author_videos` results **across lanes** within a run (the first Reels run wasted the cap re-fetching per lane).

### B.2 `intent_filter` (LLM — relevance, before scoring)

```
intent_filter(niche_id):
  for video in unclassified_candidates(niche_id):
    if intent[video_id] cached: continue                 # non-deterministic classifier → classify once, reuse
    keep = LLMProvider.analyze(INTENT, {caption, transcript?})   # product/tool PITCH vs education/storytime
    persist video.content_type / intent (cache by video_id)
```

- Keeps only product/tool pitches matching the client's job-to-be-done; drops ~half as noise. Core differentiator vs a generic scraper.

### B.3 `score`

```
score(niche_id):
  for video in pitches_needing_score(niche_id):
    author.baseline_median_views = median(DataSource.fetch_author_videos(platform, handle))  # ACCOUNT BASELINE, retry once
    strategy = strategy_for(video.platform)
    s = strategy.score(video_with_snapshots, author)     # account-baseline outperformance × reach; save/share-weighted engagement; follower floor
    insert scores(s)                                     # history preserved
```

- **Primary signal is `account_outperformance = views ÷ author's median recent views`** (via `fetch_author_videos`), NOT raw views and NOT follower count (follower count is a floor/noise filter only).
- Baseline fetch retries once before flagging `no_baseline` — one dropped call must not blank a winner. Pure/deterministic given inputs → unit-tested.

### B.4 `hook` (Layer 2 — outliers only; real hook, not the caption)

```
hook(niche_id):
  for video in top_outliers(niche_id):
    if analyses[video_id] exists: skip                   # cache by video_id
    transcript = DataSource.fetch_transcript(platform, url)      # spoken opening, no download; retry once
    clip = download opening ~3s -> frames @ ~1.5-2.5s (opencv, no ffmpeg)
    onscreen = LLMProvider.analyze(HOOK_VISION, {frames})        # on-screen text (verbatim) + format
    hook = LLMProvider.analyze(HOOK_EXTRACT, {onscreen, transcript, caption}, batch=True)
    upsert analyses(...)                                 # + llm_log
    delete media file                                    # legal posture
```

- Guard: refuses any video without a qualifying `scores` row.
- **Hook fallback chain:** on-screen (vision) → spoken (transcript) → caption (last resort, flagged low-fidelity). Batch API for `HOOK_EXTRACT`; strict JSON validated by Pydantic.

### B.5 `cluster`

```
cluster(niche_id):
  concepts = LLMProvider.analyze(CLUSTER, {outlier hooks + formats})   # 2-4 recurring concepts
  for c in concepts:
    compute #videos, #distinct_creators, median account_outperformance, niche_spike
    c.confidence = High(>=5 videos/>=4 creators) | Medium | Emerging
    c.lifecycle  = Emerging | Growing | Mature | Declining            # Growing/Declining need time-series (Phase 3)
    upsert concepts + concept_members
```

- Recurrence = credibility: the actionable unit is "this concept works across N creators," not a list of videos.

### B.6 `adapt` (the deliverable)

```
adapt(niche_id):
  for concept in concepts(niche_id):
    a = LLMProvider.analyze(ADAPT, {concept, evidence, client_context})
    # rewritten hook + format + length + shoot-ready script (timecoded beats) + test target + winning-video links
    upsert concept.adaptation
```

- One adaptation per concept, per lane; winning-video links carry per-video outperformance as client-facing evidence.

### B.7 `trend` / `alert` (Phase 3)

```
trend(niche_id):  compute growth_rate over time per concept -> lifecycle Growing/Declining; velocity from >=2 snapshots
alert(niche_id):  breakout (re-poll via fetch_video_detail, velocity threshold) | trend_rising | competitor (watchlist) | saturation
```

- Re-polling is **opt-in per niche** with a daily credit ceiling; ceiling hit → pause + log, never overspend.

---

## C. Interfaces (the swappable boundaries)

### C.1 `DataSource`
(see SPEC §2.1) — five methods, matching the validated pipeline + discovery (§4.0):

| method | purpose |
|---|---|
| `search(platform, query)` | keyword/hashtag seed → `list[RawVideo]` (discovery source #1) |
| `fetch_video_detail(platform, url)` | IG views + followers via Post/Reel Info → `RawVideo`; also used to re-poll |
| `fetch_author_videos(platform, handle)` | **ACCOUNT BASELINE** (median recent views) **+ account mining** — a competitor/niche account's recent videos as candidates (discovery source #2) |
| `fetch_song_videos(platform, audio_id)` | videos/reels using a sound → `list[RawVideo]` (discovery source #3; feeds Trending Songs §4.5) |
| `fetch_transcript(platform, url)` | spoken hook (WEBVTT), no download → `str` |

Maps vendor JSON → `RawVideo`/`RawProfile`. Logs credits (1 credit = 1 request). Missing fields → `None`, never faked.

**Verified ScrapeCreators endpoint map (PHASE0_FINDINGS §2 — docs were wrong repeatedly):**

| method | TikTok | Instagram |
|---|---|---|
| `search` | `v1/tiktok/search/keyword?query=` (param is **`query`**, not `keyword`) — returns play_count, digg, comment, **share_count**, **collect_count (saves)**, follower_count inline | `v2/reels/search?query=&date_posted=` — niche-targetable; no views/followers/shares |
| `fetch_video_detail` | (inline from search) | `instagram/post?url=` (Post/Reel Info) → `video_play_count`, followers; **shares/saves never exposed** |
| `fetch_author_videos` | `v3/tiktok/profile/videos?handle=` → recent ~10 videos' play_count | `instagram/profile?handle=` → `edge_followed_by.count` (followers) **and** timeline `video_play_count` (the account baseline — both in one call) |
| `fetch_song_videos` | `v1/tiktok/song/videos?...` (videos using a song); `v1/tiktok/song` (song detail/usage) | `v1/instagram/audio/reels?...` (reels by audio id) |
| `fetch_transcript` | `v1/tiktok/video/transcript?url=` (WEBVTT, `language` param) | — |

- **IG never exposes shares/saves** via ScrapeCreators. To get IG shares, swap the `DataSource` to Apify **`apify/instagram-reel-scraper`** (returns reel shares). Kept as a swappable option.
- **IG views + followers + baseline (verified 2026-09-09):** `instagram/post` returns the reel's `video_play_count` (views) but **not** followers; `instagram/profile` returns followers **and** the account baseline (median of the creator's recent reels' `video_play_count`) in a single call. So a Reels candidate costs 1 (post detail) + 1 (profile per unique creator).
- **Trending sounds:** no ScrapeCreators top-down chart exists — the Trending Songs signal (§4.5) is bottom-up from ingested `audio_id`s. An official TikTok chart by region is available via Apify **`novi/tiktok-music-trend-api`** (region code param; `user_count` usage) — optional paid upgrade ($45/mo), not required.
- IG views require the per-reel detail call (`instagram/post`); `video_text` is empty on TikTok → on-screen text needs frames+vision, not the API.
- Bad requests don't charge credits. Auth: `x-api-key` header. Response includes `credits_remaining` → write to `credit_log`.

### C.2 `LLMProvider`
(see SPEC §2.2) — `analyze(task, payload, batch)`, `embed(texts)`. Per-task provider+model from config. Strict JSON out, validated per task's Pydantic schema. Prompt version stored on `analyses`.

**Task → default model (validated, PHASE0_FINDINGS §9; config-overridable):**
| task | default | why |
|---|---|---|
| `INTENT` | `gpt-5-nano` | cheap pitch-vs-education classification (cache — non-deterministic) |
| `HOOK_VISION` | `gpt-4o-mini` | frames → on-screen text (verbatim) + format |
| `HOOK_EXTRACT` | `gpt-5-mini` | pick THE hook from {on-screen, spoken} |
| `CLUSTER` | `gpt-5-mini` | group outliers into recurring concepts |
| `ADAPT` | `gpt-5-mini` | rewrite hook + shoot-ready script + test target |
| embeddings | `text-embedding-3-small` | clustering |

Latest OpenAI is `gpt-5.2`; there is no "5.6 luna" / "5.4".

### C.3 `ScoringStrategy`
(see SPEC §3) — `TikTokStrategy`, `ReelsStrategy`. Reads video+snapshots+author, returns a `Score` with all components + a `flag`. Weights versioned in config; a re-score job replays stored snapshots.

---

## D. Error & status conventions

- Read API: `200` with data, `404` unknown id, `400` bad query (Zod message), `401` unauthed. Never leak vendor errors.
- Worker jobs: typed results; failures write a status (`analysis_status='failed'`, or a job-run log) and continue the batch — one bad video never kills a run.
- Every external call (DataSource/LLM) has a timeout + one retry with backoff, then a logged failure.

---

**End of API_CONTRACTS.md**
