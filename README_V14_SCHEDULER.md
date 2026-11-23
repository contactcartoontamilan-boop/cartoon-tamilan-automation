# V14 hourly CartoonTamilan publishing

The Oracle worker discovers existing CartoonTamilan stories from the homepage
and the /novel/ archive. It prepares one eligible existing story for each hourly
slot and publishes the same story to enabled channels. It never writes a new
website story. After every discovered story has been shared once, it starts a
new repost round, rotates through the archive again and changes the caption CTA
for that round so the post identity is new. The same URL can therefore be
shared again when the archive is exhausted.

## Current automatic channels

- Facebook and Instagram image posts use the existing V14 image queue.
- X image posts are added when X drafts exist and CT_V14_ENABLE_X=true.
- AI image, video and Tamil voice generation can run during the hourly refresh
  when both media gates are enabled.
- Ready AI video drafts can be scheduled as Instagram Reels, Instagram Stories,
  Facebook Reels and YouTube Shorts. The video publisher uses a durable
  delivery journal and does not retry uncertain uploads automatically.

Generated media is produced only when configured provider access is available.
The short promo generator creates title-inspired teaser material; it does not
claim to narrate the full story. A short clip is not a long-form YouTube video.

## Oracle configuration

Deploy this branch to the isolated V14 checkout and set private values in the
Oracle .env. Never put credentials in GitHub or chat.

Base image publishing:

- CT_V14_AUTO_SCHEDULE_QUEUE=true
- CT_V14_LIVE_PUBLISH=YES_I_APPROVE_V14
- DRY_RUN=false
- CT_V14_ENABLE_INSTAGRAM=true
- CT_V14_ENABLE_FACEBOOK=true
- META_PAGE_ID and META_PAGE_ACCESS_TOKEN
- INSTAGRAM_USER_ID
- PUBLIC_MEDIA_DIR and PUBLIC_MEDIA_BASE_URL; the public URL must serve generated
  JPG and MP4 files over HTTPS.

Optional X image posts require CT_V14_ENABLE_X=true and X_API_KEY, X_API_SECRET,
X_ACCESS_TOKEN and X_ACCESS_TOKEN_SECRET.

Optional media generation requires both ENABLE_AI_MEDIA_API=true and
CT_V14_HOURLY_MEDIA_ENABLED=true, plus the provider keys and model names
documented in README_MULTI_MODEL_AI.md. The provider can incur usage charges.

Opt-in video publishing requires the matching channel switches:

- Instagram Reels: CT_V14_ENABLE_INSTAGRAM_REELS=true
- Instagram Stories: CT_V14_ENABLE_INSTAGRAM_STORIES=true
- Facebook Reels: CT_V14_ENABLE_FACEBOOK_REELS=true
- YouTube Shorts: CT_V14_ENABLE_YOUTUBE_SHORTS=true

Meta video publishing also needs META_GRAPH_VERSION (defaults to v26.0) and
the same Page/Instagram access used for image publishing. YouTube Shorts uses
YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET and YOUTUBE_REFRESH_TOKEN with the
YouTube upload scope. YouTube videos are uploaded with public visibility when
that channel switch is enabled.

## Anime news and analytics

The hourly worker refreshes the RSS collector and analytics report. Configure
curated feeds in data/anime_news_sources.json. A source entry looks like:

```json
{"name":"Official studio news","url":"https://official.example/rss","official_source_confirmed":true,"allowed_hosts":["official.example"]}
```

Only add domains you have verified as official. Headlines are written to
output/v12/news_review_queue.json for fact and rights review; news is not
auto-published. Add a genuine analytics export at data/analytics_daily.csv
with date,pageviews,source,story_url columns. The worker writes
output/growth_report.json; without the CSV it reports analytics_csv_missing.
This is CSV analytics integration, not a live analytics API connection.

## Worker

Run the scheduler once per minute from Oracle cron:

```cron
* * * * * cd /home/ubuntu/cartoon-tamilan-v14-social-test && set -a && . ./.env && set +a && .venv/bin/python ct_v14_scheduler.py --poll-seconds 0 >> logs/v14_scheduler.log 2>&1
```

The worker schedules at most one fresh story per hourly slot. It records image
and video delivery attempts in SQLite. Meta or YouTube results that cannot be
confirmed are marked for reconciliation and are never blindly retried. A GitHub
Actions deployment does not itself create or publish a post.
