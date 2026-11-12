import os
import time
from .meta_common import graph_get, graph_post, required_env


def _instagram_id_and_token():
    required_env("INSTAGRAM_USER_ID", "META_PAGE_ACCESS_TOKEN")
    return os.environ["INSTAGRAM_USER_ID"], os.environ["META_PAGE_ACCESS_TOKEN"]


def create_image_container(image_url, caption):
    ig_id, token = _instagram_id_and_token()
    return graph_post(f"{ig_id}/media", token, {"image_url": image_url, "caption": caption})


def create_reel_container(video_url, caption, share_to_feed=True):
    ig_id, token = _instagram_id_and_token()
    return graph_post(f"{ig_id}/media", token, {"media_type": "REELS", "video_url": video_url, "caption": caption, "share_to_feed": str(share_to_feed).lower()})


def wait_until_container_ready(container_id, timeout_seconds=600, poll_seconds=10):
    _, token = _instagram_id_and_token()
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        result = graph_get(container_id, token, {"fields": "status_code,status"})
        status = result.get("status_code", "")
        if status == "FINISHED":
            return result
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram media processing failed: {result}")
        time.sleep(poll_seconds)
    raise TimeoutError("Instagram media processing did not finish in time")


def publish_container(container_id):
    ig_id, token = _instagram_id_and_token()
    return graph_post(f"{ig_id}/media_publish", token, {"creation_id": container_id})


def publish_image(image_url, caption):
    return publish_container(create_image_container(image_url, caption)["id"])


def publish_reel(video_url, caption, share_to_feed=True):
    container = create_reel_container(video_url, caption, share_to_feed)
    wait_until_container_ready(container["id"])
    return publish_container(container["id"])
