"""Orchestrator: ingest → intent → score → hook → cluster → adapt, per lane.
Runs on outliers only; enforces the per-run credit ceiling; retries live in the source."""
from __future__ import annotations

import datetime as dt
import statistics as st
from typing import Any

import psycopg

from . import db, llm
from .config import (CREDIT_CAP_PER_RUN, DATA_SOURCE, ENRICH_RESERVE_FRAC, MIN_CONCEPT_CREATORS,
                     MIN_CONCEPT_VIDEOS, MIN_OUTPERFORMANCE, MIN_VIEWS, RISING_MAX_AGE_DAYS, TOP_OUTLIERS)
from .media import frames_from_video
from .scoring import score_video
from .sources import get_source

sc = get_source()
LANES = ("rising", "proven")


class Budget:
    """Per-run credit ceiling. 1 credit = 1 ScrapeCreators request. Free in fixture mode.
    A slice (ENRICH_RESERVE_FRAC) is reserved for enrichment (baseline/views) so discovery
    (search/mining) can't spend the whole cap and starve the calls that PROVE a video won."""
    def __init__(self, conn: psycopg.Connection, project_id: str, cap: int):
        self.conn, self.project_id, self.remaining, self.used = conn, project_id, cap, 0
        self.free = DATA_SOURCE == "fixture"
        self.reserve = int(cap * ENRICH_RESERVE_FRAC)

    def spend(self, call: str, result_count: int | None = None, *, kind: str = "discovery") -> bool:
        if self.free:
            return True
        floor = self.reserve if kind == "discovery" else 0  # discovery can't dip into the reserve
        if self.remaining <= floor:
            return False
        self.remaining -= 1
        self.used += 1
        db.log_credit(self.conn, "scrapecreators", call, 1, result_count, self.project_id)
        return True


def _context(project: dict) -> str:
    """The business profile the operator entered — leveraged in intent, clustering, adaptation."""
    fields = [("BUSINESS", project.get("name")), ("WHAT IT DOES", project.get("product_description")),
              ("AUDIENCE", project.get("audience")), ("GOAL", project.get("job_to_be_done")),
              ("REGION", project.get("region"))]
    return "\n".join(f"{k}: {v}" for k, v in fields if v)


def _iso_today() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT00:00:00+00:00")


def _passes(v: dict, lane: str) -> bool:
    if (v.get("view_count") or 0) < MIN_VIEWS:
        return False
    if lane == "rising" and v.get("create_time"):
        age = (dt.datetime.now(dt.timezone.utc).timestamp() - v["create_time"]) / 86400
        if age > RISING_MAX_AGE_DAYS:
            return False
    return True


def _confidence(n_videos: int, n_creators: int) -> str:
    if n_videos >= 5 and n_creators >= 4:
        return "high"
    if n_videos >= 3 and n_creators >= 2:
        return "medium"
    return "emerging"


def _lifecycle(members: list[dict]) -> str:
    ages = [m["age_days"] for m in members if m.get("age_days") is not None]
    if not ages:
        return "mature"
    med = st.median(ages)
    if med <= 21 and len(members) >= 2:
        return "emerging"
    if med <= 45:
        return "growing"
    return "mature" if len(members) >= 5 else "declining"


def _taken(v: dict) -> str | None:
    ct = v.get("create_time")
    return dt.datetime.fromtimestamp(ct, dt.timezone.utc).isoformat() if ct else None


def _too_old(v: dict, lane: str) -> bool:
    if lane != "rising" or not v.get("create_time"):
        return False
    return (dt.datetime.now(dt.timezone.utc).timestamp() - v["create_time"]) / 86400 > RISING_MAX_AGE_DAYS


def _hook_for(conn, budget: Budget, v: dict, *, allow_transcript: bool) -> None:
    """Decode the real hook from the video (frames + optional transcript), persist the analysis."""
    spoken = ""
    if allow_transcript and v.get("url") and budget.spend("transcript", kind="enrich"):
        try:
            spoken = sc.tiktok_transcript(v["url"])
        except Exception:  # noqa: BLE001
            spoken = ""
    onscreen, seen_format = "", None
    if v.get("mp4"):
        fr = frames_from_video(v["mp4"])
        if fr:
            try:
                d = llm.read_onscreen(fr)
                onscreen, seen_format = d.get("onscreen_text", ""), d.get("format")
            except Exception:  # noqa: BLE001
                pass
    try:
        hk = llm.extract_hook(onscreen, spoken, v.get("caption") or "")
    except Exception:  # noqa: BLE001
        hk = {}
    v["hook_text"] = hk.get("hook_text") or onscreen or spoken or None
    v["format"] = hk.get("format") or seen_format
    db.upsert_analysis(conn, v["uuid"], {
        "hook_text": v["hook_text"], "hook_type": hk.get("hook_type"),
        "hook_source": hk.get("hook_source"), "emotional_driver": hk.get("emotional_driver"),
        "format": v["format"], "structure": hk.get("structure"),
        "replication_score": hk.get("replication_score"), "transcript": spoken,
        "onscreen_text": onscreen, "provider": "openai", "model": None,
    })


def _persist(conn, project_id: str, v: dict, platform: str, baseline: int | None) -> None:
    author_uuid = db.upsert_author(conn, platform, v["handle"], is_verified=v.get("is_verified"),
                                   follower_count=v.get("follower_count"), baseline_median_views=baseline)
    v["uuid"] = db.upsert_video(conn, platform=platform, video_id=v["video_id"], author_id=author_uuid,
                                project_id=project_id, caption=v.get("caption"), audio_id=v.get("audio_id"),
                                audio_title=v.get("audio_title"), url=v["url"], duration_s=v.get("duration_s"),
                                taken_at=_taken(v), raw=v)
    db.append_snapshot(conn, v["uuid"], view_count=v.get("view_count"), like_count=v.get("like_count"),
                       comment_count=v.get("comment_count"), share_count=v.get("share_count"),
                       save_count=v.get("save_count"))


def _intent_pitches(conn, project_id: str, items: list[dict], *, mark: bool, context: str = "") -> list[dict]:
    """Goal-relevant pitch filter. Cached per (project, video_id) — the classifier is
    non-deterministic, so we classify each video once and reuse the verdict (stable re-runs)."""
    cached = db.get_cached_intent(conn, project_id)
    verdict: dict[int, bool] = {}
    todo: list[tuple[int, dict]] = []
    for i, v in enumerate(items):
        key = (v["platform"], v["video_id"])
        if key in cached:
            verdict[i] = cached[key]
        else:
            todo.append((i, v))
    if todo:
        fresh = llm.classify_intent([v for _, v in todo], context)  # keyed by position in `todo`
        for local_idx, (gi, v) in enumerate(todo):
            is_pitch = fresh.get(local_idx, False)
            verdict[gi] = is_pitch
            db.cache_intent(conn, project_id, v["platform"], v["video_id"], is_pitch)

    pitches = []
    for i, v in enumerate(items):
        is_pitch = verdict.get(i, False)
        if mark and v.get("uuid"):
            db.set_video_content_type(conn, v["uuid"], "pitch" if is_pitch else "education")
        if is_pitch:
            pitches.append(v)
    return pitches


def _is_winner(v: dict) -> bool:
    """A real outlier: has a baseline AND beat it by >= MIN_OUTPERFORMANCE. No baseline ⇒ not proven."""
    s = v.get("score") or {}
    return s.get("flag") == "ok" and (s.get("account_outperformance") or 0) >= MIN_OUTPERFORMANCE


def _rank_and_hook(conn, budget: Budget, pitches: list[dict], *, allow_transcript: bool) -> list[dict]:
    # Only PROVEN winners get deep-analyzed and become concept evidence (never present a non-winner as one).
    ranked = sorted([p for p in pitches if _is_winner(p)],
                    key=lambda p: p["score"]["composite"], reverse=True)[:TOP_OUTLIERS]
    for v in ranked:
        prior = db.has_analysis(conn, v["uuid"])  # reuse a prior hook → deterministic + no re-download (CDN URLs expire)
        if prior:
            v["hook_text"], v["format"] = prior["hook_text"], prior["format"]
        else:
            _hook_for(conn, budget, v, allow_transcript=allow_transcript)
    return ranked


def _account_queries_first(queries: list[dict], platform: str) -> list[dict]:
    """This platform's queries, account-mining first (cheap + high-yield → gets budget before search)."""
    qs = [q for q in queries if q["platform"] == platform]
    return sorted(qs, key=lambda q: 0 if (q["type"] == "account" and not q.get("is_own")) else 1)


def _collect_tiktok(conn, project, budget: Budget, lane: str) -> list[dict]:
    """Discovery (§4.0): keyword search + account mining → persist → intent → score → rank/hook."""
    project_id = project["id"]
    videos: dict[str, dict] = {}
    baselines: dict[str, int | None] = {}  # handle → baseline (mined accounts fill this for free)
    for q in _account_queries_first(db.get_queries(conn, project_id), "tiktok"):
        if q["type"] == "account" and not q.get("is_own"):
            if not budget.spend("author_videos"):
                continue
            try:
                raws = sc.tiktok_author_videos(q["value"])
            except Exception:  # noqa: BLE001 - one bad account shouldn't kill the lane
                continue
            mv = [r["view_count"] for r in raws if r.get("view_count")]
            if mv:
                baselines[q["value"]] = int(st.median(mv))  # the mined account's own baseline, free
        elif q["type"] == "keyword":
            if not budget.spend("search"):
                continue
            try:
                raws = sc.search_tiktok(q["value"])
            except Exception:  # noqa: BLE001
                continue
        else:
            continue
        for v in raws:
            if not v.get("video_id") or not v.get("handle") or not _passes(v, lane):
                continue
            videos.setdefault(v["video_id"], v)  # dedupe on video_id (mined first wins)
    if not videos:
        return []
    for v in videos.values():
        _persist(conn, project_id, v, "tiktok", baselines.get(v["handle"]))

    pitches = _intent_pitches(conn, project_id, list(videos.values()), mark=True, context=_context(project))
    if not pitches:
        return []

    # score with account baseline (mined accounts already known; others fetched per unique handle)
    for v in pitches:
        h = v["handle"]
        if h not in baselines:
            baselines[h] = None
            if budget.spend("author_videos", kind="enrich"):
                try:
                    baselines[h] = sc.tiktok_author_baseline(h)
                except Exception:  # noqa: BLE001
                    baselines[h] = None
        v["score"] = score_video(v, baselines[h], lane)
        db.insert_score(conn, v["uuid"], v["score"])

    return _rank_and_hook(conn, budget, pitches, allow_transcript=True)


def _collect_reels(conn, project, budget: Budget, lane: str) -> list[dict]:
    """Discovery (§4.0): account mining (reels + views + baseline in ONE call) + keyword search
    (needs per-reel enrichment). Intent-filter first, then only enrich the search pitches."""
    project_id = project["id"]
    mined: dict[str, dict] = {}          # pre-enriched: views/followers/baseline inline
    search_reels: dict[str, dict] = {}   # need profile + post-detail
    profiles: dict[str, dict] = {}       # handle → {follower_count, baseline_median_views, is_verified}
    for q in _account_queries_first(db.get_queries(conn, project_id), "reels"):
        if q["type"] == "account" and not q.get("is_own"):
            if not budget.spend("author_videos"):  # one call = reels + followers + baseline
                continue
            try:
                prof = sc.instagram_author_videos(q["value"])
            except Exception:  # noqa: BLE001
                continue
            profiles[q["value"]] = prof
            for v in prof.get("videos", []):
                v["follower_count"] = prof.get("follower_count")
                if not v.get("video_id") or _too_old(v, lane):
                    continue
                mined.setdefault(v["video_id"], v)
        elif q["type"] == "keyword":
            if not budget.spend("search"):
                continue
            try:
                raws = sc.search_instagram(q["value"])
            except Exception:  # noqa: BLE001
                continue
            for v in raws:
                if not v.get("video_id") or not v.get("handle") or _too_old(v, lane):
                    continue
                search_reels.setdefault(v["video_id"], v)
    for vid in mined:
        search_reels.pop(vid, None)  # a mined reel already has views → don't re-fetch via search
    if not mined and not search_reels:
        return []

    # intent on captions across both pools — before spending on search-reel enrichment
    pitches = _intent_pitches(conn, project_id, list(mined.values()) + list(search_reels.values()),
                              mark=False, context=_context(project))
    if not pitches:
        return []

    scored: list[dict] = []
    for v in pitches:
        h = v["handle"]
        if v["video_id"] in mined:
            baseline = (profiles.get(h) or {}).get("baseline_median_views")  # already enriched, free
        else:
            if h not in profiles:
                profiles[h] = {"follower_count": None, "baseline_median_views": None, "is_verified": None}
                if budget.spend("author_videos", kind="enrich"):  # profile = followers + baseline
                    try:
                        profiles[h] = sc.instagram_profile(h)
                    except Exception:  # noqa: BLE001
                        pass
            if v.get("url") and budget.spend("video_detail", kind="enrich"):  # per-reel views (Post/Reel Info)
                try:
                    v["view_count"] = sc.instagram_post_views(v["url"])
                except Exception:  # noqa: BLE001
                    v["view_count"] = None
            v["follower_count"] = profiles[h].get("follower_count")
            v["is_verified"] = v.get("is_verified") or profiles[h].get("is_verified")
            baseline = profiles[h].get("baseline_median_views")
        if not _passes(v, lane):  # MIN_VIEWS now applies (views known)
            continue
        _persist(conn, project_id, v, "reels", baseline)
        db.set_video_content_type(conn, v["uuid"], "pitch")
        v["score"] = score_video(v, baseline, lane)
        db.insert_score(conn, v["uuid"], v["score"])
        scored.append(v)

    return _rank_and_hook(conn, budget, scored, allow_transcript=False)


def _cluster_and_adapt(conn, project, lane: str, ranked: list[dict]) -> None:
    """Cluster PROVEN winners into concepts + adapt to the client. Members are always genuine
    winners (winner-gate upstream). A concept is a "proven pattern" only when it spans enough
    winning videos AND creators; otherwise it's an honestly-labeled "single strong example"
    (confidence=emerging) — we surface it (a real winner is signal) but never call it a trend."""
    if not ranked:
        return
    project_id = project["id"]
    ctx = _context(project)
    concepts = llm.cluster_concepts(ranked, ctx)
    niche_med_save = st.median([v["score"]["save_rate"] for v in ranked]) or 1e-6

    # Build the groups the clusterer produced, then a COMPLETENESS pass: every proven winner the
    # LLM left unplaced becomes its own single-example concept — never silently drop a real winner.
    groups: list[tuple[str, str | None, list[dict]]] = []
    placed: set[int] = set()
    for c in concepts:
        idxs = [i for i in c.get("member_idxs", []) if 0 <= i < len(ranked)]
        if not idxs:
            continue
        placed.update(idxs)
        groups.append((c.get("name", "Concept"), c.get("pattern"), [ranked[i] for i in idxs]))
    for i, v in enumerate(ranked):
        if i not in placed:
            groups.append((v.get("hook_text") or "Standout winner", None, [v]))

    for name, pattern, members in groups:
        n_creators = len({m["handle"] for m in members})
        is_pattern = len(members) >= MIN_CONCEPT_VIDEOS and n_creators >= MIN_CONCEPT_CREATORS
        confidence = _confidence(len(members), n_creators) if is_pattern else "emerging"
        outs = [m["score"]["account_outperformance"] for m in members if m["score"]["account_outperformance"]]
        med_save = st.median([m["score"]["save_rate"] for m in members]) if members else 0
        try:
            a = llm.adapt_concept({"name": name, "pattern": pattern or ""}, members, ctx)
        except Exception:  # noqa: BLE001
            a = {}
        db.insert_concept(conn, {
            "project_id": project_id, "lane": lane, "name": name,
            "pattern": pattern, "n_videos": len(members), "n_creators": n_creators,
            "median_outperformance": round(st.median(outs), 2) if outs else None,
            "niche_spike": round(med_save / niche_med_save, 2),
            "confidence": confidence,
            "lifecycle": _lifecycle([m["score"] for m in members]),
            "adapted_hook": a.get("adapted_hook"), "format": a.get("format"),
            "length_s": a.get("length_s"), "test_target": a.get("test_target"),
            "script": a.get("script"),
        }, [m["uuid"] for m in members])


def _run_lane(conn, project, budget: Budget, lane: str) -> None:
    platforms = project.get("platforms") or ["tiktok"]
    collected: list[list[dict]] = []
    if "tiktok" in platforms:
        collected.append(_collect_tiktok(conn, project, budget, lane))
    if "reels" in platforms:
        collected.append(_collect_reels(conn, project, budget, lane))

    # Always clear this lane's old concepts — even with zero winners — so a stricter run can't
    # leave stale/garbage concepts from a previous run showing (honest empty > stale).
    db.clear_concepts(conn, project["id"], lane)
    for ranked in [r for r in collected if r]:
        _cluster_and_adapt(conn, project, lane, ranked)


def run_project(project_id: str) -> dict[str, Any]:
    with db.connect() as conn:
        project = db.get_project(conn, project_id)
        if not project:
            raise ValueError("project not found")
        db.set_project_status(conn, project_id, "running")

    budget_used = 0
    try:
        with db.connect() as conn:
            budget = Budget(conn, project_id, CREDIT_CAP_PER_RUN)
            project = db.get_project(conn, project_id)
            db.clear_scores(conn, project_id)  # replace derived scores each run (idempotent; snapshots still append)
            for lane in LANES:
                _run_lane(conn, project, budget, lane)
            budget_used = budget.used
            db.set_project_status(conn, project_id, "ready", refreshed=True, run_credits=budget_used)
    except Exception:
        with db.connect() as conn:
            db.set_project_status(conn, project_id, "failed")
        raise
    return {"project_id": project_id, "credits_used": budget_used}
