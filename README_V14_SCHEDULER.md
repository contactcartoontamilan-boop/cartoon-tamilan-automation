# V14 Instagram and Facebook auto-publisher

The Oracle worker automatically schedules unpublished V14 image drafts for
Instagram and Facebook. It uses each queue draft's image and caption, adds the
story title if missing, and appends #CartoonTamilan, #TamilStories and
#TamilNovels when absent. The first eligible story is scheduled about one
minute after the worker starts; later stories use daily 09:00 Asia/Kolkata
slots, one story per day, on both channels.

No manual content approvals are checked. Automated preflight still verifies
that the story belongs to CartoonTamilan, the draft is unpublished, image
dimensions and hash match the source, the caption is present, credentials and
platform publishing access exist, and Meta can fetch the image over public
HTTPS. This does not replace Meta permissions or verify factual/copyright
claims beyond the source data.

## Oracle setup

1. Deploy this branch to the isolated V14 checkout and install requirements.
2. Refresh the queue:
   `./.venv/bin/python ct_v14_social_queue.py prepare --outdir output/v14/image_posts`
3. In Oracle's private `.env`, set:
   - `CT_V14_AUTO_SCHEDULE_QUEUE=true`
   - `CT_V14_LIVE_PUBLISH=YES_I_APPROVE_V14`
   - `DRY_RUN=false`
   - `CT_V14_ENABLE_INSTAGRAM=true`
   - `CT_V14_ENABLE_FACEBOOK=true`
   Keep Meta credentials out of GitHub and chat. Set
   `PUBLIC_MEDIA_DIR` to a directory actually served by your site and
   `PUBLIC_MEDIA_BASE_URL` to its public HTTPS URL.
4. Start the worker every minute from Oracle cron:
   ```cron
   * * * * * cd /home/ubuntu/cartoon-tamilan-v14-social-test && set -a && . ./.env && set +a && .venv/bin/python ct_v14_scheduler.py --poll-seconds 0 >> logs/v14_scheduler.log 2>&1
   ```

The worker records each attempt in SQLite. An uncertain Meta result is not
retried automatically to prevent duplicate posts. Reels and Stories require
video assets and a separate publishing workflow. GitHub Actions does not post.
