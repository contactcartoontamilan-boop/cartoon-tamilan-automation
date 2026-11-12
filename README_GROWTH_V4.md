# CartoonTamilan 10K Growth Engine V4

Goal: increase genuine original-story readers from the current estimated 0–100 daily website views toward 10,000 daily **pageviews**. No growth guarantee.

## What V4 actually does
- Creates bilingual, platform-specific *drafts* with trackable UTM links for Facebook, Instagram, YouTube, Pinterest and Threads.
- Makes conservative story CTAs only from known title + link; does not hallucinate chapter details.
- Produces a report from **real manually exported analytics CSV**, with no fabricated traffic.
- Does **not** automatically publish, read private analytics, generate images, or create fake traffic.

## Termux testing

```sh
cd ~/cartoon-tamilan-automation
git pull
python -m unittest test_growth.py -v
python growth_engine.py --drafts output --out output/growth_campaigns --limit 5
python growth_analytics.py
```

Without real CSV, analytics prints **NO DATA**, which is correct.

## Analytics CSV (private, local; never commit)

Create `data/analytics_daily.csv` with actual exported measurements. Use the exact columns:

```text
date,pageviews,source,story_url
```

This is a **normalized input format**, not a direct Google Analytics export. You must map the actual GA4/export fields to these columns and avoid double-counting. Each row should represent measured pageviews for one date/source/story-page combination.

Then:

```sh
python growth_analytics.py --csv data/analytics_daily.csv --out output/growth_report.json
```

Recommended: install GA4 on the website, connect Google Search Console and verify tags. Later add a read-only Google Analytics Data API connector; only then can V4 report real traffic automatically.

## Growth operating strategy
- Prioritize original stories and chapter-one reading links (70% of content efforts).
- Use original Tamil anime meme concepts and verified relevant news for discovery (20%).
- Use community prompts, polls and returning-reader campaigns (10%).
- Measure actual landing-page visits, chapter reads, chapter-one-to-two retention, returning users and organic clicks.
- Test one promotional hypothesis per week. Retire ideas that get views but no readers.

Security: no tokens in repository; keep DRY_RUN=true, PUBLISH_FACEBOOK=false and PUBLISH_INSTAGRAM=false until independently tested.
