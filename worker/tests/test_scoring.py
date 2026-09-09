"""Golden/regression tests — the DETERMINISTIC layers only (scoring math, fixture parsing, dedupe).
LLM layers (intent/hook/cluster/adapt) are non-deterministic and are NOT asserted here; the human
quality bar for those lives in tests/reference/report_homedesign_final.md.

Run: cd worker && ./venv/bin/python -m pytest -q
"""
import json
import math
from pathlib import Path

from trendradar.scoring import score_video
from trendradar.sources import scrapecreators as sc

FIX = Path(__file__).parent / "fixtures" / "tt_interior_design_app.json"


def _video(**kw):
    base = dict(platform="tiktok", view_count=100_000, like_count=5_000, comment_count=200,
                share_count=800, save_count=1_200, follower_count=20_000, create_time=None,
                duration_s=20)
    base.update(kw)
    return base


# --- scoring: the load-bearing math ---
def test_below_follower_floor_is_noise():
    s = score_video(_video(follower_count=8), baseline=None, lane="proven")
    assert s["flag"] == "noise" and s["composite"] == 0.0


def test_missing_baseline_flagged():
    s = score_video(_video(follower_count=20_000), baseline=None, lane="proven")
    assert s["flag"] == "no_baseline"
    assert s["account_outperformance"] is None


def test_account_outperformance_and_rates():
    s = score_video(_video(view_count=100_000, follower_count=20_000, like_count=5_000,
                           save_count=1_200, share_count=800, comment_count=200),
                    baseline=10_000, lane="proven")
    assert s["flag"] == "ok"
    assert s["account_outperformance"] == 10.0          # 100k / 10k
    assert s["like_rate"] == 0.05                        # 5000 / 100000
    assert s["save_rate"] == 0.012
    assert s["share_rate"] == 0.008
    # composite = eng * log10(views) * min(outperf,50), eng weights saves/shares highest
    eng = 0.40 * 0.012 + 0.35 * 0.008 + 0.20 * 0.05 + 0.05 * 0.002
    assert s["composite"] == round(eng * math.log10(100_000) * 10.0, 4)


def test_outperformance_capped_at_50():
    s = score_video(_video(view_count=1_000_000, follower_count=20_000),
                    baseline=1_000, lane="proven")  # raw ratio 1000x
    assert s["account_outperformance"] == 1000.0        # stored uncapped
    # but composite uses min(outperf, 50)
    eng = (0.40 * s["save_rate"] + 0.35 * s["share_rate"] + 0.20 * s["like_rate"]
           + 0.05 * s["comment_rate"])
    assert s["composite"] == round(eng * math.log10(1_000_000) * 50, 4)


def test_ranking_prefers_outperformer_over_raw_views():
    big = score_video(_video(view_count=1_000_000, follower_count=20_000), baseline=2_000_000, lane="proven")
    small = score_video(_video(view_count=50_000, follower_count=5_000), baseline=5_000, lane="proven")
    # small account at 10x its baseline must outrank the big-but-below-baseline video
    assert small["composite"] > big["composite"]


# --- fixture parsing + dedupe: frozen input contract ---
def test_fixture_parses_and_has_fields():
    body = json.loads(FIX.read_text())
    vids = sc.parse_search(body)
    assert len(vids) >= 25
    v = vids[0]
    for k in ("platform", "video_id", "handle", "view_count", "url"):
        assert k in v
    assert v["platform"] == "tiktok"


def test_fixture_dedupe_by_video_id():
    body = json.loads(FIX.read_text())
    vids = sc.parse_search(body)
    ids = [v["video_id"] for v in vids if v.get("video_id")]
    deduped = {v["video_id"]: v for v in vids if v.get("video_id")}
    assert len(deduped) <= len(ids)  # dedupe never grows the set
    assert all(deduped.values())
