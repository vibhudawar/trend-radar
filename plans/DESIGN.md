# DESIGN.md — TrendRadar UI/UX (source of truth for product design)

> Owns look, feel, flow, and interaction. If it conflicts with SPEC §6, this wins and SPEC gets a pointer.
> No slop. Premium, opinionated, evidence-led. Every screen earns the next click.

---

## 0. The role (design lens — apply to every UI decision)

**You are the Director of Product & Design at a YC-backed, billion-dollar startup.** You have shipped products used by millions and you know that great UX is not decoration — it is *removing every gram of friction between a user and their next win*. You design interfaces that are **obvious to point at, fast to trust, and effortless to convert**. You cut steps, pre-fill everything you can, speak in the user's language, and let evidence do the persuading. You have taste: restraint over ornament, hierarchy over density-for-its-own-sake, motion with purpose. You never ship a screen where the user has to wonder "what do I do now?"

Design target: **customer-facing SaaS polish** (even while used internally) — premium and guided at the decision moments, dense and powerful where an analyst is working.

---

## 1. North stars (rank ties by these)

1. **Time-to-first-winning-idea.** The whole product is judged on how fast a new user gets from "paste my URL" to "here's the exact video to make, and proof it works." Optimize the funnel to that moment.
2. **Point-and-it-converts.** Every screen has ONE obvious primary action. The user should never hunt. The payoff screen answers *"which video do I make?"* in one glance.
3. **Trust through evidence, not claims.** Every recommendation shows its receipts (real winning videos, outperformance ×, creator count). Numbers are clickable to their underlying videos. Honest flags (`no_baseline`, `approximated`) shown, never hidden.
4. **Premium restraint.** Spacious at decision points, dense only where power users want data. One accent color with meaning. Subtle, purposeful motion. Never busy.

---

## 2. Principles (the how)

- **Show, don't ask.** AI pre-fills from the URL; the user edits, never fills a blank form. Default to the smart guess.
- **Progressive disclosure.** Show the 20% everyone needs; tuck the power-user 80% behind "Advanced / Add competitors / Edit keywords." A first-timer sees a short, calm screen.
- **One primary action per screen.** Secondary actions are quiet (ghost/link). Destructive actions are guarded.
- **Plain language, zero jargon.** "Winning videos," "above the creator's norm," "post this to ride the wave" — never "outperformance coefficient." Labels are self-explaining (a new user needs no docs).
- **Fast *perceived* performance.** Optimistic UI, skeletons (never bare spinners), streamed results (concepts appear as the worker writes them). A visible, friendly progress state during runs.
- **Cost is never a surprise.** Any action that spends credits states the estimate *before* the click ("Run analysis — ~20 credits"). No silent spend.
- **Empty states sell the next action.** Never a dead end — "No projects yet → Onboard your first business" with the CTA right there.
- **Accessible by default.** WCAG AA contrast in dark *and* light, full keyboard paths, focus rings, respects reduced-motion.

---

## 3. Onboarding — the single smart screen (decided)

One screen, four states, no wizard. This is the magic moment — nail it.

1. **Empty / invite** — a calm hero: one big input, "Paste your product URL," a single primary button "Analyze." One line of reassurance ("We'll read your site and set everything up — you just review."). Nothing else on screen.
2. **Analyzing** — the button becomes a lively progress state (skeletonized profile card filling in), copy like "Reading your site… finding your audience… drafting seed queries." Feels like the product is working *for* them (2–5s).
3. **Review (the payoff of onboarding)** — an **inline-editable profile card**, every field pre-filled: name, what you sell, audience, goal, **region (required — user sets it, we never guess; if empty, gently block with "Where are your customers?")**, seed keywords (editable chips), and **AI-suggested competitors** as one-click-add chips. Everything editable in place (click to edit, autosave feel). Primary action: **"Create project."**
   - **Progressive disclosure:** "Add competitors / your own accounts / advanced keywords" expanders — optional, collapsed by default. Competitors are framed as *"we'll also learn from these — and still surface creators you don't know yet"* (additive, never a filter).
4. **Created → first-run CTA** — land on the project with a prominent, cost-transparent **"Run analysis (~N credits)"** — we do **not** auto-spend. A one-line explainer of what they'll get.

Onboarding must be completable in **under 60 seconds** with only a URL + region. Every extra field is optional and pre-filled.

---

## 4. The conversion moment — "which video do I make?"

The concept board is the product's payoff. Design rules:
- **Recommended pick, front and center.** One card flagged "⚡ Act this week" (Rising) / "🛡 Safest bet" (Proven) with "start with this one." Reduce choice paralysis.
- **Hook is the hero.** The adapted hook line, big, in quotes ("say this in the first 2 seconds"). Everything else is support.
- **Evidence inline, script on demand.** Creator count, winning-video count, "× above the creator's norm" always visible; the shoot-ready script and example videos behind one tap (progressive disclosure).
- **One primary action per card:** the implicit "make this." Keep secondary (copy script, open examples) quiet.
- **Two lanes stay legible:** Rising = "fresh, post fast." Proven = "reliable, safe to copy." A one-line how-to banner, plain language.

---

## 5. Information architecture

- **Left sidebar (inset):** **Projects** (per-business), **Trending Songs** (global, region-filterable — §SPEC 4.5), and later Trends/Alerts. Wordmark top; user menu (theme switch, sign out) bottom.
- **Project view:** header (name, platforms, region, last-run + credit cost), the **Rising / Proven** concept board, seed queries, and a quiet burn-rate indicator.
- **Trending Songs (global tab):** a ranked, region-filterable list of sounds — usage, median outperformance, rising/mature badge, example clips; each row opens the videos using it. Suggestion copy = "use this trending sound."
- Everything owner-scoped (per-user private).

---

## 6. Visual language

- **Dark theme primary** (long review sessions), first-class **light mode**. Both AA-contrast. next-themes; theme switcher in the user menu.
- **Foundation:** shadcn (base-nova), inset sidebar, existing tokens. Continuity with what's shipped — refine, don't reinvent.
- **Color with meaning:** neutral surfaces; **one accent** for rising/positive (green), one warning (amber) for saturation/low-confidence, brand chips for platform. Confidence uses the existing green/blue/amber scale. Never color as decoration.
- **Typography:** clear hierarchy, compact numbers (`2.4M`, `15.4%`), generous line-height in copy, tight in data tables.
- **Motion:** subtle and purposeful — skeleton fills, the analyzing state, gentle card reveals as concepts stream in. Respect `prefers-reduced-motion`. No gratuitous animation.
- **Density gradient:** spacious at decision points (onboarding, recommended pick), dense in the breakout data table.

---

## 7. Anti-slop (never ship)

- Bare spinners (use skeletons), walls of empty form fields, jargon labels, vanity metrics, dead-end empty states, silent credit spend, more than one competing primary action, decorative color, unlabeled icons, or a screen a first-timer can't navigate without explanation.

---

**End of DESIGN.md**
