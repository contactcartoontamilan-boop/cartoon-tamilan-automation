# V14 Instagram and Facebook scheduler

This adds an Oracle cron worker for one-time, explicitly scheduled Instagram
or Facebook image drafts. It checks due jobs and calls the existing V14
publisher. It does not create or infer approvals, credentials, image hosting,
or permission to publish. All existing V9/V10/V13 review and rights checks,
public HTTPS media checks, per-platform environment opt-ins, and duplicate
journal checks remain active.

## Configure on Oracle

1. Keep this checkout isolated from V13 production and install the V14
   requirements in its virtual environment.
2. Create `data/v14_scheduled_posts.json` from
   `data/v14_scheduled_posts.example.json`.
3. Add only a story whose V14 image draft is present in the queue. Set a
   unique `id`, choose `instagram` or `facebook`, give the exact owned
   CartoonTamilan story URL and a timezone-aware `scheduled_at` (India example:
   `2026-11-14T09:00:00+05:30`). Set
   `approved_for_scheduling: true` only after reviewing that image and caption
   and completing the existing rights/copy/visual approval steps. Leave
   `published: false`.
4. Configure the existing V14 live gates and local secrets as documented in
   `README_V14_SOCIAL_PUBLISH.md`. Instagram/Facebook require a public HTTPS
   image host reachable by Meta.
5. Run one safe check:
   `../ .venv/bin/python ct_v14_scheduler.py --poll-seconds 0`
   (remove the space after `../`; the intended executable is
   `./.venv/bin/python`). A not-due job should produce an empty result list.
6. Install a once-per-minute Oracle crontab entry after setup:

   ```cron
   * * * * * cd /home/ubuntu/cartoon-tamilan-v14-social-test && .venv/bin/python ct_v14_scheduler.py --poll-seconds 0 >> logs/v14_scheduler.log 2>&1
   ```

The script marks a confirmed post in a local SQLite state file. An uncertain
result is recorded and is never automatically retried. A blocked preflight
remains eligible for another check after the configuration or approval issue
is fixed. Neither GitHub Actions nor this PR turns live posting on by itself.
