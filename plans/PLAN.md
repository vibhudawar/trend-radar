# PLAN.md — TrendRadar

> Master plan. Single source of truth until it's split into SPEC / DATABASE_SCHEMA / API_CONTRACTS / ROADMAP / CLAUDE_CODE_PROMPTS.
> Precise over complete. No slop. If a decision changes, change it here first.
>
> **TrendRadar** — a UGC trend-intelligence engine.

---

## 1. What this is

An internal trend-intelligence tool that scrapes short-form video (TikTok + Instagram Reels), finds the videos that are *punching above their weight*, reverse-engineers **why** they won, and detects **which trends are rising right now** — so we can make UGC ads/content that ride the wave before it saturates.

It is a decision tool, not a video editor and not an ad platform. It answers three questions, in order:

1. **What is winning?** (selection)
2. **Why did it win?** (explanation — hook, format, structure)
3. **What pattern is rising right now?** (trend — the meta layer that tells us what to make *next*)

The bet: most UGC is made on gut feel and doomscrolling. If we can *systematically* surface breakout content, decode its formula, and catch trends on the way up, we make content that gets pushed by the algorithm instead of guessing.

### North Star

**Time-to-a-winning-brief.** From "I have a product + niche" to "here is a shot-ready angle backed by real performance data and a rising trend" — measured in minutes, grounded in data, not vibes. Every feature exists to shorten that path.

### Who it's for (now)

Internal use — powering content/ads for our own products first, then as the engine behind a content/marketing agency:

- **Ecombox** — Indian Amazon/Flipkart/Meesho sellers → **Instagram Reels** (TikTok is banned in India).
- **GymOS** — Indian gym owners → **Instagram Reels**.
- **US SaaS/DTC products** → **TikTok + Reels**.

Both platforms are supported from day one; we *seed* with Reels (Ecombox, India) because that niche has the highest UGC volume to validate against.

### Non-goals (for now)

- **No SaaS wrapper** — no payment gateway, no billing, no public sign-up, no multi-tenant onboarding. Internal tool. (Auth is minimal; see §3.)
- **No video generation/editing** — we output *briefs* (hooks, angles, scripts), not rendered videos.
- **No re-hosting creators' videos** — we store *derived analysis* (metrics, transcripts, hook tags), not copies of the source video. (See §11 legal posture.)
- **No YouTube Shorts / other platforms** yet — the architecture supports adding them; we don't build them now.
- **No "chart for chart's sake."** Every surfaced number must change a content decision.

---

## 2. The core insight (why this can be better than a trending feed)

Anyone can open the TikTok/Reels trending feed. That's not a product — it's the content *everyone already sees*, i.e. content that's already saturated.

The edge is **selection**: outlier detection relative to an account's own baseline. A 50k-follower account's video hitting 2M views is a far stronger signal than a 10M-follower account hitting 2M — the first is the algorithm *choosing* the content, the second is just its audience. Surfacing breakouts **before** they're obviously trending, and small-account gems the trending feed buries, is the moat. LLM analysis on top is the valuable second half — but garbage selection produces polished garbage. Selection first.

---

## 3. Tech stack (locked)

### App (Next.js)
- **Next.js (App Router, Server Components by default), TypeScript strict, pnpm**
- **Tailwind + shadcn/ui** (installed via `shadcn` CLI — never hand-author a primitive)
- **Drizzle ORM + Drizzle Kit** — type-safe schema, generated migrations, one place for table defs
- **TanStack Query** (client server-state), **Zod** (I/O contracts)
- The Next app owns the **whole web/API surface**. No separate live API server in MVP.

### Data & storage
- **Supabase** — Postgres + Storage + (minimal) Auth. RLS on from day one even though it's single-team, so it's not a rewrite later.
- Supabase **cron** (pg_cron) or an external scheduler triggers ingestion runs.

### Data pipeline (Python worker)
- **Python 3.12** — ingestion + scoring + analysis jobs. **Not a request-serving API — a scheduled background worker.** Writes results into the same Supabase Postgres.
- **Why Python here and TS for the app:** the app is CRUD + views (TS wins); the pipeline is scraping, math, media processing, and LLM orchestration (Python's tooling wins). One live server (Next), one batch worker (Python).
- Media processing (Phase 2): **ffmpeg** (frame extraction), **Whisper** (transcription), **OCR** (on-screen text from opening frames).

### Two swappable boundaries (design rule)
Both are interfaces with pluggable implementations, chosen in config, never hardcoded:

1. **`DataSource`** — `ScrapeCreators` (primary now: TikTok + IG, 100 free credits, 1 credit = 1 request) → `Apify` (fallback, ~$1/1k Reels, ~$1.70/1k TikTok) → `OwnScraper` (later). One interface: `fetch_trending(platform, query) -> RawVideo[]`, `fetch_profile(handle) -> Profile`.
2. **`LLMProvider`** — model-agnostic. `OpenAI` (start — you have credits, `gpt-4o-mini`/`4.1-mini`) → `Gemini` / `DeepSeek` / `Claude`. One interface: `analyze(payload) -> JSON`. Provider + model in config.

### Ops
- App on **Vercel**; Python worker on **Render** (free tier to test, $7–15 tier when cron must run reliably — free tier sleeps).
- Env-based secrets (ScrapeCreators key, LLM keys, Supabase). No keys in code.

### Explicitly NOT in stack now
Second live API server (FastAPI serving requests) · own scrapers · payment/billing · public multi-tenant auth · YouTube/other platforms.

---

## 4. Architecture

```
                    ┌─────────────────────────────┐
   Browser (team) ─▶│        Next.js app          │
   dashboard, briefs│  Server Components/Actions   │
                    │  + Drizzle queries           │
                    └───────────────┬──────────────┘
                                    │ read/write
                    Supabase        ▼
             (Postgres · Storage ┌──────────────┐
              · Auth · RLS · cron)│  Postgres    │◀──────────┐
                                 └──────────────┘            │ writes results
                                    ▲                         │
                          triggers  │ (cron)                  │
                                    │                ┌────────┴─────────┐
                                    └───────────────▶│  Python worker    │
                                                     │  ingest→score→    │
                                                     │  analyze→trend    │
                                                     └───┬───────┬───────┘
                                                         │       │
                                              DataSource ▼       ▼ LLMProvider
                                        (ScrapeCreators/Apify) (OpenAI/…)
```

Rules:
- **Next app never scrapes and never calls the LLM directly.** It reads processed data from Postgres and writes user actions (watchlists, saved briefs). All heavy lifting is the Python worker.
- **Python worker is batch, not live.** Cron kicks off runs; it pulls via `DataSource`, computes scores, runs analysis via `LLMProvider`, writes rows. It never serves the browser.
- **Every raw metric is stored**, per platform, per snapshot, with a timestamp. Scoring reads from storage — retuning never requires a re-scrape.
- Reads → Server Components + Drizzle. Writes → Server Actions.

---

## 5. The pipeline (validated in Phase 0 — see PHASE0_FINDINGS.md, authoritative)

The full pipeline, each stage validated on real data across two products:

```
goal-matched query (job-to-be-done, NOT product topic)
  → keyword search  → filters (recency · language · min-views)
  → INTENT FILTER (keep product/tool pitches, drop education)
  → SELECTION (per-view engagement × reach, follower-floored) + ACCOUNT BASELINE (views ÷ creator's own median)
  → REAL HOOK (transcript endpoint + frames+vision) — never the caption
  → CONCEPT CLUSTERING (winners → recurring concepts; recurrence = credibility)
  → ADAPTATION (per concept: rewritten hook + shoot-ready script + test target + winning-video links)
```

### Stage A — Relevance (intent, not topic)
Seed by the client's **job-to-be-done** (e.g. *sell a SaaS to ecom sellers*), not the product topic. An **intent filter** (LLM) keeps only videos whose goal matches — product/tool pitches — and drops education/storytime. This is what separates TrendRadar from a generic scraper.

### Stage B — Selection (which videos genuinely won)
**Not raw views. Not follower count.** Primary signal = **account-baseline outperformance** (`views ÷ the creator's own median recent views`) — a small creator's 3× breakout beats a big creator's below-average post. Plus per-view engagement (saves/shares weighted highest as the public proxy for retention), velocity, follower floor. Per-platform strategies (§6).

### Stage C — Explanation (the REAL hook)
Runs **only on selected outliers**. The caption is not the hook. Read the actual video: **spoken opening** (transcript endpoint, no download) + **on-screen text** (download opening → frames → vision). LLM extracts the exact hook line, type, format, structure.

### Stage D — Concept clustering (anecdote → evidence)
Group winners into 2–4 **recurring concepts**. The actionable unit is "this concept works across N creators," not one video. Each concept carries evidence (videos, creators), spike vs baseline, **confidence** (High/Medium/Emerging), and **lifecycle** (Emerging/Growing/Mature/Declining).

### Stage E — Adaptation (the deliverable)
Per concept: rewrite the hook for the client, a **shoot-ready script with timecodes**, recommended length/format, a **test target**, and **clickable winning-video links** for inspiration.

### Two lanes (a product decision — keep both)
- **Rising now** — recency-filtered + accelerating (trend-timing edge).
- **Proven playbook** — all-time high performers, no recency filter (evergreen replicable formats — where the strongest scripts come from).

### Trend engine (accumulated data — Phase 3)
Sound/format adoption over time → true velocity, Growing/Declining lifecycle, breakout alerts. Needs the `video_snapshots` time-series.

---

## 6. Metrics & per-platform scoring (validated — KEEP THESE)

**Rule: never rank by raw views; never use follower count as the primary benchmark.** (See PHASE0_FINDINGS §3.)

**Signals we compute (public-only):**
1. **Account-baseline outperformance** — `views ÷ creator's own median recent views`. **Primary.** ("200K from a 10K creator > 500K from a 2M creator.") A 0.8× post is not a winner even at high absolute views.
2. **Per-view engagement rates** — save-rate, share-rate, like-rate, comment-rate. **Saves + shares weighted highest** — the public *proxy for watch-time/retention* (which is private).
3. **Niche-baseline spike** — a metric ÷ the niche-sample median (cheap cross-check).
4. **Velocity (proxy)** — `views ÷ age_days` from one snapshot. True 24–72h velocity needs the time-series (Phase 3).
5. **Duration, post age, platform** — normalizers.
6. **Follower floor** (~1,000) — below it, ratios are noise. Follower count is a *filter*, never the denominator.

**Per-platform strategy (`ScoringStrategy` interface — validated split):**

| | **TikTok** | **Instagram Reels** |
|---|---|---|
| Nature | FYP-driven, follower-agnostic | follower/shareability-driven |
| Metrics inline | play, likes, comments, **shares, saves**, followers (keyword search) | likes, comments only; **views + followers via Post/Reel Info**; **no shares/saves** (use Apify scraper for shares) |
| Scoring | account-baseline outperformance + save/share-rate × reach | views/follower + like-rate |

**Permanently unavailable (private — do NOT invent):** watch time, retention, completion/skip, non-follower reach, follows generated. We proxy consumption with saves + shares and say so to clients.

Adding YouTube later = one new `ScoringStrategy` + `DataSource` mapping.

---

## 7. Trend engine (Layer 3) — how "why it's winning" scales to "what's rising"

A single video's hook is not a trend. A trend is a pattern across many recent winners, **accelerating**. Three signals, cheapest first:

1. **Trending audio/sound** — the strongest, cheapest signal. Often a trend *is* a sound. Group outliers by audio/music ID → a sound suddenly used by many recent winners = active trend. Metadata-only, no media processing.
2. **Format/hook clustering** — after Layer 2 tags each outlier (hook type, format, structure), cluster them; also embed hook text so semantically-similar angles cluster despite different wording. A dense cluster of recent winners = a format trend.
3. **The time dimension (what makes it useful)** — track, per audio-ID and per cluster, how the count of winners changes over time:
   - **Rising slope** = trend forming → *make content now, this is when it gets pushed.*
   - **Flat/declining** = saturated → *skip it.*

This is why the system must **run daily and accumulate**. One scrape = what's winning today. A trend needs the slope over days/weeks. The accumulated, timestamped history *is* the trend engine.

### Alerts / Track surface (built on Layer 3)
Mirrors UGC Pulse's "Stay ahead of what happens next":
- **Breakout** — a video's views accelerating (e.g. crossed X views in N hours). **Requires re-polling the same videos on a schedule** and diffing view counts → the most credit-hungry feature → lands last.
- **Trend rising** — hook/format cluster adopted by N new accounts.
- **Competitor** — a watchlisted account posted new content.
- **Saturation** — a format cluster's growth going negative.

---

## 8. Data model (overview)

Full DDL in DATABASE_SCHEMA.md. Entities and reasoning:

| Entity | Purpose | Notes |
|---|---|---|
| `niches` | A tracked space (e.g. "IN ecom sellers") | name, platform set, owner product |
| `queries` | Seed inputs for a niche | type: `hashtag` \| `keyword` \| `sound` \| `account`; value; platform |
| `videos` | One unique short-form video | platform, external `video_id` (unique per platform), author ref, caption, audio_id, url, `taken_at`, first_seen_at |
| `video_snapshots` | Time-series metrics per video | video_id, captured_at, view_count, like_count, comment_count, share_count?, save_count?, play_count — **append-only; powers velocity & trends** |
| `authors` | A creator account | platform, handle, follower_count?, `is_verified`, baseline metrics (median views), last_profiled_at |
| `scores` | Computed selection output | video_id, strategy, outlier_multiplier, engagement_rate, momentum, composite, computed_at |
| `analyses` | Layer 2 output (outliers only) | video_id, hook_text, hook_type, format, structure, emotional_driver, replication_score, transcript_ref, provider/model |
| `trends` | Layer 3 clusters | type: `sound` \| `format` \| `hook`; key, member videos, growth_rate, status (`rising`\|`peak`\|`declining`), niche |
| `alerts` | Track surface events | type (breakout/rising/competitor/saturation), payload, niche, created_at, read |
| `watchlist` | Accounts we follow | author_id, niche, added_by |
| `briefs` | Saved content briefs (future) | niche, angle, hook, backing videos, script |

Design notes:
- **`videos` vs `video_snapshots`** is the key split: one row per video (identity), many snapshots over time (metrics). Velocity, momentum, and the whole trend engine come from snapshots. Never overwrite metrics in place.
- **Dedupe** on `(platform, video_id)`. Ingestion upserts the video, appends a snapshot.
- Every table scoped so RLS is trivial to enable later.

---

## 9. Phasing

Detailed in ROADMAP.md. What "done" means per phase:

### Phase 0 — Data spike (no UI, ~30–40 free credits)
Validate the three riskiest assumptions cheaply, in Python scripts only:
1. **Data quality** — pull ScrapeCreators trending Reels → store raw JSON in Supabase. Is the data clean/usable?
2. **Selection affordability** — profile-lookup a sample of authors → get follower counts → test whether baseline-relative outlier scoring is computable at acceptable credit cost.
3. **Explanation works** — run the *full media pipeline* (download → Whisper → OCR → vision LLM) on ~5 outliers. Does hook extraction produce something genuinely useful?
- **Exit decision:** data good? selection affordable? hooks useful? → build the platform. If not, we learned it for 40 credits, not 40 hours.

### Phase 1 — Ingestion + Selection + Dashboard
- `DataSource` (ScrapeCreators) + `LLMProvider` interfaces.
- Scheduled ingestion for one niche (Ecombox / Reels), upsert videos + append snapshots.
- Per-platform scoring strategies → ranked outliers.
- Next.js dashboard: niches, ranked breakout list, video detail with raw metrics.

### Phase 2 — Explanation (Layer 2) + TikTok
- Media pipeline on outliers → `analyses` (hook/format/structure/replication score).
- Add TikTok as a second platform + strategy (first US product).
- Brief surface: turn an outlier + its analysis into a shot-ready angle.

### Phase 3 — Trend engine + Alerts (Layer 3)
- Sound grouping + format/hook clustering + growth-over-time.
- Rising / saturation detection; the "Stay ahead" surface.
- Breakout velocity alerts (re-polling) + competitor watchlist.

### Future (designed for, built later)
Own scrapers (replace the paid `DataSource`) · YouTube Shorts · full brief/script generation · agency multi-workspace · public SaaS wrapper.

---

## 10. Engineering rules & conventions (anti-slop core)

**Tooling — use the CLIs, don't hand-write what they generate:**
- **shadcn CLI** — `pnpm dlx shadcn@latest add <component>`.
- **Supabase CLI** — migrations, types, RLS.
- **Drizzle Kit** — `drizzle-kit generate` → review SQL → apply. Never edit a committed migration.

**Git / branching (hard rule):** never commit to `main` directly. Branch from latest `main` (`git checkout main && git pull` first), name `feat/…` `fix/…` `chore/…`, one feature per branch, open a PR, Conventional Commits.

**Code quality:** Server Components by default, `'use client'` at the leaf; no `any`, no dead/commented code, no stray `console.log`; Zod as the source of truth for I/O; RLS-ready on every table; every ingestion write is idempotent (upsert video, append snapshot — never dupe).

**Data correctness:** view/engagement counts stored as integers; snapshots are append-only; dedupe enforced on `(platform, video_id)`; credit-spend of every `DataSource` call logged (we're on metered/limited credits).

**Cost discipline (this project's specific bar):** Layer 2 (media + LLM) runs **only on outliers**, never the full feed. Every scheduled job logs credits consumed. Re-polling (breakout alerts) is opt-in per niche, not global.

**Legal posture (must hold):** public data only, never logged-in/private scraping; store *derived analysis* (metrics, transcripts, tags), not re-hosted video files; let the `DataSource` vendor absorb platform-blocking risk while we're on a paid API. This is a known gray area — the whole category operates here; we minimize exposure, we don't pretend it's white.

---

## 11. Cost model (bootstrapped — cost is a design constraint, not an afterthought)

No VC, metered credits, individual budget. Cost discipline is baked into the interfaces, not bolted on. Three cost drivers: **DataSource credits**, **transcription**, **LLM analysis** (vision tokens are the priciest). Rules below are ordered by leverage.

### Structural — enforced by design (Phase 1–2)

1. **Analyze only outliers.** Layer 2 (media + LLM) runs on the top ~2% selected by Layer 1, never on the feed. ~98% of cost avoided by construction. This is the single biggest lever.
2. **OCR the text; don't pay a vision LLM to read it.** Most UGC hooks are on-screen text. A **free local OCR** (Tesseract/PaddleOCR) extracts the words; the vision LLM is used **only** to describe visual *style* (talking head / green screen / cut rhythm), or skipped entirely when style isn't needed. Reading text via vision tokens is the most wasteful call in the system and is forbidden as the default path.
3. **Transcribe only the opening window.** The hook lives in the first ~3–5s. Run **local `faster-whisper`** (on the Render worker, $0/video, CPU) on that clip only; full transcript is computed lazily, just when structure analysis needs it.
4. **Dedupe analysis two ways:** never re-analyze the same `video_id` (cache in `analyses`); and when N videos share a sound+hook cluster, analyze **one representative**, not all N. Trend clustering collapses analysis cost.
5. **Per-task model choice in `LLMProvider`.** No single global model. Cheap model (`gpt-4o-mini` / Gemini Flash / DeepSeek) for bulk extraction; a stronger model only for ambiguous/high-value cases (a cascade). The interface takes a `task` so each step picks its own provider+model from config.
6. **Batch, don't stream.** Analysis and trend jobs are not real-time → run via the provider's **Batch API (~50% off)** overnight. Jobs are designed batchable from the start.
7. **Embeddings for clustering, not LLM calls.** Hook/format grouping uses cheap embeddings (`text-embedding-3-small`), never pairwise LLM comparison.

Plus the already-stated rule (§10): **every `DataSource` call's credit spend is logged** — we always know the burn rate.

### Volume-tuning — later (needs accumulated data, Phase 2+)

8. **Distill to a local model.** The pipeline generates `(video → analysis)` pairs for free as a byproduct. After enough volume, fine-tune a small open model (or self-host Llama/Qwen on the worker) to replace the API for bulk classification — driving per-video cost toward zero. Requires the labeled data first, so it's an endgame, not a day-one move.

**Net:** cents per *outlier*, nothing per feed video. The `LLMProvider` interface in SPEC.md carries the per-task model selection (#5) and a batch flag (#6) as first-class parameters.

---

## 12. Assumptions & open items

- Product name **TrendRadar** — confirmed. Folder: `trend-engine/`.
- **Seed niche:** Ecombox / Instagram Reels India first (highest UGC volume to validate). Then a US product on TikTok.
- **Primary discovery** = hashtag + keyword + sound; account watchlist secondary.
- **`DataSource`:** ScrapeCreators now (100 free credits); Apify as fallback; own scrapers later. Interface is vendor-agnostic.
- **`LLMProvider`:** OpenAI first (`gpt-4o-mini`/`4.1-mini`); interface is provider-agnostic.
- **Open — resolved in Phase 0:** exact credit cost of baseline-relative scoring (profile lookups per author); whether a ScrapeCreators endpoint exposes shares/saves for Reels; re-poll frequency for velocity vs credit budget.
- Render tier for the Python worker decided at deploy time; contract is host-agnostic.

---

## 13. Doc set to produce after your review

Mirrors the expense-tracker format:

1. **SPEC.md** — conventions, the two swappable interfaces (`DataSource`, `LLMProvider`), per-platform `ScoringStrategy` contract, media pipeline, anti-slop, cost/legal boundaries.
2. **DATABASE_SCHEMA.md** — full Drizzle schema, the videos/snapshots split, enums, indexes, dedupe constraints, RLS.
3. **API_CONTRACTS.md** — Next app read/write endpoints, the Python worker job contracts, `DataSource`/`LLMProvider` interfaces, Zod schemas.
4. **ROADMAP.md** — phases 0–3 with task granularity.
5. **CLAUDE_CODE_PROMPTS.md** — session opener, templates, self-audit checklist.

---

**End of PLAN.md** — review this, then I'll expand into the five detailed docs.
