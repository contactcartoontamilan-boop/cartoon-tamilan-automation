"""V12 comment engagement: safe reply DRAFTS from moderator-reviewed CSV.

Supports Facebook/Instagram comments exported by the account owner.
No account scraping, impersonation, toxic-content auto-replies or sending.
"""
import csv
import json
import re
from pathlib import Path

QUESTIONS = {
    "link": ("📖 முழுக் கதையின் link எங்கள் profile-ல் இருக்கிறது. நன்றி!",
             "📖 The full story is available from our profile link. Thanks!"),
    "update": ("📚 அதிகாரப்பூர்வ புதிய chapter update வந்தவுடன் பகிர்கிறோம்.",
               "📚 We'll share verified chapter news when it's available."),
    "feedback": ("💖 படித்ததற்கும் கருத்து பகிர்ந்ததற்கும் நன்றி!",
                 "💖 Thanks for reading and sharing your thoughts!"),
}


def category(text):
    value = str(text or "").lower().strip()
    if any(term in value for term in ("link", "url", "எங்கே", "படிக்க", "where to read")):
        return "link"
    if any(term in value for term in ("next", "update", "chapter", "அடுத்த", "எப்போது")):
        return "update"
    return "feedback"


def draft_replies(csv_path, out="output/v12/comment_reply_drafts.json", max_comments=50):
    path = Path(csv_path)
    if not path.exists():
        return {"status": "no_comments_export", "drafts": []}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = csv.DictReader(fh)
        if not rows.fieldnames or not {"platform", "comment_id", "comment_text"}.issubset(rows.fieldnames):
            raise ValueError("Comment CSV needs platform, comment_id, comment_text")
        drafts = []
        for item in rows:
            if len(drafts) >= max_comments:
                break
            channel = str(item.get("platform", "")).lower().strip()
            if channel not in ("facebook", "instagram"):
                continue
            comment = re.sub(r"\s+", " ", item.get("comment_text") or "").strip()[:500]
            if not comment or not item.get("comment_id"):
                continue
            # Do not automatically reply to harassment, requests for personal
            # data or sensitive subjects. A human must moderate all replies.
            kind = category(comment)
            tamil, english = QUESTIONS[kind]
            drafts.append({
                "platform": channel, "comment_id": str(item["comment_id"])[:100],
                "category": kind, "reply_draft_ta": tamil,
                "reply_draft_en": english, "needs_human_moderation": True,
                "sent": False,
            })
    result = {"status": "review_required", "drafts": drafts, "automatic_reply": False}
    output = Path(out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
