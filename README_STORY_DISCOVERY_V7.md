# CartoonTamilan V7 — Automatic Story Discovery and Poster Drafts

The user no longer has to copy and paste each original novel URL.

## Commands (Termux)

```sh
cd ~/cartoon-tamilan-automation
git pull
python -m unittest test_story_marketing.py test_auto_story_cover.py -v
python auto_story_marketing.py --discover-only --limit 10
python auto_story_marketing.py --limit 10
```

Review the output under `output/story_discovery/report.json`. Each discovered story gets a `draft.json`; poster output exists only if the site exposes a downloadable same-site cover image and Tamil text rendering works.

To copy an actual successful poster to Android Downloads:

```sh
find output/story_discovery -name poster.png -type f
```

Choose one exact returned path and run `cp <that-path> ~/storage/downloads/` (do not type placeholders literally).

## Guardrails

- This is a **best-effort static HTML catalogue parser**. It detects strong novel-card/status evidence. If site relies on JS or external API, it may return zero and must be adapted to a verified source.
- It intentionally excludes chapter/episode and generic news links. Check report to ensure correct story association.
- It uses existing licensed cover images for template posters; **does not create new anime illustrations or 3D models**.
- Site cover downloads are limited to same-site HTTPS media. External CDNs require an explicitly vetted allowlist. Rights are not proved by hosting a cover.
- The script never publishes social posts; keep `DRY_RUN=true`, `PUBLISH_FACEBOOK=false`, `PUBLISH_INSTAGRAM=false`.
- Unit tests are offline and do not prove the live site layout works.

## V7.1: Clean headlines and Android review gallery

The original six-story report showed titles polluted by status/author metadata (`Completed`, `CT Admin`, etc.). `auto_story_marketing.py` now removes status suffixes and uses per-story names for poster headlines. Re-run the generator to regenerate new posters with corrected names.

You can **first view the six already generated posters without re-downloading**:

```sh
cd ~/cartoon-tamilan-automation
git pull
python -m unittest test_story_marketing.py test_review_posters.py -v
python review_posters.py --download-dir ~/storage/downloads/CartoonTamilanPosters
```

Open phone File Manager > Downloads > CartoonTamilanPosters > contact_sheet.png. The folder contains individually numbered poster PNGs and `story_index.txt` mapping each to its actual novel URL.

After review, optionally rebuild with cleaned titles:

```sh
python auto_story_marketing.py --limit 10
python review_posters.py --download-dir ~/storage/downloads/CartoonTamilanPosters
```

Do not enable publishing until each cover is licensed and Tamil text, story-to-cover match, layout and cropped images have been reviewed. The script does not automatically generate new anime characters or 3D models.
