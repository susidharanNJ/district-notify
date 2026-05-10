"""
District.in Show Notifier
Runs via GitHub Actions every 30 minutes.
Detects new shows at a theatre and sends email via Resend.
"""

import os
import json
import time
import sys
from datetime import datetime

# ──────────────────────────────────────────────────────────────────────
# CONFIG — set via GitHub Actions environment variables
# ──────────────────────────────────────────────────────────────────────
DISTRICT_URL    = os.getenv("DISTRICT_URL", "")
CHECK_DATES     = os.getenv("CHECK_DATES", "")        # e.g. "2026-05-14,2026-05-15"
RESEND_API_KEY  = os.getenv("RESEND_API_KEY", "")
RESEND_TO       = os.getenv("RESEND_TO", "")
RESEND_FROM     = os.getenv("RESEND_FROM", "alerts@resend.dev")
STATE_FILE      = "district_state.json"

# ──────────────────────────────────────────────────────────────────────
# FETCH PAGE using Playwright (real browser — bypasses bot detection)
# ──────────────────────────────────────────────────────────────────────
def fetch_shows(url: str) -> list[dict]:
    from playwright.sync_api import sync_playwright

    shows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        print(f"  Loading: {url}")
        page.goto(url, wait_until="networkidle", timeout=60000)

        # Wait for show cards to appear
        try:
            page.wait_for_selector("[class*='show'], [class*='ShowCard'], [class*='showtime'], article", timeout=15000)
        except Exception:
            print("  Warning: show selector timed out, parsing what's available")

        # Small extra wait for JS rendering
        time.sleep(3)

        # Grab page HTML for parsing
        html = page.content()
        browser.close()

    # Parse shows from HTML using BeautifulSoup
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    # District.in shows movie names + showtimes in cards
    # Strategy: look for time patterns and nearby movie names
    seen = set()

    # Try multiple selectors District.in might use
    show_containers = (
        soup.select("[class*='ShowCard']") or
        soup.select("[class*='show-card']") or
        soup.select("[class*='movie-card']") or
        soup.select("article") or
        soup.select("[class*='EventCard']")
    )

    if show_containers:
        for card in show_containers:
            text = card.get_text(separator=" | ", strip=True)
            if not text:
                continue
            key = text[:120]
            if key not in seen:
                seen.add(key)
                # Try to extract movie name and time
                title_el = card.select_one("h2, h3, h4, [class*='title'], [class*='name']")
                time_el  = card.select_one("[class*='time'], [class*='show-time'], time")

                shows.append({
                    "title": title_el.get_text(strip=True) if title_el else "Unknown",
                    "time":  time_el.get_text(strip=True) if time_el else "",
                    "text":  key,
                })
    else:
        # Fallback: extract all visible text blocks that look like showtimes
        import re
        time_pattern = re.compile(r'\b(\d{1,2}:\d{2}\s*[AP]M)\b', re.IGNORECASE)
        all_text = soup.get_text(separator="\n")
        for line in all_text.splitlines():
            line = line.strip()
            if time_pattern.search(line) and len(line) > 5:
                if line not in seen:
                    seen.add(line)
                    shows.append({"title": "", "time": "", "text": line})

    print(f"  Found {len(shows)} show entries")
    return shows


# ──────────────────────────────────────────────────────────────────────
# STATE  (persisted via GitHub Actions artifact between runs)
# ──────────────────────────────────────────────────────────────────────
def load_state() -> dict:
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def shows_to_state(shows: list[dict]) -> dict:
    return {s["text"]: s for s in shows}

def detect_new(old: dict, new: dict) -> list[dict]:
    return [v for k, v in new.items() if k not in old]


# ──────────────────────────────────────────────────────────────────────
# EMAIL via Resend
# ──────────────────────────────────────────────────────────────────────
def send_email(new_shows: list[dict], all_shows: list[dict], url: str):
    import requests
    from html import escape

    if not RESEND_API_KEY or not RESEND_TO:
        print("  ⚠️  RESEND_API_KEY or RESEND_TO not set — skipping email")
        return

    now = datetime.now().strftime("%d %b %Y, %I:%M %p")
    count = len(new_shows)
    subject = f"🎬 District.in: {count} new show{'s' if count>1 else ''} added!"

    # New shows rows
    new_rows = "".join(
        f"<tr><td style='padding:6px 10px;border-bottom:1px solid #eee;font-size:13px'>"
        f"{'🆕 ' + escape(s.get('title','')) if s.get('title') else ''} "
        f"{escape(s.get('time',''))} "
        f"<span style='color:#888;font-size:11px'>{escape(s['text'][:100])}</span>"
        f"</td></tr>"
        for s in new_shows
    )

    # All shows rows
    all_rows = "".join(
        f"<tr><td style='padding:5px 10px;border-bottom:1px solid #f5f5f5;font-size:12px;color:#555'>"
        f"{escape(s['text'][:120])}"
        f"</td></tr>"
        for s in all_shows
    )

    html = f"""<!doctype html><html><body style='font-family:Arial,sans-serif;padding:24px;color:#333'>
<h2 style='margin:0 0 4px'>🎬 New Shows on District.in</h2>
<p style='margin:0 0 16px;color:#888;font-size:13px'>{now}</p>
<p><a href='{url}' style='color:#e63946'>👉 Book now on District.in</a></p>
<h3 style='margin:16px 0 8px;font-size:15px'>New Additions ({count})</h3>
<table style='width:100%;border-collapse:collapse;border:1px solid #eee'>{new_rows}</table>
<h3 style='margin:20px 0 8px;font-size:14px;color:#666'>All Current Shows</h3>
<table style='width:100%;border-collapse:collapse;border:1px solid #f0f0f0'>{all_rows}</table>
<p style='margin-top:24px;font-size:11px;color:#aaa'>Automated alert from district-notifier on GitHub Actions</p>
</body></html>"""

    plain = f"New shows on District.in!\n\n{now}\n{url}\n\n"
    plain += "NEW:\n" + "\n".join(f"  - {s['text']}" for s in new_shows)
    plain += "\n\nALL:\n" + "\n".join(f"  - {s['text']}" for s in all_shows)

    import requests
    resp = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        json={"from": RESEND_FROM, "to": [RESEND_TO], "subject": subject, "html": html, "text": plain},
        timeout=15,
    )
    if resp.status_code in (200, 201):
        print(f"  ✅ Email sent → {RESEND_TO}")
    else:
        print(f"  ❌ Resend error {resp.status_code}: {resp.text}")
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────
def main():
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{now_str}] District.in Show Notifier")

    if not DISTRICT_URL:
        print("  ❌ DISTRICT_URL not set")
        sys.exit(1)

    # If multiple dates configured, check each
    dates = [d.strip() for d in CHECK_DATES.split(",") if d.strip()] if CHECK_DATES else [""]

    all_shows = []
    for date in dates:
        url = DISTRICT_URL
        if date:
            # Inject/replace fromdate param
            import re
            if "fromdate=" in url:
                url = re.sub(r'fromdate=[^&]+', f'fromdate={date}', url)
            else:
                url += f"{'&' if '?' in url else '?'}fromdate={date}"

        print(f"\n  Checking date: {date or 'default'}")
        try:
            shows = fetch_shows(url)
            for s in shows:
                s["date"] = date
                s["text"] = f"[{date}] {s['text']}" if date else s["text"]
            all_shows.extend(shows)
        except Exception as e:
            print(f"  ⚠️  Error fetching {url}: {e}")

    if not all_shows:
        print("\n  No shows found (page may have changed structure or blocked)")
        sys.exit(0)

    # Compare with last state
    new_state = shows_to_state(all_shows)
    old_state = load_state()

    new_shows = detect_new(old_state, new_state)
    save_state(new_state)

    if new_shows:
        print(f"\n  ⚡ {len(new_shows)} new show(s) detected!")
        for s in new_shows:
            print(f"    → {s['text']}")
        send_email(new_shows, all_shows, DISTRICT_URL)
    else:
        print(f"\n  ✅ No new shows. Total tracked: {len(all_shows)}")

    print("\n  Done.")


if __name__ == "__main__":
    main()
