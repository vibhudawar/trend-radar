"""
Accurate client run: reuses a cached TikTok search, applies recency + language filters,
CORRECTED engagement-rate scoring, then reads the REAL hook per outlier
(spoken transcript endpoint + on-screen text via frames+vision) — NOT the caption.

Run: python run_client_real.py <client_key> "<query used earlier>" [days] [topN]
  e.g. python run_client_real.py homedesign "interior design app" 60 6
"""
import base64
import datetime as dt
import json
import math
import re
import sys

import cv2
import requests
from openai import OpenAI

from common import OPENAI_KEY, sc_get, load_json, DATA, MEDIA
from run_client import CLIENTS, FLOOR, score, intent_filter

client = OpenAI(api_key=OPENAI_KEY)
HDRS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.tiktok.com/"}
CYRILLIC = re.compile(r"[Ѐ-ӿ]")


def records(query):
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
        out.append({
            "handle": au.get("unique_id"), "followers": au.get("follower_count") or 0,
            "play": s.get("play_count") or 0, "likes": s.get("digg_count") or 0,
            "comments": s.get("comment_count") or 0, "shares": s.get("share_count") or 0,
            "saves": s.get("collect_count") or 0, "music": mu.get("title"),
            "desc": a.get("desc") or "", "url": a.get("url"), "mp4": mp4,
            "create_time": a.get("create_time"),
        })
    return out


def cyrillic_share(t):
    letters = [c for c in t if c.isalpha()]
    return (sum(bool(CYRILLIC.match(c)) for c in letters) / len(letters)) if letters else 0


def spoken_hook(url):
    try:
        tr = sc_get("/v1/tiktok/video/transcript", params={"url": url}, call="tt_transcript")
        vtt = tr.get("transcript") or tr.get("text") or ""
        lines = [l.strip() for l in vtt.splitlines()
                 if l.strip() and "-->" not in l and l.strip() != "WEBVTT"]
        return " ".join(lines[:3])
    except Exception:  # noqa: BLE001
        return ""


def onscreen_text(mp4_url):
    try:
        r = requests.get(mp4_url, headers=HDRS, timeout=120)
        if r.status_code != 200 or len(r.content) < 5000:
            return "", ""
        p = MEDIA / "tmp.mp4"; p.write_bytes(r.content)
        cap = cv2.VideoCapture(str(p)); fps = cap.get(cv2.CAP_PROP_FPS) or 30
        imgs = []
        for t in (1.0, 1.8, 2.6):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps)); ok, fr = cap.read()
            if ok:
                ok2, buf = cv2.imencode(".jpg", cv2.resize(fr, (0, 0), fx=0.5, fy=0.5))
                if ok2:
                    imgs.append(base64.b64encode(buf).decode())
        cap.release(); p.unlink(missing_ok=True)
        if not imgs:
            return "", ""
        content = [{"type": "text", "text":
            "First seconds of a TikTok. Return JSON {\"onscreen_text\":\"the FULL text overlaid "
            "on screen, verbatim\",\"format\":\"talking-head|before-after|screen-record|"
            "text-on-video|voiceover-broll\"}"}]
        for b in imgs:
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}})
        resp = client.chat.completions.create(model="gpt-4o-mini",
            messages=[{"role": "user", "content": content}],
            response_format={"type": "json_object"})
        d = json.loads(resp.choices[0].message.content)
        return d.get("onscreen_text", ""), d.get("format", "")
    except Exception:  # noqa: BLE001
        return "", ""


def decode_adapt(r, client_desc):
    prompt = f"""Turn a winning UGC ad into a shoot-ready brief for a CLIENT. The REAL hook is the
on-screen text and/or the spoken opening — NOT the caption (caption is context only).

WINNING TIKTOK:
  ON-SCREEN TEXT (the overlay hook): {r['onscreen'] or '(none detected)'}
  SPOKEN OPENING: {r['spoken'] or '(no speech)'}
  caption (context): {r['desc']}
  metrics: {r['play']:,} views / {r['followers']:,} followers · {r['saves']:,} saves · like {r['like_rate']}% save {r['save_rate']}% · format {r['seen_format']}

CLIENT: {client_desc}

Return ONLY JSON:
  real_hook: the actual opening hook as it appears in the video (on-screen or spoken), verbatim
  hook_type: question|POV|bold-claim|curiosity-gap|negativity|listicle|story|transformation|other
  why_it_works: one sentence
  adapted_hook: the real_hook rewritten for the client, punchy, <=14 words
  format: {r['seen_format'] or 'talking-head|before-after|screen-record|text-on-video'}
  script: array of 3-4 beats, each {{"t":"0-2s","action":"on-screen action"}}
  replication_score: integer 0-100
"""
    resp = client.chat.completions.create(model="gpt-5-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"})
    return json.loads(resp.choices[0].message.content)


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "homedesign"
    query = sys.argv[2] if len(sys.argv) > 2 else "interior design app"
    days = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    topn = int(sys.argv[4]) if len(sys.argv) > 4 else 6
    cutoff = dt.datetime.utcnow().timestamp() - days * 86400

    recs = records(query)
    total = len(recs)
    recs = [r for r in recs if r["play"] >= 200]
    recs = [r for r in recs if r["create_time"] and r["create_time"] >= cutoff]      # recency
    recs = [r for r in recs if cyrillic_share(r["desc"]) < 0.3]                       # language
    print(f"{total} videos -> {len(recs)} after recency(<{days}d)+language+play filters")
    recs = [score(r) for r in recs]
    recs = intent_filter(recs)
    pitches = sorted([r for r in recs if r["is_pitch"] and r["composite"] > 0],
                     key=lambda r: r["composite"], reverse=True)[:topn]
    print(f"{len(pitches)} pitches -> reading REAL hooks (transcript + frames+vision)...")

    out = [f"# TrendRadar — {key} · REAL hooks (transcript + on-screen text)", "",
           f"*query \"{query}\" · last {days}d · English · save/share/like-rate × reach · "
           f"hooks read from the VIDEO, not the caption*", ""]
    for i, r in enumerate(pitches, 1):
        r["spoken"] = spoken_hook(r["url"]) if r["url"] else ""
        r["onscreen"], r["seen_format"] = onscreen_text(r["mp4"]) if r["mp4"] else ("", "")
        print(f"  [{i}] @{r['handle']}  onscreen='{r['onscreen'][:40]}'  spoken='{r['spoken'][:40]}'")
        d = decode_adapt(r, CLIENTS[key])
        beats = "\n".join(f"  - **{b.get('t','')}** — {b.get('action','')}" for b in d.get("script", []))
        out += [
            f"## {i}. @{r['handle']}",
            f"**Proof:** {r['play']:,} views / {r['followers']:,} followers · {r['saves']:,} saves · "
            f"like {r['like_rate']}% · save {r['save_rate']}% · sound *{r['music']}*  ",
            f"[link]({r['url']})", "",
            f"**REAL hook (on-screen):** {r['onscreen'] or '—'}  ",
            f"**REAL hook (spoken):** {r['spoken'] or '—'}  ",
            f"**Caption (was wrongly used):** {r['desc'][:90]}", "",
            f"**Decoded hook:** \"{d.get('real_hook')}\" — *{d.get('hook_type')}*  ",
            f"**Why it works:** {d.get('why_it_works')}  ",
            f"**Format:** {d.get('format')} · **Replication:** {d.get('replication_score')}/100", "",
            f"**➜ Adapted hook for {key}:** \"{d.get('adapted_hook')}\"", "",
            "**Shoot-ready script:**", beats, "", "---", "",
        ]
    path = DATA / f"report_{key}_real.md"
    path.write_text("\n".join(x for x in out if x is not None))
    print(f"\nreport -> {path}")


if __name__ == "__main__":
    main()
