import os
import logging
from .facebook import publish_text, publish_link, publish_photo
from .instagram import publish_image, publish_reel

log = logging.getLogger(__name__)


def publish_item(item, caption, media=None):
    if os.getenv("DRY_RUN", "true").lower() == "true":
        log.info("DRY_RUN enabled: would publish %s", item.get("title"))
        return {"dry_run": True}

    results = {}
    link = item.get("link", "")
    if os.getenv("PUBLISH_FACEBOOK", "false").lower() == "true":
        if media and media.get("type") == "image":
            results["facebook"] = publish_photo(media["url"], caption)
        elif link:
            results["facebook"] = publish_link(caption, link)
        else:
            results["facebook"] = publish_text(caption)

    if os.getenv("PUBLISH_INSTAGRAM", "false").lower() == "true":
        if not media:
            log.warning("Instagram skipped: Instagram requires an image or video URL.")
        elif media["type"] == "image":
            results["instagram"] = publish_image(media["url"], caption)
        elif media["type"] == "reel":
            results["instagram"] = publish_reel(media["url"], caption)
        else:
            log.warning("Instagram skipped: unsupported media type %s", media["type"])
    return results
