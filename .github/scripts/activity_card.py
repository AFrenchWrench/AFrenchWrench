"""Render a small terminal-style SVG card from the public contribution calendar.

Usage: GITHUB_TOKEN=... GH_LOGIN=AFrenchWrench python3 activity_card.py dist/activity.svg
Stdlib only, so the workflow needs no dependency install.
"""

import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

BG, BORDER = "#0d0f13", "#262b33"
TEXT, MUTED, FAINT, ACCENT = "#eef0f2", "#8a919c", "#5b6169", "#c9a227"
MONO = "ui-monospace,SFMono-Regular,'JetBrains Mono',Consolas,'Liberation Mono',monospace"


def fetch_calendar(login, token, attempts=3):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-activity-card"},
    )
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.load(resp)
            break
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == attempts:
                raise SystemExit(f"GitHub API unreachable after {attempts} attempts: {exc}")
            time.sleep(5 * attempt)

    if payload.get("errors"):
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    user = (payload.get("data") or {}).get("user")
    if user is None:
        raise SystemExit(f"GitHub user {login!r} not found")
    return user["contributionsCollection"]["contributionCalendar"]


def summarize(calendar):
    days = [
        (dt.date.fromisoformat(d["date"]), d["contributionCount"])
        for week in calendar["weeks"]
        for d in week["contributionDays"]
    ]

    longest = run = 0
    for _, count in days:
        run = run + 1 if count else 0
        longest = max(longest, run)

    # An empty "today" shouldn't reset the current streak; the day isn't over yet.
    tail = days[:-1] if days and days[-1][1] == 0 else days
    current = 0
    for _, count in reversed(tail):
        if not count:
            break
        current += 1

    by_weekday = [0] * 7
    for date, count in days:
        by_weekday[date.weekday()] += count
    busiest = dt.date(2024, 1, 1 + by_weekday.index(max(by_weekday))).strftime("%A")

    weekly = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in calendar["weeks"]]

    return {
        "total": calendar["totalContributions"],
        "active": sum(1 for _, c in days if c),
        "longest": longest,
        "current": current,
        "busiest": busiest if any(by_weekday) else "n/a",
        "weekly": weekly[-52:],
    }


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def render(s, today):
    width, pad = 495, 24
    rows = [
        ("contributions", f"{s['total']:,}"),
        ("active days", str(s["active"])),
        ("longest streak", plural(s["longest"], "day")),
        ("current streak", plural(s["current"], "day")),
        ("busiest weekday", s["busiest"]),
    ]
    row_top, row_h = 66, 21
    bars_top = row_top + len(rows) * row_h + 6
    bars_h = 34
    height = bars_top + bars_h + 36

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="GitHub activity for the last year">',
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="12" fill="{BG}" stroke="{BORDER}"/>',
        f'<g font-family="{MONO}" font-size="12.5">',
    ]
    for i in range(3):
        out.append(f'<circle cx="{pad + i * 16}" cy="24" r="4.5" fill="#3a3f47"/>')
    out.append(
        f'<text x="{width / 2:.0f}" y="28" fill="{FAINT}" font-size="11.5" text-anchor="middle">'
        "github activity · last 12 months</text>"
    )
    for i, (label, value) in enumerate(rows):
        y = row_top + i * row_h
        out.append(f'<text x="{pad}" y="{y}" fill="{MUTED}">{escape(label)}</text>')
        out.append(f'<text x="{pad + 150}" y="{y}" fill="{TEXT}">{escape(value)}</text>')

    weekly = s["weekly"]
    peak = max(weekly) or 1
    slot = (width - 2 * pad) / max(len(weekly), 1)
    for i, count in enumerate(weekly):
        h = max(2, round(bars_h * count / peak)) if count else 2
        opacity = "1" if count else "0.25"
        out.append(
            f'<rect x="{pad + i * slot:.1f}" y="{bars_top + bars_h - h}" width="{slot - 2:.1f}" '
            f'height="{h}" rx="1.5" fill="{ACCENT}" opacity="{opacity}"/>'
        )
    out.append(
        f'<text x="{pad}" y="{height - 14}" fill="{FAINT}" font-size="10.5">contributions per week</text>'
        f'<text x="{width - pad}" y="{height - 14}" fill="{FAINT}" font-size="10.5" text-anchor="end">'
        f"updated {today.isoformat()}</text>"
    )
    out.append("</g></svg>")
    return "\n".join(out)


def main():
    dest = sys.argv[1] if len(sys.argv) > 1 else "dist/activity.svg"
    calendar = fetch_calendar(os.environ["GH_LOGIN"], os.environ["GITHUB_TOKEN"])
    svg = render(summarize(calendar), dt.date.today())
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {dest}")


if __name__ == "__main__":
    main()
