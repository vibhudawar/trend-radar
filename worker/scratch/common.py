"""Shared helpers for the Phase 0 spike. Throwaway — not production code."""
import csv
import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

HERE = Path(__file__).parent
DATA = HERE / "data"
MEDIA = HERE / "media"
DATA.mkdir(exist_ok=True)
MEDIA.mkdir(exist_ok=True)

load_dotenv(HERE / ".env")

SC_KEY = os.getenv("SCRAPECREATORS_API_KEY", "")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
SC_BASE = "https://api.scrapecreators.com"

CREDIT_LOG = DATA / "credit_log.csv"


def require_sc_key() -> None:
    if not SC_KEY:
        raise SystemExit("SCRAPECREATORS_API_KEY missing in scratch/.env")


def log_credit(call: str, credits: int, result_count: int, remaining) -> None:
    new = not CREDIT_LOG.exists()
    with CREDIT_LOG.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["ts", "call", "credits", "result_count", "remaining"])
        w.writerow([int(time.time()), call, credits, result_count, remaining])


def sc_get(path: str, params: dict | None = None, call: str = "") -> dict:
    """GET a ScrapeCreators endpoint, log the credit spend, return parsed JSON."""
    require_sc_key()
    r = requests.get(
        f"{SC_BASE}{path}",
        headers={"x-api-key": SC_KEY},
        params=params or {},
        timeout=60,
    )
    r.raise_for_status()
    body = r.json()
    remaining = body.get("credits_remaining", "?")
    charged = body.get("credits_charged", 1)
    log_credit(call or path, charged, _count_results(body), remaining)
    return body


def _count_results(body: dict) -> int:
    if isinstance(body.get("reels"), list):
        return len(body["reels"])
    data = body.get("data", {})
    if isinstance(data, dict) and isinstance(data.get("reels"), list):
        return len(data["reels"])
    return 1


def save_json(name: str, obj) -> Path:
    p = DATA / name
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
    return p


def load_json(name: str):
    return json.loads((DATA / name).read_text())


def pct(n: int, d: int) -> str:
    return f"{(100 * n / d):.0f}%" if d else "—"
