# CartoonTamilan V14 — automated Facebook, Instagram and X image publishing

The command remains offline by default. When the existing live environment
switches and account credentials are configured on Oracle, the publisher
automatically checks and posts eligible queue drafts without manual content
approval.

## Automated checks and post content

- Posts only unpublished drafts linked to CartoonTamilan story pages.
- Verifies the queue/preview linkage, platform image dimensions and JPEG hash.
- Requires a non-empty story title and caption. Adds the title if missing.
- Adds #CartoonTamilan, #TamilStories and #TamilNovels when absent.
- Requires platform credentials, account publishing access, and a public HTTPS
  media URL that Meta can fetch.
- Uses a SQLite delivery journal; uncertain API results are not retried.

These checks validate structure and configured access. They do not guarantee
that every story detail or copyright claim is factually correct. Meta may
require app review and permissions for publishing.

## Oracle configuration

Set these on the Oracle host only; never commit secrets to GitHub or send them
in chat:

```env
DRY_RUN=false
CT_V14_LIVE_PUBLISH=YES_I_APPROVE_V14
CT_V14_ENABLE_INSTAGRAM=true
CT_V14_ENABLE_FACEBOOK=true
CT_V14_AUTO_SCHEDULE_QUEUE=true
META_PAGE_ID=...
META_PAGE_ACCESS_TOKEN=...
INSTAGRAM_USER_ID=...
PUBLIC_MEDIA_DIR=...
PUBLIC_MEDIA_BASE_URL=https://your-site.example/media
```

The `PUBLIC_MEDIA_DIR` must map to the public HTTPS URL in
`PUBLIC_MEDIA_BASE_URL`. Use a real served directory on your website.

Refresh the queue with:
```bash
.venv/bin/python ct_v14_social_queue.py prepare --outdir output/v14/image_posts
``

Run a one-time manual publish only when intended:
```bash
.venv/bin/python ct_v14_social_publish.py --platform instagram --live --confirm PUBLISH_REVIEWED_POSTS
```

For background publishing, follow `README_V14_SCHEDULER.md`. That worker
schedules the first eligible post about one minute after it starts, then one
story per day at 09:00 Asia/Kolkata on Instagram and Facebook.

Reels, Stories, token refresh and video uploads are not part of this image
publisher. A successful API response confirms a post ID; check the account if
you need to verify visibility. Do not blindly retry uncertain posts.
