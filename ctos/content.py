"""Original-story promotional copy for platform-specific review bundles."""
from urllib.parse import urlsplit

from social_copy_v10 import premium_copy
from v12_strategy import make_brief

PLATFORMS = (
    "instagram", "facebook", "youtube", "pinterest",
    "threads", "x", "linkedin", "telegram",
)
LABELS = {
    "youtube": "Watch/Read the original Tamil story:",
    "pinterest": "Original Tamil story — read the full story:",
    "threads": "Original Tamil story — link:",
    "x": "Original story — read:",
    "linkedin": "Original Tamil creative writing — discover:",
    "telegram": "தமிழ் அசல் கதை | Read:",
}


def make_captions(story, approval=None):
    url = story.get("link", "")
    parts = urlsplit(url)
    allowed_path = (parts.path.startswith("/novel/") or
                    (story.get("content_type") == "episode" and
                     parts.path.startswith("/chapter/")))
    if (parts.scheme != "https" or parts.hostname not in
            ("cartoontamilan.in", "www.cartoontamilan.in") or not allowed_path):
        raise ValueError("Only original CartoonTamilan story or episode URLs may be promoted")

    if story.get("content_type") == "episode":
        title = story["title"].strip()
        parent = str(story.get("parent_title") or "").strip()
        episode_number = story.get("episode_number")
        episode_label = ("எபிசோடு " + str(episode_number) if episode_number
                         else "புதிய எபிசோடு")
        excerpt = " ".join(str(story.get("summary") or "").split())[:260].strip()
        tags = ["#CartoonTamilan", "#TamilStories", "#TamilNovels", "#TamilAnimeStory"]
        summary_line = ("📖 Episode teaser: " + excerpt + "\n\n") if excerpt else ""
        base_caption = ("✨ " + episode_label + " வெளியானது!\n\n" + parent + "\n"
                        + title + "\n\n" + summary_line
                        + "📚 முழு எபிசோடு: " + url + "\n\n"
                        + " ".join(tags))
        captions = {channel: base_caption for channel in
                    ("youtube", "pinterest", "threads", "linkedin", "telegram")}
        captions["facebook"] = base_caption
        captions["instagram"] = (base_caption
                                 + "\n💬 படித்துவிட்டு உங்கள் கருத்தைச் சொல்லுங்கள்!")
        captions["x"] = (title[:100] + " — " + url + " #CartoonTamilan")
        return {
            "captions": captions, "hashtags": tags,
            "tracked_story_url": url, "requires_editorial_review": True,
            "bio_link_setup_required": False, "verified_intro_only": False,
            "facebook_pinned_comment": "📖 முழு எபிசோடு: " + url,
        }

    pack = premium_copy(story, approval or {})
    source = make_brief(story, approval=approval, channel="instagram")
    tags = " ".join(pack.get("hashtags", []))
    captions = {
        "instagram": pack["instagram"]["caption"],
        "facebook": pack["facebook"]["caption"],
    }
    # Reuse the approved bilingual intro; no invented characters or chapters.
    for platform, label in LABELS.items():
        content = (f"{story['title']}\n\n"
                   f"{(approval or {}).get('intro_ta', '')}\n"
                   f"{(approval or {}).get('intro_en', '')}\n\n"
                   f"{label} {url}\n\n{tags}")
        captions[platform] = content.strip()
    # Character limits below are conservative publishing/export design bounds.
    # Do not truncate away the actual story CTA/link on short-post platforms.
    short_title = story["title"].strip()
    max_title = max(24, 260 - len(url) - 42)
    captions["x"] = (short_title[:max_title].rstrip() +
                     ("…" if len(short_title) > max_title else "") +
                     "\nOriginal Tamil story — read: " + url)
    return {
        "captions": captions,
        "hashtags": pack.get("hashtags", []),
        "tracked_story_url": source["tracked_link"],
        "requires_editorial_review": pack.get("requires_editorial_review", True),
        "bio_link_setup_required": True,
        "verified_intro_only": bool((approval or {}).get("copy_reviewed") is True
                                    and (approval or {}).get("intro_ta")
                                    and (approval or {}).get("intro_en")),
        "facebook_pinned_comment": pack["facebook"]["pinned_comment"],
    }
