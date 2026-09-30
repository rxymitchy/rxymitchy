#!/usr/bin/env python3
"""Draw profile charts from a GitHub contribution calendar JSON file."""

import json
import sys
from datetime import datetime
from pathlib import Path

MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]


def load_calendar(path: Path) -> dict:
    raw = path.read_bytes()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        text = raw.decode("utf-16")
    else:
        text = raw.decode("utf-8-sig")
    payload = json.loads(text)
    return payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def weeks_of(calendar: dict) -> list[dict]:
    rows = []
    for week in calendar["weeks"]:
        days = week["contributionDays"]
        if not days:
            continue
        total = sum(day["contributionCount"] for day in days)
        start = datetime.strptime(days[0]["date"], "%Y-%m-%d")
        rows.append({"total": total, "start": start, "days": days})
    return rows


def level(count: int) -> str:
    if count <= 0:
        return LEVELS[0]
    if count <= 2:
        return LEVELS[1]
    if count <= 6:
        return LEVELS[2]
    if count <= 12:
        return LEVELS[3]
    return LEVELS[4]


def activity_svg(calendar: dict) -> str:
    weeks = weeks_of(calendar)
    width, height = 860, 250
    left, right, top, bottom = 36, 16, 58, 36
    chart_w = width - left - right
    chart_h = height - top - bottom
    peak = max((week["total"] for week in weeks), default=1) or 1
    scale = peak ** 0.5

    def x_at(index: int) -> float:
        if len(weeks) == 1:
            return left + chart_w / 2
        return left + chart_w * index / (len(weeks) - 1)

    def y_at(total: int) -> float:
        return top + chart_h - (chart_h * (total ** 0.5) / scale)

    points = [(x_at(i), y_at(week["total"])) for i, week in enumerate(weeks)]
    baseline = top + chart_h
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    area = f"{points[0][0]:.1f},{baseline:.1f} " + line + f" {points[-1][0]:.1f},{baseline:.1f}"

    labels = []
    seen = set()
    last_label_x = -999.0
    for index, week in enumerate(weeks):
        key = (week["start"].year, week["start"].month)
        if key in seen:
            continue
        x = x_at(index)
        if x - last_label_x < 36:
            continue
        seen.add(key)
        last_label_x = x
        labels.append(
            f'<text x="{x_at(index):.1f}" y="{height - 12}" fill="#8b949e" '
            f'font-size="11" font-family="Segoe UI, Helvetica, Arial, sans-serif">'
            f"{MONTHS[week['start'].month - 1]}</text>"
        )

    dots = []
    for (x, y), week in zip(points, weeks):
        if week["total"] <= 0:
            continue
        dots.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="#3ddc97"/>')

    total = calendar.get("totalContributions", 0)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{total} contributions this year">
  <rect width="100%" height="100%" rx="12" fill="#0d1117"/>
  <text x="{left}" y="28" fill="#3ddc97" font-size="16" font-family="Segoe UI, Helvetica, Arial, sans-serif" font-weight="650">The year, in commits</text>
  <text x="{left}" y="46" fill="#8b949e" font-size="12" font-family="Segoe UI, Helvetica, Arial, sans-serif">{total} public contributions. The hills are the busy weeks.</text>
  <line x1="{left}" y1="{baseline}" x2="{width - right}" y2="{baseline}" stroke="#21262d" stroke-width="1"/>
  <polygon points="{area}" fill="#3ddc97" opacity="0.22"/>
  <polyline points="{line}" fill="none" stroke="#3ddc97" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>
  {"".join(dots)}
  {"".join(labels)}
</svg>
"""


def snake_svg(calendar: dict) -> str:
    weeks = weeks_of(calendar)
    cell, gap = 12, 3
    step = cell + gap
    origin_x, origin_y = 44, 32
    cols = len(weeks)
    width = origin_x + cols * step + 16
    height = origin_y + 7 * step + 28

    squares = []
    centers = {}
    for col, week in enumerate(weeks):
        for row, day in enumerate(week["days"]):
            x = origin_x + col * step
            y = origin_y + row * step
            color = level(day["contributionCount"])
            squares.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{color}">'
                f'<title>{day["date"]}: {day["contributionCount"]}</title></rect>'
            )
            centers[(col, row)] = (x + cell / 2, y + cell / 2)

    month_labels = []
    seen = set()
    last_label_x = -999.0
    for col, week in enumerate(weeks):
        key = (week["start"].year, week["start"].month)
        if key in seen:
            continue
        x = origin_x + col * step
        if x - last_label_x < 36:
            continue
        seen.add(key)
        last_label_x = x
        month_labels.append(
            f'<text x="{origin_x + col * step}" y="18" fill="#8b949e" font-size="11" '
            f'font-family="Segoe UI, Helvetica, Arial, sans-serif">{MONTHS[week["start"].month - 1]}</text>'
        )

    day_labels = []
    for row, name in enumerate(WEEKDAYS):
        if name not in {"Mon", "Wed", "Fri"}:
            continue
        day_labels.append(
            f'<text x="4" y="{origin_y + row * step + 10}" fill="#8b949e" font-size="9" '
            f'font-family="Segoe UI, Helvetica, Arial, sans-serif">{name}</text>'
        )

    path_parts = []
    started = False
    for row in range(7):
        columns = [col for col in range(cols) if (col, row) in centers]
        if row % 2 == 1:
            columns.reverse()
        for col in columns:
            x, y = centers[(col, row)]
            path_parts.append(("M" if not started else "L") + f"{x:.1f},{y:.1f}")
            started = True
    path = " ".join(path_parts)

    snakes = []
    for radius, delay, color, opacity in (
        (3.1, "-0.7s", "#0e4429", "0.95"),
        (3.4, "-0.45s", "#26a641", "0.95"),
        (3.8, "-0.22s", "#3ddc97", "1"),
        (4.4, "0s", "#f0fff4", "1"),
    ):
        snakes.append(
            f'<circle r="{radius}" fill="{color}" opacity="{opacity}">'
            f'<animateMotion dur="18s" begin="{delay}" repeatCount="indefinite" path="{path}"/>'
            f"</circle>"
        )

    legend_x = width - 148
    legend = ['<text x="' + str(legend_x) + '" y="' + str(height - 8) + '" fill="#8b949e" font-size="11" font-family="Segoe UI, Helvetica, Arial, sans-serif">quiet</text>']
    for index, color in enumerate(LEVELS):
        legend.append(
            f'<rect x="{legend_x + 36 + index * 14}" y="{height - 18}" width="11" height="11" rx="2" fill="{color}"/>'
        )
    legend.append(
        f'<text x="{legend_x + 108}" y="{height - 8}" fill="#8b949e" font-size="11" font-family="Segoe UI, Helvetica, Arial, sans-serif">busy</text>'
    )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Contribution grid with a snake">
  <rect width="100%" height="100%" rx="12" fill="#0d1117"/>
  {"".join(month_labels)}
  {"".join(day_labels)}
  {"".join(squares)}
  {"".join(snakes)}
  {"".join(legend)}
</svg>
"""


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: activity_graph.py calendar.json dist/activity.svg dist/contrib-snake.svg")
    calendar = load_calendar(Path(sys.argv[1]))
    for target, drawing in (
        (Path(sys.argv[2]), activity_svg(calendar)),
        (Path(sys.argv[3]), snake_svg(calendar)),
    ):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(drawing, encoding="utf-8")


if __name__ == "__main__":
    main()
