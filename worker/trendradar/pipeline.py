"""Orchestrator: ingest → intent → score → hook → cluster → adapt, per lane.
Runs on outliers only; enforces the per-run credit ceiling; retries live in the source."""
from __future__ import annotations

import datetime as dt
import hashlib
import statistics as st
from collections import defaultdict
from typing import Any

import numpy as np
import psycopg

from . import db, llm
from .config import (CLUSTER_SIM_THRESHOLD, CREDIT_CAP_PER_RUN, DATA_SOURCE, EMBED_MODEL,
                     ENRICH_RESERVE_FRAC, MAX_OUTPERFORMANCE, MIN_CONCEPT_CREATORS, MIN_CONCEPT_VIDEOS,
                     MIN_OUTPERFORMANCE, MIN_VIEWS, RISING_MAX_AGE_DAYS, TOP_OUTLIERS)
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
    # A cross-creator pattern (>=2 creators) reads as a real (if early) pattern, not a single example.
    if n_videos >= 5 and n_creators >= 4:
        return "high"
    if n_videos >= 2 and n_creators >= 2:
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


def _is_winner(v: dict) -> bool:
    """A real outlier: has a baseline AND beat it by a MEANINGFUL but not absurd multiple.
    No baseline ⇒ not proven; >MAX_OUTPERFORMANCE ⇒ baseline artifact, not an insight."""
    s = v.get("score") or {}
    outperf = s.get("account_outperformance") or 0
    return s.get("flag") == "ok" and MIN_OUTPERFORMANCE <= outperf <= MAX_OUTPERFORMANCE


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


def _search(platform: str, query: str) -> list[dict]:
    return sc.search_tiktok(query) if platform == "tiktok" else sc.search_instagram(query)


def _mine(platform: str, handle: str) -> tuple[list[dict], int | None, str]:
    """A peer account's recent videos (metrics inline) + its baseline + bio, in one call."""
    if platform == "tiktok":
        vids = sc.tiktok_author_videos(handle)
        views = [v["view_count"] for v in vids if v.get("view_count")]
        followers = next((v.get("follower_count") for v in vids if v.get("follower_count")), None)
        for v in vids:
            v["follower_count"] = v.get("follower_count") or followers
        return vids, (int(st.median(views)) if views else None), ""
    prof = sc.instagram_author_videos(handle)
    vids = prof.get("videos", [])
    for v in vids:
        v["follower_count"] = prof.get("follower_count")
    return vids, prof.get("baseline_median_views"), prof.get("bio", "")


def _collect_peers(conn, project, budget: Budget, lane: str, platform: str) -> list[dict]:
    """NORTH_STAR discovery: build & mine the PEER SET, analyze ALL their content (any type).
    keyword search → candidate accounts → classify peers → mine → confirm → score → rank/hook."""
    project_id = project["id"]
    ctx = _context(project)
    cache = db.get_cached_peers(conn, project_id)  # {(platform, handle): is_peer}
    queries = [q for q in db.get_queries(conn, project_id) if q["platform"] == platform]

    seed_peers = [q["value"] for q in queries if q["type"] == "account" and not q.get("is_own")]  # trusted
    own = {q["value"].lower() for q in queries if q["type"] == "account" and q.get("is_own")}

    # 1. keyword search finds candidate ACCOUNTS (not content) — collect creators + their captions
    candidate_caps: dict[str, list[str]] = {}
    for q in queries:
        if q["type"] != "keyword" or not budget.spend("search"):
            continue
        try:
            for v in _search(platform, q["value"]):
                h = v.get("handle")
                if h and h.lower() not in own:
                    candidate_caps.setdefault(h, []).append(v.get("caption") or "")
        except Exception:  # noqa: BLE001
            continue

    # 2. provisional peer classify (free) — only uncached, non-seed candidates
    todo = [h for h in candidate_caps if (platform, h) not in cache and h not in seed_peers]
    if todo:
        verdict = llm.classify_peers([{"handle": h, "sample_captions": candidate_caps[h]} for h in todo], ctx)
        for i, h in enumerate(todo):
            cache[(platform, h)] = verdict.get(i, False)
            db.cache_peer(conn, project_id, platform, h, cache[(platform, h)])

    provisional = list(dict.fromkeys(seed_peers + [h for h in candidate_caps if cache.get((platform, h))]))
    if not provisional:
        return []

    # 3. mine provisional peers → all their content (metrics inline) + baseline + bio
    videos: dict[str, dict] = {}
    baselines: dict[str, int | None] = {}
    bios: dict[str, str] = {}
    for h in provisional:
        if not budget.spend("author_videos"):
            break
        try:
            vids, baseline, bio = _mine(platform, h)
        except Exception:  # noqa: BLE001 - one bad account shouldn't kill the lane
            continue
        baselines[h], bios[h] = baseline, bio
        for v in vids:
            if not v.get("video_id") or not v.get("handle") or _too_old(v, lane):
                continue
            videos.setdefault(v["video_id"], v)

    # 4. confirm non-seed peers from the fuller picture (bio + their own captions); drop false positives
    non_seed = [h for h in provisional if h not in seed_peers]
    if non_seed:
        caps_by_handle: dict[str, list[str]] = {}
        for v in videos.values():
            caps_by_handle.setdefault(v["handle"], []).append(v.get("caption") or "")
        confirm = llm.classify_peers(
            [{"handle": h, "bio": bios.get(h, ""), "sample_captions": caps_by_handle.get(h, [])[:6]} for h in non_seed], ctx)
        for i, h in enumerate(non_seed):
            is_peer = confirm.get(i, False)
            cache[(platform, h)] = is_peer
            db.cache_peer(conn, project_id, platform, h, is_peer)
            if is_peer:
                db.add_account_query(conn, project_id, platform, h)  # peer set compounds across runs
    confirmed = set(seed_peers) | {h for h in non_seed if cache.get((platform, h))}

    # 5. keep only confirmed-peer content; persist + score (all metrics inline — no per-video enrichment)
    scored: list[dict] = []
    for v in videos.values():
        if v["handle"] not in confirmed or not _passes(v, lane):
            continue
        _persist(conn, project_id, v, platform, baselines.get(v["handle"]))
        v["score"] = score_video(v, baselines.get(v["handle"]), lane)
        db.insert_score(conn, v["uuid"], v["score"])
        scored.append(v)
    if not scored:
        return []

    return _rank_and_hook(conn, budget, scored, allow_transcript=(platform == "tiktok"))


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


def _first_line(text: str | None) -> str:
    lines = (text or "").strip().splitlines()
    return lines[0][:140] if lines else ""


def _greedy_cluster(embs: list[list[float]], threshold: float = 0.82) -> list[list[int]]:
    """Deterministic greedy cosine clustering (process in input order; join to nearest centroid)."""
    x = np.array(embs, dtype=float)
    x = x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-9)
    clusters: list[dict] = []  # {"idx": [...], "cent": vec}
    for i in range(len(x)):
        best, best_sim = None, threshold
        for c in clusters:
            sim = float(np.dot(x[i], c["cent"]))
            if sim >= best_sim:
                best, best_sim = c, sim
        if best is None:
            clusters.append({"idx": [i], "cent": x[i].copy()})
        else:
            best["idx"].append(i)
            m = x[best["idx"]].mean(axis=0)
            best["cent"] = m / (np.linalg.norm(m) + 1e-9)
    return [c["idx"] for c in clusters]


def _hash(text: str) -> str:
    return hashlib.md5(text.lower().encode()).hexdigest()


def _as_np(e: Any) -> np.ndarray:
    """A stored embedding may come back as a numpy array, a pgvector Vector, or a list."""
    if isinstance(e, np.ndarray):
        return e.astype(float)
    if hasattr(e, "to_numpy"):
        return np.asarray(e.to_numpy(), dtype=float)
    if hasattr(e, "to_list"):
        return np.asarray(e.to_list(), dtype=float)
    return np.asarray(list(e), dtype=float)


def _count_trends(conn, project_id: str) -> None:
    """Tiered counting layer (NORTH_STAR §5): cheap "N uses across M accounts" over the WHOLE peer
    corpus. Hooks cluster on caption/on-screen text (embeddings stored in pgvector, compute-once);
    sounds group by audio_id. Stored as `trends`. Only produces output at scale (recurring hooks)."""
    rows = db.get_corpus_for_counting(conn, project_id)
    db.clear_trends(conn, project_id)

    # HOOKS — proxy = deep hook (outliers) else caption's first line; embed once, reuse via pgvector.
    # Wrapped so a hook failure can't block sound counting below.
    try:
        hook_rows = [r for r in rows if (r.get("hook_text") or _first_line(r.get("caption")))]
        hook_rows.sort(key=lambda r: (r.get("views") or 0), reverse=True)  # top-views video = representative
        proxies = {str(r["uuid"]): (r.get("hook_text") or _first_line(r.get("caption"))).strip() for r in hook_rows}
        stored = db.get_stored_embeddings(conn, project_id)  # {video_id: (source_hash, embedding)}
        to_embed = [(vid, p) for vid, p in proxies.items() if p and stored.get(vid, (None,))[0] != _hash(p)]
        if to_embed:
            new_embs = llm.embed([p for _, p in to_embed])
            for (vid, p), emb in zip(to_embed, new_embs):
                db.upsert_embedding(conn, vid, EMBED_MODEL, _hash(p), emb)
                stored[vid] = (_hash(p), np.asarray(emb, dtype=float))
        order = [str(r["uuid"]) for r in hook_rows if str(r["uuid"]) in stored]
        embs = [_as_np(stored[vid][1]) for vid in order]
        if embs:
            for cl in _greedy_cluster(embs, CLUSTER_SIM_THRESHOLD):
                member_vids = [order[j] for j in cl]
                if len(member_vids) < 2:
                    continue
                rep = proxies[member_vids[0]]
                db.insert_trend(conn, project_id, ttype="hook", key="hook:" + _hash(rep)[:16],
                                label=rep, member_uuids=member_vids)
    except Exception:  # noqa: BLE001 - hook counting is best-effort
        pass

    # SOUNDS — exact group by audio_id (from instagram/user/reels; music_canonical_id groups a sound).
    by_audio: dict[str, list[str]] = defaultdict(list)
    titles: dict[str, str | None] = {}
    for r in rows:
        if r.get("audio_id"):
            by_audio[r["audio_id"]].append(str(r["uuid"]))
            titles.setdefault(r["audio_id"], r.get("audio_title"))
    for audio_id, vids in by_audio.items():
        if len(vids) < 2:
            continue
        db.insert_trend(conn, project_id, ttype="sound", key="sound:" + str(audio_id),
                        label=titles.get(audio_id), member_uuids=vids)


def _run_lane(conn, project, budget: Budget, lane: str) -> None:
    platforms = project.get("platforms") or ["tiktok"]
    collected = [_collect_peers(conn, project, budget, lane, p) for p in ("tiktok", "reels") if p in platforms]

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
            try:
                _count_trends(conn, project_id)  # corpus-wide "N uses across M accounts" (NORTH_STAR §5)
            except Exception:  # noqa: BLE001 - counting is best-effort; never fail the run over it
                pass
            budget_used = budget.used
            db.set_project_status(conn, project_id, "ready", refreshed=True, run_credits=budget_used)
    except Exception:
        with db.connect() as conn:
            db.set_project_status(conn, project_id, "failed")
        raise
    return {"project_id": project_id, "credits_used": budget_used}
