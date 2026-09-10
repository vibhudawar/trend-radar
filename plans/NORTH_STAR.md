# NORTH_STAR.md — what TrendRadar actually is

> The pinned product definition. If any other doc (SPEC/PLAN/ROADMAP) conflicts with this, **this wins** and the other gets fixed. Written 2026-09-10 after a deliberate reset — we had drifted into "copy competitors' conversion ads"; this steers back.

---

## 1. One line

**Show a user what content is *winning and rising* among the peers they compete with for the same audience — decode *why* it works — and hand them their own version to make.** They grow by riding what's already working in their world.

## 2. Who the user is (two personas, one model)

"Shared intent" is **not** "sells the same product." It is **same niche + same growth goal** — i.e. *who you compete with for the same audience's attention*:

| Persona | Growth goal | Their peer set = |
|---|---|---|
| **Business** (e.g. ClearTrack, a challan app) | acquire customers | other businesses in that space (challan/vehicle-compliance apps) |
| **Creator / influencer** (e.g. a fitness creator) | grow an audience | other creators in that niche (fitness/gym/nutrition creators) |

The model doesn't change between them; only the faces do. Result quality scales with **how big the peer set is** (fitness = huge/rich; challan = tiny/thin-but-real). That is honest and fine.

## 3. The one rule we broke — and the fix

**Relevance is judged at the ACCOUNT level, not the video level.**

- ❌ What we wrongly built: a per-video "is this a product *pitch*?" filter. That forced our commercial frame onto discovery and reduced the tool to "competitor conversion ads."
- ✅ The fix: classify **accounts** ("is this a shared-intent peer?"). Once an account is in the peer set, **ALL of its content counts** — the relatable skit, the meme, the educational reel, not just the "download our app" pitch. A same-intent peer's *organic* content is exactly the playbook.
- Out of scope: a random comedian's traffic skit — topically adjacent, but not a peer.

**The commercial GOAL enters only at the ADAPTATION step** ("here's how *you* ride this"), never at discovery. Mixing goal into discovery was the drift.

## 4. The pipeline (reframed)

1. **Build the peer set** (account-centric discovery). Seeds = the user's known competitors/peers (onboarding). Expand via: creators surfaced by keyword/hashtag search **then filtered to peers**, same-audio creators, and (future) related accounts. Keyword search is now a way to **find accounts**, not to pull content directly (that dragged in off-niche noise).
2. **Mine the peer set** — pull each peer's recent videos (mining = the moat: ~1 credit ≈ many videos + views + the account baseline). All content, not just pitches.
3. **Analyze — tiered (see §5).**
4. **Detect trends over time (see §6)** — the "stay ahead" intelligence.
5. **Adapt to the user** — the winning hook/format/sound → their version (hook + shoot-ready timecoded script + test target). **Goal enters here.**
6. **Deploy — the user's choice** — post organically or run it as a paid ad. Our output is **deployment-agnostic** (see §7).

Selection signal stays: **account-baseline outperformance** ("a spike, not baseline performance") is primary — never raw views. This is correct and unchanged.

## 5. Tiered analysis — "N uses across M accounts" cheaply

To say *"Hook X — 14 uses across 12 accounts"* you need a **broad corpus + hook clustering**, but deep vision on every video is too expensive. So two layers:

- **Cheap counting layer (broad):** cluster hooks using the **caption + on-screen text we already scrape** (no vision) across the *whole* peer corpus → group equivalent hooks ("almost fired me on camera" ≈ "my manager almost fired me") via embeddings/LLM → count **uses** (videos) and **accounts** (distinct creators). Accounts is the trust number (many accounts = real pattern; many videos from one account = that creator's shtick — our ≥2-creator rule).
- **Deep DNA layer (narrow):** full download + vision dissection (hook, format, structure, emotional driver, story arc, replication score) only on the **outliers/winners**.

So counts come from the cheap layer at scale; the expensive breakdown runs only where it matters. "N uses" always means *"N in the corpus we analyzed"* — a sample, not a census; bigger/fresher corpus → more accurate.

## 6. The trend engine — "stay ahead of what happens next" (the real gap)

This is the intelligence that makes it feel powerful, and it's what we're most short on. It needs **time-series** — the pipeline running repeatedly so `video_snapshots` accumulates history:

- **Rising** — a hook/format/sound being **adopted by more accounts over time** ("'POV: the app knows' adopted by 12 new accounts").
- **Breakout** — a single video **accelerating** unusually fast ("crossed 2M views in 4 hours").
- **Saturation** — a format **past peak**, engagement declining ("greenscreen nearing peak").
- **Competitor activity** — a peer **published/shifted strategy**.

Backed by `trends` / `trend_members` + snapshot velocity. Alerts are the surfacing layer. This is the priority build after the reframe lands.

## 7. Deployment & the ads question (both true)

- **Deploy on winners:** once we surface a winning creative/hook, the user can post it organically **or run it as a paid ad**. Output is deployment-agnostic — organic-first discovery *feeds* paid, it doesn't block it.
- **Ad-library as a premium CONVERSION signal (PLANNED — a later phase, after the main pipeline reframe):** competitors' Meta/TikTok ad libraries ("still running after 47 days / 18 ad variants") signal what **converts**, not just what gets reach — a stronger signal for the **business** persona. Different data source (`ad-library-teardown` skill ready). Organic outperformance = reach signal (creator persona); ad-library persistence = conversion signal (business persona). **Sequencing: fix the main pipeline first; add ad-library after.**

## 8. Creative DNA (mostly built — surface it)

Per winner, dissect and show: **hook, hook type, format, pattern, emotional driver, story arc/structure, replication score, audience signal.** We already capture most of this (`HookResult`); the gap is UI surfacing, not extraction.

## 9. What this CHANGES from the current build

- **Delete** the per-video pitch intent filter; **replace** with per-account peer classification. (Intent moves from video → account.)
- Keyword/hashtag search → **account discovery**, not direct content pull.
- Onboarding captures the **peer set** (competitors/peers you chase) + niche, not a "sell-this-product" goal that filters content. Goal is used only at adaptation.
- Add the **cheap hook-counting layer** (caption/on-screen clustering at corpus scale) alongside deep-vision-on-outliers.
- Build the **trend/time-series engine** (rising/breakout/saturation/adoption) — the headline "stay ahead" value.
- Keep, unchanged: account-baseline outperformance selection, account mining as the moat, rising/proven lanes, adapt→hook+script, evidence guardrails (winner-gate, honest tiers, no dropped winners), determinism (intent/hook caching).

## 10. Reference bar

UGCPulse (ugcpulse.app) is the quality/intelligence bar. Our engine (baseline outliers + creative DNA + account-centric discovery + adapt) already matches its foundation; the deltas are **corpus breadth**, the **cheap counting layer**, and the **time-series trend engine**. We deliberately lean **organic-first** (broader than their paid-ad focus), with ad-library as an optional conversion upgrade.
