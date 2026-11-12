# CartoonTamilan V6 — Auto Story Cover / Error Handling

## Fixes in this version

- No more hard-coded `my_anime_art.png` file required when using `--auto-cover`.
- Reads the **selected story draft** and uses its image URL or visits the exact story page for a featured cover.
- Accepts same-site `og:image`, `twitter:image`, featured/article lazy images and first srcset candidate.
- Checks HTTPS site identity, image validity, size and dimensions via the existing downloader; blocks redirects/private addresses.
- Saves cover image and a `.rights.json` file (not automatic publication permission).
- Clear error if a cover is absent, uses JavaScript rendering, is hosted on external CDN, or is not available.
- Skips Openverse for this workflow; its observed 504 timeout should not block story-cover retrieval.

## Termux test commands

```sh
cd ~/cartoon-tamilan-automation
git pull
python -m unittest test_auto_story_cover.py test_assets.py test_poster.py test_studio_v5.py test_growth.py -v
```

To select one existing story draft (these are produced by `python main.py`):

```sh
find output -maxdepth 1 -name '*.json' | head
```

Use the exact same draft for cover extraction and poster rendering:

```sh
DRAFT="$(ls -t output/*.json | head -1)"
python auto_story_cover.py --draft "$DRAFT"
python creative_studio_v5.py --draft "$DRAFT" --auto-cover --headline "புதிய தமிழ் கதை" --outdir output/creative_v6
```

If successful, inspect:

```sh
ls -lh output/creative_v6/
cp output/creative_v6/story_poster.png ~/storage/downloads/cartoon_story_poster_v6.png
```

Only copy the output if the poster command succeeded. Verify that the image is the *same story*, that you own/license it, and the Tamil text renders cleanly.

## Known limitations and next steps

- A screenshot showing a cover in a browser does **not** guarantee the static HTML has a discoverable, same-domain image URL. Javascript-only sites or external media hosts need custom site-specific extraction, verified first.
- It uses the existing image as a poster component; **does not generate new anime artwork or 3D models**.
- Publisher must remain disabled; `DRY_RUN=true` with `PUBLISH_FACEBOOK=false` and `PUBLISH_INSTAGRAM=false`.
- Unit tests run offline; success in live Termux or Oracle depends on site HTML, network, fonts, and available media rights.

## V6 updated quick commands

```sh
cd ~/cartoon-tamilan-automation
git pull
python -m unittest test_auto_story_cover.py test_assets.py test_poster.py test_studio_v5.py -v
python auto_story_cover.py --draft latest --poster --headline 'புதிய தமிழ் கதை'
python creative_studio_v5.py --draft latest --auto-cover --headline 'புதிய தமிழ் கதை' --outdir output/creative_v6
```

The script now picks the most recent **story** draft automatically. Do not copy the resulting image until the command reports successful completion. The srcset extractor now prefers its last entry, which is normally higher resolution.

## V6.1 critical bug fix (November 2026)

Termux reported `FAILED (errors=1)` because the test mocks the image downloader and the destination directory did not exist when `.rights.json` was written. `auto_story_cover.py` now creates that directory itself before downloading/writing metadata. Re-run tests; prior passing tests did not verify real website compatibility.

**Important content classification correction:** Your RSS test selected a `Kodansha USA licenses new manga` article. That is anime news, **not an original CartoonTamilan novel**. Previously `config.yaml` incorrectly labeled every RSS entry as `kind: story`; this has been changed to `kind: news` to prevent misleading promotional copy. Old `output/*.json` files remain mislabeled unless regenerated, so do not rely on `--draft latest` for an original novel yet.

For a real ORIGINAL story, copy its exact URL from the website and run:

```sh
cd ~/cartoon-tamilan-automation
git pull
python -m unittest test_auto_story_cover.py -v
python auto_story_cover.py --story-url "https://cartoontamilan.in/REPLACE-WITH-REAL-NOVEL-URL" --diagnose
python auto_story_cover.py --story-url "https://cartoontamilan.in/REPLACE-WITH-REAL-NOVEL-URL" --poster --headline "புதிய தமிழ் கதை"
```

Replace the placeholder URL with an **actual original novel page**, not the news article or homepage. If `Matching same-site cover: (none)` remains, inspect the printed `IMG:` sources and send the output for CDN/JavaScript adaptation; the code intentionally will not fetch arbitrary third-party images.

Only after `Poster saved:` is printed should you run:

```sh
cp output/covers/story_poster.png ~/storage/downloads/cartoon_story_poster.png
```

The commands `Cover candidate saved: ...` and `Poster saved: ...` are *messages printed by Python*, never commands to type at the `$` prompt.
