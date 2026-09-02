#!/usr/bin/env python3
"""Render history.csv into an interactive index.html for GitHub Pages."""

from __future__ import annotations

import csv
import html
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"
HISTORY_FILE = BASE_DIR / "history.csv"

PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.35.2.min.js"

COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    "#393b79", "#9c9ede",
]


def load_history(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def build_series(rows: list[dict]) -> dict[str, tuple[list[str], list[int]]]:
    series: dict[str, tuple[list[str], list[int]]] = {}
    for r in rows:
        key = f"{r['state']} {r['variant']}"
        if key not in series:
            series[key] = ([], [])
        series[key][0].append(r["timestamp_utc"])
        series[key][1].append(int(r["count"]))
    return series


def to_iso(timestamp_utc: str) -> str:
    """Convert 'YYYY-MM-DD HH:MM:SS UTC' to 'YYYY-MM-DDTHH:MM:SSZ'."""
    date_part, time_part = timestamp_utc.split(" ", maxsplit=1)
    return f"{date_part}T{time_part.split(' UTC')[0]}Z"


def series_to_traces(series: dict[str, tuple[list[str], list[int]]]) -> list[dict]:
    traces = []
    for i, (label, (timestamps, counts)) in enumerate(sorted(series.items())):
        traces.append(
            {
                "name": label,
                "x": [to_iso(ts) for ts in timestamps],
                "y": counts,
                "mode": "lines+markers",
                "line": {"width": 2},
                "marker": {"size": 6},
                "color": COLORS[i % len(COLORS)],
            }
        )
    return traces


def render_html(
    series: dict[str, tuple[list[str], list[int]]],
    out_path: Path,
) -> Path:
    traces = series_to_traces(series)
    traces_json = json.dumps(traces)
    rows_html = "".join(
        f"<tr><td>{html.escape(label)}</td><td>{counts[-1] if counts else 0}</td></tr>"
        for label, (_, counts) in sorted(series.items())
    )
    content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BYD Atto 2 Stock Monitor</title>
<script src="{PLOTLY_CDN}"></script>
<style>
body {{ font-family: sans-serif; margin: 2rem auto; max-width: 1000px; padding: 0 1rem; }}
h1 {{ font-size: 1.5rem; }}
h2 {{ font-size: 1.1rem; }}
table {{ border-collapse: collapse; margin-top: 1rem; }}
th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.8rem; text-align: left; }}
</style>
</head>
<body>
<h1>BYD Atto 2 Stock Monitor</h1>
<p>Click a legend entry to show or hide that series. Hover over points
for details. Times are UTC.</p>
<div id="chart"></div>
<h2>Latest counts by state &amp; variant:</h2>
<table>
<tr><th>State / Variant</th><th>Latest count</th></tr>
{rows_html}
</table>
<script>
const TRACES = {traces_json};
Plotly.newPlot("chart", TRACES, {{
  xaxis: {{ title: "Date (UTC)" }},
  yaxis: {{ title: "Units available" }},
  legend: {{ orientation: "h", y: -0.2 }},
  margin: {{ t: 20, r: 20, b: 50, l: 60 }},
}});
</script>
</body>
</html>
"""
    out_path.write_text(content)
    return out_path


def main() -> int:
    if not HISTORY_FILE.exists():
        print("No history.csv yet; nothing to render.", flush=True)
        return 0
    rows = load_history(HISTORY_FILE)
    series = build_series(rows)
    render_html(series, INDEX_FILE)
    print(f"Rendered {len(series)} series to {INDEX_FILE.name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
