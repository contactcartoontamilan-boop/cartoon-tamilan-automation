"""Original-story promotional copy for platform-specific review bundles."""
import re
from urllib.parse import unquote, urlsplit

from social_copy_v10 import premium_copy
from v12_strategy import make_brief

PLATFORMS = (
    "instagram", "facebook", "youtube", "pinterest",
    "threads", "x", "linkedin", "telegram",
)
LABELS = {
    "youtube": "Read the full original Tamil episode:",
    "pinterest": "Read the original Tamil story:",
    "threads": "Read the full episode:",
    "x": "Read:",
    "linkedin": "Discover the original Tamil story:",
    "telegram": "முழு தமிழ் அத்தியாயம் | Read:",
}
EPISODE_TAGS = [
    "#TamilFantasy", "#TamilWebNovel", "#TamilStories",
    "#AnimeInspiredStories", "#CartoonTamilan",
]


def _episode_titles(story, url):
    """Use an English URL slug only when it provides a readable episode title."""
    slug = unquote(urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1])
    match = re.search(
        r"^(?P<series>.+?)-episode-?(?P<number>\d+)(?:-(?P<episode>.+))?$",
        slug, re.IGNORECASE,
    )
    if match:
        def clean(value):
            return " ".join(
                word.capitalize() for word in re.sub(r"[-_]+", " ", value).split()
            )
        series = clean(match.group("series"))
        episode = clean(match.group("episode") or "")
        number = story.get("episode_number") or match.group("number")
        return series, episode, str(number)

    number = story.get("episode_number")
    title = str(story.get("english_title") or story.get("title") or "").strip()
    parent = str(story.get("english_parent_title") or story.get("parent_title") or
                 "CartoonTamilan Original Story").strip()
    return parent, title, str(number) if number else ""


def _episode_caption(story, channel, url):
    tamil_title = str(story.get("title") or "புதிய எபிசோடு").strip()
    tamil_series = str(story.get("parent_title") or "கார்ட்டூன் தமிழன் அசல் கதை").strip()
    series_en, episode_en, number = _episode_titles(story, url)
    episode_label = f"Episode {number}" if number else "New Episode"
    if episode_en:
        episode_label += f": {episode_en}"
    heading = f"{series_en} | {episode_label}"
    english = (
        f"{heading}\n"
        "An original story published in Tamil by CartoonTamilan. "
        "Read this episode in Tamil and follow the series."
    )
    tamil = (
        f"📖 {tamil_series} — {tamil_title}\n"
        "கார்ட்டூன் தமிழனில் வெளியாகும் அசல் தமிழ் கதை."
    )

    if channel == "instagram":
        cta = "🔗 Read the full episode in Tamil — tap the link in our bio."
        question = "💬 இந்த அத்தியாயம் பற்றி உங்கள் கருத்தைச் சொல்லுங்கள்."
    else:
        cta = f"📚 Read the full episode in Tamil: {url}"
        question = "💬 Which story or episode should we feature next?"

    tags = " ".join(EPISODE_TAGS)
    text = f"{english}\n\n{tamil}\n\n{cta}\n{question}\n\n{tags}"
    if channel == "x":
        # Keep the destination link and one searchable niche tag within X's limit.
        short_cta = f"Read in Tamil: {url}"
        suffix = f"\n{short_cta} #TamilStories"
        prefix = f"{heading}\nOriginal Tamil story."
        available = max(12, 280 - len(suffix) - len(prefix) - 1)
        shortened_label = episode_label[:available]
        return prefix + (f"\n{shortened_label}" if len(episode_label) > available
                         else "") + suffix
    return text


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
        captions = {channel: _episode_caption(story, channel, url)
                    for channel in PLATFORMS}
        return {
            "captions": captions,
            "hashtags": EPISODE_TAGS,
            "tracked_story_url": url,
            "requires_editorial_review": True,
            "bio_link_setup_required": True,
            "verified_intro_only": False,
            "facebook_pinned_comment": "📖 Read the full Tamil episode: " + url,
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
