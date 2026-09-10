"""Thin Postgres access (psycopg3). Same schema as packages/db — we never declare tables here."""
from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

from .config import DATABASE_URL, require


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(require("DATABASE_URL", DATABASE_URL), row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# --- reads ---
def get_project(conn: psycopg.Connection, project_id: str) -> dict[str, Any] | None:
    return conn.execute("select * from projects where id = %s", (project_id,)).fetchone()


def get_queries(conn: psycopg.Connection, project_id: str) -> list[dict[str, Any]]:
    return conn.execute(
        "select * from queries where project_id = %s and active = true and deleted_at is null",
        (project_id,),
    ).fetchall()


def credits_spent_since(conn: psycopg.Connection, project_id: str, iso_since: str) -> int:
    row = conn.execute(
        "select coalesce(sum(credits),0) as s from credit_log where project_id = %s and created_at >= %s",
        (project_id, iso_since),
    ).fetchone()
    return int(row["s"]) if row else 0


# --- writes ---
def set_project_status(conn: psycopg.Connection, project_id: str, status: str,
                       refreshed: bool = False, run_credits: int | None = None) -> None:
    if refreshed:
        conn.execute(
            "update projects set status=%s, last_refreshed_at=now(), last_run_credits=%s, updated_at=now() where id=%s",
            (status, run_credits, project_id),
        )
    else:
        conn.execute("update projects set status=%s, updated_at=now() where id=%s", (status, project_id))


def log_credit(conn: psycopg.Connection, source: str, call: str, credits: int,
               result_count: int | None, project_id: str | None) -> None:
    conn.execute(
        "insert into credit_log (source, call, credits, result_count, project_id) values (%s,%s,%s,%s,%s)",
        (source, call, credits, result_count, project_id),
    )


def upsert_author(conn: psycopg.Connection, platform: str, handle: str, *,
                  is_verified: bool | None, follower_count: int | None,
                  baseline_median_views: int | None) -> str:
    row = conn.execute(
        """
        insert into authors (platform, handle, is_verified, follower_count, baseline_median_views, last_profiled_at)
        values (%s,%s,%s,%s,%s, case when %s::bigint is not null then now() else null end)
        on conflict (platform, handle) do update set
          is_verified = coalesce(excluded.is_verified, authors.is_verified),
          follower_count = coalesce(excluded.follower_count, authors.follower_count),
          baseline_median_views = coalesce(excluded.baseline_median_views, authors.baseline_median_views),
          last_profiled_at = coalesce(excluded.last_profiled_at, authors.last_profiled_at),
          updated_at = now()
        returning id
        """,
        (platform, handle, is_verified, follower_count, baseline_median_views, baseline_median_views),
    ).fetchone()
    return row["id"]


def upsert_video(conn: psycopg.Connection, *, platform: str, video_id: str, author_id: str,
                 project_id: str, caption: str | None, audio_id: str | None, audio_title: str | None,
                 url: str, duration_s: int | None, taken_at: str | None, raw: dict) -> str:
    row = conn.execute(
        """
        insert into videos (platform, video_id, author_id, project_id, caption, audio_id, audio_title,
                            url, duration_s, taken_at, raw_payload)
        values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        on conflict (platform, video_id) do update set
          caption = excluded.caption, audio_id = excluded.audio_id, duration_s = excluded.duration_s
        returning id
        """,
        (platform, video_id, author_id, project_id, caption, audio_id, audio_title, url,
         duration_s, taken_at, json.dumps(raw)),
    ).fetchone()
    return row["id"]


def set_video_content_type(conn: psycopg.Connection, video_uuid: str, content_type: str) -> None:
    conn.execute("update videos set content_type=%s where id=%s", (content_type, video_uuid))


def get_cached_peers(conn: psycopg.Connection, project_id: str) -> dict[tuple[str, str], bool]:
    """All cached PEER verdicts for a project → {(platform, handle): is_peer}."""
    rows = conn.execute(
        "select platform, handle, is_peer from peer_cache where project_id=%s", (project_id,)
    ).fetchall()
    return {(r["platform"], r["handle"]): r["is_peer"] for r in rows}


def cache_peer(conn: psycopg.Connection, project_id: str, platform: str, handle: str, is_peer: bool) -> None:
    conn.execute(
        """insert into peer_cache (project_id, platform, handle, is_peer) values (%s,%s,%s,%s)
           on conflict (project_id, platform, handle) do update set is_peer=excluded.is_peer""",
        (project_id, platform, handle, is_peer),
    )


def add_account_query(conn: psycopg.Connection, project_id: str, platform: str, handle: str) -> None:
    """Persist a newly-confirmed peer as an account seed so the peer set compounds across runs."""
    conn.execute(
        """insert into queries (project_id, platform, type, value, is_own) values (%s,%s,'account',%s,false)
           on conflict (project_id, platform, type, value) do nothing""",
        (project_id, platform, handle),
    )


def has_analysis(conn: psycopg.Connection, video_uuid: str) -> dict[str, Any] | None:
    """Existing hook analysis for a video (so we reuse it instead of re-running vision — deterministic)."""
    return conn.execute(
        "select hook_text, format from analyses where video_id=%s and status='done'", (video_uuid,)
    ).fetchone()


def append_snapshot(conn: psycopg.Connection, video_uuid: str, *, view_count: int | None,
                    like_count: int | None, comment_count: int | None,
                    share_count: int | None, save_count: int | None) -> None:
    conn.execute(
        """insert into video_snapshots (video_id, view_count, like_count, comment_count, share_count, save_count)
           values (%s,%s,%s,%s,%s,%s)""",
        (video_uuid, view_count, like_count, comment_count, share_count, save_count),
    )


def insert_score(conn: psycopg.Connection, video_uuid: str, s: dict[str, Any]) -> None:
    conn.execute(
        """insert into scores (video_id, strategy, lane, account_outperformance, save_rate, share_rate,
             like_rate, comment_rate, velocity, niche_spike, duration_s, age_days, composite, flag)
           values (%(video_id)s,%(strategy)s,%(lane)s,%(account_outperformance)s,%(save_rate)s,%(share_rate)s,
             %(like_rate)s,%(comment_rate)s,%(velocity)s,%(niche_spike)s,%(duration_s)s,%(age_days)s,
             %(composite)s,%(flag)s)""",
        {**s, "video_id": video_uuid},
    )


def upsert_analysis(conn: psycopg.Connection, video_uuid: str, a: dict[str, Any]) -> None:
    conn.execute(
        """insert into analyses (video_id, status, hook_text, hook_type, hook_source, emotional_driver,
             format, structure, replication_score, transcript, onscreen_text, provider, model)
           values (%(video_id)s,'done',%(hook_text)s,%(hook_type)s,%(hook_source)s,%(emotional_driver)s,
             %(format)s,%(structure)s,%(replication_score)s,%(transcript)s,%(onscreen_text)s,%(provider)s,%(model)s)
           on conflict (video_id) do update set
             status='done', hook_text=excluded.hook_text, hook_type=excluded.hook_type,
             hook_source=excluded.hook_source, format=excluded.format, structure=excluded.structure,
             replication_score=excluded.replication_score, updated_at=now()""",
        {**a, "video_id": video_uuid},
    )


def clear_scores(conn: psycopg.Connection, project_id: str) -> None:
    """Scores are derived, not a time-series — replace them each run (unlike append-only snapshots)."""
    conn.execute(
        "delete from scores where video_id in (select id from videos where project_id=%s)", (project_id,)
    )


def clear_concepts(conn: psycopg.Connection, project_id: str, lane: str) -> None:
    conn.execute(
        """delete from concept_members where concept_id in
             (select id from concepts where project_id=%s and lane=%s)""",
        (project_id, lane),
    )
    conn.execute("delete from concepts where project_id=%s and lane=%s", (project_id, lane))


def insert_concept(conn: psycopg.Connection, c: dict[str, Any], member_video_uuids: list[str]) -> None:
    row = conn.execute(
        """insert into concepts (project_id, lane, name, pattern, n_videos, n_creators,
             median_outperformance, niche_spike, confidence, lifecycle, adapted_hook, format,
             length_s, test_target, script)
           values (%(project_id)s,%(lane)s,%(name)s,%(pattern)s,%(n_videos)s,%(n_creators)s,
             %(median_outperformance)s,%(niche_spike)s,%(confidence)s,%(lifecycle)s,%(adapted_hook)s,
             %(format)s,%(length_s)s,%(test_target)s,%(script)s)
           returning id""",
        {**c, "script": json.dumps(c.get("script"))},
    ).fetchone()
    for vid in member_video_uuids:
        conn.execute(
            "insert into concept_members (concept_id, video_id) values (%s,%s) on conflict do nothing",
            (row["id"], vid),
        )
