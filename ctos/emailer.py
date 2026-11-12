"""Consent-based owned-subscriber email campaigns.

Generates copyable HTML/text drafts offline. SMTP sending is opt-in and
requires explicit user confirmation, subscribers' opt-in and unsubscribe URL.
"""
from __future__ import annotations

import csv
import html
import json
import os
import re
import smtplib
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv


def build_email(story, intro_ta="", intro_en="", unsubscribe_url="",
                sender_address="", newsletter_type="story_release"):
    if newsletter_type not in ("story_release", "weekly_digest", "reader_welcome",
                               "completed_story", "reader_return"):
        raise ValueError("Unsupported newsletter type")
    title = str(story.get("title", "")).strip()
    story_link = str(story.get("link", "")).strip()
    parsed = urlsplit(story_link)
    if not title or parsed.scheme != "https" or parsed.hostname not in (
            "cartoontamilan.in", "www.cartoontamilan.in"):
        raise ValueError("Verified CartoonTamilan story title and URL required")
    subject = "📚 CartoonTamilan | " + title[:80]
    safe_title = html.escape(title)
    safe_ta = html.escape(intro_ta or "புதிய தமிழ் அசல் கதையைப் படியுங்கள்.")
    safe_en = html.escape(intro_en or "Discover an original Tamil story.")
    safe_link = html.escape(story_link, quote=True)
    unsubscribe = (
        f'<p><a href="{html.escape(unsubscribe_url, quote=True)}">Unsubscribe</a></p>'
        if unsubscribe_url else '<p>Unsubscribe link must be configured before sending.</p>'
    )
    markup = ("""<!doctype html><html lang="ta"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="background:#0e1129;color:#fff;font-family:Arial,sans-serif;padding:26px;">
<main style="max-width:600px;margin:auto"><h1>CartoonTamilan.in</h1>"""
        + f"<h2>{safe_title}</h2><p>{safe_ta}</p><p>{safe_en}</p>"
        + f'<p><a href="{safe_link}" style="background:#ffce77;color:#181020;padding:12px;">'
        + "READ THE STORY</a></p>"
        + f"<p>{html.escape(sender_address) if sender_address else 'Sender address required before sending.'}</p>"
        + unsubscribe + "</main></body></html>")
    plain = (f"CartoonTamilan.in\n{title}\n\n{intro_ta}\n{intro_en}\n\n"
             f"Read: {story_link}\n\n"
             f"{sender_address}\nUnsubscribe: {unsubscribe_url or '[configure before sending]'}")
    return {"subject": subject, "html": markup, "text": plain,
            "story_url": story_link, "approval_required": True,
            "ready_to_send": bool(unsubscribe_url and sender_address),
            "newsletter_type": newsletter_type}


def save_draft(payload, directory):
    dest = Path(directory)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "newsletter.html").write_text(payload["html"], encoding="utf-8")
    (dest / "newsletter.txt").write_text(payload["text"], encoding="utf-8")
    (dest / "newsletter.json").write_text(
        json.dumps({k: v for k, v in payload.items() if k != "html"},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    return str(dest / "newsletter.html")


def opted_in_subscribers(csv_path):
    """Only send to recipients that affirmatively opted in and never unsubscribed."""
    csv_path = Path(csv_path)
    if not csv_path.is_file():
        raise FileNotFoundError("Private subscriber CSV missing")
    subscribers = []
    with csv_path.open(encoding="utf-8-sig", newline="") as file:
        rows = csv.DictReader(file)
        if not rows.fieldnames or not {"email", "opted_in", "unsubscribed"}.issubset(rows.fieldnames):
            raise ValueError("CSV requires email,opted_in,unsubscribed")
        seen = set()
        for item in rows:
            email = item.get("email", "").strip().lower()
            if (re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)
                    and email not in seen
                    and item.get("opted_in", "").strip().lower() == "true"
                    and item.get("unsubscribed", "").strip().lower() != "true"):
                seen.add(email)
                subscribers.append(email)
    return subscribers


def send_one(payload, recipient, *, approved=False, smtp_factory=smtplib.SMTP):
    """Actual SMTP sender; never used by scheduled preview or without explicit gates."""
    load_dotenv()
    if not approved or os.getenv("CT_EMAIL_LIVE") != "YES_SEND_OPTED_IN":
        raise PermissionError("Email requires reviewed approval and CT_EMAIL_LIVE=YES_SEND_OPTED_IN")
    if not payload.get("ready_to_send"):
        raise ValueError("Physical sender address and working unsubscribe link required")
    if recipient not in opted_in_subscribers(os.environ.get("CT_EMAIL_SUBSCRIBERS", "data/subscribers_v13.csv")):
        raise PermissionError("Recipient is not on the consent-based list")
    host = os.getenv("CT_SMTP_HOST", "")
    user = os.getenv("CT_SMTP_USER", "")
    password = os.getenv("CT_SMTP_PASSWORD", "")
    sender = os.getenv("CT_FROM_EMAIL", "")
    if not host or not user or not password or not sender:
        raise ValueError("Configure SMTP host/user/password/sender privately")
    msg = EmailMessage()
    msg["Subject"] = payload["subject"].replace("\r", "").replace("\n", "")
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(payload["text"])
    msg.add_alternative(payload["html"], subtype="html")
    with smtp_factory(host, 587, timeout=25) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)
    return {"recipient": recipient, "sent": True}
