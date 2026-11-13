# CartoonTamilan V14 — automatic website image-post preview (first milestone)

This is a **V14-only additive preview**, not an automated live publisher.
It reuses the existing V13 tested modules; V13 production code and timers
are not modified.

## What it does

1. Discovers original-story catalogue links from https://cartoontamilan.in/
   using `auto_story_marketing.discover` (best-effort static HTML; no fake URLs).
2. Selects 1–3 website stories by existing deterministic daily rotation.
3. Uses an available **same-site, existing cover** as source artwork.
4. Generates 10 platform-specific JPEG layouts with Tamil titles and CTA via
   `ctos.creative.render_pack`; captions, email drafts and social export
   drafts are produced by the existing V13 preview pipeline.
5. Verifies V13 image QA, manifest status and saved files, then writes
   `output/v14/image_posts/image_post_index.json`.
6. Does **not** call any publishing or email-sending API. Requires manual
   source-rights, Tamil text, visual and story-match review.

This first milestone **does not** create new AI anime images, read full chapters,
write a video narration or render V14 60–120-second story videos.
The V14 website-to-video integration remains a separate next step.

## Oracle Ubuntu: safe isolated checkout

Run on **Oracle SSH**, not in the local Android Termux shell.

```bash
cd ~/cartoon-tamilan-v14-test
git fetch origin feature/v14-image-post-preview
git switch -c v14-image-post-local --track origin/feature/v14-image-post-preview
.venv/bin/python -m unittest test_ct_v14_image_post.py test_ct_v14.py -v
```

If the new branch already exists locally, switch to it rather than creating it
again. Do not run `git pull` or install this branch in the production
`~/cartoon-tamilan-automation` worktree.

## Generate the first image-post draft

```bash
cd ~/cartoon-tamilan-v14-test
.venv/bin/python ct_v14_image_post.py --limit 1
.venv/bin/python ct_v14_image_post.py --status
find output/v14/image_posts -name instagram_feed.jpg -type f
find output/v14/image_posts -name platform_drafts.json -type f
```

Open the saved `instagram_feed.jpg` to inspect it. Also check the
`facebook_feed.jpg`, `instagram_story.jpg`, captions, and manifest.
The `--status` command reads the local result without network access.

If no original stories are found, the website has changed layout or is
JavaScript-driven, the site returns an error, or a source cover is unavailable,
the run fails/partially fails. It does not invent content or claim success.
Inspect the index and the V13-format report under the V14 output directory.

## QA and production safety

- GitHub branch: `feature/v14-image-post-preview` based on the isolated V14
  story-video branch. **Not merged into main**.
- All files generated in `output/v14/image_posts/`, which is gitignored.
- Real source cover is **not AI-generated**; copyright and permission review
  remain required even for the owner's own website.
- Existing V13 live posting and email permissions are not used.
- Do not automatically schedule or publish before website and image QA.
- Oracle ARM CPU can render these layouts without a GPU; install the repo's
  dependencies, Noto Tamil font, and RAQM support as described in V13 README.
- The offline tests use a mock story and dummy images; passing them does not
  prove the live website is accessible or that a real poster was rendered.

## Rollback

Switch back to `v14-local-test` in the isolated V14 worktree. No production
files, systemd services, Meta settings, or email state are changed.
