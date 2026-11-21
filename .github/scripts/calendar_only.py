"""Keep only the last six months of the 3D calendar from github-profile-3d-contrib output.

The full image also draws a language donut, a commits/issues/PRs radar and a contributions/stars
footer. The profile already shows all of that in other cards, so strip them, drop the solid
background (so it blends with GitHub's light and dark themes), drop the older weeks so the
calendar isn't mostly empty, and crop to what's left.

usage: python3 calendar_only.py <in.svg> <out.svg>
"""
import json
import os
import re
import subprocess
import urllib.request
from collections import Counter
from datetime import date
import sys
import xml.etree.ElementTree as ET

NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)


def fetch_days(weeks):
    """Per-day contribution counts for the same weeks the calendar keeps."""
    token = os.environ.get("GITHUB_TOKEN") or subprocess.run(
        ["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()
    user = os.environ.get("USERNAME", "Chetan-boi")
    query = ('{user(login:"%s"){contributionsCollection{contributionCalendar'
             '{weeks{contributionDays{date contributionCount}}}}}}' % user)
    req = urllib.request.Request("https://api.github.com/graphql", json.dumps({"query": query}).encode(),
                                 {"Authorization": f"bearer {token}"})
    data = json.load(urllib.request.urlopen(req))
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"][-weeks:]
    return [(date.fromisoformat(d["date"]), d["contributionCount"]) for wk in cal for d in wk["contributionDays"]]


def add_corner_stats(root, x, y, w, h):
    """The calendar is a diagonal band, which leaves the top-right and bottom-left corners empty.
    Fill them with numbers no other card on the profile shows."""
    days = fetch_days(WEEKS)
    total = sum(c for _, c in days)
    active = sum(1 for _, c in days if c)
    best_day, best = max(days, key=lambda d: d[1])
    weekday = Counter()
    for d, c in days:
        weekday[d.strftime("%A")] += c
    fav = weekday.most_common(1)[0][0]
    span = f"{days[0][0]:%b %-d} – {days[-1][0]:%b %-d}"

    style = ET.SubElement(root, f"{{{NS}}}style")
    style.text = (
        ".st-t{font:600 15px -apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;fill:#e6edf3}"
        ".st-n{font:600 26px -apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;fill:#3fb950}"
        ".st-l{font:400 13px -apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;fill:#8b949e}"
        "@media (prefers-color-scheme: light){.st-t{fill:#1f2328}.st-n{fill:#1a7f37}.st-l{fill:#59636e}}"
    )

    def text(tx, ty, cls, s, anchor="start"):
        t = ET.SubElement(root, f"{{{NS}}}text", {"x": str(tx), "y": str(ty), "class": cls, "text-anchor": anchor})
        t.text = s

    # Top right: what this is
    r = x + w - 14
    text(r, y + 34, "st-t", "Last 6 months", "end")
    text(r, y + 54, "st-l", span, "end")

    # Bottom left: three numbers, one per column
    cols = [(str(total), "contributions"), (str(active), "active days"), (str(best), f"best day · {best_day:%b %-d}")]
    bx, by = x + 16, y + h - 22
    for i, (n, label) in enumerate(cols):
        cx = bx + i * 96
        text(cx, by - 20, "st-n", n)
        text(cx, by, "st-l", label)
    text(bx, by - 58, "st-l", f"Most active on {fav}s")


src, dst = sys.argv[1], sys.argv[2]
root = ET.parse(src).getroot()

children = list(root)
groups = [c for c in children if c.tag == f"{{{NS}}}g"]
calendar = max(groups, key=lambda g: sum(1 for _ in g.iter()))  # the calendar is by far the largest group

for c in children:
    if c.tag == f"{{{NS}}}style" or c is calendar:
        continue
    root.remove(c)

# Each day is a <g transform="translate(x y)">, oldest first. Within a week x falls by 20 per day,
# so a rise in x marks the start of a new week.
WEEKS = 26
cells = list(calendar)
xs = [float(re.search(r"translate\(([-\d.]+)", c.get("transform")).group(1)) for c in cells]
week_starts = [0] + [i for i in range(1, len(xs)) if xs[i] > xs[i - 1]]
first = week_starts[-WEEKS] if len(week_starts) > WEEKS else 0
for c in cells[:first]:
    calendar.remove(c)

# Crop to the remaining cells, measured from a render, with a margin (bars rise from below when the
# animation starts, so leave a little extra at the bottom).
ET.ElementTree(root).write(dst, encoding="unicode")
png = subprocess.run(["rsvg-convert", dst], capture_output=True, check=True).stdout
bbox = subprocess.run(["convert", "-", "-format", "%@", "info:"], input=png, capture_output=True, check=True).stdout.decode()
w, h, x, y = map(int, re.match(r"(\d+)x(\d+)\+(\d+)\+(\d+)", bbox).groups())
m = 12
x, y, w, h = x - m, y - m, w + 2 * m, h + 2 * m + 8
root.set("viewBox", f"{x} {y} {w} {h}")
add_corner_stats(root, x, y, w, h)
root.set("width", str(w))
root.set("height", str(h))

ET.ElementTree(root).write(dst, encoding="unicode")
print(f"wrote {dst}")
