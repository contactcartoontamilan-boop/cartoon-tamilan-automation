# CartoonTamilan V2 — Termux testing

The V2 poster generator is a **quality-gated template compositor**, not an AI image generator.
It refuses to publish or make a fake anime illustration. Provide an original or licensed image.

## Termux preparation

```sh
pkg install harfbuzz fribidi freetype libraqm -y
python -c "from PIL import features; print('RAQM:', features.check('raqm'))"
python -m unittest test_poster.py -v
```

Tests must say **OK** without `skipped`. A missing Tamil font or English font may still require setup.

## Create a poster from your own artwork

Put your original artwork in Downloads as `my_anime_art.png`, then:

```sh
cd ~/cartoon-tamilan-automation
python poster_generator.py --draft "$(ls -t output/*.json | head -1)" --artwork ~/storage/downloads/my_anime_art.png --headline "புதிய தமிழ் அனிமே கதை" --mode story --out output/story_poster_v2.png
cp output/story_poster_v2.png ~/storage/downloads/
```

Use `--mode meme` for a meme, or `--mode news` for news; review each headline and rights to artwork before posting.

**Important:** A passing dimensions test does not prove visual correctness. Open the PNG on your phone and review Tamil glyph shaping, grammar, contrast, cropping, and brand quality. `DRY_RUN=true` and both publishing flags should remain disabled until reviewed.

## What is not yet implemented

No local generative AI illustration/3D generation, automated Tamil proofreading, video/voiceover generation, or end-to-end live publication validation is included in this V2 poster module. These require separate modules and tests.
