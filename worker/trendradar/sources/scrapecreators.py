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


def _aweme_to_video(a: dict[str, Any]) -> dict[str, Any]:
    """One TikTok aweme object → our normalized video dict (shared by search + profile-videos)."""
    s = a.get("statistics", {}) or {}
    au = a.get("author", {}) or {}
    audio_id, audio_title = _music(a)
    return {
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
    }


def parse_search(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize a TikTok keyword-search body into our video dicts (shared by live + fixture)."""
    return [_aweme_to_video(it.get("aweme_info", {})) for it in body.get("search_item_list", [])]


def search_tiktok(query: str) -> list[dict[str, Any]]:
    """Keyword search (live) — returns normalized videos with full metrics inline."""
    return parse_search(_get("/v1/tiktok/search/keyword", {"query": query}))


def parse_tiktok_author_videos(body: dict[str, Any], handle: str) -> list[dict[str, Any]]:
    out = []
    for a in (body.get("aweme_list") or []):
        v = _aweme_to_video(a)
        v["handle"] = v["handle"] or handle  # profile-videos may omit the author block
        if v["video_id"] and v["video_id"] != "None":
            out.append(v)
    return out


def tiktok_author_videos(handle: str) -> list[dict[str, Any]]:
    """Account mining (§4.0 source #2): the creator's recent videos as candidates + baseline source."""
    return parse_tiktok_author_videos(_get("/v3/tiktok/profile/videos", {"handle": handle}), handle)


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


def _ig_node_to_video(n: dict[str, Any], handle: str) -> dict[str, Any]:
    """One profile-timeline node → our reel video dict. Views (`video_play_count`) are inline here."""
    cap = (n.get("edge_media_to_caption") or {}).get("edges") or []
    m = n.get("clips_music_attribution_info") or {}
    aid = m.get("audio_id") or m.get("id")
    sc_code = n.get("shortcode")
    return {
        "platform": "reels",
        "video_id": str(n.get("id") or sc_code),
        "handle": (n.get("owner") or {}).get("username") or handle,
        "is_verified": None,
        "follower_count": None,  # set by caller from the profile
        "caption": (cap[0].get("node", {}).get("text") if cap else "") or "",
        "audio_id": str(aid) if aid else None,
        "audio_title": m.get("song_name") or m.get("title"),
        "url": f"https://www.instagram.com/reel/{sc_code}/" if sc_code else None,
        "mp4": n.get("video_url"),
        "duration_s": round(n["video_duration"]) if n.get("video_duration") else None,
        "create_time": n.get("taken_at_timestamp"),
        "view_count": n.get("video_play_count"),
        "like_count": (n.get("edge_media_preview_like") or {}).get("count"),
        "comment_count": (n.get("edge_media_to_comment") or n.get("edge_media_preview_comment") or {}).get("count"),
        "share_count": None, "save_count": None,
    }


def parse_ig_profile(body: dict[str, Any], handle: str) -> dict[str, Any]:
    """Profile body → followers + account baseline + the creator's recent reels (views inline)."""
    u = (body.get("data") or {}).get("user") or {}
    edges = (u.get("edge_owner_to_timeline_media") or {}).get("edges") or []
    vids = [_ig_node_to_video(e.get("node") or {}, handle) for e in edges]
    vids = [v for v in vids if v["video_id"] and v.get("view_count")]  # video reels with views only
    plays = [v["view_count"] for v in vids]
    return {
        "follower_count": (u.get("edge_followed_by") or {}).get("count"),
        "baseline_median_views": int(st.median(plays)) if plays else None,
        "is_verified": bool(u.get("is_verified")) or None,
        "bio": u.get("biography") or "",  # for peer confirmation (NORTH_STAR §4)
        "videos": vids,
    }


def instagram_profile(handle: str) -> dict[str, Any]:
    """One call → follower count + account baseline (median views of recent reels)."""
    p = parse_ig_profile(_get("/v1/instagram/profile", {"handle": handle}), handle)
    return {k: p[k] for k in ("follower_count", "baseline_median_views", "is_verified")}


def _ig_reel_item_to_video(it: dict[str, Any], handle: str) -> dict[str, Any]:
    """One `instagram/user/reels` item → our reel dict. This endpoint carries the SOUND inline
    (music_canonical_id) plus play_count/caption — unlike the profile-timeline, which omits audio."""
    m = it.get("media") or it
    cm = m.get("clips_metadata") or {}
    osi = cm.get("original_sound_info") or {}
    mi = cm.get("music_info") or {}
    # canonical id groups the SAME sound across videos (best key for "N videos use this sound")
    audio_id = (cm.get("music_canonical_id") or (cm.get("audio_ranking_info") or {}).get("best_audio_cluster_id")
                or osi.get("audio_asset_id"))
    audio_title = ((mi.get("music_asset_info") or {}).get("title") if mi else None) or osi.get("original_audio_title")
    user = m.get("user") or {}
    code = m.get("code")
    vv = m.get("video_versions") or []
    dur = m.get("video_duration")
    return {
        "platform": "reels",
        "video_id": str(code or m.get("id") or m.get("pk")),
        "handle": user.get("username") or handle,
        "is_verified": bool(user.get("is_verified")) or None,
        "follower_count": None,  # user/reels is reels-only; baseline (below) is the reliability signal
        "caption": ((m.get("caption") or {}) or {}).get("text") or "",
        "audio_id": str(audio_id) if audio_id else None,
        "audio_title": audio_title,
        "url": f"https://www.instagram.com/reel/{code}/" if code else None,
        "mp4": vv[0].get("url") if vv else None,
        "duration_s": round(dur) if dur else None,
        "create_time": m.get("taken_at"),  # unix seconds
        "view_count": m.get("play_count") or m.get("ig_play_count"),
        "like_count": m.get("like_count"),
        "comment_count": m.get("comment_count"),
        "share_count": None, "save_count": None,
    }


def parse_ig_user_reels(body: dict[str, Any], handle: str) -> dict[str, Any]:
    vids = [_ig_reel_item_to_video(it, handle) for it in (body.get("items") or [])]
    vids = [v for v in vids if v["video_id"] and v["video_id"] != "None"]
    plays = [v["view_count"] for v in vids if v.get("view_count")]
    return {
        "follower_count": None,
        "baseline_median_views": int(st.median(plays)) if plays else None,
        "is_verified": next((v["is_verified"] for v in vids if v.get("is_verified")), None),
        "bio": "",  # not in this endpoint; peer confirmation uses the reels' captions instead
        "videos": vids,
    }


def instagram_author_videos(handle: str) -> dict[str, Any]:
    """Account mining (§4.0 source #2): recent reels WITH sound (music_canonical_id) + views +
    captions + baseline, one call. Uses instagram/user/reels (carries audio; profile-timeline doesn't)."""
    return parse_ig_user_reels(_get("/v1/instagram/user/reels", {"handle": handle}), handle)
