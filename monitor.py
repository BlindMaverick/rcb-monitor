#!/usr/bin/env python3
"""
RCB Ticket Page Monitor
=======================
Polls https://shop.royalchallengers.com/ticket every 30 seconds,
detects content changes via SHA-256 hashing, and sends Telegram alerts.
"""

import asyncio
import hashlib
import logging
import os
import re
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from apscheduler.schedulers.blocking import BlockingScheduler
from telegram import Bot
from telegram.constants import ParseMode

# ── Configuration ────────────────────────────────────────────────────────────

TARGET_URL = "https://shop.royalchallengers.com/ticket"
POLL_INTERVAL_SECONDS = 30
STATE_DIR = Path(os.environ.get("STATE_DIR", "."))
STATE_FILE = STATE_DIR / "last_state.txt"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

REQUEST_TIMEOUT = 30  # seconds

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("rcb-monitor")

# ── Core Functions ───────────────────────────────────────────────────────────


def fetch_page() -> str:
    """Fetch the target URL and return raw HTML."""
    with httpx.Client(headers=HEADERS, timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        response = client.get(TARGET_URL)
        response.raise_for_status()
        return response.text


def extract_text(html: str) -> str:
    """Extract and normalise visible text from the <main> tag.

    Strips <script>, <style>, and <noscript> elements before extracting text.
    Falls back to the full <body> if no <main> tag is found.
    """
    soup = BeautifulSoup(html, "lxml")

    # Remove invisible elements
    for tag in soup.find_all(["script", "style", "noscript"]):
        tag.decompose()

    container = soup.find("main") or soup.find("body") or soup
    text = container.get_text(separator=" ", strip=True)

    # Collapse whitespace
    return re.sub(r"\s+", " ", text).strip()


def compute_hash(text: str) -> str:
    """Return the SHA-256 hex digest of the given text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_titles(html: str) -> list[str]:
    """Pull ticket / event titles from the page.

    Looks at <h1>, <h2>, and any element whose class name contains
    'ticket' or 'product'.
    """
    soup = BeautifulSoup(html, "lxml")

    for tag in soup.find_all(["script", "style", "noscript"]):
        tag.decompose()

    titles: list[str] = []

    # Headings
    for heading in soup.find_all(["h1", "h2"]):
        t = heading.get_text(strip=True)
        if t:
            titles.append(t)

    # Elements with ticket/product in class
    for el in soup.find_all(attrs={"class": True}):
        classes = " ".join(el.get("class", []))
        if re.search(r"ticket|product", classes, re.IGNORECASE):
            t = el.get_text(strip=True)
            if t and t not in titles:
                titles.append(t)

    return titles


# ── State Persistence ────────────────────────────────────────────────────────


def load_hash() -> str | None:
    """Load the previously saved hash, or None on first run."""
    if STATE_FILE.exists():
        return STATE_FILE.read_text().strip()
    return None


def save_hash(h: str) -> None:
    """Persist the current hash to disk."""
    STATE_FILE.write_text(h)


# ── Telegram ─────────────────────────────────────────────────────────────────


def send_telegram(message: str) -> None:
    """Send a Telegram message (sync wrapper around the async API)."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram credentials not set — skipping notification")
        return

    async def _send() -> None:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
            parse_mode=ParseMode.MARKDOWN,
        )

    try:
        asyncio.run(_send())
        log.info("Telegram alert sent successfully")
    except Exception as exc:
        log.error("Failed to send Telegram alert: %s", exc)


# ── Monitoring Logic ─────────────────────────────────────────────────────────


def check() -> None:
    """Single monitoring cycle: fetch → extract → hash → compare → alert."""
    try:
        html = fetch_page()
    except Exception as exc:
        log.error("Fetch failed, skipping cycle: %s", exc)
        return

    try:
        text = extract_text(html)
        new_hash = compute_hash(text)
    except Exception as exc:
        log.error("Parsing failed, skipping cycle: %s", exc)
        return

    old_hash = load_hash()

    # ── First run ────────────────────────────────────────────────────────
    if old_hash is None:
        save_hash(new_hash)
        log.info("Monitoring started — baseline hash: %s", new_hash[:16])
        return

    # ── No change ────────────────────────────────────────────────────────
    if new_hash == old_hash:
        log.info("No change  | hash: %s", new_hash[:16])
        return

    # ── Change detected ──────────────────────────────────────────────────
    log.info(
        "CHANGE DETECTED  | old: %s → new: %s",
        old_hash[:16],
        new_hash[:16],
    )

    titles = extract_titles(html)
    title_section = "\n".join(f"• {t}" for t in titles) if titles else "_No specific titles found_"

    message = (
        "🚨 *RCB Ticket Page Changed!*\n\n"
        f"🔗 [View Page]({TARGET_URL})\n\n"
        f"*Detected Items:*\n{title_section}\n\n"
        f"`old: {old_hash[:16]}…`\n"
        f"`new: {new_hash[:16]}…`"
    )

    send_telegram(message)
    save_hash(new_hash)


# ── Entry Point ──────────────────────────────────────────────────────────────


def main() -> None:
    log.info("Starting RCB Ticket Monitor (interval=%ds)", POLL_INTERVAL_SECONDS)

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning(
            "TELEGRAM_BOT_TOKEN and/or TELEGRAM_CHAT_ID not set. "
            "Notifications will be skipped."
        )

    # Run the first check immediately
    check()

    scheduler = BlockingScheduler()
    scheduler.add_job(
        check,
        "interval",
        seconds=POLL_INTERVAL_SECONDS,
        max_instances=1,
        id="rcb_ticket_check",
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped — goodbye!")


if __name__ == "__main__":
    main()
