"""Demo: read the REAL hook = on-screen text (frames+vision) + spoken (transcript),
vs the caption we were wrongly using. Proves OCR/vision is needed for hook fidelity."""
import base64
import sys

import cv2
import requests
from openai import OpenAI

from common import OPENAI_KEY, MEDIA

client = OpenAI(api_key=OPENAI_KEY)
HDRS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.tiktok.com/"}


def frames(mp4, times=(0.4, 1.2, 2.4)):
    cap = cv2.VideoCapture(str(mp4))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    out = []
    for t in times:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ok, fr = cap.read()
        if ok:
            ok2, buf = cv2.imencode(".jpg", cv2.resize(fr, (0, 0), fx=0.5, fy=0.5))
            if ok2:
                out.append(base64.b64encode(buf).decode())
    cap.release()
    return out


def read_onscreen(imgs):
    content = [{"type": "text", "text":
        "These are the first ~2.5 seconds of a TikTok. Return JSON: "
        '{"onscreen_text": verbatim text overlaid on the video (the hook), '
        '"format": talking-head|before-after|screen-record|text-on-video|voiceover-broll, '
        '"visual": one line describing what is shown}'}]
    for b in imgs:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}})
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": content}],
        response_format={"type": "json_object"})
    return r.choices[0].message.content


def main():
    url = open("data/_top_mp4.txt").read().strip()
    if not url:
        print("no mp4 url"); sys.exit(1)
    mp4 = MEDIA / "top.mp4"
    r = requests.get(url, headers=HDRS, timeout=120)
    print("download status:", r.status_code, "bytes:", len(r.content))
    if r.status_code != 200 or len(r.content) < 5000:
        print("TikTok CDN blocked the download (needs cookies). On-screen-text step needs a real fetch."); return
    mp4.write_bytes(r.content)
    imgs = frames(mp4)
    print(f"extracted {len(imgs)} frames")
    print("ON-SCREEN TEXT (vision):", read_onscreen(imgs))
    mp4.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
