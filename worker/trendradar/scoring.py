"""Per-platform scoring. NEVER rank by raw views. Account-baseline outperformance is primary;
saves/shares weighted as the retention proxy; follower count only a noise floor. (PHASE0_FINDINGS §3)"""
from __future__ import annotations

import math
import time
from typing import Any

from .config import FOLLOWER_FLOOR


def score_video(v: dict[str, Any], baseline: int | None, lane: str) -> dict[str, Any]:
    views = v.get("view_count") or 0
    followers = v.get("follower_count") or 0
    likes = v.get("like_count") or 0
    comments = v.get("comment_count") or 0
    shares = v.get("share_count") or 0
    saves = v.get("save_count") or 0
    ct = v.get("create_time")
    age_days = round((time.time() - ct) / 86400) if ct else None

    p = views or 1
    like_r, save_r, share_r, comment_r = likes / p, saves / p, shares / p, comments / p
    if v.get("platform") == "reels":
        # Instagram exposes no saves/shares → lean on likes/comments per view
        eng = 0.80 * like_r + 0.20 * comment_r
    else:
        # saves + shares weighted highest (public proxy for retention/watch-time)
        eng = 0.40 * save_r + 0.35 * share_r + 0.20 * like_r + 0.05 * comment_r

    outperf = round(views / baseline, 3) if baseline else None
    velocity = round(views / age_days) if age_days else None

    if followers and followers < FOLLOWER_FLOOR:
        flag, composite = "noise", 0.0
    elif outperf is None:
        flag, composite = "no_baseline", round(eng * math.log10(max(views, 10)), 4)
    else:
        flag = "ok"
        # blend quality (engagement rate) with reach (log views) and account outperformance
        composite = round(eng * math.log10(max(views, 10)) * min(outperf, 50), 4)

    return {
        "strategy": f"{v['platform']}-v1",
        "lane": lane,
        "account_outperformance": outperf,
        "save_rate": round(save_r, 5),
        "share_rate": round(share_r, 5),
        "like_rate": round(like_r, 5),
        "comment_rate": round(comment_r, 5),
        "velocity": velocity,
        "niche_spike": None,  # filled at cluster time
        "duration_s": v.get("duration_s"),
        "age_days": age_days,
        "composite": composite,
        "flag": flag,
    }
