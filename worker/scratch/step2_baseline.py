"""
Phase 0 · Step 2 — Is baseline-relative outlier scoring affordable? (Instagram)
reels/search gives no followers, so we profile each UNIQUE author (1 credit each) to get
follower_count, then compute the Instagram outlier signal:
    eng_per_follower = (likes + comments) / followers
The profile endpoint also returns recent video_view_counts (a per-account baseline we can
use later for TikTok-style scoring, and to sanity-check reach).

Run: python step2_baseline.py [N_authors]   (default 10)
"""
import sys
from statistics import median

from common import sc_get, save_json, load_json


def profile(handle: str):
    body = sc_get("/v1/instagram/profile",
                  params={"handle": handle, "cache_max_age": "7d"},
                  call="profile")
    user = (body.get("data") or {}).get("user") or body.get("user") or {}
    followers = ((user.get("edge_followed_by") or {}).get("count")
                 or user.get("follower_count"))
    edges = ((user.get("edge_owner_to_timeline_media") or {}).get("edges")) or []
    views = [e["node"].get("video_view_count") for e in edges
             if e.get("node", {}).get("video_view_count")]
    return followers, (int(median(views)) if views else None)


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    candidates = load_json("candidates.json")

    # unique authors, in engagement order, cap at n
    handles, seen = [], set()
    for c in candidates:
        h = c["username"]
        if h and h not in seen:
            seen.add(h)
            handles.append(h)
        if len(handles) >= n:
            break

    followers_by = {}
    baseline_by = {}
    credits = 0
    print(f"profiling {len(handles)} unique authors...")
    for h in handles:
        try:
            f, base = profile(h)
        except Exception as e:  # noqa: BLE001
            print(f"  @{h}: failed {e}")
            continue
        credits += 1
        followers_by[h] = f
        baseline_by[h] = base
        fstr = f"{f:,}" if f else "?"
        bstr = f"{base:,}" if base else "—"
        print(f"  @{h[:24]:24s} followers={fstr:>12s}  median_recent_views={bstr}")

    enriched = []
    for c in candidates:
        f = followers_by.get(c["username"])
        epf = round(c["engagement"] / f, 4) if f else None
        enriched.append({**c, "followers": f,
                         "baseline_median_views": baseline_by.get(c["username"]),
                         "eng_per_follower": epf})

    ranked = sorted([e for e in enriched if e["eng_per_follower"] is not None],
                    key=lambda e: e["eng_per_follower"], reverse=True)
    save_json("outliers.json", ranked)

    print(f"\n=== affordability ===")
    print(f"unique authors profiled: {credits} credits  ->  {len(ranked)} scorable outliers")
    if ranked:
        print(f"~{credits / len(ranked):.1f} credits per scorable outlier")
    print(f"\ntop outliers by engagement-per-follower -> data/outliers.json")
    print(f"{'user':24s} {'followers':>11s} {'eng':>8s} {'eng/foll':>9s}")
    for e in ranked[:12]:
        print(f"@{str(e['username'])[:22]:22s} {e['followers']:>11,} {e['engagement']:>8,} "
              f"{e['eng_per_follower']:>9.4f}{'  [ad]' if e['is_ad'] else ''}")


if __name__ == "__main__":
    main()
