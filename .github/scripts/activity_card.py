"""Render a small terminal-style SVG card from the public contribution calendar.

Usage: GITHUB_TOKEN=... GH_LOGIN=AFrenchWrench python3 activity_card.py dist/activity.svg
Stdlib only, so the workflow needs no dependency install.
"""

import datetime as dt
import json
import os
import sys
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
# Separate <text> runs placed by an approximate monospace advance, instead of
# <tspan> flow, which some SVG renderers lay out inconsistently.
CHAR_W = 7.6
MONO = "ui-monospace,SFMono-Regular,'JetBrains Mono',Consolas,'Liberation Mono',monospace"


def fetch_calendar(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-activity-card"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]


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
        ("contributions", f"{s['total']:,}", "in the last year"),
        ("active days", str(s["active"]), ""),
        ("longest streak", plural(s["longest"], "day"), ""),
        ("current streak", plural(s["current"], "day"), ""),
        ("busiest day", s["busiest"], ""),
    ]
    row_top, row_h = 72, 21
    bars_top = row_top + len(rows) * row_h + 6
    bars_h = 34
    height = bars_top + bars_h + 36

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="GitHub activity for the last year">',
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="12" fill="{BG}" stroke="{BORDER}"/>',
        f'<g font-family="{MONO}" font-size="12.5">',
    ]
    for i, color in enumerate(("#3a3f47", "#3a3f47", "#3a3f47")):
        out.append(f'<circle cx="{pad + i * 16}" cy="22" r="4.5" fill="{color}"/>')
    out.append(
        f'<text x="{pad}" y="52" fill="{FAINT}">$</text>'
        f'<text x="{pad + CHAR_W * 2}" y="52" fill="{MUTED}">git log --since="1 year ago" | summarize</text>'
    )
    for i, (label, value, note) in enumerate(rows):
        y = row_top + i * row_h
        out.append(f'<text x="{pad}" y="{y}" fill="{MUTED}">{escape(label)}</text>')
        out.append(f'<text x="{pad + 150}" y="{y}" fill="{TEXT}">{escape(value)}</text>')
        if note:
            note_x = pad + 150 + CHAR_W * (len(value) + 1)
            out.append(f'<text x="{note_x:.0f}" y="{y}" fill="{FAINT}">{escape(note)}</text>')

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
        f'<text x="{pad}" y="{height - 14}" fill="{FAINT}" font-size="10.5">52 weeks, one bar each</text>'
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
