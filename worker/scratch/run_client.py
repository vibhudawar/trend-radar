"""
Reusable client run: TikTok keyword search -> intent filter -> CORRECTED TikTok scoring
(engagement-rate x reach, follower-floored) -> decode + adapt to the client -> report.

Scoring reflects Phase 0 learning: TikTok is follower-agnostic, so rank by save/share/like
RATE (saves/shares = the public proxy for retention), blended with reach, not views/followers.

Run: python run_client.py <client_key> "<search query>"
  e.g. python run_client.py homedesign "interior design app"
"""
import json
import math
import sys

from openai import OpenAI

from common import OPENAI_KEY, sc_get, save_json, DATA

client = OpenAI(api_key=OPENAI_KEY)

CLIENTS = {
    "ecombox": ("Ecombox: a SaaS for Indian Amazon/Flipkart/Meesho sellers — diagnoses payment "
                "leaks, fixes broken listings with AI, flags penalties, automates inventory. "
                "Goal: get online sellers to sign up."),
    "homedesign": ("Home Design AI (homedesignapp.ai): an AI interior-design app for designers, "
                   "homeowners, realtors and hobbyists. Upload a room photo OR a raw sketch and "
                   "instantly restyle it in 25+ styles, add/remove furniture, virtual staging, "
                   "sketch-to-render. Goal: get designers & homeowners to use the app."),
}

FLOOR = 1000  # follower floor: below this, view/engagement ratios are noise


def fetch(query: str) -> list[dict]:
    body = sc_get("/v1/tiktok/search/keyword", params={"query": query}, call="tt_search")
    save_json(f"tt_{query.replace(' ', '_')}.json", body)
    out = []
    for it in body.get("search_item_list", []):
        a = it.get("aweme_info", {})
        s = a.get("statistics", {})
        au = a.get("author", {})
        mu = a.get("added_sound_music_info") or a.get("music") or {}
        play = s.get("play_count") or 0
        if play < 200:
            continue
        out.append({
            "handle": au.get("unique_id"), "followers": au.get("follower_count") or 0,
            "play": play, "likes": s.get("digg_count") or 0,
            "comments": s.get("comment_count") or 0, "shares": s.get("share_count") or 0,
            "saves": s.get("collect_count") or 0, "music": mu.get("title"),
            "desc": a.get("desc") or "", "url": a.get("url") or a.get("share_url"),
        })
    print(f"  {len(out)} videos (credits_remaining={body.get('credits_remaining')})")
    return out


def score(r: dict) -> dict:
    p = r["play"] or 1
    like_r, save_r, share_r, comm_r = r["likes"]/p, r["saves"]/p, r["shares"]/p, r["comments"]/p
    r["like_rate"] = round(100*like_r, 1)
    r["save_rate"] = round(100*save_r, 1)
    r["share_rate"] = round(100*share_r, 1)
    # saves+shares weighted highest (retention proxy), then likes (~10% rule), then comments
    eng = 100 * (0.40*save_r + 0.35*share_r + 0.20*like_r + 0.05*comm_r)
    # blend quality (rate) with reach (log views); follower floor kills micro-account noise
    r["composite"] = 0.0 if r["followers"] < FLOOR else round(eng * math.log10(max(p, 10)), 2)
    return r


def intent_filter(recs: list[dict]) -> list[dict]:
    listing = "\n".join(f'{i}: {r["desc"][:160]}' for i, r in enumerate(recs))
    prompt = ("Classify short videos by MARKETING INTENT. For each numbered description:\n"
              "  is_pitch: true if it PROMOTES a specific app/tool/software/service the viewer "
              "should use or buy; false if generic education, storytime, or entertainment.\n"
              'Return ONLY JSON: {"items":[{"idx":int,"is_pitch":bool}]}\n\n' + listing)
    r = client.chat.completions.create(model="gpt-5-nano",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"})
    by = {x["idx"]: x for x in json.loads(r.choices[0].message.content).get("items", [])}
    for i, rec in enumerate(recs):
        rec["is_pitch"] = by.get(i, {}).get("is_pitch", False)
    return recs


def decode_adapt(r: dict, client_desc: str) -> dict:
    prompt = f"""Turn a winning UGC ad into a shoot-ready brief for a CLIENT.

WINNING TIKTOK: desc="{r['desc']}"
metrics: {r['play']:,} views / {r['followers']:,} followers · {r['saves']:,} saves · {r['shares']:,} shares · like {r['like_rate']}% save {r['save_rate']}% · sound "{r['music']}"

CLIENT: {client_desc}

Return ONLY JSON:
  hook_type: question|POV|bold-claim|curiosity-gap|negativity|listicle|story|transformation|other
  why_it_works: one sentence on the mechanism driving views/saves
  transfer_reason: why this formula transfers to the client
  adapted_hook: exact opening line rewritten for the client, punchy, <=14 words
  format: talking-head|screen-record demo|before-after|text-on-video|skit|voiceover-broll
  script: array of 3-4 beats, each {{"t":"0-2s","action":"on-screen action"}} — shoot-ready
  replication_score: integer 0-100 (90+=copy in a day, 70-89=needs an angle, 50-69=real production, <50=hard)
"""
    r2 = client.chat.completions.create(model="gpt-5-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"})
    return json.loads(r2.choices[0].message.content)


def main() -> None:
    key = sys.argv[1] if len(sys.argv) > 1 else "homedesign"
    query = sys.argv[2] if len(sys.argv) > 2 else "interior design app"
    client_desc = CLIENTS[key]

    print(f"client={key}  query='{query}'")
    recs = [score(r) for r in fetch(query)]
    recs = intent_filter(recs)
    pitches = [r for r in recs if r["is_pitch"] and r["composite"] > 0]
    print(f"  {len(pitches)} pitches after intent filter + follower floor")
    ranked = sorted(pitches, key=lambda r: r["composite"], reverse=True)[:6]

    out = [f"# TrendRadar — {key} · TikTok winners adapted", "",
           f"*query \"{query}\" · intent-filtered to product pitches · "
           f"scored by save/share/like rate × reach (follower floor {FLOOR})*", ""]
    for i, r in enumerate(ranked, 1):
        print(f"  [{i}] @{r['handle']}  eng-composite={r['composite']}  "
              f"like {r['like_rate']}% save {r['save_rate']}%  decoding...")
        d = decode_adapt(r, client_desc)
        beats = "\n".join(f"  - **{b.get('t','')}** — {b.get('action','')}" for b in d.get("script", []))
        out += [
            f"## {i}. @{r['handle']}",
            f"**Original:** \"{r['desc'][:120]}\"  ",
            f"**Proof:** {r['play']:,} views / {r['followers']:,} followers · {r['saves']:,} saves · "
            f"{r['shares']:,} shares · like {r['like_rate']}% · save {r['save_rate']}% · sound *{r['music']}*  ",
            f"[link]({r['url']})", "",
            f"**Why it works:** {d.get('why_it_works')}  ",
            f"**Why it transfers:** {d.get('transfer_reason')}  ",
            f"**Hook:** {d.get('hook_type')} · **Format:** {d.get('format')} · "
            f"**Replication:** {d.get('replication_score')}/100", "",
            f"**➜ Adapted hook:** \"{d.get('adapted_hook')}\"", "",
            "**Shoot-ready script:**", beats, "", "---", "",
        ]
    path = DATA / f"report_{key}.md"
    path.write_text("\n".join(x for x in out if x is not None))
    print(f"\nreport -> {path}")


if __name__ == "__main__":
    main()
