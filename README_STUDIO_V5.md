# CartoonTamilan Creative Studio V5

Goal: 10K genuine daily website pageviews, prioritizing original novels and returning readers. V5 produces marketing **drafts** and visual edits from user-owned/licensed artwork; it does not guarantee traffic or publish to Instagram/Facebook.

## New files
- `social_content_v5.py`: Tamil and English story introductions, Facebook/Instagram captions, limited genre-relevant hashtags and UTM campaign links, plus creative prompts.
- `creative_studio_v5.py`: Illustration color enhancement, cinematic pseudo-3D depth treatment, and branded story poster from an image supplied by you.
- `test_studio_v5.py`: six offline tests.

### Limitations
- Tamil story intro is based on the title and RSS summary, not a verified full chapter analysis; review before publishing.
- English intro is a basic template, not a translation. Supply verified English story synopsis with `--intro-en`.
- No generative AI model or 3D mesh generator has been installed. `cinematic_depth_style.png` is an image effect on an existing illustration.
- Artwork must be owned or licensed. A photo found on your website is not automatically safe if copyrighted by someone else.
- Instagram feed captions do not contain clickable links; place the campaign link in the profile/bio or another supported link destination.
- Facebook/Instagram API modules are separate; **V5 does not enable posting.**

## Termux step-by-step

```sh
cd ~/cartoon-tamilan-automation
git pull
pip install -r requirements.txt
python -m unittest test_studio_v5.py test_poster.py test_growth.py -v
```

Create five-platform + bilingual content drafts for the latest existing story:

```sh
python social_content_v5.py --draft "$(ls -t output/*.json | head -1)" --out output/social_pack_v5.json
```

Check output:
```sh
python -m json.tool output/social_pack_v5.json
```

The item must be a `kind=story` draft from your own site. If the latest file is a news item, select a known story draft from `output/` instead.

### Use a story cover image

If you own the cover art, copy it to your phone's Downloads folder as `my_anime_art.png`, or download a candidate via `asset_pipeline.py` and **verify the original rights/source before use**.

```sh
python creative_studio_v5.py --draft "$(ls -t output/*.json | head -1)" --artwork ~/storage/downloads/my_anime_art.png --headline "புதிய தமிழ் அனிமே கதை" --mode story --outdir output/creative_v5
```

Copy result to Downloads:
```sh
cp output/creative_v5/story_poster.png ~/storage/downloads/cartoon_story_poster.png
cp output/creative_v5/cinematic_depth_style.png ~/storage/downloads/cartoon_3d_style.png
```

### Publish later, after review

Keep these `.env` flags unchanged for now:
```
DRY_RUN=true
PUBLISH_FACEBOOK=false
PUBLISH_INSTAGRAM=false
```

Live publishing needs approved Meta permissions, working Page/IG IDs, secure tokens, publicly reachable licensed image URLs, retries, and a tested deduplication policy. None are guaranteed by these V5 drafts.

### Next modules
1. Real chapter parser and verified character/story bible.
2. Optional locally hosted generative art model, if server CPU/GPU can support it, or an authorized external provider.
3. Human-reviewed original story images and captions, then API publishing tests.
4. Video/reel creation from licensed images + voiceover, analytics integration.
