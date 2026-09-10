"""Refresh the GLOBAL Trending Songs chart (SPEC §4.5) — one standalone fetch per region,
independent of the peer pipeline. Primary source is TikTok's global songs chart; falls back to
the region trending feed when it's unavailable. Run manually now; cron later.

Usage: python refresh_trending_sounds.py [REGION ...]   (default: US IN)
"""
import sys

from trendradar import db
from trendradar.sources import get_source

DEFAULT_REGIONS = ["US", "IN"]


def refresh(regions: list[str]) -> dict[str, int]:
    src = get_source()
    out: dict[str, int] = {}
    with db.connect() as conn:
        for region in regions:
            sounds, spent = src.tiktok_trending_sounds(region)
            for s in sounds:
                db.upsert_trending_sound(conn, region, s)
            db.clear_region_sounds(conn, region, [s["audio_id"] for s in sounds])
            if spent:
                # credit_call enum has no 'trending' → log as 'search' (a discovery-style call)
                db.log_credit(conn, "scrapecreators", "search", spent, len(sounds), None)
            conn.commit()
            out[region] = len(sounds)
    return out


if __name__ == "__main__":
    regions = sys.argv[1:] or DEFAULT_REGIONS
    result = refresh(regions)
    total = sum(result.values())
    print(f"done: sounds={result} total={total}")
