# 🏏 RCB Ticket Page Monitor

A Python agent that watches [shop.royalchallengers.com/ticket](https://shop.royalchallengers.com/ticket) every **30 seconds** and sends an instant **Telegram notification** when the page content changes — so you never miss a ticket drop.

---

## Quick Start

### 1. Clone & install

```bash
cd RCB_Ticket_AI_Agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Set environment variables

```bash
export TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."
export TELEGRAM_CHAT_ID="your_chat_id"
```

### 3. Run

```bash
python monitor.py
```

You'll see:

```
2026-03-24 18:45:00  INFO      Starting RCB Ticket Monitor (interval=30s)
2026-03-24 18:45:02  INFO      Monitoring started — baseline hash: a1b2c3d4e5f6...
```

---

## Environment Variables

| Variable             | Required | Description                       |
| -------------------- | -------- | --------------------------------- |
| `TELEGRAM_BOT_TOKEN` | Yes      | Bot token from @BotFather         |
| `TELEGRAM_CHAT_ID`   | Yes      | Numeric chat ID for notifications |

---

## Telegram Setup

### Get a Bot Token

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts to name your bot
3. Copy the **HTTP API token** (looks like `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`)

### Get Your Chat ID

1. Search for **@userinfobot** on Telegram
2. Send `/start` — it will reply with your numeric **chat ID**
3. Alternatively, use **@RawDataBot** and look for `"id"` in the response

> **Tip:** To send to a group, add your bot to the group and use the group's chat ID (starts with `-`).

---

## Docker

### Build & run

```bash
docker build -t rcb-monitor .
docker run -d \
  --name rcb-monitor \
  -e TELEGRAM_BOT_TOKEN="your_token" \
  -e TELEGRAM_CHAT_ID="your_chat_id" \
  -v rcb-state:/app/data \
  --restart unless-stopped \
  rcb-monitor
```

The `-v rcb-state:/app/data` volume keeps `last_state.txt` across container restarts.

### View logs

```bash
docker logs -f rcb-monitor
```

---

## Playwright Fallback (JS-Rendered Pages)

If the ticket page uses heavy JavaScript rendering and `httpx` returns incomplete HTML, swap in this Playwright-based fetcher:

### Install Playwright

```bash
pip install playwright
playwright install chromium
```

### Replace `fetch_page()` in `monitor.py`

```python
from playwright.sync_api import sync_playwright

def fetch_page() -> str:
    """Fetch the target URL using a headless browser (Playwright).

    Use this instead of the httpx version if the page relies on
    client-side JavaScript to render ticket information.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=USER_AGENT)
        page.goto(TARGET_URL, wait_until="networkidle", timeout=60_000)
        html = page.content()
        browser.close()
        return html
```

> **Note:** Playwright adds ~200 MB for the Chromium binary. Only use this if the default `httpx` fetch is missing content.

---

## How It Works

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  fetch_page  │ ──▸ │ extract_text │ ──▸ │ compute_hash │
└─────────────┘     └──────────────┘     └──────┬───────┘
                                                 │
                                          ┌──────▼───────┐
                                          │ compare hash │
                                          └──────┬───────┘
                                                 │
                              ┌──────────────────┼──────────────────┐
                              ▼                  ▼                  ▼
                        First run          No change          Change found
                       save hash           log & skip      extract titles →
                                                           Telegram alert →
                                                             save hash
```

Every cycle is logged with timestamp, status, and hash prefix.

---

## Troubleshooting

| Problem                      | Fix                                                                 |
| ---------------------------- | ------------------------------------------------------------------- |
| `Telegram credentials not set` | Ensure `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are exported    |
| `Fetch failed` errors        | The site may be down or blocking requests — check your network      |
| Empty text extracted          | The page may use JS rendering — try the Playwright fallback above   |
| Too many alerts               | Content may be dynamic (ads, timestamps) — customise `extract_text` |
