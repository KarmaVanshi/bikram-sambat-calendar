# Bikram Sambat Calendar

A B.S. (Bikram Sambat) date-label calendar for Apple Calendar, Google Calendar,
and any other app that supports iCalendar subscriptions. Every day gets one
all-day event; the 1st of each B.S. month shows `MonthName Year` (e.g.
`Bhadra 2083`), every other day shows just the bare day number — it reads
like a wall calendar in an agenda view instead of repeating the same month
and year on every line.

Data is scraped from [hamropatro.com](https://www.hamropatro.com), currently
covering roughly BS 2081–2100 (~AD 2024–2044) and growing by one year at a
time as hamropatro.com publishes new years.

## Subscribe

Use this URL in any calendar app's "subscribe by URL" / "from URL" option:

```
https://raw.githubusercontent.com/KarmaVanshi/bikram-sambat-calendar/main/bikram_sambat_calendar.ics
```

- **macOS Calendar:** File → New Calendar Subscription → paste the URL → set
  auto-refresh (Get Info on the calendar) to your preferred interval.
- **iOS Calendar:** Settings → Calendar → Accounts → Add Account → Other →
  Add Subscribed Calendar → paste the URL. Or open
  `webcal://raw.githubusercontent.com/KarmaVanshi/bikram-sambat-calendar/main/bikram_sambat_calendar.ics`
  in Safari.
- **Android (Google Calendar):** on calendar.google.com (desktop browser,
  same Google account as your phone) → Other calendars (+) → From URL →
  paste the URL. Syncs to the Android app automatically. Google controls the
  refresh interval (usually every 12–24h); there's no user setting for it.

## How it works

`scrape_bs_calendar.py` fetches `hamropatro.com/en/calendar/{year}/{month}`
pages, which each embed a Next.js RSC JSON payload containing the requested
month plus the month before and after it — so one BS year only needs 4
requests (months 2, 5, 8, 11) to be fully covered. It builds one RFC5545
all-day `VEVENT` per Gregorian day from that data.

```
python3 scrape_bs_calendar.py --year-start 2081 --year-end 2093 -o bikram_sambat_calendar.ics
```

`--lang en|np|both` picks English, Devanagari, or both for the month-header
labels (day numbers on non-header days follow the same choice). `--extend`
is the self-update mode: it reads the year range already in an existing
output file, keeps the same start year, and grows the end year by 1 if
hamropatro.com has published a new one — this is what the scheduled job
below runs.

## Auto-update

**hamropatro.com's CDN blocks GitHub Actions' IP range with HTTP 403 on
every request** (confirmed 2026-08-21 — a full scheduled run failed
end-to-end, then the identical code succeeded immediately from a local
Mac). So the scraping step can't run on GitHub's infrastructure; it runs
locally instead, from a macOS LaunchAgent, while GitHub still hosts the
resulting `.ics` file that all subscriptions actually read from.

- **LaunchAgent:** `~/Library/LaunchAgents/com.rakesh.bs-calendar-update.plist`
  — runs every 7 days (`StartInterval`).
- **Working copy it operates on:**
  `~/Library/Application Support/bikram-sambat-calendar` — a separate clone
  from whatever you're looking at in `~/Desktop/Calendar` right now, so
  deleting the Desktop copy doesn't affect it.
- **Self-healing:** the job's logic is inlined directly in the plist (not a
  separate script file), and it re-clones the repo from scratch if the
  working copy is missing or damaged. It also `git pull --rebase`s before
  every run, so it always uses the latest version of
  `scrape_bs_calendar.py` regardless of where that update was pushed from.
- Logs: `~/Library/Logs/bs-calendar-update.log`

Manually trigger a run: `launchctl start com.rakesh.bs-calendar-update`
