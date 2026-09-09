"""Fixture DataSource — replays the Phase-0 spike's cached ScrapeCreators JSON.
Zero live credits. Used to test the pipeline end-to-end (DATA_SOURCE=fixture).
Baseline/transcript are skipped (no cached data) → scoring falls back to no_baseline,
hooks fall back to on-screen/caption. Good enough to exercise DB → concepts → UI."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import scrapecreators as sc

_ROOT = Path(__file__).resolve().parent.parent.parent
# frozen test fixtures first; fall back to the spike's scratch data
_DATA = _ROOT / "tests" / "fixtures" if (_ROOT / "tests" / "fixtures").exists() else _ROOT / "scratch" / "data"


def _slug(query: str) -> str:
    return query.strip().lower().replace(" ", "_")


def search_tiktok(query: str) -> list[dict[str, Any]]:
    path = _DATA / f"tt_{_slug(query)}.json"
    if not path.exists():
        # fall back to any cached TikTok search so a test project always has data
        for cand in ("tt_interior_design_app.json", "tt_raw.json"):
            if (_DATA / cand).exists():
                path = _DATA / cand
                break
        else:
            return []
    return sc.parse_search(json.loads(path.read_text()))


def tiktok_author_baseline(handle: str) -> int | None:
    return None  # no cached baselines → scoring uses no_baseline (free)


def tiktok_transcript(url: str) -> str:
    return ""  # skip (would cost a live credit); hook falls back to on-screen/caption


# --- Instagram (replays the captured IG fixtures — zero credits) -----------
import statistics as _st  # noqa: E402


def _load(name: str) -> Any:
    path = _DATA / name
    return json.loads(path.read_text()) if path.exists() else None


def search_instagram(query: str) -> list[dict[str, Any]]:
    cap = _load("capture_search.json") or {}          # real captured dataset, keyed by query
    reels = cap.get(query) or (_load("ig_reels_search.json") or [])
    return sc.parse_ig_search(reels)


def instagram_post_views(url: str) -> int | None:
    for f in ("capture_posts.json", "ig_post_details.json"):
        d = _load(f) or {}
        if url in d:
            m = ((d[url].get("data") or {}).get("xdt_shortcode_media")) or {}
            return m.get("video_play_count") or m.get("video_view_count")
    return None


def _ig_profile_body(handle: str) -> dict[str, Any] | None:
    for f in ("capture_profiles.json", "ig_profiles.json"):
        d = _load(f) or {}
        if handle in d:
            return d[handle]
    return None  # honest: no cached profile for this handle → no baseline (mirrors a live miss)


def instagram_profile(handle: str) -> dict[str, Any]:
    body = _ig_profile_body(handle)
    if not body:
        return {"follower_count": None, "baseline_median_views": None, "is_verified": None}
    p = sc.parse_ig_profile(body, handle)
    return {k: p[k] for k in ("follower_count", "baseline_median_views", "is_verified")}


def instagram_author_videos(handle: str) -> dict[str, Any]:
    body = _ig_profile_body(handle)
    if not body:
        return {"follower_count": None, "baseline_median_views": None, "is_verified": None, "videos": []}
    return sc.parse_ig_profile(body, handle)


def tiktok_author_videos(handle: str) -> list[dict[str, Any]]:
    # no cached TikTok profile-videos fixture → replay a slice of the search fixture as this account's videos
    vids = search_tiktok("")[:6]
    for v in vids:
        v["handle"] = handle
    return vids
