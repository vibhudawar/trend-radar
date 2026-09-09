# ROADMAP.md — TrendRadar

> Phased build. Each phase has a goal, tasks, and a hard **exit criterion** — you don't move on until it's met. Bootstrapped: prove cheaply before building.
> Order is deliberate: validate data → selection → explanation → trend. Never build a later layer on an unvalidated earlier one.

---

## Phase 0 — Data spike (no UI) — DONE — PASSED

**Goal:** kill or confirm the riskiest assumptions with throwaway Python scripts before any product code.

**Validated** (real runs vs ScrapeCreators + OpenAI GPT-5, ~45/100 credits, two niches — see `PHASE0_FINDINGS.md`, the canonical source of truth):
- **Relevance:** goal-matched seeding (job-to-be-done, not product topic) + LLM intent filter (keep tool pitches, drop education) — dropped ~50% as noise.
- **Scoring:** account-baseline outperformance (`views ÷ creator's own median`) beats raw views and flips rankings correctly; follower count is only a noise floor, never the denominator.
- **Real hooks** come from the video (transcript + opencv frames + vision), NOT the caption — proven divergent.
- **Insight quality:** concept clustering with confidence + lifecycle turns anecdotes into evidence; per-concept adaptation (hook + shoot-ready script + winning-video links) is the deliverable.
- **Two lanes** (rising now / proven playbook) are both needed; retention/watch-time confirmed unscrapable → proxied by saves + shares.

**Exit criterion:** PASSED — concept validated end-to-end across two very different products; proceed to Phase 1 building the corrected design below.

---

## Phase 1 — Build the validated pipeline (one niche, both lanes)

**Goal:** stand up the Phase-0-validated pipeline end to end for ONE real niche, running in both lanes, surfacing evidence-backed concept cards in a dashboard.

**Tasks — db**
- `packages/db` Drizzle schema: niches, queries, authors (incl. account baseline / median recent views), videos (incl. `intent`/`content_type`, share/save columns nullable — IG null, TikTok filled), video_snapshots, scores (outperformance, velocity, duration, age), **concepts** + **concept_members** (confidence + lifecycle), credit_log. Migrations via Drizzle Kit.

**Tasks — worker (`DataSource` = ScrapeCreators)**
- `DataSource`: `search`, `fetch_video_detail` (IG views/followers), `fetch_author_videos` (baseline), `fetch_transcript`; `credit_log` on every call; **retry-once** on transient failure so one dropped call never blanks a winner.
- Job pipeline, per niche:
  1. `ingest` — keyword search + filters (recency via `create_time`, language/region, min-views floor).
  2. `intent_filter` — LLM keeps product/tool pitches, drops education/storytime; **cached by video_id** (classify once, persist, reuse — the classifier is non-deterministic).
  3. `score` — engagement-rate (saves/shares weighted) × reach + **account-baseline outperformance** (primary), follower floor (~1,000) as a noise filter only. Never rank by raw views.
  4. `hook` — real hook from the video: transcript (spoken) + opencv frames + vision (on-screen text); fallback chain on-screen → spoken → caption (last resort, flagged low-fidelity).
  5. `cluster` — group winners into recurring concepts with evidence counts, confidence (HIGH/MEDIUM/EMERGING), lifecycle (Emerging/Mature now; Growing/Declining in Phase 3).
  6. `adapt` — per concept: rewritten hook + shoot-ready script + test target + clickable winning-video links.
- Run the whole pipeline in **two lanes**: **rising now** (recency-filtered + accelerating) and **proven playbook** (all-time performers, no recency filter).
- Analysis/vision run on **outliers only**. Unit tests on scoring math + dedupe.

**Tasks — web**
- Next.js app scaffold, shadcn, Drizzle client, Supabase auth (single workspace).
- Niches list + create; queries add/toggle (Server Actions).
- **Concept cards per lane:** name, pattern, confidence, lifecycle, evidence counts (#videos, #creators), median outperformance.
- **Concept detail:** adapted hook, shoot-ready script, clickable winning-video links.
- Burn-rate tile (`credit_log`).

**Exit criterion:** for a real niche, the dashboard shows evidence-backed concept cards with correct account-baseline outperformance and real hooks (from the video, not the caption), in both lanes, within a known credit budget.

---

## Phase 2 — Breadth + robustness

**Goal:** widen the sample so concepts reach HIGH confidence, add a second platform, and harden determinism and the deliverable.

**Tasks**
- **Breadth:** multiple goal-matched queries + pages per niche (one query/page ~30 results, ~10 pitches is too thin for HIGH confidence).
- **Second platform — Instagram Reels:** `reels/search` for discovery, per-reel `instagram/post` (Post/Reel Info) for views/followers; IG never exposes shares/saves, so add the **Apify `instagram-reel-scraper`** as a swappable `DataSource` when IG shares are needed.
- **Caching / determinism hardening:** persist intent classification and derived analysis; make repeat runs stable for a client-facing tool.
- **Brief/script refinement:** improve adapted hook + shoot-ready script quality (angle, format, length, test target).

**Exit criterion:** for a real niche the tool produces HIGH-confidence concepts from a broad sample; Instagram Reels ingests and ranks alongside TikTok; repeat runs are deterministic and cost stays within the credit budget.

---

## Phase 3 — Time-series + Trend engine + Alerts

**Goal:** the "Stay ahead of what happens next" surface — powered by accumulated `video_snapshots` history, so lifecycle and velocity become real rather than proxied.

**Tasks**
- **Time-series:** use the `video_snapshots` history for true 24–72h velocity (not the single-snapshot `views ÷ age` proxy) and real **Growing/Declining** lifecycle on concepts.
- `trend` job: sound grouping (by `audio_id`) + hook/format embedding clusters + growth-rate over time → sound/format adoption trends with status (rising / peak / declining).
- Trends board UI (rising / peak / declining + growth sparkline).
- **Breakout alerts:** fire on genuine accelerations; opt-in re-polling per niche, daily credit ceiling, pause-on-ceiling. Most credit-hungry feature — gated last.
- Watchlist management UI.

**Exit criterion:** the trends board correctly flags at least one real rising trend and one saturating format in a live niche using time-series data, and breakout alerts fire on genuine accelerations without blowing the credit ceiling.

---

## Future (designed for, not scheduled)

- **`OwnScraperSource`** — replace the paid DataSource (revisit legal/proxy posture in SPEC §9 first).
- **YouTube Shorts** — one new `DataSource` mapping + `ScoringStrategy`.
- **Full brief/script generation** — shot-ready scripts with timecodes (the Create layer of the reference product).
- **Distill-to-local model** (PLAN §11.8) — fine-tune on accumulated `(video → analysis)` pairs to cut LLM cost toward zero.
- **Agency multi-workspace + public SaaS wrapper** — enable RLS enforcement, billing, onboarding.

---

## Cross-cutting (every phase)

- Never commit to `main`; branch + PR per feature (SPEC §10).
- Every DataSource/LLM call logged; burn-rate visible.
- High-value tests only: scoring, dedupe, field-mapping, trend math.
- **Never rank by raw views**; account-baseline outperformance is primary. **Follower count is only a floor** (~1,000), never the denominator.
- **Retention/watch-time is unscrapable** — proxy with saves + shares and say so honestly.
- Analysis/vision run **on outliers only**; **retry external calls** once; **cache by video_id** (intent + derived analysis) for determinism.
- Public data only; store derived analysis, delete source media.

---

**End of ROADMAP.md**
