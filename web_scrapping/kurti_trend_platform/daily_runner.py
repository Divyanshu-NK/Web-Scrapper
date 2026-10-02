#!/usr/bin/env python3
"""
daily_runner.py — Daily Automated Scraper Runner & Notification Dispatcher

Runs nightly at 11:59 PM (or via GitHub Actions trigger).
1. Executes multi-brand & marketplace scrape pipeline.
2. Updates time-series daily metrics & re-calculates trend velocity & scores.
3. Sends detailed start, success, and failure notifications with full stats breakdown.
"""

import os
import sys
import json
import logging
import requests
from datetime import datetime

# Add parent directory to path to enable backend package imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Force line-buffered output for real-time logging
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from backend.database import DatabaseManager
from backend.scrapers.orchestrator import ScraperOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("daily_runner")



ALL_PLATFORMS = [
    "libas", "janasya", "aarsi", "bunaai", "mulmul", 
    "gulabojaipur", "rustorange", "karagiri", "jaipurkurti", 
    "fashor", "sabhyata", "tjori", "truebrowns"
]

def send_webhook_notification(title: str, text: str, is_error: bool = False):
    """Sends notification to GitHub Actions Step Summary, Slack, Telegram, Discord, or generic Webhook"""
    print(f"--- [NOTIFICATION] {title} ---\n{text}\n----------------------------------", flush=True)

    # 1. Output to GitHub Step Summary if running in GitHub Actions
    github_summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if github_summary_path:
        try:
            with open(github_summary_path, "a", encoding="utf-8") as f:
                f.write(f"\n## {title}\n\n{text}\n")
            logger.info("Wrote summary to GitHub Step Summary.")
        except Exception as e:
            logger.error(f"Failed to write GitHub Step Summary: {e}")


    # 2. Slack Webhook
    slack_url = os.getenv("SLACK_WEBHOOK_URL")
    if slack_url:
        try:
            color = "#ff0000" if is_error else "#36a64f"
            payload = {
                "attachments": [
                    {
                        "color": color,
                        "title": title,
                        "text": text,
                        "ts": datetime.now().timestamp()
                    }
                ]
            }
            requests.post(slack_url, json=payload, timeout=10)
            logger.info("Sent Slack notification.")
        except Exception as e:
            logger.error(f"Slack webhook failed: {e}")

    # 3. Discord Webhook
    discord_url = os.getenv("DISCORD_WEBHOOK_URL")
    if discord_url:
        try:
            payload = {"content": f"**{title}**\n{text}"}
            requests.post(discord_url, json=payload, timeout=10)
            logger.info("Sent Discord notification.")
        except Exception as e:
            logger.error(f"Discord webhook failed: {e}")

    # 4. Telegram Bot
    tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
    tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if tg_token and tg_chat_id:
        try:
            tg_url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
            msg = f"<b>{title}</b>\n\n{text}"
            requests.post(tg_url, json={"chat_id": tg_chat_id, "text": msg, "parse_mode": "HTML"}, timeout=10)
            logger.info("Sent Telegram notification.")
        except Exception as e:
            logger.error(f"Telegram notification failed: {e}")

    # 5. Generic Webhook
    generic_url = os.getenv("WEBHOOK_URL")
    if generic_url:
        try:
            requests.post(generic_url, json={"title": title, "body": text, "status": "failed" if is_error else "success"}, timeout=10)
            logger.info("Sent generic webhook notification.")
        except Exception as e:
            logger.error(f"Generic webhook failed: {e}")

    # 6. Direct SMTP Email Notification
    recipient_email = os.getenv("NOTIFICATION_EMAIL") or os.getenv("EMAIL_TO")
    smtp_user = os.getenv("SMTP_USER") or os.getenv("EMAIL_USER")
    smtp_password = os.getenv("SMTP_PASSWORD") or os.getenv("EMAIL_PASSWORD")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))

    if recipient_email and smtp_user and smtp_password:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = title
            msg["From"] = smtp_user
            msg["To"] = recipient_email

            body_html = f"""
            <html>
              <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2 style="color: {'#d9534f' if is_error else '#2e7d32'};">{title}</h2>
                <div style="background: #f9f9f9; padding: 15px; border-radius: 8px; border: 1px solid #ddd;">
                  <pre style="font-family: monospace; white-space: pre-wrap;">{text}</pre>
                </div>
                <p style="font-size: 12px; color: #777; margin-top: 20px;">
                  Sent automatically by <b>Kurti Trend Platform Scraper Engine</b>
                </p>
              </body>
            </html>
            """
            msg.attach(MIMEText(text, "plain"))
            msg.attach(MIMEText(body_html, "html"))

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)

            logger.info(f"Sent email notification to {recipient_email}.")
        except Exception as e:
            logger.error(f"SMTP email notification failed: {e}")



def main():
    start_time = datetime.now()
    now_str = start_time.strftime("%Y-%m-%d %H:%M:%S IST")
    
    logger.info(f"Triggering daily 11:59 PM Kurti Scraper run at {now_str}...")

    # Notify Trigger Start
    start_title = "🚀 Daily Kurti Scraper Started"
    start_msg = f"The automated 11:59 PM scraping job has started execution across {len(ALL_PLATFORMS)} platforms.\n*Timestamp:* `{now_str}`"
    send_webhook_notification(start_title, start_msg)

    db = DatabaseManager()
    orchestrator = ScraperOrchestrator(db)

    try:
        result = orchestrator.run_orchestrator(platforms=ALL_PLATFORMS, keyword="kurti")
        duration = (datetime.now() - start_time).seconds

        if result.get("status") == "success":
            scraped = result.get("scraped_count", 0)
            new_cnt = result.get("new_count", 0)
            updated_cnt = result.get("updated_count", 0)
            reviews_gained = result.get("total_reviews_gained", 0)
            price_changes = result.get("price_changes_count", 0)
            new_samples = result.get("new_products_sample", [])
            top_trending = result.get("top_trending_products", [])

            # Format New Articles Info
            new_articles_str = f"**{new_cnt} New Articles Discovered**"
            if new_samples:
                samples_formatted = "\n  • " + "\n  • ".join(new_samples[:5])
                new_articles_str += f":{samples_formatted}"

            # Format Top 5 Trending Products
            top_str = ""
            if top_trending:
                top_lines = [
                    f"  {idx+1}. **{p['title']}** ({p['brand']}) — Score: `{p['score']}` | Price: `₹{p['price']}` | Velocity: `{p['velocity']} rev/day`"
                    for idx, p in enumerate(top_trending)
                ]
                top_str = "\n\n🔥 **Top 5 Trending Kurtis After Today's Update:**\n" + "\n".join(top_lines)

            success_title = "✅ Daily Scraper Completed Successfully"
            success_msg = (
                f"**Job Summary ({duration}s):**\n"
                f"• 📦 **Total Catalog Scraped:** `{scraped}` products\n"
                f"• 🆕 {new_articles_str}\n"
                f"• 🔄 **Existing Articles Updated:** `{updated_cnt}` articles\n"
                f"• 💬 **Review Data Gained Today:** `+{reviews_gained}` new reviews recorded across products\n"
                f"• 🏷️ **Price Fluctuation Tracked:** `{price_changes}` products with price changes"
                f"{top_str}\n\n"
                f"*(Updated time-series metrics & trend velocity scores for today)*"
            )

            send_webhook_notification(success_title, success_msg)
            logger.info("Daily scraper run completed successfully.")
            sys.exit(0)
        else:
            err_detail = result.get("error", "Unknown error")
            fail_title = "❌ Daily Scraper Execution Failed"
            fail_msg = f"The automated daily scraper encountered an error:\n```\n{err_detail}\n```"
            send_webhook_notification(fail_title, fail_msg, is_error=True)
            logger.error(f"Daily scraper failed: {err_detail}")
            sys.exit(1)

    except Exception as e:
        fail_title = "💥 Daily Scraper Crash Alert"
        fail_msg = f"Unhandled exception during daily scraper run:\n```\n{str(e)}\n```"
        send_webhook_notification(fail_title, fail_msg, is_error=True)
        logger.error(f"Fatal scraper crash: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
