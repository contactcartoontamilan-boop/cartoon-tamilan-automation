"""V14 website chapter collector + source-excerpt storyboard. NEVER publishes.

Only reads public HTTPS /novel/ URLs on the owner's site. Source text is
untrusted data and is never executed, sent to an LLM, or treated as instructions.
A contiguous, verbatim excerpt is a DRAFT teaser, NOT a plot summary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from ctos.v14_story import normalize_script, plan_story, save_plan
from v12_story_reader import extract_chapter_text, owned_story_url, _get_html

CHAPTER_HINTS = ("chapter", "episode", "part-", "அத்தியாயம்", "பாகம்", "தொடர்")
MAX_PAGES = 40
MAX_CHARS = 50000


def _safe_story_url(url: str) -> bool:
    if not owned_story_url(url):
        return False
    parsed = urlsplit(url)
    return not (parsed.username or parsed.password or parsed.port not in (None, 443))


def _same_story_chapter_path(story_url: str, candidate_url: str) -> bool:
    """Accept nested chapters or a chapter-number suffix on the same novel slug.

    Some sites store chapters at /novel/story-chapter-1/ rather than
    /novel/story/chapter-1/. Never follow a different novel's slug.
    """
    base_path = urlsplit(story_url).path.rstrip("/")
    candidate_path = urlsplit(candidate_url).path.rstrip("/")
    if candidate_path.startswith(base_path + "/"):
        return True
    if not candidate_path.startswith(base_path):
        return False
    suffix = candidate_path[len(base_path):]
    return bool(re.fullmatch(
        r"[-_](?:chapter|episode|part)[-_]?[0-9]+(?:[-_][a-z0-9-]+)?",
        suffix, flags=re.IGNORECASE))


def discover_chapters(story_url: str, html: str, *, base_url: str | None = None) -> list[str]:
    """Follow only same-novel chapter-looking links, nested or slug-suffixed."""
    if not _safe_story_url(story_url):
        raise ValueError("Only owner HTTPS /novel/ story URLs are allowed")
    base = base_url or story_url
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    for anchor in soup.select("a[href]"):
        raw = anchor.get("href", "")
        if not isinstance(raw, str) or not raw:
            continue
        url = urldefrag(urljoin(base, raw))[0]
        if not _safe_story_url(url):
            continue
        parsed = urlsplit(url)
        if not _same_story_chapter_path(story_url, url):
            continue
        label = anchor.get_text(" ", strip=True).lower()
        path = parsed.path.lower()
        if not any(hint in (label + " " + path) for hint in CHAPTER_HINTS):
            continue
        if url not in links:
            links.append(url)
    return links


def landing_page_signals(story_url: str, html: str) -> dict:
    """Bounded HTML diagnostics: structure and public URL paths, never story prose."""
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.select("a[href]")
    novel_paths: list[str] = []
    for anchor in anchors:
        raw = anchor.get("href", "")
        if not isinstance(raw, str) or not raw:
            continue
        url = urldefrag(urljoin(story_url, raw))[0]
        if not _safe_story_url(url):
            continue
        path = urlsplit(url).path
        if path != urlsplit(story_url).path and path not in novel_paths:
            novel_paths.append(path)
        if len(novel_paths) >= 8:
            break
    selectors = (".chapter-content", ".reading-content", ".entry-content",
                 ".chapter-body", "article")
    selector_chars = {
        selector: max((len(node.get_text(" ", strip=True))
                       for node in soup.select(selector)), default=0)
        for selector in selectors
    }
    body = soup.body
    return {
        "html_bytes": len(html.encode("utf-8")),
        "page_title": soup.title.get_text(" ", strip=True)[:120] if soup.title else "",
        "anchor_count": len(anchors),
        "novel_path_examples": novel_paths,
        "body_visible_characters": len(body.get_text(" ", strip=True)) if body else 0,
        "selector_characters": selector_chars,
        "script_tag_count": len(soup.select("script")),
    }


def collect_full_story(story_url: str, *, session=None, max_pages: int = 24) -> dict:
    """Collect accessible chapter text up to a bounded limit; never claim completeness."""
    if not _safe_story_url(story_url):
        raise ValueError("Only HTTPS CartoonTamilan /novel/ URLs are allowed")
    if not 1 <= max_pages <= MAX_PAGES:
        raise ValueError("max_pages must be 1–40")
    http = session or requests
    landing = _get_html(story_url, http)
    landing_signals = landing_page_signals(story_url, landing)
    landing_body = extract_chapter_text(landing, limit_chars=MAX_CHARS + 1)
    landing_words = len(normalize_script(landing_body).split())
    initial_links = discover_chapters(story_url, landing)
    queue = deque(initial_links)
    seen: set[str] = set()
    chapters: list[dict] = []
    failures: list[dict] = []
    while queue and len(seen) < max_pages:
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        try:
            html = _get_html(url, http)
            # Use existing selector-based extraction; cap and flag potential truncation.
            body = extract_chapter_text(html, limit_chars=MAX_CHARS + 1)
            for discovered in discover_chapters(story_url, html, base_url=url):
                if discovered not in seen and discovered not in queue:
                    queue.append(discovered)
            if len(body) < 120:
                failures.append({"url": url, "reason": "No readable chapter body"})
                continue
            truncated = len(body) > MAX_CHARS
            text = body[:MAX_CHARS]
            chapters.append({
                "url": url,
                "text": text,
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "characters": len(text),
                "potentially_truncated": truncated,
                "editorially_verified": False,
            })
        except (requests.RequestException, ValueError) as exc:
            failures.append({"url": url, "reason": type(exc).__name__})
    # A single-page novel is possible; do not silently confuse its intro with
    # a verified complete chapter. Preserve the explicit source classification.
    if not chapters and not seen:
        if len(landing_body) >= 700:
            text = landing_body[:MAX_CHARS]
            chapters.append({
                "url": story_url, "text": text,
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "characters": len(text),
                "potentially_truncated": len(landing_body) > MAX_CHARS,
                "editorially_verified": False,
                "source_kind": "landing_article_unverified",
            })
    return {
        "version": 14,
        "story_url": story_url,
        "pages_examined": len(seen),
        "chapter_links_discovered": len(initial_links),
        "chapter_link_examples": initial_links[:6],
        "landing_readable_words": landing_words,
        "landing_page_signals": landing_signals,
        "extracted_words": sum(len(normalize_script(ch["text"]).split()) for ch in chapters),
        "chapters_extracted": len(chapters),
        "chapters": chapters,
        "failures": failures,
        "more_links_unread": bool(queue),
        "completeness": "unverified_even_if_no_more_links_found",
        "copyright_and_story_review_required": True,
        "published": False,
    }


def diagnostic_summary(collected: dict) -> dict:
    """Share counts and URLs without leaking the entire original story text."""
    return {
        "story_url": collected.get("story_url"),
        "pages_examined": collected.get("pages_examined", 0),
        "chapter_links_discovered": collected.get("chapter_links_discovered", 0),
        "chapter_link_examples": collected.get("chapter_link_examples", []),
        "landing_readable_words": collected.get("landing_readable_words", 0),
        "landing_page_signals": collected.get("landing_page_signals", {}),
        "chapters_extracted": collected.get("chapters_extracted", 0),
        "extracted_words": collected.get("extracted_words", 0),
        "failures": collected.get("failures", []),
        "more_links_unread": collected.get("more_links_unread", False),
        "completeness": collected.get("completeness", "unverified"),
        "published": False,
    }


def draft_source_excerpt(collected: dict, *, target_words: int = 180,
                         scene_count: int = 8) -> dict:
    """Create a verbatim teaser from real chapter text, with URL provenance."""
    if not 70 <= target_words <= 340:
        raise ValueError("target_words must be 70–340")
    pieces: list[str] = []
    sources: list[dict] = []
    remaining = target_words
    for chapter in collected.get("chapters", []):
        body = normalize_script(chapter.get("text", ""))
        words = body.split()
        if not words:
            continue
        # Avoid introducing source text from other websites.
        if not _safe_story_url(chapter.get("url", "")):
            raise ValueError("Unsafe source chapter URL")
        selected = words[:remaining]
        if selected:
            pieces.extend(selected)
            sources.append({"url": chapter["url"], "words_used": len(selected),
                            "sha256": chapter["sha256"]})
            remaining -= len(selected)
        if remaining == 0:
            break
    narration = " ".join(pieces)
    if len(pieces) < 70:
        raise ValueError("Not enough real chapter words for a 60–120s draft; do not invent")
    if not re.search(r"[\u0B80-\u0BFF]", narration):
        raise ValueError("Tamil chapter text not detected; human review needed")
    storyboard = plan_story(narration, scene_count)
    return {
        "narration": narration,
        "storyboard": storyboard,
        "provenance": sources,
        "draft_type": "verbatim_source_excerpt_not_summary",
        "source_faithfulness": "words copied in source order; meaning not automatically verified",
        "story_completeness": collected.get("completeness", "unknown"),
        "requires_human_review": True,
        "approved_for_video": False,
        "published": False,
    }


def save_draft(collected: dict, draft: dict, outdir: str | Path) -> dict:
    """Keep all fetched story text local, under the ignored output/ folder."""
    output = Path(outdir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    repo_root = Path(__file__).resolve().parent
    if output.is_relative_to(repo_root):
        relative = output.relative_to(repo_root)
        if not relative.parts or relative.parts[0] not in ("output", "private"):
            raise ValueError("Save story text only in git-ignored output/ or private/")
    if ".git" in output.parts:
        raise ValueError("Do not write story text into .git")
    (output / "source_chapters.json").write_text(
        json.dumps(collected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "narration_draft_ta.txt").write_text(
        draft["narration"] + "\n", encoding="utf-8")
    save_plan(draft["storyboard"], output / "storyboard_draft.json")
    manifest = {
        "version": 14, "created_utc": datetime.now(timezone.utc).isoformat(),
        "story_url": collected["story_url"],
        "chapters_extracted": collected["chapters_extracted"],
        "source_provenance": draft["provenance"],
        "draft_type": draft["draft_type"],
        "story_completeness": draft["story_completeness"],
        "narration_file": "narration_draft_ta.txt",
        "storyboard_file": "storyboard_draft.json",
        "review_status": "needs_human_story_and_rights_review",
        "unique_scene_art_generated": False,
        "tamil_voice_generated": False,
        "video_generated": False,
        "published": False,
        "live_publishing": False,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def discover_latest_owned_story(discoverer=None) -> str:
    """Reuse the existing V13 story discovery; never invent a URL."""
    if discoverer is None:
        from auto_story_marketing import discover as discoverer
    candidates = discoverer(limit=10)
    for item in candidates:
        if isinstance(item, dict) and _safe_story_url(item.get("link", "")):
            return item["link"]
    raise ValueError("No owned CartoonTamilan novel discovered")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Read owned website chapters and create a review-only Tamil teaser")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--story-url")
    source.add_argument("--discover-latest", action="store_true")
    parser.add_argument("--outdir", default="output/v14/full_story")
    parser.add_argument("--max-pages", type=int, default=24)
    parser.add_argument("--words", type=int, default=180)
    parser.add_argument("--scenes", type=int, default=8)
    parser.add_argument("--inspect", action="store_true",
                        help="Print source/chapter diagnostics without generating narration")
    args = parser.parse_args(argv)
    story_url = discover_latest_owned_story() if args.discover_latest else args.story_url
    collected = collect_full_story(story_url, max_pages=args.max_pages)
    if args.inspect:
        print(json.dumps({"status": "diagnostic_only", **diagnostic_summary(collected)},
                         ensure_ascii=False, indent=2))
        return 0
    try:
        draft = draft_source_excerpt(collected, target_words=args.words,
                                     scene_count=args.scenes)
    except ValueError as exc:
        print(json.dumps({
            "status": "insufficient_or_invalid_chapter_text",
            "error": str(exc),
            "diagnostics": diagnostic_summary(collected),
            "next_step": "Inspect chapter_link_examples and try a verified --story-url; do not invent missing story text",
        }, ensure_ascii=False, indent=2))
        return 2
    digest = hashlib.sha256(story_url.encode("utf-8")).hexdigest()[:16]
    target = Path(args.outdir) / digest
    manifest = save_draft(collected, draft, target)
    print(json.dumps({"status": manifest["review_status"],
                      "chapters_extracted": collected["chapters_extracted"],
                      "story_completeness": collected["completeness"],
                      "narration_file": str(target / "narration_draft_ta.txt"),
                      "storyboard_file": str(target / "storyboard_draft.json"),
                      "published": False}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
