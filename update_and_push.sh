#!/bin/bash
# Re-scrapes hamropatro.com, extends bikram_sambat_calendar.ics if a new B.S.
# year is available, and pushes the change to GitHub if the file changed.
# Run on a schedule by ~/Library/LaunchAgents/com.rakesh.bs-calendar-update.plist
# -- must run from this Mac, not a cloud CI runner: hamropatro.com's CDN
# returns HTTP 403 for GitHub Actions' IP range (confirmed 2026-08-21).
set -euo pipefail

REPO_DIR="/Users/rakesh/Desktop/Calendar"
PYTHON3="/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
GIT="/usr/bin/git"

cd "$REPO_DIR"
"$PYTHON3" scrape_bs_calendar.py --extend -o bikram_sambat_calendar.ics

if ! "$GIT" diff --quiet -- bikram_sambat_calendar.ics; then
  "$GIT" add bikram_sambat_calendar.ics
  "$GIT" commit -m "Update Bikram Sambat calendar"
  "$GIT" push
  echo "Pushed updated calendar."
else
  echo "No changes."
fi
