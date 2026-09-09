"""
Phase 0 · Step 1 (real seeder) — niche keyword search on Instagram Reels.
Uses /v2/instagram/reels/search: niche-targeted, returns owner.follower_count inline
(so no separate profile call). Instagram exposes NO view count, so the outlier signal
is engagement-per-follower = (likes + comments) / followers.

Costs 1 credit per page.
Run: python step1_search.py "amazon seller india" [pages]
"""
import sys

from common import sc_get, save_json, pct


def audio_id(reel: dict):
    info = reel.get("clips_music_attribution_info") or {}
    return info.get("audio_id") or info.get("song_name")


def owner(reel: dict) -> dict:
    return reel.get("owner") or {}


def main() -> None:
    query = sys.argv[1] if len(sys.argv) > 1 else "amazon seller india"
    pages = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    reels: list[dict] = []
    for p in range(1, pages + 1):
        body = sc_get("/v2/instagram/reels/search",
                      params={"query": query, "date_posted": "last-month", "page": p},
                      call="reels_search")
        batch = body.get("reels") or []
        reels.extend(batch)
        print(f"page {p}: {len(batch)} reels  (credits_remaining={body.get('credits_remaining')})")

    save_json("search_raw.json", reels)
    total = len(reels)
    if total == 0:
        print("No reels returned — inspect data/search_raw.json")
        return

    # dedupe
    seen, uniq = set(), []
    for r in reels:
        vid = str(r.get("id") or r.get("shortcode"))
        if vid in seen:
            continue
        seen.add(vid)
        uniq.append(r)

    ads = sum(1 for r in uniq if r.get("is_ad") or r.get("is_paid_partnership"))
    print(f"\n=== '{query}' — {total} reels, {len(uniq)} unique "
          f"(dupes {pct(total - len(uniq), total)}), ads: {ads} ===")
    print("note: reels/search returns NO follower_count and NO view_count inline.")

    scored = []
    for r in uniq:
        o = owner(r)
        likes = r.get("like_count") or 0
        comments = r.get("comment_count") or 0
        cap = r.get("caption")
        scored.append({
            "video_id": str(r.get("id") or r.get("shortcode")),
            "username": o.get("username"),
            "is_verified": o.get("is_verified"),
            "likes": likes,
            "comments": comments,
            "engagement": likes + comments,
            "comment_ratio": round(comments / (likes + comments), 3) if (likes + comments) else 0,
            "is_ad": bool(r.get("is_ad") or r.get("is_paid_partnership")),
            "audio_id": audio_id(r),
            "taken_at": r.get("taken_at"),
            "video_url": r.get("video_url"),
            "caption": cap.get("text") if isinstance(cap, dict) else cap,
        })

    ranked = sorted(scored, key=lambda s: s["engagement"], reverse=True)
    save_json("candidates.json", ranked)

    print(f"\ncandidates ranked by absolute engagement -> data/candidates.json")
    print(f"{'user':24s} {'likes':>9s} {'comments':>9s} {'eng':>9s}  verified")
    for s in ranked[:12]:
        print(f"@{str(s['username'])[:22]:22s} {s['likes']:>9,} {s['comments']:>9,} "
              f"{s['engagement']:>9,}  {'✓' if s['is_verified'] else ''}{'  [ad]' if s['is_ad'] else ''}")


if __name__ == "__main__":
    main()
