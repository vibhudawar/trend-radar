"""ScrapeCreators DataSource (TikTok, validated in Phase 0). Pure HTTP — the pipeline handles
credit logging + ceiling. Each function = 1 ScrapeCreators credit. Retries once on transient error."""
from __future__ import annotations

import datetime as dt
import statistics as st
import time
from typing import Any

import httpx

from ..config import SC_BASE, SCRAPECREATORS_API_KEY, require

_HEADERS = lambda: {"x-api-key": require("SCRAPECREATORS_API_KEY", SCRAPECREATORS_API_KEY)}


def _get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(2):  # retry once
        try:
            r = httpx.get(f"{SC_BASE}{path}", headers=_HEADERS(), params=params, timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt == 0:
                time.sleep(1.5)
    raise RuntimeError(f"ScrapeCreators {path} failed: {last}")


def _music(a: dict) -> tuple[str | None, str | None]:
    m = a.get("added_sound_music_info") or a.get("music") or {}
    return (str(m.get("id") or m.get("mid")) if (m.get("id") or m.get("mid")) else None, m.get("title"))


def _mp4(a: dict) -> str | None:
    for br in ((a.get("video") or {}).get("bit_rate") or []):
        ul = (br.get("play_addr", {}) or {}).get("url_list") or []
        if ul:
            return ul[0]
    return None


def parse_search(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize a TikTok keyword-search body into our video dicts (shared by live + fixture)."""
    out: list[dict[str, Any]] = []
    for it in body.get("search_item_list", []):
        a = it.get("aweme_info", {})
        s = a.get("statistics", {}) or {}
        au = a.get("author", {}) or {}
        audio_id, audio_title = _music(a)
        out.append({
            "platform": "tiktok",
            "video_id": str(a.get("aweme_id")),
            "handle": au.get("unique_id"),
            "is_verified": bool(au.get("custom_verify")) or None,
            "follower_count": au.get("follower_count"),
            "caption": a.get("desc") or "",
            "audio_id": audio_id, "audio_title": audio_title,
            "url": a.get("url") or a.get("share_url"),
            "mp4": _mp4(a),
            "duration_s": round((a.get("video") or {}).get("duration", 0) / 1000) or None,
            "create_time": a.get("create_time"),  # unix seconds
            "view_count": s.get("play_count"),
            "like_count": s.get("digg_count"),
            "comment_count": s.get("comment_count"),
            "share_count": s.get("share_count"),
            "save_count": s.get("collect_count"),
        })
    return out


def search_tiktok(query: str) -> list[dict[str, Any]]:
    """Keyword search (live) — returns normalized videos with full metrics inline."""
    return parse_search(_get("/v1/tiktok/search/keyword", {"query": query}))


def tiktok_author_baseline(handle: str) -> int | None:
    """Median of the creator's recent video views = the account baseline."""
    body = _get("/v3/tiktok/profile/videos", {"handle": handle, "trim": "true"})
    views = [(x.get("statistics") or {}).get("play_count") for x in (body.get("aweme_list") or [])]
    views = [v for v in views if v]
    return int(st.median(views)) if views else None


def tiktok_transcript(url: str) -> str:
    """Spoken opening (WEBVTT) — no video download."""
    body = _get("/v1/tiktok/video/transcript", {"url": url})
    vtt = body.get("transcript") or body.get("text") or ""
    lines = [l.strip() for l in vtt.splitlines() if l.strip() and "-->" not in l and l.strip() != "WEBVTT"]
    return " ".join(lines[:4])


# --- Instagram Reels ------------------------------------------------------
# IG has no inline views/followers/shares. Flow: reels/search (cheap, no views)
# → instagram/post per reel for views → instagram/profile per creator for
# followers + account baseline. IG never exposes shares/saves (left None).

def _ig_ts(taken_at: Any) -> int | None:
    if not taken_at:
        return None
    if isinstance(taken_at, (int, float)):
        return int(taken_at)
    try:
        return int(dt.datetime.fromisoformat(str(taken_at).replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


def _ig_audio(r: dict) -> tuple[str | None, str | None]:
    m = r.get("clips_music_attribution_info") or {}
    aid = m.get("audio_id") or m.get("id")
    return (str(aid) if aid else None, m.get("song_name") or m.get("title"))


def parse_ig_search(reels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize reels/search items into our video dicts. Views/followers filled later."""
    out: list[dict[str, Any]] = []
    for r in reels:
        au = r.get("owner") or {}
        aid, atitle = _ig_audio(r)
        dur = r.get("video_duration")
        out.append({
            "platform": "reels",  # DB enum value for Instagram Reels
            "video_id": str(r.get("id") or r.get("shortcode")),
            "handle": au.get("username"),
            "is_verified": bool(au.get("is_verified")) or None,
            "follower_count": None,       # from instagram/profile
            "caption": r.get("caption") or "",
            "audio_id": aid, "audio_title": atitle,
            "url": r.get("url"),
            "mp4": r.get("video_url"),
            "duration_s": round(dur) if dur else None,
            "create_time": _ig_ts(r.get("taken_at")),  # unix seconds
            "view_count": None,           # from instagram/post
            "like_count": r.get("like_count"),
            "comment_count": r.get("comment_count"),
            "share_count": None,          # IG never exposes these
            "save_count": None,
        })
    return out


def search_instagram(query: str) -> list[dict[str, Any]]:
    """Niche keyword search over Reels (live). No views/followers inline."""
    body = _get("/v2/instagram/reels/search", {"query": query})
    return parse_ig_search(body.get("reels") or [])


def instagram_post_views(url: str) -> int | None:
    """Play count for one reel (Post/Reel Info)."""
    body = _get("/v1/instagram/post", {"url": url})
    m = ((body.get("data") or {}).get("xdt_shortcode_media")) or {}
    return m.get("video_play_count") or m.get("video_view_count")


def instagram_profile(handle: str) -> dict[str, Any]:
    """One call → follower count + account baseline (median views of recent reels)."""
    body = _get("/v1/instagram/profile", {"handle": handle})
    u = (body.get("data") or {}).get("user") or {}
    followers = (u.get("edge_followed_by") or {}).get("count")
    edges = (u.get("edge_owner_to_timeline_media") or {}).get("edges") or []
    plays = [e.get("node", {}).get("video_play_count") for e in edges]
    plays = [p for p in plays if p]
    return {
        "follower_count": followers,
        "baseline_median_views": int(st.median(plays)) if plays else None,
        "is_verified": bool(u.get("is_verified")) or None,
    }
