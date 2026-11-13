# V14 Instagram and Facebook auto-publisher

The Oracle worker can automatically schedule reviewed V14 image drafts for
Instagram and Facebook. It reuses each queue draft's existing image and exact
caption text (including any title/hashtags already present in that caption).
For each eligible story it schedules both channels on the same daily slot,
starting at 09:00 Asia/Kolkata. Later stories use the next day.

A draft is eligible only after the existing story-rights, copy and V10 visual
approval checks pass. The worker never invents or grants approval. It skips
unapproved/invalid drafts. Reels and Stories are not included: they need video
assets and a separate publishing flow.

## Oracle setup

1. Deploy this branch into the isolated V14 checkout and install the V14
   requirements in its virtual environment.
2. Prepare or refresh the queue from the generated image-post preview:
   `./.venv/bin/python ct_v14_social_queue.py prepare --outdir output/v14/image_posts`
3. Configure the V14 live-publish variables and private secrets as described
   in `README_V14_SOCIAL_PUBLISH.md`. Facebook and Instagram also need a
   public HTTPS media host that Meta can fetch. Never commit access tokens to
   GitHub.
4. Set these variables in the Oracle service environment only after reviewing
   the intended live-publishing behavior:
   - `CT_V14_AUTO_SCHEDULE_APPROVED_QUEUE=true` to discover approved queue
     items and create the daily jobs.
   - `CT_V14_LIVE_PUBLISH=YES_I_APPROVE_V14`
   - `DRY_RUN=false`
   - `CT_V14_ENABLE_INSTAGRAM=true`
   - `CT_V14_ENABLE_FACEBOOK=true`
   The publisher also requires its explicit confirmation constant internally,
   checks approvals again immediately before publishing, and validates the
   image, account configuration, HTTPS host, and duplicate journal.
5. First run once and inspect the output:
   `./.venv/bin/python ct_v14_scheduler.py --poll-seconds 0`
   It reports how many approved jobs it added. Future jobs are scheduled for
   09:00 India time, one story per day, on both channels.
6. Run the worker every minute from Oracle cron:
   ```cron
   * * * * * cd /home/ubuntu/cartoon-tamilan-v14-social-test && .venv/bin/python ct_v14_scheduler.py --poll-seconds 0 >> logs/v14_scheduler.log 2>&1
   ```

The worker only publishes due jobs while all live gates are enabled. Posts
with uncertain API outcomes are recorded for manual reconciliation and are
never retried automatically, to avoid duplicate posts. Keep the schedule,
SQLite state, publish journal, queue, media files and credentials on the
Oracle server. GitHub Actions does not publish posts.
