"""CartoonTamilan V12 extra tools CLI. Nothing here publishes to social APIs."""
import argparse
import json
import os
from datetime import date, timedelta
from dotenv import load_dotenv
from pathlib import Path

from auto_story_marketing import discover
from campaign_v9 import read_json
from story_bible_v10 import BIBLES
from campaign_v9 import APPROVALS
from v12_strategy import save_calendar
from v12_seo import audit_pages
from v12_news import discover_news, save_news
from v12_story_reader import collect_chapters, save_chapters, draft_with_local_ai
from v12_media import create_variants, make_reel
from v12_engagement import draft_replies
from v12_weekly import prepare_weekly
from v12_google import (ga4_daily_pageviews, export_ga4_csv, search_console_queries,
                        pagespeed_mobile, refresh_google_token, export_google_report)


def main():
    p = argparse.ArgumentParser(description="CartoonTamilan advanced V12 safe tools")
    sub = p.add_subparsers(dest="task", required=True)
    sub.add_parser("calendar", help="14-day bilingual editorial calendar, draft only")
    sub.add_parser("seo", help="Audit live original-story SEO, report only")
    news = sub.add_parser("news", help="Read confirmed official RSS source list")
    news.add_argument("--sources", default="data/official_sources_v12.json")
    reader = sub.add_parser("chapters", help="Read first publicly accessible chapters into review draft")
    reader.add_argument("--story-url", required=True)
    reader.add_argument("--local-ai", action="store_true", help="Optional local Ollama; no cloud calls")
    art = sub.add_parser("variants", help="Create 4 approved image formats")
    art.add_argument("--artwork", required=True)
    art.add_argument("--title", required=True)
    art.add_argument("--outdir", default="output/v12/variants")
    art.add_argument("--rights-confirmed", action="store_true", required=True)
    reel = sub.add_parser("reel", help="Generate 9:16 MP4 from approved poster using FFmpeg")
    reel.add_argument("--poster", required=True)
    reel.add_argument("--out", default="output/v12/reel.mp4")
    reel.add_argument("--seconds", type=int, default=12)
    reel.add_argument("--voiceover")
    reel.add_argument("--voice-rights-confirmed", action="store_true")
    replies = sub.add_parser("comments", help="Create moderated reply drafts from exported comments")
    replies.add_argument("--csv", default="data/comments_v12.csv")
    sub.add_parser("weekly", help="Real-data weekly report")
    google = sub.add_parser("google", help="Read GA4, Search Console and optionally mobile PageSpeed")
    google.add_argument("--days", type=int, default=7)
    google.add_argument("--pagespeed", action="store_true")
    a = p.parse_args()

    if a.task == "calendar":
        stories = discover(limit=30)
        path = save_calendar(stories, read_json(APPROVALS, {}), read_json(BIBLES, {}))
        print("Editorial calendar saved:", path)
    elif a.task == "seo":
        stories = discover(limit=20)
        report = audit_pages([story["link"] for story in stories], limit=10)
        print("SEO pages checked:", report["pages_checked"])
    elif a.task == "news":
        src = Path(a.sources)
        if not src.is_file():
            p.error("Source JSON missing; use only confirmed official anime/cartoon feeds")
        sources = json.loads(src.read_text(encoding="utf-8"))
        if not isinstance(sources, list):
            p.error("News sources config must contain a JSON array")
        queue = discover_news(sources)
        print("News review queue saved:", save_news(queue), "items:", len(queue))
    elif a.task == "chapters":
        data = collect_chapters(a.story_url)
        path = save_chapters(data)
        print("Chapter excerpts saved:", path, "count:", data["chapters_extracted"])
        if a.local_ai:
            draft = draft_with_local_ai(data)
            from campaign_v9 import write_json
            write_json("output/v12/ai_editor_draft.json", draft)
            print("Unverified local AI editorial draft saved: output/v12/ai_editor_draft.json")
    elif a.task == "variants":
        files = create_variants(a.artwork, a.title, a.outdir,
                                approved_art=a.rights_confirmed)
        print(json.dumps(files, indent=2, ensure_ascii=False))
    elif a.task == "reel":
        path = make_reel(a.poster, a.out, seconds=a.seconds,
                         voiceover=a.voiceover,
                         voice_rights_confirmed=a.voice_rights_confirmed)
        print("Reel saved (still requires visual review and rights):", path)
    elif a.task == "comments":
        result = draft_replies(a.csv)
        print("Comment drafts:", len(result.get("drafts", [])),
              "status:", result["status"])
    elif a.task == "weekly":
        result = prepare_weekly()
        print("Weekly review: pageviews=", result["real_pageview_report"].get("status"),
              "social=", result["social_to_site_report"].get("status"))
    elif a.task == "google":
        load_dotenv()
        if not 1 <= a.days <= 90:
            p.error("--days must be 1–90")
        property_id = os.getenv("GA4_PROPERTY_ID", "")
        site_property = os.getenv("GSC_PROPERTY", "")
        token = os.getenv("GOOGLE_OAUTH_ACCESS_TOKEN", "")
        if not token:
            token = refresh_google_token(
                os.getenv("GOOGLE_CLIENT_ID", ""),
                os.getenv("GOOGLE_CLIENT_SECRET", ""),
                os.getenv("GOOGLE_REFRESH_TOKEN", ""))
        finish = date.today() - timedelta(days=1)
        start = finish - timedelta(days=a.days - 1)
        ga4 = None
        gsc = None
        speed = None
        if property_id:
            ga4 = ga4_daily_pageviews(property_id, token, start.isoformat(), finish.isoformat())
            if ga4:
                export_ga4_csv(ga4)
        if site_property:
            gsc = search_console_queries(site_property, token, start.isoformat(), finish.isoformat())
        if a.pagespeed:
            speed = pagespeed_mobile("https://cartoontamilan.in/")
        if ga4 is None and gsc is None and speed is None:
            p.error("Configure GA4_PROPERTY_ID / GSC_PROPERTY or --pagespeed; no data obtained")
        print("Verified Google API report:", export_google_report(ga4, gsc, speed))
        print("GA4 dates:", len(ga4 or []), "GSC queries:", len(gsc or []))



if __name__ == "__main__":
    main()
