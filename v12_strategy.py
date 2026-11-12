"""V12 editorial strategy, brand-safe content calendar, and multi-platform drafts.

No invented plot facts, no off-site scraping, and no social publishing.
Story facts are drawn only from previously approved story records/bibles.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

from growth_engine import tracked_link
from social_copy_v10 import premium_copy
from story_bible_v10 import validate_bible

FORMATS = ("story_hook", "character_spotlight", "reader_poll", "chapter_teaser",
           "original_meme", "poster", "reel", "story_slide")
CHANNELS = ("facebook", "instagram", "youtube", "threads", "pinterest")
THEME_ROTATION = ("story_hook", "poster", "reader_poll", "original_meme",
                  "character_spotlight", "reel", "chapter_teaser")
CAPTIONS = {
    "story_hook": ("📖 அடுத்த வாசிப்பு என்ன?", "📚 Meet your next original story."),
    "poster": ("✨ இன்று படிக்க ஒரு தமிழ் அசல் கதை!", "✨ Discover an original story."),
    "reader_poll": ("💬 இந்தக் கதையைப் படித்தீர்களா? உங்கள் கருத்து என்ன?",
                    "💬 Have you read this story? What did you think?"),
    "original_meme": ("😄 வாசிப்பு ஆர்வம் உங்களுக்கும் இருக்கா?",
                      "😄 When your reading list keeps getting longer!"),
    "character_spotlight": ("🎭 இந்தக் கதையின் கதாபாத்திரங்களை அறிமுகம் செய்கிறோம்.",
                            "🎭 Get to know the characters in this story."),
    "reel": ("🎬 புதிய கதை teaser!", "🎬 A new original-story reading teaser."),
    "chapter_teaser": ("📚 இந்தக் கதை உங்களுக்காகக் காத்திருக்கிறது!",
                       "📚 Your next chapter of reading starts here."),
}


def story_id(url):
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def _verified_notes(bible):
    if not validate_bible(bible or {}):
        return {"canon_verified": False, "synopsis": "", "characters": [], "world_visuals": ""}
    return {
        "canon_verified": True,
        "synopsis": bible["synopsis"].strip()[:800],
        "world_visuals": str(bible.get("world_visuals", ""))[:300],
        "characters": [str(ch["appearance"])[:180] for ch in bible.get("characters", [])[:4]],
    }


def make_brief(story, approval=None, bible=None, fmt="poster", channel="instagram", when=None):
    if fmt not in FORMATS or channel not in CHANNELS:
        raise ValueError("Unsupported content format/channel")
    if story.get("kind") != "story" or not story.get("link") or not story.get("title"):
        raise ValueError("Original story with URL and title is required")
    if not story["link"].startswith(("https://cartoontamilan.in/novel/",
                                     "https://www.cartoontamilan.in/novel/")):
        raise ValueError("Only CartoonTamilan original novel links are accepted")
    approval = approval or {}
    notes = _verified_notes(bible)
    # Cast spotlight only when actual character appearance is verified.
    if fmt == "character_spotlight" and not notes["characters"]:
        fmt = "story_hook"
    if fmt == "chapter_teaser" and not approval.get("approved_chapter_url"):
        # No fabricated chapter announcement.
        fmt = "story_hook"
    if fmt in ("original_meme", "reel") and approval.get("media_rights_checked") is not True:
        media_review = True
    else:
        media_review = False

    copy = premium_copy(story, approval)
    ta, en = CAPTIONS[fmt]
    campaign = "v12_" + story_id(story["link"])
    tracked = tracked_link(story["link"], channel, campaign)
    approved_copy = bool(approval.get("copy_reviewed") is True and
                         approval.get("intro_ta") and approval.get("intro_en"))
    rights_ok = approval.get("rights_confirmed") is True
    if channel == "instagram":
        link_line = "🔗 முழுக் கதை: profile bio link | Full story in bio"
    else:
        link_line = "🔗 " + tracked
    caption = (f"{ta}\n{en}\n\n{story['title']}\n\n"
               f"{approval.get('intro_ta', '') if approved_copy else ''}\n"
               f"{approval.get('intro_en', '') if approved_copy else ''}\n\n"
               f"{link_line}\n\n" + " ".join(copy.get("hashtags", [])))
    status = "draft_review_required"
    if approved_copy and rights_ok and not media_review:
        status = "editorially_approved_for_review"
    return {
        "story_id": story_id(story["link"]),
        "story_url": story["link"],
        "story_title": story["title"],
        "format": fmt,
        "channel": channel,
        "scheduled_date_ist": str(when or date.today()),
        "caption": caption.strip(),
        "tracked_link": tracked,
        "creative_direction": {
            "style": "original anime-inspired / optional cinematic 3D-style concept",
            "canon_verified": notes["canon_verified"],
            "synopsis": notes["synopsis"],
            "character_appearances": notes["characters"],
            "world_visuals": notes["world_visuals"],
            "do_not_invent_events": True,
            "no_other_anime_franchise_images": True,
        },
        "requires_media_review": media_review,
        "rights_verified": rights_ok,
        "copy_verified": approved_copy,
        "status": status,
        "published": False,
        "action_required": "review creative/media, verify rights, confirm real platform API access",
    }


def calendar(stories, approvals=None, bibles=None, start=None, days=14, posts_per_day=2):
    if not 1 <= days <= 90 or not 1 <= posts_per_day <= 4:
        raise ValueError("days must be 1–90 and posts_per_day 1–4")
    start = start or date.today()
    approvals, bibles = approvals or {}, bibles or {}
    usable = sorted([story for story in stories
                     if story.get("kind") == "story" and story.get("link")
                     and story.get("title")], key=lambda st: st["link"])
    if not usable:
        return []
    results = []
    for index in range(days):
        for slot in range(posts_per_day):
            # Rotate safely across stories, channels and formats.
            story = usable[(index * posts_per_day + slot) % len(usable)]
            fmt = THEME_ROTATION[(index + slot) % len(THEME_ROTATION)]
            channel = ("instagram", "facebook", "youtube", "pinterest", "threads")[
                (index + slot) % 5]
            results.append(make_brief(story, approvals.get(story["link"]),
                                      bibles.get(story["link"]),
                                      fmt=fmt, channel=channel,
                                      when=start + timedelta(days=index)))
    return results


def save_calendar(stories, approvals=None, bibles=None,
                  out="output/v12/content_calendar.json", days=14, posts_per_day=2):
    result = calendar(stories, approvals, bibles, days=days, posts_per_day=posts_per_day)
    path = Path(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "status": "draft_review_required", "count": len(result),
        "automatic_publishing": False, "calendar": result,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
