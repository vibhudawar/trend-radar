"""Download the opening of a video and extract frames for on-screen-text vision.
SSRF: only fetch from trusted media-CDN host suffixes (allowlist); no redirects; timeout; size cap.
Clip is transient — written to /tmp, frames extracted, file deleted immediately."""
from __future__ import annotations

import base64
import os
import tempfile
from urllib.parse import urlparse

import cv2
import httpx

from .config import MEDIA_HOST_SUFFIXES

_HDRS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.tiktok.com/"}
_MAX_BYTES = 12_000_000


def _host_allowed(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == s or host.endswith("." + s) for s in MEDIA_HOST_SUFFIXES)


def frames_from_video(url: str, times=(1.0, 1.8, 2.6)) -> list[str]:
    """Return base64 JPEGs of opening frames, or [] on any failure. SSRF-guarded."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not _host_allowed(url):
        return []  # not a trusted media CDN → refuse
    path = os.path.join(tempfile.gettempdir(), f"tr_{abs(hash(url))}.mp4")
    try:
        with httpx.stream("GET", url, headers=_HDRS, timeout=60, follow_redirects=False) as r:
            if r.status_code != 200:
                return []
            total, chunks = 0, []
            for chunk in r.iter_bytes():
                total += len(chunk)
                if total > _MAX_BYTES:
                    break
                chunks.append(chunk)
        if total < 5000:
            return []
        with open(path, "wb") as f:
            f.write(b"".join(chunks))
        return _extract(path, times)
    except Exception:  # noqa: BLE001
        return []
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _extract(path: str, times) -> list[str]:
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    out: list[str] = []
    for t in times:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
        ok, fr = cap.read()
        if ok:
            ok2, buf = cv2.imencode(".jpg", cv2.resize(fr, (0, 0), fx=0.5, fy=0.5))
            if ok2:
                out.append(base64.b64encode(buf.tobytes()).decode())
    cap.release()
    return out
