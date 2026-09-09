"""Central config — all secrets from worker/.env (never hardcoded)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
SCRAPECREATORS_API_KEY = os.getenv("SCRAPECREATORS_API_KEY", "")
APIFY_API_KEY = os.getenv("APIFY_API_KEY", "")

SC_BASE = "https://api.scrapecreators.com"

# "scrapecreators" (live) | "fixture" (replay cached spike JSON — zero live credits, for testing)
DATA_SOURCE = os.getenv("DATA_SOURCE", "scrapecreators")

# Models (see PHASE0_FINDINGS §9). Per-task, cheapest that works.
MODEL_INTENT = os.getenv("MODEL_INTENT", "gpt-5-nano")
MODEL_VISION = os.getenv("MODEL_VISION", "gpt-4o-mini")
MODEL_REASON = os.getenv("ONBOARDING_MODEL", "gpt-5-mini")  # hook-extract / cluster / adapt

# Credit ceilings (1 credit = 1 ScrapeCreators request). BACKEND.md §8.
CREDIT_CAP_PER_RUN = int(os.getenv("CREDIT_CAP_PER_RUN", "40"))

# Scoring (PHASE0_FINDINGS §3).
FOLLOWER_FLOOR = int(os.getenv("FOLLOWER_FLOOR", "1000"))
RISING_MAX_AGE_DAYS = int(os.getenv("RISING_MAX_AGE_DAYS", "60"))
MIN_VIEWS = int(os.getenv("MIN_VIEWS", "200"))
TOP_OUTLIERS = int(os.getenv("TOP_OUTLIERS", "12"))  # how many to deep-analyze per lane

# SSRF: only download media from these trusted CDN host suffixes.
MEDIA_HOST_SUFFIXES = (
    "tiktokcdn.com", "tiktokcdn-us.com", "tiktokv.com", "muscdn.com",
    "cdninstagram.com", "fbcdn.net",
)


def require(name: str, value: str) -> str:
    if not value:
        raise RuntimeError(f"{name} is not set in worker/.env")
    return value
