"""Refresh the Trending Songs chart (SPEC §4.5). Region-native, per platform:
  IN → Instagram only (TikTok is banned in India)
  US → Instagram + TikTok
Independent of the peer pipeline. Run manually now; cron (every ~3 days) later.

Usage: python refresh_trending_sounds.py [REGION ...]   (default: IN US)
"""
import os
import sys

from trendradar import db
from trendradar.sources import get_source

# region → platforms to fetch. IN has no TikTok userbase, so IG only; US has both.
REGION_PLATFORMS = {
    "IN": ["instagram"],
    "US": ["instagram", "tiktok"],
}
DEFAULT_REGIONS = [r.strip().upper() for r in os.getenv("TRENDING_REGIONS", "IN,US").split(",") if r.strip()]
IG_TOP_N = int(os.getenv("IG_TOP_N", "12"))  # how many top trending reels to enrich for audio


def _fetch(src, region: str, platform: str) -> tuple[list[dict], int]:
    if platform == "instagram":
        return src.instagram_trending_sounds(region, IG_TOP_N)
    return src.tiktok_trending_sounds(region)  # tiktok


def refresh(regions: list[str]) -> dict[str, int]:
    src = get_source()
    out: dict[str, int] = {}
    with db.connect() as conn:
        for region in regions:
            for platform in REGION_PLATFORMS.get(region, ["instagram"]):
                sounds, spent = _fetch(src, region, platform)
                for s in sounds:
                    db.upsert_trending_sound(conn, region, platform, s)
                db.clear_region_sounds(conn, region, platform, [s["audio_id"] for s in sounds])
                if spent:
                    # credit_call enum has no 'trending' → log as 'search' (a discovery-style call)
                    db.log_credit(conn, "scrapecreators", "search", spent, len(sounds), None)
                conn.commit()
                out[f"{region}:{platform}"] = len(sounds)
    return out


if __name__ == "__main__":
    regions = [r.upper() for r in sys.argv[1:]] or DEFAULT_REGIONS
    result = refresh(regions)
    print(f"done: {result} total={sum(result.values())}")
