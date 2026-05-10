# District.in Show Notifier

Monitors a District.in theatre page for new shows and emails you the moment they appear. Runs free on **GitHub Actions** every 30 minutes — no server needed.

---

## How It Works

1. GitHub Actions runs this script every 30 minutes (free)
2. It launches a real Chromium browser (bypasses bot detection)
3. Loads your District.in theatre page
4. Compares shows with the last run
5. Emails you via Resend if anything new appeared

---

## Setup (10 minutes)

### Step 1 — Fork this repo
Click **Fork** at the top right on GitHub.

### Step 2 — Get a free Resend account
1. Go to [resend.com](https://resend.com) → Sign up (free)
2. Go to **API Keys** → Create a key → copy it
3. For `RESEND_FROM`: use `alerts@resend.dev` (works without a custom domain on free tier)

### Step 3 — Add Secrets
In your forked repo → **Settings → Secrets and variables → Actions → Secrets**

| Secret | Value |
|--------|-------|
| `RESEND_API_KEY` | Your Resend API key (`re_...`) |
| `RESEND_TO` | Your email address (where to receive alerts) |
| `RESEND_FROM` | `alerts@resend.dev` *(or your own domain email if you have one)* |

### Step 4 — Add Variables
Same page → click **Variables** tab

| Variable | Example | Description |
|----------|---------|-------------|
| `DISTRICT_URL` | `https://www.district.in/movies/vettri-theatres-rgb-laser-chrompet-chennai-in-chennai-CD4891` | Your theatre page URL (without `?fromdate=`) |
| `CHECK_DATES` | `2026-05-14,2026-05-15,2026-05-16` | Dates to monitor (comma-separated, YYYY-MM-DD). Leave empty to use URL default. |

### Step 5 — Test it manually
Go to **Actions → District.in Show Notifier → Run workflow** → click **Run workflow**

Watch the logs. If shows are found, you'll get an email next time new ones appear.

---

## Frequency
GitHub Actions runs the cron every 30 minutes. Note: GitHub may delay scheduled runs by a few minutes during high traffic.

## Cost
**Free** — GitHub Actions gives 2,000 minutes/month on free accounts. This script uses ~2 min per run × 48 runs/day = ~96 min/day, well within limits.

Resend free tier: 3,000 emails/month — more than enough.

---

## Troubleshooting

**No shows found** — District.in may have updated their HTML structure. Open an issue and paste the URL you're monitoring.

**Email not arriving** — Check spam. Verify `RESEND_API_KEY` and `RESEND_TO` are set correctly under Secrets (not Variables).

**Workflow not running** — GitHub disables scheduled workflows after 60 days of repo inactivity. Just commit a small change to reactivate, or trigger manually.
