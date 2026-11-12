import os
from .meta_common import graph_post, required_env


def publish_text(message):
    """Publish a text/link post to a Facebook Page."""
    required_env("META_PAGE_ID", "META_PAGE_ACCESS_TOKEN")
    page_id = os.environ["META_PAGE_ID"]
    token = os.environ["META_PAGE_ACCESS_TOKEN"]
    return graph_post(f"{page_id}/feed", token, {"message": message})


def publish_link(message, link):
    """Publish a link post to a Facebook Page."""
    required_env("META_PAGE_ID", "META_PAGE_ACCESS_TOKEN")
    page_id = os.environ["META_PAGE_ID"]
    token = os.environ["META_PAGE_ACCESS_TOKEN"]
    return graph_post(f"{page_id}/feed", token, {"message": message, "link": link})


def publish_photo(photo_url, caption):
    """Publish one publicly reachable image URL to a Facebook Page."""
    required_env("META_PAGE_ID", "META_PAGE_ACCESS_TOKEN")
    page_id = os.environ["META_PAGE_ID"]
    token = os.environ["META_PAGE_ACCESS_TOKEN"]
    return graph_post(
        f"{page_id}/photos",
        token,
        {"url": photo_url, "caption": caption}
    )
