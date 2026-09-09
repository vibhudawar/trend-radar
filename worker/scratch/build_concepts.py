"""
Prototype: turn N winning videos into RECURRING CONCEPTS with evidence.
- reads real hooks (transcript + on-screen text) for the pitches
- clusters them into named concepts (recurrence = credibility)
- per concept: #videos, #distinct accounts, median save-rate, x above niche median (spike),
  confidence, and one adapted shoot-ready script for the client
Writes report_<client>_concepts.md

Run: python build_concepts.py <client_key> "<query used earlier>" [maxPitches]
"""
import json
import statistics as st
import sys

from openai import OpenAI

from common import OPENAI_KEY, DATA
from run_client import CLIENTS, score, intent_filter
from run_client_real import records, cyrillic_share, spoken_hook, onscreen_text

client = OpenAI(api_key=OPENAI_KEY)


def cluster(items):
    payload = [{"i": i, "hook": (it["onscreen"] or it["spoken"] or it["desc"])[:180],
                "format": it["seen_format"], "save_rate": it["save_rate"]} for i, it in enumerate(items)]
    prompt = (
        "You are a UGC strategist. Below are winning short-video ads (their REAL hooks). "
        "Group them into 2-4 RECURRING CONCEPTS — a concept is a repeatable hook+angle pattern "
        "(e.g. 'AI-replaces-the-expert bold claim', 'messy-room before/after transformation'). "
        "Every video must map to exactly one concept; ignore none.\n"
        'Return ONLY JSON: {"concepts":[{"name":str,"pattern":str (the repeatable formula in one '
        'line),"member_idxs":[int]}]}\n\n' + json.dumps(payload, ensure_ascii=False)
    )
    r = client.chat.completions.create(model="gpt-5-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"})
    return json.loads(r.choices[0].message.content).get("concepts", [])


def adapt(concept, examples, client_desc):
    ex = "\n".join(f'- "{e["onscreen"] or e["spoken"] or e["desc"][:80]}" '
                   f'({e["play"]:,} views, save {e["save_rate"]}%)' for e in examples[:4])
    prompt = f"""Concept: {concept['name']} — {concept['pattern']}
Real winning examples:
{ex}

CLIENT: {client_desc}

Return ONLY JSON:
  adapted_hook: this concept's hook rewritten for the client, punchy, <=14 words
  format: talking-head|before-after|screen-record|text-on-video|voiceover-broll
  length_s: recommended video length in seconds (integer)
  script: array of 3-4 beats {{"t":"0-2s","action":"on-screen action"}}
  test_target: one-line measurable goal (e.g. 'save-rate >= 3%')
"""
    r = client.chat.completions.create(model="gpt-5-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"})
    return json.loads(r.choices[0].message.content)


def confidence(n_videos, n_accounts):
    if n_videos >= 5 and n_accounts >= 4:
        return "HIGH"
    if n_videos >= 3 and n_accounts >= 2:
        return "MEDIUM"
    return "EMERGING"


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "homedesign"
    query = sys.argv[2] if len(sys.argv) > 2 else "interior design app"
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 12

    recs = [r for r in records(query) if r["play"] >= 200 and cyrillic_share(r["desc"]) < 0.3]
    recs = intent_filter([score(r) for r in recs])
    pitches = sorted([r for r in recs if r["is_pitch"] and r["composite"] > 0],
                     key=lambda r: r["composite"], reverse=True)[:cap]
    print(f"{len(pitches)} pitches -> reading real hooks...")
    for i, r in enumerate(pitches, 1):
        r["spoken"] = spoken_hook(r["url"]) if r["url"] else ""
        r["onscreen"], r["seen_format"] = onscreen_text(r["mp4"]) if r["mp4"] else ("", "")
        print(f"  [{i}] @{r['handle']} save={r['save_rate']}% hook='{(r['onscreen'] or r['spoken'])[:45]}'")

    niche_median_save = st.median([r["save_rate"] for r in pitches]) or 0.01
    concepts = cluster(pitches)
    print(f"\n{len(concepts)} concepts found")

    out = [f"# TrendRadar — {key} · Recurring concepts (evidence-backed)", "",
           f"*query \"{query}\" · {len(pitches)} winning pitches clustered · "
           f"spike = save-rate vs niche median ({niche_median_save:.1f}%)*", ""]
    ranked = []
    for c in concepts:
        members = [pitches[i] for i in c.get("member_idxs", []) if i < len(pitches)]
        if not members:
            continue
        accounts = {m["handle"] for m in members}
        med_save = st.median([m["save_rate"] for m in members])
        spike = round(med_save / niche_median_save, 1) if niche_median_save else 0
        ranked.append((len(members), c, members, accounts, med_save, spike))
    ranked.sort(key=lambda x: (x[0], x[5]), reverse=True)

    for n, c, members, accounts, med_save, spike in ranked:
        conf = confidence(n, len(accounts))
        a = adapt(c, members, CLIENTS[key])
        beats = "\n".join(f"  - **{b.get('t','')}** — {b.get('action','')}" for b in a.get("script", []))
        exs = "\n".join(f"  - @{m['handle']} · {m['play']:,} views · save {m['save_rate']}% · "
                        f"\"{(m['onscreen'] or m['spoken'] or m['desc'])[:70]}\"" for m in
                        sorted(members, key=lambda m: m['play'], reverse=True)[:5])
        out += [
            f"## {c['name']}",
            f"**Confidence: {conf}** — {n} videos across {len(accounts)} accounts · "
            f"median save-rate {med_save:.1f}% = **{spike}× niche median**",
            f"**The formula:** {c['pattern']}", "",
            "**Proof (examples):**", exs, "",
            f"**➜ Adapted for {key}:** \"{a.get('adapted_hook')}\"  ",
            f"**Format:** {a.get('format')} · **Length:** {a.get('length_s')}s · "
            f"**Test target:** {a.get('test_target')}", "",
            "**Shoot-ready script:**", beats, "", "---", "",
        ]
    path = DATA / f"report_{key}_concepts.md"
    path.write_text("\n".join(x for x in out if x is not None))
    print(f"report -> {path}")


if __name__ == "__main__":
    main()
