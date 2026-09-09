"""
Phase 0 · Step 1 — Data quality of the ScrapeCreators trending-reels endpoint.
Costs 1 credit. Saves raw JSON, reports duplicate rate + field coverage.

Run: python step1_trending.py
"""
from common import sc_get, save_json, pct


def dig_audio_id(reel: dict):
    """Best-effort extraction of the sound/music id from clips_metadata."""
    cm = reel.get("clips_metadata") or {}
    for path in (
        ("music_info", "music_asset_info", "audio_cluster_id"),
        ("original_sound_info", "audio_asset_id"),
        ("music_info", "music_asset_info", "id"),
    ):
        cur = cm
        ok = True
        for k in path:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                ok = False
                break
        if ok and cur:
            return str(cur)
    return None


def main() -> None:
    body = sc_get("/v1/instagram/reels/trending", call="trending")
    save_json("trending_raw.json", body)

    reels = (body.get("data") or {}).get("reels") or []
    total = len(reels)
    if total == 0:
        print("No reels returned. Raw body saved to data/trending_raw.json — inspect it.")
        print("Top-level keys:", list(body.keys()))
        return

    ids = [str(r.get("id") or r.get("pk")) for r in reels]
    unique = len(set(ids))

    fields = {
        "like_count": 0, "comment_count": 0, "play_count": 0,
        "ig_play_count": 0, "share_count": 0, "save_count": 0,
        "video_url": 0, "caption": 0, "taken_at": 0, "audio_id": 0,
        "user.username": 0,
    }
    for r in reels:
        for k in ("like_count", "comment_count", "play_count", "ig_play_count",
                  "share_count", "save_count", "video_url", "taken_at"):
            if r.get(k) not in (None, ""):
                fields[k] += 1
        cap = r.get("caption")
        if cap not in (None, "") and (not isinstance(cap, dict) or cap.get("text")):
            fields["caption"] += 1
        if (r.get("user") or {}).get("username"):
            fields["user.username"] += 1
        if dig_audio_id(r):
            fields["audio_id"] += 1

    print(f"\n=== TRENDING REELS: data quality ===")
    print(f"returned:        {total}")
    print(f"unique by id:    {unique}  (dupes: {total - unique}, {pct(total - unique, total)})")
    print(f"credits_remaining: {body.get('credits_remaining', '?')}")
    print(f"\nfield coverage (non-null / {total}):")
    for k, v in fields.items():
        flag = "  <-- missing/rare" if v < total * 0.5 else ""
        print(f"  {k:16s} {v:3d}  {pct(v, total):>4s}{flag}")

    # rough candidate ranking by play_count for step 2
    def views(r):
        return r.get("play_count") or r.get("ig_play_count") or 0
    top = sorted(reels, key=views, reverse=True)[:12]
    candidates = [{
        "video_id": str(r.get("id") or r.get("pk")),
        "username": (r.get("user") or {}).get("username"),
        "views": views(r),
        "likes": r.get("like_count"),
        "comments": r.get("comment_count"),
        "audio_id": dig_audio_id(r),
        "video_url": r.get("video_url"),
        "caption": (r.get("caption") or {}).get("text") if isinstance(r.get("caption"), dict) else r.get("caption"),
    } for r in top]
    save_json("candidates.json", candidates)

    print(f"\ntop {len(candidates)} candidates by views -> data/candidates.json")
    for c in candidates[:12]:
        print(f"  @{str(c['username'])[:22]:22s} views={c['views']:>10,}  likes={c['likes']}  comments={c['comments']}")


if __name__ == "__main__":
    main()
