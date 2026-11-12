# CartoonTamilan image assets V3

## What is implemented

1. `asset_selector.py` detects website-local images (RSS image or a post's `og:image`/article image), and rejects third-party URLs masquerading as the website.
2. `image_sources.py` searches Openverse for CC0/Public Domain Mark records only, as a **fallback candidate**.
3. `asset_pipeline.py` downloads a valid candidate locally as PNG, checks format/size/dimensions, and saves `*.rights.json`.
4. `main.py` saves discovered website image metadata in each new draft but **does not auto-post candidate images**.
5. `test_assets.py` provides unit tests with mocked search results, no network required.

## Copyright and reliability

An image appearing on your own website does not prove you own it.
Openverse is a discovery index, and its license metadata is not guaranteed accurate.
Review the original landing page and copyright status, recognizable characters, brands and people before public commercial reuse.
An unrelated stock background must never be represented as an actual scene/character from your story.
Do not use copyrighted anime screenshots or posters without permission.

Openverse search is optional and is NOT enabled in `main.py`.
It is available through the separate `asset_pipeline.py --openverse` command.
All downloaded candidates remain review-required. No provider can guarantee 100% uptime or safe licensing.

## Termux test

```sh
cd ~/cartoon-tamilan-automation
git pull
pip install -r requirements.txt
python -m unittest test_assets.py test_poster.py -v
```

To create a fresh draft, note that the main workflow processes only new RSS items:

```sh
python main.py
```

To test one existing draft with asset discovery:

```sh
python asset_pipeline.py --draft "$(ls -t output/*.json | head -1)" --site https://cartoontamilan.in
```

If the post has no website-local image, it says no suitable image found.
To enable Openverse candidate search for **manual review only**:

```sh
python asset_pipeline.py --draft "$(ls -t output/*.json | head -1)" --openverse
```

Then inspect `output/assets/*.rights.json` and check the actual source license.
If a vetted image exists, use the V2 poster CLI with that `--artwork` path, preferably with a short verified `--headline`.

**Keep `DRY_RUN=true`, `PUBLISH_FACEBOOK=false`, and `PUBLISH_INSTAGRAM=false` until credentials, copyrights, media hosting and platform-specific publishing tests are complete.**
