import os
from .meta_common import graph_post, required_env


def publish_text(message):
    required_env("META_PAGE_ID", "META_PAGE_ACCESS_TOKEN")
    return graph_post(f"{os.environ['META_PAGE_ID']}/feed", os.environ["META_PAGE_ACCESS_TOKEN"], {"message": message})


def publish_link(message, link):
    required_env("META_PAGE_ID", "META_PAGE_ACCESS_TOKEN")
    return graph_post(f"{os.environ['META_PAGE_ID']}/feed", os.environ["META_PAGE_ACCESS_TOKEN"], {"message": message, "link": link})


def publish_photo(photo_url, caption):
    required_env("META_PAGE_ID", "META_PAGE_ACCESS_TOKEN")
    return graph_post(f"{os.environ['META_PAGE_ID']}/photos", os.environ["META_PAGE_ACCESS_TOKEN"], {"url": photo_url, "caption": caption})
