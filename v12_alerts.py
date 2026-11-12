"""Optional private, opt-in Telegram alert for Oracle automation failures.

Do not put the bot token/chat ID into GitHub or public logs. The feature is
disabled unless both V12_ALERTS_ENABLED=true and credentials are set.
"""
import os
import requests
from dotenv import load_dotenv


def report_alert(status, issues=None, http=None):
    load_dotenv()
    if os.getenv("V12_ALERTS_ENABLED", "false").lower() != "true":
        return "disabled"
    token = os.getenv("V12_TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("V12_TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return "not_configured"
    if not token.replace(":", "").replace("_", "").replace("-", "").isalnum():
        raise ValueError("Invalid bot token format")
    safe_issues = [str(reason)[:180] for reason in (issues or [])[:4]]
    # Never send exceptions that could contain secrets, local server IPs or filenames.
    message = ("CartoonTamilan V12 Oracle status: " + str(status)[:35] +
               "\nIssues: " + str(len(issues or [])) +
               "\nCheck Oracle journalctl and output/v12/latest_health.json for details.")
    try:
        response = (http or requests).post(
            "https://api.telegram.org/bot" + token + "/sendMessage",
            data={"chat_id": chat_id, "text": message},
            timeout=12,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        # Do not include underlying URL; Telegram embeds the token in it.
        raise RuntimeError("Telegram alert failed (details suppressed to protect token)") from None
    return "sent"
