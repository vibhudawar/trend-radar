# CLAUDE_CODE_PROMPTS.md — TrendRadar

> How to drive the build with an AI coding agent without producing slop. Session opener, per-phase task templates, and a self-audit checklist.
> The plans in this folder are the contract. When in doubt, the agent reads them, not its assumptions.

---

## 1. Session opener (paste at the start of every session)

```
You are building TrendRadar. Before writing anything, read:
  plans/PLAN.md, plans/SPEC.md, plans/DATABASE_SCHEMA.md,
  plans/API_CONTRACTS.md, plans/ROADMAP.md

Rules that override your defaults:
- No slop. Precise over complete. No dead/commented code, no console.log, no `any`.
- Server Components by default; 'use client' at the leaf only.
- The web app NEVER calls a DataSource or LLMProvider — only the worker does.
- Ingestion is idempotent: upsert video on (platform, video_id), APPEND a snapshot. Never overwrite metrics.
- Every DataSource call logs to credit_log. Every LLM call (Phase 2+) logs to llm_log.
- Layer 2 (media + LLM) runs ONLY on outliers with a qualifying scores row.
- OCR reads text (local, free); vision LLM describes style only — never send frames to read text.
- Never commit to main. Branch feat/…, one feature per branch, open a PR, Conventional Commits.
- Use the CLIs: shadcn, Supabase, Drizzle Kit. Never hand-write what they generate. Never edit a committed migration.
- Tests: high-value only (scoring, dedupe, field-mapping, trend math). Skip boilerplate.

State which phase (ROADMAP.md) and which task you are on before coding. Ask if a decision isn't in the docs.
```

---

## 2. Per-task template

```
Phase: <n>  Task: <name from ROADMAP.md>
Goal: <one line — what "done" looks like>
Touches: <files/dirs, e.g. worker/jobs/ingest.py, packages/db/schema.ts>
Contracts: <the relevant SPEC/API_CONTRACTS section>
Out of scope: <what NOT to touch>
Definition of done:
  - <observable behavior>
  - <test(s) added, if high-value>
  - <credit/LLM logging wired, if applicable>
```

---

## 3. Phase-specific prompts

### Phase 0 — spike (throwaway, no product code)
```
Write a standalone Python script (worker/scratch/) that:
1. Calls ScrapeCreators trending reels, writes raw JSON to a scratch table + logs credits.
2. Reports duplicate rate and field coverage (which of share/save/follower are null).
3. On ~10 authors, fetches profile, computes trial outlier_multiplier, prints credits spent per outlier.
4. On ~5 outliers, runs download → faster-whisper (opening 5s) → OCR keyframes → HOOK_EXTRACT, prints results.
This is throwaway. Do not build interfaces or tables yet beyond the scratch table. Optimize for learning, not reuse.
```

### Phase 1 — ingestion + selection + dashboard
```
Implement per ROADMAP Phase 1. Start with packages/db schema (niches, queries, authors,
videos, video_snapshots, scores, credit_log) via Drizzle Kit — generate, review SQL, apply.
Then worker: DataSource interface + ScrapeCreatorsSource, ingest job (idempotent upsert+append),
selective profile job, ReelsStrategy + score job with flag handling. Unit-test scoring + dedupe.
Then web: niches CRUD, breakout table, video detail with snapshot chart, burn-rate tile.
Do NOT implement analysis, TikTok, trends, or alerts.
```

### Phase 2 — explanation + TikTok
```
Implement per ROADMAP Phase 2. Media pipeline (local whisper/OCR, keyframe downsample),
analyze job (outliers only, cache, cluster-representative dedupe, batch API, llm_log),
analyses table + UI card, per-task LLMProvider model config, TikTok source mapping + TikTokStrategy.
Guard: analysis refuses any video without a qualifying scores row.
```

### Phase 3 — trends + alerts
```
Implement per ROADMAP Phase 3. trend job (sound grouping + hook/format embedding clusters +
growth-rate), trends board, alert job (rising/saturation/competitor), alerts feed,
opt-in breakout re-polling with per-niche daily credit ceiling. Re-polling must pause+log on ceiling.
```

---

## 4. Self-audit checklist (agent runs before opening a PR)

**Correctness**
- [ ] Ingestion upserts on `(platform, video_id)` and appends a snapshot — no in-place metric overwrite.
- [ ] Dedupe within a pull handled; duplicate rate sane.
- [ ] Scoring stores all components + flag, not just composite.
- [ ] Missing fields are `None`/nullable, never faked to 0.

**Cost/legal**
- [ ] Every DataSource call logs credits. (Phase 2+) every LLM call logs spend.
- [ ] Layer 2 runs only on outliers; guard present.
- [ ] OCR reads text; vision only for style; keyframes downsampled.
- [ ] No source video persisted beyond processing.
- [ ] Re-polling (Phase 3) is opt-in with a ceiling.

**Code quality**
- [ ] No `any`, no dead/commented code, no stray `console.log`/`print` debug.
- [ ] Server Components by default; `'use client'` at the leaf.
- [ ] Web app doesn't import worker code or call DataSource/LLM directly.
- [ ] Files < 300 lines, components < 150.
- [ ] High-value tests added (scoring/dedupe/mapping/trend math); no boilerplate tests.

**Process**
- [ ] On a `feat/…` branch off latest `main`, not `main`.
- [ ] Migrations generated by Drizzle Kit, reviewed, not hand-edited.
- [ ] shadcn components added via CLI.
- [ ] Conventional Commit messages.

---

## 5. When the agent should stop and ask

- A needed decision isn't in the plans (e.g. a scoring weight, a retention window, a new enum value).
- A `DataSource` field the plan assumed is missing or shaped differently than SPEC §2.3 says.
- A task would exceed a credit ceiling or require a paid tier not yet approved.
- Anything touching the legal posture (private data, storing media, own-scraper).

Do not guess on these. A wrong assumption here is expensive (credits) or risky (legal).

---

**End of CLAUDE_CODE_PROMPTS.md**
