"""CartoonTamilan V5 bilingual social draft creator.

Content is based only on supplied title, synopsis and verified approved copy.
All outputs are review-required and never sent to social APIs.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from growth_engine import tracked_link

GENRES = {
    "fantasy": ("கற்பனை உலகம்", "Fantasy"),
    "action": ("ஆக்‌ஷன்", "Action"),
    "romance": ("காதல்", "Romance"),
    "adventure": ("சாகசம்", "Adventure"),
    "horror": ("திகில்", "Horror"),
    "drama": ("உணர்வுகள்", "Drama"),
    "comedy": ("நகைச்சுவை", "Comedy"),
    "isekai": ("இசெகாய்", "Isekai"),
}
TAGS = {
    "fantasy": "FantasyNovel",
    "action": "ActionStory",
    "romance": "RomanceNovel",
    "adventure": "AdventureNovel",
    "horror": "HorrorStory",
    "drama": "DramaStory",
    "comedy": "ComedyStory",
    "isekai": "Isekai",
}


def short_summary(summary, max_chars=420):
    s = re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", summary or "")).strip()
    if len(s) <= max_chars:
        return s
    return s[:max_chars].rsplit(" ", 1)[0].rstrip(" ,.;:") + "…"


def hashtags(genres):
    result = ["#CartoonTamilan", "#OriginalStories", "#TamilNovel", "#AnimeInspired", "#WebNovel"]
    for genre in genres:
        name = TAGS.get(genre.lower())
        if name:
            result.append("#" + name)
    return " ".join(dict.fromkeys(result[:9]))


def make_social_pack(item, genres=(), verified_intro_ta="", verified_intro_en=""):
    if item.get("kind") != "story":
        raise ValueError("Social story pack requires kind=story")
    title = (item.get("title") or "").strip()
    url = (item.get("link") or "").strip()
    if not title:
        raise ValueError("Story title is missing")
    if urlsplit(url).hostname not in {"cartoontamilan.in", "www.cartoontamilan.in"}:
        raise ValueError("Story must be hosted on CartoonTamilan")
    title_clean = short_summary(title, 115)
    source_description = (
        item.get("summary") or item.get("description") or
        item.get("excerpt") or item.get("plot")
    )
    summary = short_summary(source_description, 420)
    # Never translate or embellish source prose. Use reviewed English if available.
    ta_intro = verified_intro_ta.strip() or (
        "புதிய கதையுலகை அறிமுகம் செய்கிறோம்: " + title_clean +
        (". " + summary if summary else ".")
    )
    english_source = item.get("description_en") or item.get("summary_en") or ""
    en_intro = verified_intro_en.strip() or (
        short_summary(english_source, 420) or
        "Discover an original story on CartoonTamilan: " + title_clean + "."
    )
    notes = []
    if not verified_intro_ta and not summary:
        notes.append("Tamil copy has no source synopsis; add a verified plot description for richer captions.")
    if not verified_intro_en and not english_source:
        notes.append("English copy is a short promotional line; add a reviewed English synopsis for richer captions.")
    slug = "story_" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    tags = hashtags(genres)
    fb = tracked_link(url, "facebook", slug)
    ig = tracked_link(url, "instagram", slug)
    prompts = {
        "realistic_cinematic": (
            "Create a photorealistic, cinematic original story image in 9:16. "
            "Use only the verified source description and approved character bible; "
            "keep character appearance consistent, add no unverified plot details, "
            "and include no text, logos, watermark, or franchise characters."
        ),
        "anime_illustration": (
            "Create an ORIGINAL anime-inspired illustration based ONLY on the "
            "verified character bible for this story. Preserve established design, "
            "do not invent story events, and add no text or famous franchise characters."
        ),
        "cinematic_3d_style": (
            "Create an ORIGINAL cinematic 3D-style illustration from approved "
            "story/character references. No copyrighted characters or typography."
        ),
        "meme": (
            "Create an original Tamil anime-fandom meme concept relevant to the "
            "verified chapter and use original or licensed art."
        ),
    }
    return {
        "story_title": title,
        "story_url": url,
        "genres": list(genres),
        "source_description": summary,
        "intro_tamil": ta_intro,
        "intro_english": en_intro,
        "facebook": {
            "caption": f"📖 {ta_intro}\n\n🌍 {en_intro}\n\n👉 Read the full story:\n{fb}\n\n{tags}",
            "link": fb,
        },
        "instagram": {
            "caption": f"📚 {title_clean}\n\n{ta_intro}\n\n{en_intro}\n\n🔗 Full story: link in bio.\n💬 Which moment caught your attention?\n{tags}",
            "tracked_link_for_bio": ig,
            "requires_public_media": True,
        },
        "hashtags": tags.split(),
        "creative_prompts": prompts,
        "creative_note": "Prompts are saved as creative direction; image generation is handled by the configured ComfyUI path.",
        "review_notes": notes,
        "status": "draft_review_required",
    }


def build_from_file(draft_path, out_path, genres=(), intro_ta="", intro_en=""):
    draft = json.loads(Path(draft_path).read_text(encoding="utf-8"))
    result = make_social_pack(draft["item"], genres, intro_ta, intro_en)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--draft", required=True)
    p.add_argument("--out", default="output/social_pack_v5.json")
    p.add_argument("--genres", default="fantasy,action,romance,adventure,horror,drama,comedy,isekai")
    p.add_argument("--intro-ta", default="")
    p.add_argument("--intro-en", default="")
    a = p.parse_args()
    print("Social drafts saved:", build_from_file(draft_path=a.draft, out_path=a.out,
        genres=[g.strip() for g in a.genres.split(",") if g.strip()],
        intro_ta=a.intro_ta, intro_en=a.intro_en))
    print("DRY RUN: No Facebook / Instagram posts sent.")
