"""
Phase 0 · Step 4 — Build the actual deliverable: a report card per top outlier
with metrics + decoded hook. This is what the product would show.

For top K outliers: fetch Post/Reel Info (views, 1 cr each), transcribe, decode hook.
Writes data/report.md.

Run: python step4_report.py [K]   (default 5)
"""
import json
import sys

from openai import OpenAI

from common import MEDIA, OPENAI_KEY, sc_get, load_json, DATA
from step3_analyze import download, transcribe

client = OpenAI(api_key=OPENAI_KEY)


def url_for(video_id: str) -> str | None:
    for r in json.load(open(DATA / "search_raw.json")):
        if str(r.get("id")) == str(video_id):
            return r.get("url")
    return None


def views_for(url: str):
    try:
        b = sc_get("/v1/instagram/post", params={"url": url}, call="post_info")
        m = (((b.get("data") or {}).get("xdt_shortcode_media")) or {})
        return m.get("video_play_count") or m.get("video_view_count")
    except Exception:  # noqa: BLE001
        return None


def decode(caption, transcript) -> dict:
    prompt = f"""You analyze short-form UGC video ads to help a marketing team replicate what works.
Return ONLY a JSON object with keys:
  hook_text: the exact opening line (spoken or on-screen), verbatim
  hook_type: one of question | POV | bold-claim | curiosity-gap | negativity | listicle | story | other
  emotional_driver: the core emotion/motivation (1-3 words)
  format: e.g. talking-head | green-screen | product-demo | text-on-video | skit | voiceover-broll
  structure: the beat sequence, e.g. "hook -> problem -> solution -> CTA"
  why_it_works: one sentence on WHY this likely drove engagement
  replication_score: integer 0-100. Use this rubric strictly:
     90-100 = simple, universal formula copyable for almost any product in a day
     70-89  = strong, needs a specific angle or a decent on-camera presence
     50-69  = works but needs real production effort or niche credibility
     0-49   = hard to replicate (relies on the creator's persona, a stunt, or luck)
  replication_notes: one line on what you'd need to copy it

CAPTION:
{caption}

SPOKEN TRANSCRIPT:
{transcript}
"""
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(r.choices[0].message.content)


def main() -> None:
    k = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    outliers = load_json("outliers.json")[:k]
    out = ["# TrendRadar — sample report", "",
           "*Niche: Indian e-com sellers · Instagram Reels · query \"amazon seller india\"*", ""]

    for i, o in enumerate(outliers, 1):
        handle = o["username"]
        followers = o.get("followers")
        url = url_for(o["video_id"])
        views = views_for(url) if url else None
        vpf = round(views / followers, 1) if (views and followers) else None
        like_rate = round(100 * o["likes"] / views, 1) if views else None

        transcript = ""
        mp4 = MEDIA / f"{o['video_id']}.mp4"
        if o.get("video_url") and download(o["video_url"], mp4):
            transcript = transcribe(mp4)
            for p in MEDIA.glob(f"{o['video_id']}*"):
                p.unlink(missing_ok=True)
        d = decode(o.get("caption") or "", transcript)

        out += [
            f"## {i}. @{handle}",
            f"**Why it surfaced:** {'views ' + format(views, ',') + ' = ' + str(vpf) + '× the account' + chr(39) + 's followers' if vpf else 'engagement/follower = ' + str(o.get('eng_per_follower'))}",
            "",
            "| metric | value |",
            "|---|---|",
            f"| followers | {followers:,} |" if followers else "| followers | ? |",
            f"| views | {views:,} |" if views else "| views | n/a |",
            f"| views ÷ followers | {vpf}× |" if vpf else "",
            f"| likes / comments | {o['likes']:,} / {o['comments']:,} |",
            f"| like-rate (likes÷views) | {like_rate}% |" if like_rate else "",
            f"| engagement ÷ followers | {o.get('eng_per_follower')} |",
            f"| reel | {url or o.get('video_url')} |",
            "",
            f"**Hook:** \"{d.get('hook_text')}\"  ",
            f"**Type:** {d.get('hook_type')} · **Emotion:** {d.get('emotional_driver')} · **Format:** {d.get('format')}  ",
            f"**Structure:** {d.get('structure')}  ",
            f"**Why it works:** {d.get('why_it_works')}  ",
            f"**Replication score:** {d.get('replication_score')}/100 — {d.get('replication_notes')}",
            "",
            "---", "",
        ]
        print(f"[{i}/{len(outliers)}] @{handle}  views={views}  vpf={vpf}  hook_type={d.get('hook_type')}  repl={d.get('replication_score')}")

    (DATA / "report.md").write_text("\n".join(x for x in out if x is not None))
    print(f"\nreport -> {DATA / 'report.md'}")


if __name__ == "__main__":
    main()
