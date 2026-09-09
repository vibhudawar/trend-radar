# PHASE0_FINDINGS.md — TrendRadar

> Canonical record of the Phase 0 spike (2026-09-06). Real runs against ScrapeCreators + OpenAI GPT-5, ~45 credits.
> **These validated facts override doc assumptions elsewhere.** Where PLAN/SPEC conflict with this, this wins.
> Spike code lives in `worker/scratch/` (throwaway).

## Verdict: PASS. The concept is validated across two very different products (Ecombox — India B2B ecom SaaS; Home Design AI — global consumer AI app). Proceed to Phase 1 building the CORRECTED design below.

---

## 1. The pipeline that works (end to end)

```
goal-matched query (job-to-be-done, NOT product topic)
  → keyword search (TikTok / IG reels-search)
  → filters: recency (create_time), language, min-views floor
  → intent filter (LLM): keep product/tool PITCHES, drop education/storytime
  → scoring: per-view engagement rate × reach, follower-floored  (per-platform)
  → account baseline enrichment: views ÷ creator's own median recent views = outperformance ×
  → real hook: transcript endpoint (spoken) + frames+vision (on-screen text)  — NOT the caption
  → concept clustering: group winners into recurring concepts (recurrence = credibility)
  → per concept: evidence (videos, creators), spike, confidence, lifecycle
  → adaptation: rewrite hook + shoot-ready script for the CLIENT + test target + winning-video links
```

Everything before "scoring" decides relevance; everything after decides insight quality.

---

## 2. Data reality (ScrapeCreators, verified — docs were wrong repeatedly)

### Instagram (endpoints tested)
| Endpoint | Niche-targetable | views | followers | shares/saves |
|---|---|---|---|---|
| `reels/trending` | ❌ global feed | ❌ | ❌ | ❌ |
| `v2/reels/search?query=&date_posted=` | ✅ | ❌ | ❌ | ❌ |
| `instagram/profile?handle=` | — | ❌ | ✅ | ❌ |
| `instagram/post?url=` (Post/Reel Info) | — | ✅ `video_play_count` | ✅ | ❌ never |

- **Instagram never exposes shares/saves** via ScrapeCreators. To get IG shares, use a different `DataSource` — the **Apify `apify/instagram-reel-scraper`** (returns reel shares). Kept as a swappable option.
- IG views require the per-reel detail call (`instagram/post`).

### TikTok (the richer platform)
| Endpoint | Returns |
|---|---|
| `v1/tiktok/search/keyword?query=` | play_count, digg (likes), comment, **share_count**, **collect_count (saves)**, follower_count, music, desc, create_time, url, mp4 — **all inline** (1 cr) |
| `v3/tiktok/profile/videos?handle=` | creator's recent 10 videos w/ play_count → **account baseline** (1 cr) |
| `v1/tiktok/video/transcript?url=` | spoken transcript (WEBVTT), `language` param (1 cr) |

- Param is `query` (not `keyword`); bad requests don't charge credits.
- `video_text` field is empty (0/30) → on-screen text is NOT in the API; needs frames.

---

## 3. Scoring — the corrected, per-platform model (KEEP THESE METRICS)

**Do NOT rank by raw views. Do NOT use follower count as the primary benchmark.**

### Signals we compute (public-only)
- **Account-baseline outperformance** = `views ÷ creator's own median recent views`. **Primary signal.** Proven to flip rankings correctly (a 7,225-view video at 0.8× its creator's norm is NOT a winner; a 2,646-view video at 3.1× IS). This is the "200K-from-a-10K-creator > 500K-from-a-2M-creator" rule.
- **Niche-baseline spike** = a metric (e.g. save-rate) ÷ the niche-sample median. Cheaper cross-check.
- **Per-view engagement rates**: save-rate, share-rate, like-rate, comment-rate. **Saves + shares weighted highest** — they are the public *proxy for watch-time/retention* (which is private and unscrapable).
- **Velocity (proxy)** = `views ÷ age_days` from a single snapshot. True first-24–72h velocity needs the time-series (Phase 3).
- **Duration**, **post age**, **platform** — normalizers.
- **Follower floor** (~1,000): below it, ratios are noise (an 8-follower account faked a 355× multiplier). Follower count is a *noise filter*, never the denominator.

### Per-platform strategy (validated split)
- **TikTok:** account-baseline outperformance + engagement-rate (save/share weighted) × reach. Full metric set available inline. Follower-agnostic (FYP-driven).
- **Instagram Reels:** views/follower + like-rate via Post/Reel Info; **no shares/saves** unless using the Apify scraper. More follower/shareability-driven.

### Permanently unavailable (private analytics — never scrapable; do NOT invent them)
Watch time, retention curve, 3-sec retention, completion/skip rate, non-follower reach %, follows generated. **We proxy consumption with saves + shares** and say so honestly to clients.

---

## 4. Relevance corrections

- **Seed by job-to-be-done, not product topic.** "amazon seller india" (topic) surfaced seller *education* — wrong. The client's job is *sell a SaaS to sellers*, so seed from how tools/SaaS are pitched ("amazon seller software"). Confirmed: goal-matched query → tool pitches.
- **Intent filter (LLM)** keeps only product/tool pitches, drops education/storytime. Dropped ~50% as noise in both runs. This is a core differentiator vs a generic scraper.
- **US TikTok is the reference library even for India-only products** — the SaaS-UGC-ad playbook is richer there; hooks/formats transfer, then we adapt to the client's language/market.

---

## 5. Real hooks require the video (reversing the earlier "no download")

The caption (`desc`) is NOT the hook. Proven: `@roominterio` caption = "Explore & visualize your dream home design…"; real hook (on-screen + spoken) = "In this small bedroom, just placing a bed already filled the room…". Completely different.

- **Spoken hook:** transcript endpoint (no download, 1 cr).
- **On-screen text hook:** requires opening frames → download opening seconds → extract frames (opencv, no brew/ffmpeg needed — the pip wheel bundles a decoder) → **vision model** (not plain OCR — TikTok text is stylized/animated). Sample frames ~1.5–2.5s so the fully-animated text is captured.
- Video file is transient (processed, then deleted) — aligns with the "store derived analysis, not the media" posture.

---

## 6. Insight quality — from anecdotes to evidence

- **Concept clustering:** group winners into 2–4 recurring concepts. The actionable unit is "this concept works across N creators," not "here are 6 videos."
- **Evidence per concept:** #videos, #distinct creators, median account-baseline outperformance, save-rate spike.
- **Confidence:** HIGH (≥5 videos, ≥4 creators) / MEDIUM / EMERGING.
- **Lifecycle:** Emerging / Growing / Mature / Declining. Emerging vs Mature is doable now (recency + count); Growing/Declining need the time-series (Phase 3).
- **Adaptation:** per concept → rewritten hook + format + length + shoot-ready script + **test target** + **clickable winning-video links** (for client inspiration).

---

## 7. Lanes — reach vs recency (a product decision, KEEP BOTH)

Keyword search sorts by all-time relevance, so big-reach videos are often old (the 2.99M `@roominterio` was 178 days old; a 1.7M video was 3 years old). Recency-filtering discards proven winners. Resolution — **two lanes**:
- **Rising now** — recency-filtered + accelerating. Trend-timing edge. Needs breadth (multiple queries/pages) since few fresh ones per query.
- **Proven playbook** — all-time high performers, no recency filter. Evergreen replicable formats. Where the strongest scripts come from.

---

## 8. Robustness fixes (found via failures — required in Phase 1)

- **Retry external calls** — a transient profile-videos failure blanked our best example's baseline. One dropped call must not blank a winner.
- **Cache the intent classification** — `gpt-5-nano` is non-deterministic (7 vs 11 pitches across runs). Classify once, persist, reuse. Determinism matters for a client tool.
- **Hook fallback chain** — on-screen (vision) → spoken (transcript) → caption (last resort, flagged low-fidelity).
- **Breadth for confidence** — one query/page (~30 results, ~10 pitches) is too thin for HIGH confidence. Pull multiple goal-matched queries + pages per niche.
- **Language/region filter** — Cyrillic/off-language pitches leaked in; filter per the client's market.

---

## 9. Models & cost (measured)

- **OpenAI GPT-5 family available and used:** `gpt-5-nano` (intent filter), `gpt-5-mini` (hook decode, clustering, adaptation), `gpt-4o-mini` (vision on frames). (No "5.6 luna / 5.4" — those don't exist; latest is `gpt-5.2`.)
- **Credit model:** seed 1 cr/page; per fully-scored outlier ≈ account-baseline (1) + transcript (1) = ~2 cr; run analysis/vision only on outliers. ~45 of 100 credits spent across the whole spike.
- **Stay on ScrapeCreators** (validated, complete endpoint set); `DataSource` keeps Apify/others swappable (notably Apify for IG shares).

---

## 10. Concrete changes this forces in the other docs

1. **SPEC scoring:** account-baseline outperformance as primary; per-view engagement (save/share weighted); follower floor; velocity/duration/age; per-platform strategies; retention explicitly unavailable → proxied.
2. **SPEC pipeline:** add **intent filter**, **real-hook media pipeline** (transcript + frames+vision), **concept clustering**, **adaptation**, **two lanes**, robustness (retry, cache, fallback).
3. **DATABASE_SCHEMA:** add `account baseline` on authors; `outperformance`, `velocity`, `duration`, `age` on scores/snapshots; `concepts` + `concept_members` with confidence + lifecycle; `intent`/`content_type` on videos; keep share/save columns nullable (IG null, TikTok filled).
4. **API_CONTRACTS:** `DataSource` gains `fetch_video_detail` (IG views/followers) + `fetch_author_videos` (baseline) + `fetch_transcript`; worker jobs: ingest → enrich(baseline) → hook(media) → score → cluster → adapt. Endpoint map in §2.
5. **ROADMAP:** Phase 1 builds this corrected pipeline (single niche, both lanes, concept output); time-series (true velocity, Growing/Declining lifecycle) is Phase 3.

---

## 11. Audio / discovery endpoints (verified 2026-09-10, for Phase 2.5)

Checked provider docs to enable **account mining** + **audio expansion** discovery (SPEC §4.0) and the **Trending Songs** tab (§4.5).

**ScrapeCreators — audio expansion CONFIRMED (≈1 credit each):**
- TikTok: `v1/tiktok/song/videos` (videos using a song), `v1/tiktok/song` (song detail/usage).
- Instagram: `v1/instagram/audio/reels` (reels by audio id).
- Account mining reuses the existing `v3/tiktok/profile/videos` + `instagram/profile` (returns the account's recent videos with views) — no new endpoint.
- **No top-down "trending sounds chart by region"** exists in ScrapeCreators → the Trending Songs signal is **bottom-up** (aggregate ingested `audio_id`s), which is region-scoped and niche-relevant anyway.

**Apify — optional top-down chart:** `novi/tiktok-music-trend-api` returns an official TikTok trending-sounds chart, **filterable by 2-char region code** (US, IN…), with `user_count` usage. **$45/mo + usage, TikTok-only.** Treat as an optional upgrade if the bottom-up signal proves insufficient — not required for Phase 2.5. (`apify/instagram-reel-scraper` remains the option for IG shares.)

**Verified IG metrics reality (2026-09-09):** `instagram/post` → `data.xdt_shortcode_media.video_play_count` (views) but NOT followers; `instagram/profile` → `edge_followed_by.count` (followers) AND the account baseline (median of timeline `video_play_count`) in one call. Reels candidate cost = 1 (post) + 1 (profile/creator).
