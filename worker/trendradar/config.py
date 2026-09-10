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
# Shared secret the web app sends (X-Worker-Secret) to authorize a refresh. When set, the API
# rejects calls without it — protects the credit-spending endpoint once it's publicly reachable.
WORKER_SECRET = os.getenv("WORKER_SECRET", "")

SC_BASE = "https://api.scrapecreators.com"

# "scrapecreators" (live) | "fixture" (replay cached spike JSON — zero live credits, for testing)
DATA_SOURCE = os.getenv("DATA_SOURCE", "scrapecreators")

# Models (see PHASE0_FINDINGS §9). Per-task, cheapest that works.
MODEL_INTENT = os.getenv("MODEL_INTENT", "gpt-5-nano")
MODEL_VISION = os.getenv("MODEL_VISION", "gpt-4o-mini")
MODEL_REASON = os.getenv("ONBOARDING_MODEL", "gpt-5-mini")  # hook-extract / cluster / adapt
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")  # counting-layer hook embeddings (pgvector)
CLUSTER_SIM_THRESHOLD = float(os.getenv("CLUSTER_SIM_THRESHOLD", "0.78"))  # cosine sim to group hooks

# Credit ceilings (1 credit = 1 ScrapeCreators request). BACKEND.md §8.
CREDIT_CAP_PER_RUN = int(os.getenv("CREDIT_CAP_PER_RUN", "40"))

# Scoring (PHASE0_FINDINGS §3).
FOLLOWER_FLOOR = int(os.getenv("FOLLOWER_FLOOR", "1000"))
RISING_MAX_AGE_DAYS = int(os.getenv("RISING_MAX_AGE_DAYS", "60"))
MIN_VIEWS = int(os.getenv("MIN_VIEWS", "200"))
TOP_OUTLIERS = int(os.getenv("TOP_OUTLIERS", "12"))  # how many to deep-analyze per lane

# Evidence guardrails — never present non-winners as winners, or thin clusters as concepts.
# A video only backs a concept if it BEAT its creator's own baseline by this much (needs a baseline).
MIN_OUTPERFORMANCE = float(os.getenv("MIN_OUTPERFORMANCE", "1.5"))
# ...but absurd multiples (e.g. 300x) are almost always a tiny/unreliable baseline, not a real insight.
MAX_OUTPERFORMANCE = float(os.getenv("MAX_OUTPERFORMANCE", "75"))
# A concept is only surfaced with at least this many winning videos AND distinct creators.
MIN_CONCEPT_VIDEOS = int(os.getenv("MIN_CONCEPT_VIDEOS", "2"))
MIN_CONCEPT_CREATORS = int(os.getenv("MIN_CONCEPT_CREATORS", "2"))
# Reserve this fraction of the run cap for enrichment (baseline + views), so a pile of
# keyword searches can't starve the calls that PROVE a video won.
ENRICH_RESERVE_FRAC = float(os.getenv("ENRICH_RESERVE_FRAC", "0.5"))

# SSRF: only download media from these trusted CDN host suffixes.
MEDIA_HOST_SUFFIXES = (
    "tiktokcdn.com", "tiktokcdn-us.com", "tiktokv.com", "muscdn.com",
    "cdninstagram.com", "fbcdn.net",
)


def require(name: str, value: str) -> str:
    if not value:
        raise RuntimeError(f"{name} is not set in worker/.env")
    return value
