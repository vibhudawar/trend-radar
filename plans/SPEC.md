# SPEC.md — TrendRadar

> Conventions, contracts, and boundaries. Derived from PLAN.md. If it conflicts with PLAN.md, PLAN.md wins and this gets fixed.
> No slop. Precise over complete.

---

## 1. Repo layout (monorepo, pnpm workspaces)

```
trend-engine/
├── plans/                     # these docs
├── apps/
│   └── web/                   # Next.js app (dashboard, briefs)
├── packages/
│   └── db/                    # Drizzle schema + migrations (shared types)
├── worker/                    # Python pipeline (ingest → score → analyze → trend)
│   ├── trendradar/
│   │   ├── sources/           # DataSource implementations
│   │   ├── llm/               # LLMProvider implementations
│   │   ├── scoring/           # ScoringStrategy per platform
│   │   ├── media/             # download, transcribe, ocr, frames
│   │   ├── jobs/              # ingest, score, analyze, trend, alert
│   │   └── config.py
│   ├── pyproject.toml
│   └── tests/
└── README.md
```

- **`packages/db`** is the single source of schema truth. The Python worker does **not** re-declare tables — it reads the schema from a generated JSON/SQL artifact and uses raw SQL / SQLAlchemy Core against the same Postgres. Drizzle owns migrations; Python only reads/writes rows.
- The web app never imports from `worker/` and vice versa. Their only shared contract is the **database schema** and the **Zod/Pydantic mirror of row shapes** (§7).

---

## 2. The two swappable boundaries

Both are interfaces with implementations chosen by config (env), never hardcoded at call sites.

### 2.1 `DataSource`

```python
class DataSource(Protocol):
    name: str  # "scrapecreators" | "apify" | "own"

    def search(self, platform: Platform, query: Query) -> list[RawVideo]: ...     # keyword/hashtag seed
    def fetch_video_detail(self, platform: Platform, url: str) -> RawVideo: ...    # IG views+followers (Post/Reel Info); re-poll
    def fetch_author_videos(self, platform: Platform, handle: str) -> list[RawVideo]: ...  # ACCOUNT BASELINE (median recent views)
    def fetch_transcript(self, platform: Platform, url: str) -> str: ...           # spoken hook, no download
```

- **Implementations:** `ScrapeCreatorsSource` (primary, validated), `ApifySource` (fallback — `apify/instagram-reel-scraper` is the way to get **IG shares**), `OwnScraperSource` (future).
- Endpoint map (ScrapeCreators, PHASE0_FINDINGS §2): TikTok `search/keyword`, `v3/profile/videos`, `video/transcript`; IG `v2/reels/search`, `instagram/post`, `instagram/profile`.
- Every method **logs credits consumed** (`credit_log` table, §DATABASE_SCHEMA) with the call type and result count. No exceptions — we are on metered credits.
- `RawVideo` is the **normalized** shape (§2.3). Each source maps its vendor JSON into it. Missing fields are `None`, never faked.
- Rate-limit / error handling lives **inside** the source; jobs get clean results or a typed error, never raw HTTP.

### 2.2 `LLMProvider`

```python
class LLMProvider(Protocol):
    name: str  # "openai" | "gemini" | "deepseek" | "claude"

    def analyze(self, task: LLMTask, payload: dict, *, batch: bool = False) -> dict: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...
```

- **`task`** selects provider+model from config (per-task cascade — PLAN §11.5). Validated tasks+models (PHASE0_FINDINGS §9): `INTENT` → `gpt-5-nano`; `HOOK_VISION` (frames→on-screen text+format) → `gpt-4o-mini`; `HOOK_EXTRACT`/`CLUSTER`/`ADAPT` → `gpt-5-mini`. (Latest OpenAI is `gpt-5.2`; there is no "5.6 luna".)
- **`batch=True`** routes through the provider's Batch API where available (~50% off — PLAN §11.6). Used for all non-urgent analysis.
- All `analyze` calls demand **strict JSON output** validated against the task's Pydantic schema. A malformed response retries once, then is marked `analysis_failed` — never silently dropped.
- Prompts live in `worker/trendradar/llm/prompts/` as versioned files; the version is stored on each `analyses` row so we can compare prompt revisions.

### 2.3 Normalized `RawVideo` / `RawProfile`

```python
@dataclass
class RawVideo:
    platform: Platform            # "tiktok" | "reels"
    video_id: str                 # external id, unique per platform
    author_handle: str
    author_is_verified: bool | None
    caption: str | None
    audio_id: str | None          # music/sound id — trend signal
    audio_title: str | None
    url: str
    taken_at: datetime | None
    view_count: int | None
    like_count: int | None
    comment_count: int | None
    share_count: int | None       # often None (Reels trending endpoint)
    save_count: int | None        # often None
    play_count: int | None
    raw: dict                     # untouched vendor payload, stored for reprocessing

@dataclass
class RawProfile:
    platform: Platform
    handle: str
    follower_count: int | None
    recent_view_counts: list[int] # for baseline/median
```

`raw` is always persisted (`videos.raw_payload`) so we can recompute derived fields without re-spending credits.

---

## 3. Scoring — `ScoringStrategy` per platform (validated, PHASE0_FINDINGS §3)

```python
class ScoringStrategy(Protocol):
    platform: Platform
    def score(self, video: VideoWithSnapshots, author: Author) -> Score: ...
```

**Rule: never rank by raw views; follower count is a noise filter, never the denominator.**

- **Primary: `account_outperformance = latest_views / author.baseline_median_views`** (author's median of ~10 recent videos, via `fetch_author_videos`). If baseline missing → `None`, flagged `no_baseline`, rank on engagement only. **Do not drop the winner — retry the baseline fetch first.**
- **Per-view engagement rates:** `save_rate, share_rate, like_rate, comment_rate = count / views`. **Saves + shares weighted highest** (public proxy for retention/watch-time, which is private and unavailable).
- **`velocity = views / age_days`** (single-snapshot proxy; true 24–72h velocity needs ≥2 snapshots — Phase 3).
- **`niche_spike`** = a rate ÷ the niche-sample median (cheap cross-check).
- **`duration`, `age_days`** stored as normalizers.
- **Follower floor** (~1,000): below it, all ratios are `flagged noise`, excluded from ranking.
- **`TikTokStrategy`:** `composite = f(account_outperformance, save+share-rate, reach)`. Full metric set inline from keyword search.
- **`ReelsStrategy`:** `views/follower + like_rate` (via Post/Reel Info). No shares/saves unless the `DataSource` is Apify (`apify/instagram-reel-scraper`) which returns shares.
- Every component stored on the `scores` row; **weights in versioned config**; a re-score job replays stored data.

**Never fabricate** watch time, retention, completion, non-follower reach, follows. Absent = `None`, shown honestly.

---

## 4. Analysis pipeline (outliers only)

### 4.1 Intent filter (relevance — runs before scoring on candidates)
`LLMProvider(INTENT)` classifies each candidate: **is this a product/tool PITCH** (matches the client's job-to-be-done) or education/storytime? Keep pitches only. **Cache the result per `video_id`** (the classifier is non-deterministic — classify once, reuse; determinism matters).

### 4.2 Real hook (the caption is NOT the hook — PHASE0_FINDINGS §5)
```
outlier → transcript endpoint (spoken opening, no download, DataSource.fetch_transcript)
        → download opening ~3s → extract 2-3 frames @ ~1.5–2.5s (opencv — pip wheel bundles decoder, no ffmpeg)
        → LLMProvider(HOOK_VISION): frames → on-screen text (verbatim) + format
        → LLMProvider(HOOK_EXTRACT): pick THE hook from {on-screen, spoken}; caption = context only
        → write analyses row (cache by video_id)
```
- **Hook fallback chain:** on-screen (vision) → spoken (transcript) → caption (last resort, flag low-fidelity).
- Use a **vision model to read on-screen text** (stylized/animated — plain OCR fails), and to read the format.
- Source video is **transient** — processed then deleted (legal posture §9).

### 4.3 Concept clustering (anecdote → evidence — PHASE0_FINDINGS §6)
`LLMProvider(CLUSTER)` groups the niche's outliers into 2–4 **recurring concepts**. Per concept, computed & stored: `#videos`, `#distinct_creators`, median `account_outperformance`, `niche_spike`, **confidence** (High ≥5 videos/≥4 creators, Medium, Emerging), **lifecycle** (Emerging/Growing/Mature/Declining — Growing/Declining need the time-series).

### 4.4 Adaptation (the deliverable)
`LLMProvider(ADAPT)` per concept → rewritten hook for the client, format, length, **shoot-ready script (timecoded beats)**, **test target**, and the **winning-video links** (evidence for the client).

### Two lanes
Run selection twice: **Rising now** (recency-filtered) and **Proven playbook** (all-time, no recency filter). Both surfaced separately.

### Cross-cutting robustness (required)
Retry every external call once with backoff; cache intent + hook + analysis by `video_id`; language/region filter on candidates; pull **multiple queries/pages per niche** for confidence (one page ≈ too thin).

---

## 5. Server/client rules (web app)

- **Server Components by default.** `'use client'` pushed to the leaf (charts, interactive filters).
- **Reads** → Server Components with direct Drizzle queries. Client polling/optimistic → TanStack Query over `/api` routes.
- **Writes** (create niche, add query, add to watchlist, save brief) → **Server Actions**.
- The web app **never** calls a `DataSource` or `LLMProvider`. It only reads processed rows and writes user intent. All heavy work is the worker.
- Every list is paginated; every query filters by `niche_id` and (future) `user_id` for RLS.

---

## 6. Design system (dashboard)

- **Desktop-first, data-dense.** This is an analyst tool — the primary view is a wide, sortable table of ranked breakout videos at ~1280px+, collapsing to cards on mobile.
- **Dark theme primary** (matches the UGC Pulse reference and reduces eye strain for long review sessions); light mode a fast-follow.
- **Signature surfaces:**
  - **Breakout table** — ranked outliers: thumbnail, author, outlier ×, engagement %, velocity, age, platform badge. Sortable, filterable by niche/platform.
  - **Video detail** — metric time-series (from `video_snapshots`), the analysis card (hook line, type, format, replication score), link to source.
  - **Trends board** — rising / peak / declining clusters with a sparkline of growth over time (Phase 3).
  - **Alerts feed** — the "Stay ahead" surface (Phase 3).
- **Anti-slop UI:** skeletons not spinners; empty states name the next action ("No niches yet — create one"); every surfaced number is clickable to its underlying videos. No vanity metrics.
- Numbers formatted compact (`2.4M`, `15.4%`); `approximated`/`no_baseline` flags shown honestly, never hidden.
- Full palette/tokens: dark neutral surfaces, one accent for "rising/positive" (green), one for "saturation/warning" (amber/purple), platform brand chips.

---

## 7. Type contracts

- **Zod** is the source of truth for the web app's I/O; **Pydantic** mirrors row shapes in the worker. Both are generated/derived from the Drizzle schema shapes where possible, kept in sync manually where not.
- Enums (`platform`, `query_type`, `trend_type`, `trend_status`, `alert_type`, `llm_task`) are declared **once** in the DB schema and mirrored in both languages. A drift check is part of CI (Phase 1+).

---

## 8. Cost & credit discipline (enforced, not aspirational)

- Every `DataSource` call → a `credit_log` row (call type, count, credits, source). A dashboard tile shows daily/weekly burn.
- Layer 2 runs **only on outliers**; a guard rejects analysis of any video without a qualifying `scores` row.
- Re-polling for velocity/breakout alerts is **opt-in per niche**, with a configurable interval and a per-niche daily credit ceiling. Hitting the ceiling pauses re-polling and logs it, never silently overspends.
- Batch API for all non-urgent LLM work.

---

## 9. Legal & safety posture (must hold)

- **Public data only.** No logged-in, private, or authenticated scraping. Ever.
- **Store derived analysis, not re-hosted media.** Metrics, transcripts, hook tags — yes. Copies of creators' videos — no (transient processing only, then deleted).
- **Vendor absorbs blocking risk** while on a paid `DataSource`; if we build `OwnScraper` later, this section gets revisited with proxy/rate/identity rules before a line is written.
- No PII compilation across sources. We analyze content patterns, not people.
- This is a known gray area for the whole category; we minimize exposure and are honest about it — we do not claim it is fully sanctioned.

---

## 10. Engineering conventions (anti-slop)

- **Tooling:** shadcn CLI for components; Supabase CLI for migrations/types/RLS; Drizzle Kit for schema — never hand-write what a CLI generates; never edit a committed migration.
- **Git:** never commit to `main`; branch from latest `main`, `feat/…|fix/…|chore/…`, one feature per branch, PR + Conventional Commits.
- **TS:** no `any`; no dead/commented code; no stray `console.log`; file < 300 lines, component < 150; Server Components by default.
- **Python:** typed (mypy), `ruff` lint/format, small pure functions in `scoring/` and `media/` with unit tests; jobs are idempotent and re-runnable.
- **Idempotency:** ingestion upserts `videos` on `(platform, video_id)` and **appends** a `video_snapshots` row; never overwrites metrics in place.
- **Tests (high-value only):** scoring math, dedupe, DataSource field-mapping (fixtures of real vendor JSON), trend growth-rate calc. Skip trivial boilerplate.
- **Secrets:** env only. ScrapeCreators key, LLM keys, Supabase service key never in code or client bundles.

---

**End of SPEC.md**
