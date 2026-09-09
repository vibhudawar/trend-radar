"""
Best-results report: concept clustering + account baseline + velocity + duration + video links.
Implements the spec's #1 signal — outperformance vs the CREATOR'S OWN baseline (not raw views).

Per video: views, account baseline (median of creator's recent 10), outperformance x, velocity
(views/day), duration. Per concept: evidence across creators, confidence, lifecycle, adapted script.

Run: python build_report.py <client_key> "<query used earlier>" [maxPitches]
"""
import datetime as dt
import json
import statistics as st
import sys

import requests

from common import OPENAI_KEY, SC_KEY, SC_BASE, sc_get, load_json, DATA
from run_client import CLIENTS, score, intent_filter
from run_client_real import cyrillic_share, spoken_hook, onscreen_text
from build_concepts import cluster, adapt, confidence

NOW = dt.datetime.utcnow().timestamp()
_baseline_cache: dict[str, int | None] = {}


def load_records(query: str) -> list[dict]:
    body = load_json(f"tt_{query.replace(' ', '_')}.json")
    out = []
    for it in body.get("search_item_list", []):
        a = it.get("aweme_info", {}); s = a.get("statistics", {}); au = a.get("author", {})
        mu = a.get("added_sound_music_info") or a.get("music") or {}
        v = a.get("video", {}) or {}
        mp4 = None
        for br in (v.get("bit_rate") or []):
            ul = (br.get("play_addr", {}) or {}).get("url_list") or []
            if ul:
                mp4 = ul[0]; break
        dur = v.get("duration") or a.get("duration") or 0
        dur = round(dur / 1000) if dur > 1000 else dur  # ms -> s
        ct = a.get("create_time")
        out.append({
            "handle": au.get("unique_id"), "followers": au.get("follower_count") or 0,
            "play": s.get("play_count") or 0, "likes": s.get("digg_count") or 0,
            "comments": s.get("comment_count") or 0, "shares": s.get("share_count") or 0,
            "saves": s.get("collect_count") or 0, "music": mu.get("title"),
            "desc": a.get("desc") or "", "url": a.get("url"), "mp4": mp4,
            "create_time": ct, "duration_s": dur,
            "age_days": round((NOW - ct) / 86400) if ct else None,
        })
    return out


def account_baseline(handle: str) -> int | None:
    if handle in _baseline_cache:
        return _baseline_cache[handle]
    try:
        b = sc_get("/v3/tiktok/profile/videos", params={"handle": handle, "trim": "true"},
                   call="profile_videos")
        views = [(x.get("statistics") or {}).get("play_count") for x in (b.get("aweme_list") or [])]
        views = [v for v in views if v]
        val = int(st.median(views)) if views else None
    except Exception:  # noqa: BLE001
        val = None
    _baseline_cache[handle] = val
    return val


def lifecycle(members: list[dict]) -> str:
    ages = [m["age_days"] for m in members if m["age_days"] is not None]
    if not ages:
        return "Unknown"
    med_age = st.median(ages)
    n = len(members)
    # heuristic (Growing/Declining need time-series; approximated by recency + volume)
    if med_age <= 21 and n >= 2:
        return "Emerging"
    if med_age <= 45:
        return "Growing"
    if n >= 5:
        return "Mature"
    return "Declining"


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "homedesign"
    query = sys.argv[2] if len(sys.argv) > 2 else "interior design app"
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 12

    recs = [r for r in load_records(query) if r["play"] >= 200 and cyrillic_share(r["desc"]) < 0.3]
    recs = intent_filter([score(r) for r in recs])
    pitches = sorted([r for r in recs if r["is_pitch"] and r["composite"] > 0],
                     key=lambda r: r["composite"], reverse=True)[:cap]
    print(f"{len(pitches)} pitches -> enriching (baseline, velocity, real hooks)...")

    for i, r in enumerate(pitches, 1):
        r["spoken"] = spoken_hook(r["url"]) if r["url"] else ""
        r["onscreen"], r["seen_format"] = onscreen_text(r["mp4"]) if r["mp4"] else ("", "")
        base = account_baseline(r["handle"])
        r["baseline"] = base
        r["outperf"] = round(r["play"] / base, 1) if base else None
        r["velocity"] = round(r["play"] / r["age_days"]) if r["age_days"] else None
        print(f"  [{i}] @{r['handle']:18s} views={r['play']:>9,} base={base or '?':>9} "
              f"outperf={r['outperf']}x vel={r['velocity']}/d dur={r['duration_s']}s")

    niche_med_save = st.median([r["save_rate"] for r in pitches]) or 0.01
    concepts = cluster(pitches)
    print(f"\n{len(concepts)} concepts")

    out = [f"# TrendRadar — {key} · Winning concepts (account-baseline scored)", "",
           f"*query \"{query}\" · {len(pitches)} pitches · outperformance = views ÷ the creator's "
           f"OWN median · spike = save-rate vs niche median ({niche_med_save:.1f}%)*", ""]
    rows = []
    for c in concepts:
        members = [pitches[i] for i in c.get("member_idxs", []) if i < len(pitches)]
        if members:
            rows.append((len(members), c, members))
    rows.sort(key=lambda x: x[0], reverse=True)

    for n, c, members in rows:
        accounts = {m["handle"] for m in members}
        outs = [m["outperf"] for m in members if m["outperf"]]
        med_out = round(st.median(outs), 1) if outs else None
        med_save = round(st.median([m["save_rate"] for m in members]), 1)
        med_dur = round(st.median([m["duration_s"] for m in members if m["duration_s"]]) or 0)
        a = adapt(c, members, CLIENTS[key])
        beats = "\n".join(f"  - **{b.get('t','')}** — {b.get('action','')}" for b in a.get("script", []))
        ex = []
        for m in sorted(members, key=lambda m: (m["outperf"] or 0), reverse=True)[:5]:
            ex.append(f"  - [@{m['handle']}]({m['url']}) — **{m['play']:,} views** · "
                      f"baseline {m['baseline']:,} = **{m['outperf']}× their norm** · "
                      f"{m['velocity']:,}/day · save {m['save_rate']}% · {m['duration_s']}s  "
                      if m["baseline"] else
                      f"  - [@{m['handle']}]({m['url']}) — {m['play']:,} views · "
                      f"save {m['save_rate']}% · {m['duration_s']}s (no baseline)  ")
        out += [
            f"## {c['name']}",
            f"**Confidence: {confidence(n, len(accounts))} · Lifecycle: {lifecycle(members)}**",
            f"- {n} videos across {len(accounts)} creators",
            f"- median **{med_out}× the creator's own baseline**" if med_out else "- baseline n/a",
            f"- median save-rate {med_save}% ({round(med_save/niche_med_save,1)}× niche) · "
            f"typical length {med_dur}s",
            f"- **Formula:** {c['pattern']}", "",
            "**▶ Winning videos (watch for inspiration):**", *ex, "",
            f"**➜ Adapted for {key}:** \"{a.get('adapted_hook')}\"  ",
            f"**Format:** {a.get('format')} · **Length:** {a.get('length_s')}s · "
            f"**Test:** {a.get('test_target')}", "",
            "**Shoot-ready script:**", beats, "", "---", "",
        ]
    path = DATA / f"report_{key}_final.md"
    path.write_text("\n".join(x for x in out if x is not None))
    print(f"report -> {path}")


if __name__ == "__main__":
    main()
