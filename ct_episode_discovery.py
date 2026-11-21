"""Discover original CartoonTamilan episodes incrementally for the hourly queue.

The crawler stays on the site's HTTPS host, records only episode URLs linked from
owned story/episode pages, and keeps a persistent crawl frontier so a large
back catalogue is gradually indexed without downloading every chapter at once.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from auto_story_marketing import discover
from v12_story_reader import HOSTS, _get_html, extract_chapter_text

STATE_PATH = Path("data/v14_episode_catalog.json")
EPISODE_PATH = re.compile(r"/(?:chapter|episode|part-)/", re.IGNORECASE)
NUMBER = re.compile(r"(?:episode|chapter|ep)[-_ ]*(\d+)", re.IGNORECASE)


def _episode_number(url: str, label: str = "") -> int:
    match = NUMBER.search(url) or NUMBER.search(label)
    if match:
        return int(match.group(1))
    digits = re.findall(r"\d+", urlsplit(url).path)
    return int(digits[-1]) if digits else 0


def _episode_links(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    found = {}
    for node in soup.select("a[href], option[value]"):
        raw = node.get("href") or node.get("value") or ""
        target = urldefrag(urljoin(base_url, raw))[0]
        parts = urlsplit(target)
        if (parts.scheme != "https" or parts.hostname not in HOSTS
                or not EPISODE_PATH.search(parts.path)):
            continue
        label = node.get_text(" ", strip=True)
        if node.name == "option":
            label = label or str(node.get("label") or "")
        found[target] = {"url": target, "label": label[:220],
                         "number": _episode_number(target, label)}
    return sorted(found.values(), key=lambda item: (
        item["number"] or 10**9, item["url"]))


def _title(html: str, fallback: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find("h1")
    value = heading.get_text(" ", strip=True) if heading else ""
    if not value:
        meta = soup.find("meta", attrs={"property": "og:title"})
        value = str(meta.get("content") or "") if meta else ""
    if not value and soup.title:
        value = soup.title.get_text(" ", strip=True)
    value = re.sub(r"\s*[|–—-]\s*Cartoon Tamilan.*$", "", value,
                   flags=re.IGNORECASE).strip()
    return value[:220] or fallback[:220]


def _load_state(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict) and isinstance(value.get("stories"), dict):
            return value
    except (OSError, json.JSONDecodeError):
        pass
    return {"version": 1, "stories": {}}


def _save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    temp.replace(path)


def _seed_urls(novel_html: str, novel_url: str) -> list[dict]:
    links = _episode_links(novel_html, novel_url)
    # When the series page exposes only First and Latest, start at First and
    # walk forward. If it exposes a full episode selector, keep the full list.
    if len(links) <= 4:
        numbers = [item["number"] for item in links if item["number"]]
        if numbers and max(numbers) - min(numbers) > 1:
            first = min(numbers)
            links = [item for item in links if item["number"] == first]
    return links


def discover_episode_posts(limit=30, session=None, state_path=STATE_PATH) -> list[dict]:
    """Return cached episodes in order while indexing a bounded number per run."""
    http = session or requests
    path = Path(state_path)
    state = _load_state(path)
    novels = discover(limit=60, session=http)
    stories = state["stories"]
    # Recover URLs marked attempted by an older version but never successfully
    # recorded as an episode. They were failed fetches, not completed chapters.
    for entry in stories.values():
        completed = entry.get("episodes", {})
        attempted = entry.get("attempted", [])
        retry = [url for url in attempted if url not in completed]
        entry["attempted"] = [url for url in attempted if url in completed]
        frontier = entry.setdefault("frontier", [])
        for url in retry:
            if url not in frontier:
                frontier.append(url)

    for novel in novels:
        novel_url = novel.get("link", "")
        if not novel_url.startswith("https://"):
            continue
        entry = stories.setdefault(novel_url, {
            "title": str(novel.get("title") or ""), "parent_url": novel_url,
            "episodes": {}, "frontier": [], "attempted": [],
        })
        entry["title"] = str(novel.get("title") or entry.get("title") or "")
        try:
            novel_html = _get_html(novel_url, http)
        except (ValueError, requests.RequestException):
            continue
        for item in _seed_urls(novel_html, novel_url):
            target = item["url"]
            if (target not in entry["episodes"]
                    and target not in entry["attempted"]
                    and target not in entry["frontier"]):
                entry["frontier"].append(target)
        entry["frontier"].sort(key=lambda url: (
            _episode_number(url) or 10**9, url))

    try:
        scan_budget = max(1, min(200, int(os.getenv(
            "CT_V14_EPISODE_SCAN_LIMIT", "40"))))
    except ValueError:
        scan_budget = 40

    entries = list(stories.values())
    failed_this_run = set()
    while scan_budget and any(entry.get("frontier") for entry in entries):
        did_work = False
        for entry in entries:
            frontier = entry.get("frontier", [])
            if not frontier or scan_budget <= 0:
                continue
            frontier.sort(key=lambda url: (_episode_number(url) or 10**9, url))
            target = frontier.pop(0)
            if (target in entry.get("attempted", [])
                    or target in entry.get("episodes", {})
                    or target in failed_this_run):
                continue
            did_work = True
            scan_budget -= 1
            try:
                html = _get_html(target, http)
            except (ValueError, requests.RequestException):
                # Preserve transient failures for the next hourly discovery run.
                entry.setdefault("frontier", []).append(target)
                failed_this_run.add(target)
                continue
            entry.setdefault("attempted", []).append(target)
            chapter_title = _title(html, target.rsplit("/", 2)[-2])
            body = extract_chapter_text(html, limit_chars=5000)
            number = _episode_number(target, chapter_title)
            entry.setdefault("episodes", {})[target] = {
                "title": chapter_title, "link": target, "kind": "story",
                "content_type": "episode", "parent_title": entry["title"],
                "parent_url": entry.get("parent_url", ""),
                "episode_number": number or None,
                "summary": body[:320].rsplit(" ", 1)[0] if body else "",
                "evidence": "owned_episode_page",
            }
            for linked in _episode_links(html, target):
                candidate = linked["url"]
                if (candidate not in entry["episodes"]
                        and candidate not in entry.get("attempted", [])
                        and candidate not in entry.get("frontier", [])):
                    entry["frontier"].append(candidate)
        if not did_work:
            break

    _save_state(path, state)
    result = [item for entry in stories.values()
              for item in entry.get("episodes", {}).values()]
    result.sort(key=lambda item: (
        int(item.get("episode_number") or 10**9),
        str(item.get("parent_title", "")).casefold(),
        str(item.get("link", ""))))
    return result
