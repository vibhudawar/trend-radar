"""
Phase 0 · Step 5 — CORRECTED INTENT re-test (TikTok, goal-matched).
Job-to-be-done: sell an ecommerce-seller SaaS (Ecombox). Seed = "how ecom tools/software
are pitched via UGC" (US TikTok playbook), NOT "how to sell on amazon" education.

Pipeline: keyword search -> LLM intent filter (keep product/tool PITCHES) ->
outlier rank (views/follower) -> decode hook -> ADAPT to Ecombox. Writes report_tiktok.md.

Models: gpt-5-nano (intent), gpt-5-mini (decode+adapt).
Run: python step5_intent_retest.py
"""
import json

from openai import OpenAI

from common import OPENAI_KEY, load_json, DATA

client = OpenAI(api_key=OPENAI_KEY)

ECOMBOX = ("Ecombox: a SaaS for Indian Amazon/Flipkart/Meesho sellers. It diagnoses payment "
           "leaks, fixes broken listings with AI, flags penalties, and automates inventory & "
           "shipment planning — helping sellers recover lost margin and grow revenue.")


def records():
    body = load_json("tt_raw.json")
    out = []
    for it in body["search_item_list"]:
        a = it.get("aweme_info", {})
        s = a.get("statistics", {})
        au = a.get("author", {})
        mu = a.get("added_sound_music_info") or a.get("music") or {}
        out.append({
            "aweme_id": a.get("aweme_id"),
            "handle": au.get("unique_id"),
            "followers": au.get("follower_count") or 0,
            "play": s.get("play_count") or 0,
            "likes": s.get("digg_count") or 0,
            "comments": s.get("comment_count") or 0,
            "shares": s.get("share_count") or 0,
            "saves": s.get("collect_count") or 0,
            "music": mu.get("title"),
            "desc": a.get("desc") or "",
            "url": a.get("url") or a.get("share_url"),
        })
    return out


def intent_filter(recs):
    """One gpt-5-nano call: classify each as pitch vs education/other."""
    listing = "\n".join(f'{i}: {r["desc"][:160]}' for i, r in enumerate(recs))
    prompt = (
        "You classify short-form videos by MARKETING INTENT for a tool that helps a SaaS "
        "company find reference ads. For each numbered description, decide:\n"
        "  is_pitch: true if it PROMOTES/pitches a specific software, tool, app or service the "
        "viewer should use/buy; false if it is generic education, storytime, or entertainment "
        "with no product being sold.\n"
        "  content_type: pitch | education | other\n\n"
        "Return ONLY JSON: {\"items\":[{\"idx\":int,\"is_pitch\":bool,\"content_type\":str}]}\n\n"
        f"{listing}"
    )
    r = client.chat.completions.create(
        model="gpt-5-nano",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    data = json.loads(r.choices[0].message.content)
    by_idx = {x["idx"]: x for x in data.get("items", [])}
    for i, rec in enumerate(recs):
        rec["is_pitch"] = by_idx.get(i, {}).get("is_pitch", False)
        rec["content_type"] = by_idx.get(i, {}).get("content_type", "other")
    return recs


def score(rec):
    f = rec["followers"] or 1
    rec["view_per_follower"] = round(rec["play"] / f, 2)
    eng = rec["likes"] + rec["comments"] + rec["shares"] + rec["saves"]
    rec["eng_rate"] = round(100 * eng / rec["play"], 1) if rec["play"] else 0
    # composite: reward reach-vs-audience, weight saves/shares (intent to act)
    rec["composite"] = round(rec["view_per_follower"] * (1 + rec["eng_rate"] / 100), 2)
    return rec


def decode_and_adapt(rec):
    prompt = f"""You help a marketing agency turn a winning UGC ad into a shoot-ready brief for a CLIENT.

WINNING TIKTOK (selling an Amazon-seller tool):
  caption/desc: {rec['desc']}
  metrics: {rec['play']:,} views on {rec['followers']:,} followers ({rec['view_per_follower']}x), {rec['saves']:,} saves, {rec['shares']:,} shares
  sound: {rec['music']}

CLIENT: {ECOMBOX}

Return ONLY JSON with:
  hook_type: question | POV | bold-claim | curiosity-gap | negativity | listicle | story | other
  why_it_works: one sentence on the mechanism driving views/saves
  transfer_reason: why this formula transfers to selling Ecombox
  adapted_hook: the exact opening line REWRITTEN for Ecombox (in Hinglish is fine, punchy, <=14 words)
  format: e.g. talking-head | screen-record demo | text-on-video | skit | voiceover-broll
  script: array of 3-4 beats, each {{"t":"0-2s","action":"what happens on screen"}} — shoot-ready for an Ecombox reel
  replication_score: integer 0-100 (rubric: 90+=copy in a day, 70-89=needs a specific angle, 50-69=real production, <50=hard)
"""
    r = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(r.choices[0].message.content)


def main() -> None:
    recs = [score(r) for r in records()]
    print("running intent filter (gpt-5-nano)...")
    recs = intent_filter(recs)
    pitches = [r for r in recs if r["is_pitch"]]
    print(f"total {len(recs)} -> {len(pitches)} pitches "
          f"({len(recs) - len(pitches)} education/other filtered out)")

    ranked = sorted(pitches, key=lambda r: r["composite"], reverse=True)[:6]
    out = ["# TrendRadar — corrected report (goal: sell Ecombox)", "",
           "*TikTok · query \"amazon seller software\" · intent-filtered to product pitches · "
           "adapted to Ecombox*", ""]

    for i, r in enumerate(ranked, 1):
        print(f"[{i}/{len(ranked)}] @{r['handle']}  {r['view_per_follower']}x  saves={r['saves']}  decoding...")
        d = decode_and_adapt(r)
        beats = d.get("script", [])
        script_md = "\n".join(f"  - **{b.get('t','')}** — {b.get('action','')}" for b in beats)
        out += [
            f"## {i}. @{r['handle']} — {r['view_per_follower']}× reach vs followers",
            f"**Original:** \"{r['desc'][:120]}\"  ",
            f"**Proof:** {r['play']:,} views / {r['followers']:,} followers · {r['saves']:,} saves · "
            f"{r['shares']:,} shares · {r['eng_rate']}% eng · sound: *{r['music']}*  ",
            f"[link]({r['url']})",
            "",
            f"**Why it works:** {d.get('why_it_works')}  ",
            f"**Why it transfers to Ecombox:** {d.get('transfer_reason')}  ",
            f"**Hook type:** {d.get('hook_type')} · **Format:** {d.get('format')} · "
            f"**Replication:** {d.get('replication_score')}/100",
            "",
            f"**➜ Adapted hook for Ecombox:** \"{d.get('adapted_hook')}\"",
            "",
            "**Shoot-ready script:**",
            script_md,
            "", "---", "",
        ]

    (DATA / "report_tiktok.md").write_text("\n".join(x for x in out if x is not None))
    print(f"\nreport -> {DATA / 'report_tiktok.md'}")


if __name__ == "__main__":
    main()
