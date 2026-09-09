# Phase 0 spike (throwaway)

Validates three things before we build anything (see `plans/ROADMAP.md` Phase 0):
1. **Data quality** of the ScrapeCreators trending-reels endpoint.
2. **Affordability** of baseline-relative outlier scoring (credits per outlier).
3. **Usefulness** of hook extraction.

This is throwaway code. It does not use the real interfaces or DB.

## Setup

1. Create `scratch/.env` with:
   ```
   SCRAPECREATORS_API_KEY=your_key
   OPENAI_API_KEY=your_key
   ```
2. `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`
3. (optional, for step 3 on-screen text) `brew install ffmpeg`

## Run

```
python step1_trending.py       # 1 credit  -> data quality + candidates.json
python step2_baseline.py 10    # ~10 credits -> outliers.json + affordability
python step3_analyze.py 5      # 0 SC credits, small OpenAI cost -> hook breakdowns
```

Total ScrapeCreators cost: ~11 credits. Every call is logged to `data/credit_log.csv`.

## Exit decision
- Data clean, dupes manageable?
- Outlier scoring affordable (credits/outlier)?
- ≥3/5 hook breakdowns useful?

All yes → build Phase 1. Otherwise rethink cheaply.
