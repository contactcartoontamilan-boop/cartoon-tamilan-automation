# CartoonTamilan V14 — automatic image-post PREVIEW (no publishing)

This is the first isolated V14 automation step. It **reuses the existing V13
website story discovery, licensed/approved cover fetch, Tamil typography and
10-platform image-layout pipeline** rather than copying or modifying V13 code.

## What the new command does

1. Automatically discovers a CartoonTamilan.in original novel card.
2. Reads its title, story URL and existing same-site cover (if available).
3. Creates review-only JPG designs in 10 formats, including Instagram and
   Facebook feeds, Stories, YouTube thumbnail, Pinterest, X and LinkedIn.
4. Saves draft captions, a per-story manifest and platform draft exports.
5. Verifies that exported images exist, are JPEGs of expected dimensions, and
   records their SHA-256 hashes in `image_post_preview.json`.

**No manual Tamil narration is required for image posts.** This workflow does
not read complete chapters or create a 60–120 second video. That is a separate
V14 integration task.

**This is NOT live posting or a scheduler.** Nothing is sent to Facebook,
Instagram, Telegram, YouTube, email or other services. All covers, text,
licenses and post content require human review before any separate, explicitly
approved publishing action.

## Oracle Ubuntu test in a NEW isolated worktree

Run on the **Oracle SSH prompt**, not on Android's local Termux shell. Leave
`~/cartoon-tamilan-automation` (V13 production) and
`~/cartoon-tamilan-v14-test` untouched.

```bash
cd ~/cartoon-tamilan-v14-test
git fetch origin feature/v14-auto-image-post-preview
git worktree add -b v14-image-post-local \
  ~/cartoon-tamilan-v14-image-post-test \
  origin/feature/v14-auto-image-post-preview

cd ~/cartoon-tamilan-v14-image-post-test
sudo apt-get install -y fonts-noto-core libraqm0
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

.venv/bin/python -m unittest test_ct_v14_image_post.py -v
.venv/bin/python ct_v14_image_post.py create --limit 1
.venv/bin/python ct_v14_image_post.py status
find output/v14/image_posts -name instagram_feed.jpg -type f
```

The CLI returns a nonzero exit code if no image post was saved. Inspect
`output/v14/image_posts/image_post_preview.json` for failures and file paths.

Example output layout (paths include the actual run date and story ID):

```text
output/v14/image_posts/
  image_post_preview.json
  latest.json
  YYYY-MM-DD/
    report.json
    STORY_ID/
      source_story.json
      original_cover/
      media/
        instagram_feed.jpg
        facebook_feed.jpg
        instagram_story.jpg
        youtube_thumbnail.jpg
        ...
      platform_drafts.json
      manifest.json
      email/newsletter.html
```

The existing V13 renderer also saves an email **draft**, but does not send it.

## Requirements / known limits

- The site must expose discoverable static novel cards and a usable same-site
  cover image. The command reports failure instead of inventing a story,
  image or successful post.
- Cover mode uses the website's existing artwork; it is **not AI-generated
  character art**. Hosting artwork does not prove rights for promotion.
- The image renderer needs working Pillow RAQM and Tamil fonts.
- Source covers may already contain printed text or watermarks, which require
  human visual review.
- Image generation does not prove story-character accuracy. Review the
  source URL, image crop, Tamil headline and captions.
- Tests are offline. Real website access and Oracle rendering need to be
  run and verified by the owner; GitHub commits alone do not produce a
  server-side JPG.
- This branch is a proposed review-first addition, not a V13 deployment.
