"""
Phase 0 · Step 3 — Does hook extraction actually work?
For the top K outliers: download the video, transcribe (OpenAI, mp4 direct),
extract frames + read on-screen text/style via vision (if ffmpeg present),
then LLM hook extraction. Prints a breakdown per video.

Spike shortcuts (production differs — see plans/SPEC.md §4):
  - transcription via OpenAI hosted (prod: local faster-whisper)
  - vision reads on-screen text (prod: local OCR, vision for style only)

Run: python step3_analyze.py [K]   (default K=5)
"""
import base64
import json
import shutil
import subprocess
import sys
from pathlib import Path

import requests
from openai import OpenAI

from common import MEDIA, OPENAI_KEY, load_json

UA = {"User-Agent": "Mozilla/5.0"}
HAS_FFMPEG = shutil.which("ffmpeg") is not None
client = OpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None

HOOK_SCHEMA = {
    "hook_text": "the exact opening hook line (on-screen or spoken)",
    "hook_type": "one of: question | POV | bold-claim | curiosity-gap | negativity | listicle | other",
    "emotional_driver": "the core emotion/motivation it triggers",
    "format": "e.g. talking-head | green-screen | product-demo | text-on-video | skit",
    "structure": "the beat structure, e.g. hook -> problem -> solution",
    "replication_score": "integer 0-100: how easily this formula can be replicated for another product",
}


def download(url: str, dest: Path) -> bool:
    try:
        r = requests.get(url, headers=UA, timeout=120, stream=True)
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
        return dest.stat().st_size > 1000
    except Exception as e:  # noqa: BLE001
        print(f"    download failed: {e}")
        return False


def transcribe(mp4: Path) -> str:
    try:
        with mp4.open("rb") as f:
            tr = client.audio.transcriptions.create(model="whisper-1", file=f)
        return tr.text.strip()
    except Exception as e:  # noqa: BLE001
        return f"(transcription failed: {e})"


def frames_b64(mp4: Path, n: int = 3) -> list[str]:
    if not HAS_FFMPEG:
        return []
    out = []
    for i, t in enumerate([0.5, 1.5, 2.5][:n]):
        fp = mp4.with_name(f"{mp4.stem}_f{i}.jpg")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(mp4),
             "-frames:v", "1", "-vf", "scale=512:-1", str(fp)],
            check=False,
        )
        if fp.exists():
            out.append(base64.b64encode(fp.read_bytes()).decode())
    return out


def read_frames(frames: list[str]) -> str:
    if not frames or not client:
        return ""
    content = [{"type": "text", "text":
                "These are the opening frames of a short video ad. "
                "Transcribe any on-screen text verbatim, then in one line describe the visual style."}]
    for b in frames:
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b}"}})
    try:
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": content}],
        )
        return r.choices[0].message.content.strip()
    except Exception as e:  # noqa: BLE001
        return f"(vision failed: {e})"


def extract_hook(caption, transcript, onscreen) -> dict:
    prompt = (
        "You analyze short-form UGC video ads. Given the signals below, return ONLY a JSON object "
        f"with these keys and meanings:\n{json.dumps(HOOK_SCHEMA, indent=2)}\n\n"
        f"CAPTION:\n{caption}\n\nSPOKEN TRANSCRIPT:\n{transcript}\n\n"
        f"ON-SCREEN TEXT + STYLE:\n{onscreen}\n"
    )
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    return json.loads(r.choices[0].message.content)


def main() -> None:
    if not client:
        raise SystemExit("OPENAI_API_KEY missing in scratch/.env")
    k = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    try:
        outliers = load_json("outliers.json")
    except FileNotFoundError:
        print("No outliers.json — falling back to candidates.json (no outlier scoring).")
        outliers = load_json("candidates.json")
    outliers = outliers[:k]

    print(f"ffmpeg present: {HAS_FFMPEG}  (frames/on-screen text {'ON' if HAS_FFMPEG else 'OFF'})\n")
    for i, o in enumerate(outliers, 1):
        handle = o.get("username")
        epf = o.get("eng_per_follower", o.get("outlier_multiplier"))
        eng = o.get("engagement")
        engstr = f"{eng:,}" if isinstance(eng, int) else "—"
        print(f"[{i}/{len(outliers)}] @{handle}  eng/foll={epf}  engagement={engstr}  followers={o.get('followers','?')}")
        url = o.get("video_url")
        if not url:
            print("    no video_url, skipping\n")
            continue
        mp4 = MEDIA / f"{o['video_id']}.mp4"
        if not download(url, mp4):
            print("    (IG CDN url may have expired) skipping\n")
            continue
        transcript = transcribe(mp4)
        onscreen = read_frames(frames_b64(mp4))
        try:
            hook = extract_hook(o.get("caption") or "", transcript, onscreen)
        except Exception as e:  # noqa: BLE001
            print(f"    hook extraction failed: {e}\n")
            continue
        print(f"    hook_text        : {hook.get('hook_text')}")
        print(f"    hook_type        : {hook.get('hook_type')}")
        print(f"    emotional_driver : {hook.get('emotional_driver')}")
        print(f"    format           : {hook.get('format')}")
        print(f"    structure        : {hook.get('structure')}")
        print(f"    replication_score: {hook.get('replication_score')}")
        print()
        # legal posture: don't keep the source video around
        for p in MEDIA.glob(f"{o['video_id']}*"):
            p.unlink(missing_ok=True)

    print("Done. Judge: are >=3/5 hook breakdowns genuinely useful?")


if __name__ == "__main__":
    main()
