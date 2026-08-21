#!/usr/bin/env python3
"""
Scrape HamroPatro.com's calendar pages and generate a Bikram Sambat (B.S.)
date-label .ics calendar for Apple Calendar (macOS / iOS).

Each Gregorian day in the chosen range gets one all-day event whose title is
the equivalent B.S. date (e.g. "5 Bhadra 2083"). No holiday/event names are
included -- this is a pure date-conversion overlay.

Data source: the Next.js RSC JSON payload embedded in
https://www.hamropatro.com/en/calendar/{year_bs}/{month_bs} -- each page load
returns the requested month plus the month before and after it, so a BS year
only needs 4 fetches (months 2, 5, 8, 11) to be fully covered.

robots.txt for hamropatro.com disallows /widgets/, /login, /en/login,
/contest-term-condition, /terms, /privacy, /bookmark, /notes -- /calendar/ is
not disallowed. This script fetches only /en/calendar/{year}/{month} pages,
one request every DELAY_SECONDS, and is intended for light personal use.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "https://www.hamropatro.com/en/calendar/{year}/{month}"
# NOTE: the bare /calendar/{year}/{month} URL (no /en/ prefix) is only served
# directly (HTTP 200) for whichever BS year the site currently treats as
# "current"; every other year 307-redirects to /en/calendar/... anyway. So we
# always request /en/ for consistency. Its Devanagari "Np" numeral fields
# (dayBsNp/yearBsNp) are ASCII digits rather than real Devanagari, so those are
# not used -- Devanagari numerals are generated locally instead (see
# to_devanagari_numerals below). monthNameNp (the Devanagari month name) is
# correct in this locale, so that field is used as-is.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
    "bs-calendar-generator/1.0 (personal use; contact via github repo)"
)
DELAY_SECONDS = 0.5
FETCH_MONTHS = (2, 5, 8, 11)  # each covers (month-1, month, month+1) -> full year in 4 requests
MIN_YEAR_BS, MAX_YEAR_BS = 2000, 2100  # currently available range on hamropatro.com

CHUNK_RE = re.compile(r"self\.__next_f\.push\((\[.*?\])\)</script>", re.S)


def fetch_month_page(year_bs: int, month_bs: int, retries: int = 3) -> str | None:
    url = BASE_URL.format(year=year_bs, month=month_bs)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last_err = e
        except Exception as e:  # noqa: BLE001 - network flakiness, just retry
            last_err = e
        time.sleep(1.5 * (attempt + 1))
    print(f"  warning: giving up on {year_bs}-{month_bs:02d}: {last_err}", file=sys.stderr)
    return None


def extract_balanced(s: str, start_idx: int) -> str | None:
    """Return s[start_idx:end] for the JSON array/object starting at s[start_idx],
    respecting string quoting so brackets inside string values are ignored."""
    depth = 0
    in_str = False
    esc = False
    for i in range(start_idx, len(s)):
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c in "[{":
                depth += 1
            elif c in "]}":
                depth -= 1
                if depth == 0:
                    return s[start_idx : i + 1]
    return None


def extract_months(html: str) -> list[dict]:
    """Pull every 'initialMonths' array out of the page's Next.js RSC payload."""
    months = []
    for raw_chunk in CHUNK_RE.findall(html):
        try:
            parsed = json.loads(raw_chunk)
        except (json.JSONDecodeError, ValueError):
            continue
        if not (isinstance(parsed, list) and len(parsed) == 2 and isinstance(parsed[1], str)):
            continue
        content = parsed[1]
        idx = content.find('"initialMonths":')
        if idx == -1:
            continue
        arr_start = content.find("[", idx)
        arr_text = extract_balanced(content, arr_start)
        if arr_text is None:
            continue
        try:
            months.extend(json.loads(arr_text))
        except json.JSONDecodeError:
            continue
    return months


def scrape_range(year_start: int, year_end: int, cache_dir: Path | None = None) -> dict:
    """Returns dict keyed by (year_ad, month_ad, day_ad) -> BS day record."""
    days_by_ad: dict[tuple[int, int, int], dict] = {}
    for year in range(year_start, year_end + 1):
        if not (MIN_YEAR_BS <= year <= MAX_YEAR_BS):
            print(f"BS {year} is outside hamropatro.com's available range "
                  f"({MIN_YEAR_BS}-{MAX_YEAR_BS}); skipping.", file=sys.stderr)
            continue
        for month in FETCH_MONTHS:
            html = None
            cache_file = cache_dir / f"{year}-{month:02d}.html" if cache_dir else None
            if cache_file and cache_file.exists():
                html = cache_file.read_text(encoding="utf-8")
            if html is None:
                print(f"Fetching BS {year}-{month:02d} ...", file=sys.stderr)
                html = fetch_month_page(year, month)
                if html is None:
                    continue
                if cache_file:
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    cache_file.write_text(html, encoding="utf-8")
                time.sleep(DELAY_SECONDS)

            for m in extract_months(html):
                for d in m["days"]:
                    if not d["inMonth"]:
                        continue
                    key = (d["year_ad"], d["month_ad"], d["day_ad"])
                    days_by_ad[key] = {
                        "year_ad": d["year_ad"],
                        "month_ad": d["month_ad"],
                        "day_ad": d["day_ad"],
                        "year_bs": d["year_bs"],
                        "month_bs": d["month_bs"],
                        "day_bs": d["day_bs"],
                        "month_name_en": m["monthNameEn"],
                        "month_name_np": m["monthNameNp"],
                    }
    return days_by_ad


_DEVANAGARI_DIGITS = "०१२३४५६७८९"


def to_devanagari_numerals(n: int) -> str:
    return "".join(_DEVANAGARI_DIGITS[int(c)] for c in str(n))


def label_for(rec: dict, lang: str) -> str:
    """Month name + year on the 1st of each B.S. month; just the day number
    on every other day (so a day-by-day agenda view reads like a wall
    calendar: a month header, then bare day numbers until the next one)."""
    is_month_start = rec["day_bs"] == 1
    if is_month_start:
        en = f"{rec['month_name_en']} {rec['year_bs']}"
        np = f"{rec['month_name_np']} {to_devanagari_numerals(rec['year_bs'])}"
    else:
        en = str(rec["day_bs"])
        np = to_devanagari_numerals(rec["day_bs"])
    if lang == "en":
        return en
    if lang == "np":
        return np
    return f"{np} ({en})"


def escape_ics_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def fold_line(line: str) -> str:
    """RFC5545 line folding at 75 octets, splitting on UTF-8 byte boundaries."""
    data = line.encode("utf-8")
    if len(data) <= 75:
        return line
    parts = []
    start = 0
    limit = 75
    while start < len(data):
        end = min(start + limit, len(data))
        # don't split in the middle of a UTF-8 multi-byte sequence
        while end < len(data) and (data[end] & 0xC0) == 0x80:
            end -= 1
        parts.append(data[start:end].decode("utf-8"))
        start = end
        limit = 74  # continuation lines start with a space, which counts as 1 octet
    return "\r\n ".join(parts)


def build_ics(days_by_ad: dict, lang: str, calname: str) -> str:
    now_stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//hamropatro-bs-calendar//scrape_bs_calendar.py//EN",
        "CALSCALE:GREGORIAN",
        f"X-WR-CALNAME:{escape_ics_text(calname)}",
        "X-WR-TIMEZONE:UTC",
    ]
    for key in sorted(days_by_ad):
        rec = days_by_ad[key]
        year_ad, month_ad, day_ad = key
        dtstart = f"{year_ad:04d}{month_ad:02d}{day_ad:02d}"
        dtend = (datetime.date(year_ad, month_ad, day_ad) + datetime.timedelta(days=1)).strftime(
            "%Y%m%d"
        )
        summary = escape_ics_text(label_for(rec, lang))
        uid = f"bs-date-{dtstart}@hamropatro-bs-calendar"
        lines.append("BEGIN:VEVENT")
        lines.append(fold_line(f"UID:{uid}"))
        lines.append(f"DTSTAMP:{now_stamp}")
        lines.append(f"DTSTART;VALUE=DATE:{dtstart}")
        lines.append(f"DTEND;VALUE=DATE:{dtend}")
        lines.append(fold_line(f"SUMMARY:{summary}"))
        lines.append("TRANSP:TRANSPARENT")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


SUMMARY_YEAR_RE = re.compile(r"^SUMMARY:.*\s(\d{4})\s*$")


def detect_existing_year_range(ics_path: Path) -> tuple[int, int]:
    """Read an already-generated .ics and return (min_year_bs, max_year_bs)
    found in its SUMMARY lines (lang=en format: '<day> <MonthName> <year>')."""
    years = []
    for line in ics_path.read_text(encoding="utf-8").splitlines():
        m = SUMMARY_YEAR_RE.match(line)
        if m:
            years.append(int(m.group(1)))
    if not years:
        raise ValueError(f"couldn't find any B.S. years in {ics_path}")
    return min(years), max(years)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year-start", type=int, default=2081, help="First B.S. year (default 2081)")
    parser.add_argument("--year-end", type=int, default=2093, help="Last B.S. year (default 2093)")
    parser.add_argument("--lang", choices=["en", "np", "both"], default="en", help="Label language")
    parser.add_argument("-o", "--output", default="bikram_sambat_calendar.ics", help="Output .ics path")
    parser.add_argument("--cache-dir", default=None, help="Optional dir to cache fetched HTML pages")
    parser.add_argument(
        "--calname", default="Bikram Sambat Calendar", help="Calendar display name (X-WR-CALNAME)"
    )
    parser.add_argument(
        "--extend",
        action="store_true",
        help=(
            "Self-update mode: read the existing B.S. year range out of the file at "
            "--output, keep the same start year, and grow the end year by 1 if "
            "hamropatro.com has published a new year. Ignores --year-start/--year-end."
        ),
    )
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir) if args.cache_dir else None

    year_start, year_end = args.year_start, args.year_end
    if args.extend:
        out_path = Path(args.output)
        if not out_path.exists():
            print(f"--extend needs an existing file at {out_path}", file=sys.stderr)
            sys.exit(1)
        year_start, existing_max = detect_existing_year_range(out_path)
        year_end = existing_max
        if fetch_month_page(existing_max + 1, 1) is not None:
            print(f"BS {existing_max + 1} is now available -- extending range.", file=sys.stderr)
            year_end = existing_max + 1

    days_by_ad = scrape_range(year_start, year_end, cache_dir=cache_dir)
    if not days_by_ad:
        print("No data scraped -- aborting without writing a file.", file=sys.stderr)
        sys.exit(1)

    ics_text = build_ics(days_by_ad, args.lang, args.calname)
    out_path = Path(args.output)
    out_path.write_text(ics_text, encoding="utf-8")
    print(
        f"Wrote {len(days_by_ad)} day-events "
        f"({min(days_by_ad):}..{max(days_by_ad):}) to {out_path}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
