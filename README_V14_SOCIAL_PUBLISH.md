# CartoonTamilan V14 — Facebook, Instagram and X (Twitter) image publishing QA

**Experimental, isolated feature branch. Production V13 remains unchanged.**

This adds a **review-gated, one-story-at-a-time** publisher for V14 image drafts.
The command is **dry-run by default** and **does not start a scheduler**.
No credentials are included. A GitHub test passing does **not** prove an
actual post was uploaded to a real account.

## What is integrated

- **Facebook Page photo:** reuses `social.facebook.publish_photo` (Meta Graph API).
- **Instagram Professional feed image:** reuses the existing container creation,
  processing poll and `media_publish` adapter. The account must be eligible
  for the chosen Meta API login flow and linked/configured correctly.
- **X image Post:** uses the official X API v2 chunked media
  `/2/media/upload/initialize`, `/{id}/append`, `/{id}/finalize`,
  optional processing-status check, then `POST /2/tweets`.
  Requires developer access, user-context OAuth credentials, and any applicable
  billing/credits. X is not assumed free.
- Every platform uses its own existing V14 caption and image export.
- Revalidates the source preview, queue identity, JPEG dimensions and SHA-256
  against the source manifest; changed artwork or copy is blocked.
- **Manual approval gates:** V13 tamper-evident approval via
  `ctos.review.require_approval`, plus V9 story rights/copy and V10 visual
  policy approval. These are **not** granted automatically.
- SQLite attempt journal in `data/ct_v14_publish_journal.sqlite3`
  (already ignored by Git). Marks `inflight` before network calls; a
  timeout/crash is **not retried automatically**. Confirm on the platform
  before reconciling an `uncertain` entry.
- The default run has no platform network calls and creates no journal.
- One invocation handles **one verified story**, up to one image per channel.
  This is **not** background 24/7 automatic posting yet.

## Termux isolated test (safe, no real publishing)

Do not run in `~/cartoon-tamilan-automation` (V13 production).
Clone the isolated V14 branch to a **new** folder:

```bash
cd ~
git clone --depth 1 --branch feature/v14-social-publish-fb-ig-x-qa \
  https://github.com/contactcartoontamilan-boop/cartoon-tamilan-automation.git \
  cartoon-tamilan-v14-social-test
cd ~/cartoon-tamilan-v14-social-test
PY="$HOME/cartoon-tamilan-v14-image-post-test/.venv/bin/python"
"$PY" -m unittest test_ct_v14_social_publish.py -v
"$PY" ct_v14_social_queue.py create-and-prepare --limit 1
"$PY" ct_v14_social_publish.py --platform all
```

If that shared Python path is missing, create a separate venv in the new
checkout and install `requirements.txt` (Termux Pillow/RAQM setup may need
the existing working Termux build):

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
PY="$PWD/.venv/bin/python"
```

Expected dry-run output: `"status": "dry_run_only"`,
`"network_calls": 0`, `"published": false`, and three items:
Facebook, Instagram, X. Check the images and captions in
`output/v14/image_posts` first.

## Before a live test (manual setup and review)

1. Open the **actual** JPEGs and verify original-story ownership, commercial
   cover rights, image crop, Tamil title, caption and each platform CTA.
2. Complete the existing V9/V10 story approval and V13 manifest snapshot
   approval workflows. If either is missing, live publishing must fail.
   Do **not** mark approvals true without performing those checks.
3. Obtain Meta Page ID, Meta Page token with correct Page publishing rights,
   and Instagram Professional user ID with Instagram content publishing access.
   Meta may require app review/permissions. The Meta JPEG must be hosted on a
   **public HTTPS** URL that Meta can fetch; configure
   `PUBLIC_MEDIA_DIR` and `PUBLIC_MEDIA_BASE_URL`. The existing
   `campaign_v9.publish_media_url` verifies HTTPS availability and JPEG MIME.
4. Obtain **X developer API** user-context OAuth 1.0a credentials and confirm
   media/write permissions, applicable pricing and account rate limits. For X
   image upload only, install `requests-oauthlib` in the isolated venv:
   `"$PY" -m pip install requests-oauthlib`.
5. Store credentials in the **local server environment only**, never in a
   GitHub commit, screenshot, issue, chat message or shared log. Required keys:
   `META_PAGE_ID`, `META_PAGE_ACCESS_TOKEN`, `INSTAGRAM_USER_ID`,
   `PUBLIC_MEDIA_DIR`, `PUBLIC_MEDIA_BASE_URL`,
   `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`,
   `X_ACCESS_TOKEN_SECRET`.
6. Do a **single-channel** live test on a suitable account, using a reviewed
   image and caption. Review the resulting post in the actual app before
   enabling the other channels.

Live mode requires **all** of the following (the values are explicit opt-ins,
not default settings):

```bash
export DRY_RUN=false
export CT_V14_LIVE_PUBLISH=YES_I_APPROVE_V14
export CT_V14_ENABLE_FACEBOOK=true
# Enable the other platforms only after their separate review:
# export CT_V14_ENABLE_INSTAGRAM=true
# export CT_V14_ENABLE_X=true
"$PY" ct_v14_social_publish.py --platform facebook \
  --live --confirm PUBLISH_REVIEWED_POSTS
```

For the Instagram or X test, change `--platform` and explicitly enable the
corresponding `CT_V14_ENABLE_INSTAGRAM` or `CT_V14_ENABLE_X` variable.
For one already-reviewed story across all three platforms, enable all three
flags and use `--platform all`. If any channel lacks approvals/credentials,
the command **preflights all three before sending any post**.

**Never run the live command just to test whether it works:** it is intended
to publish publicly. The safe test command omits `--live`.

## Important limits and failure policy

- The journal is independent of V9's existing publication state. Before the
  first V14 live test, check that the story has not already been posted by V9.
- A successful API response ID is recorded, but **real post visibility still
  needs account-side verification**. A timeout may still have published.
- `uncertain` entries are deliberately blocked from automatic retries.
  Do not delete the journal to retry blindly.
- No auto-scheduler, account token refresh, metrics, Reels, Stories or
  long-form video uploads are implemented by this file.
- X image size must be at most 5 MB; a conservative 280-character caption
  guard avoids unintended truncation. If it blocks a draft, revise the
  caption in the normal preview workflow and reapprove it; do not bypass
  the SHA-256/identity checks.
- The code and unit tests cannot establish that an account's OAuth tokens,
  API permissions, pricing, quota or live network requests work. Those must
  be verified in the user's own accounts.

Official references:
- Meta Graph API: https://developers.facebook.com/docs/graph-api/overview/
- Facebook Page photos: https://developers.facebook.com/docs/graph-api/reference/photo/
- Instagram media: https://developers.facebook.com/docs/graph-api/reference/ig-user/media/
- X chunked upload: https://docs.x.com/x-api/media/quickstart/media-upload-chunked
- X create Post: https://docs.x.com/x-api/posts/manage-tweets/quickstart
