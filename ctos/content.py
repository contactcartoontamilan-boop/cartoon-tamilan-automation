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
    if (parts.scheme != "https" or parts.hostname not in
            ("cartoontamilan.in", "www.cartoontamilan.in") or
            not parts.path.startswith("/novel/")):
        raise ValueError("Only original stories on CartoonTamilan HTTPS /novel/ may be promoted")
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
    captions["x"] = captions["x"][:225] + "…" if len(captions["x"]) > 240 else captions["x"]
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
