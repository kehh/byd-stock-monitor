#!/usr/bin/env python3
"""Render history.csv into graph.png and index.html for GitHub Pages."""

from __future__ import annotations

import csv
import html
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent
GRAPH_FILE = BASE_DIR / "graph.png"
INDEX_FILE = BASE_DIR / "index.html"
HISTORY_FILE = BASE_DIR / "history.csv"

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


def render_graph(series: dict[str, tuple[list[str], list[int]]], out_path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 6))
    for i, (label, (timestamps, counts)) in enumerate(sorted(series.items())):
        color = COLORS[i % len(COLORS)]
        ax.plot(range(len(counts)), counts, marker="o", label=label, color=color)
    ax.set_xticks([])
    ax.set_xlabel("Poll over time")
    ax.set_ylabel("Units available")
    ax.set_title("BYD Atto 2 stock over time (by state & variant)")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def render_html(
    series: dict[str, tuple[list[str], list[int]]],
    graph_file: Path,
    out_path: Path,
) -> Path:
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
<style>
body {{ font-family: sans-serif; margin: 2rem auto; max-width: 900px; padding: 0 1rem; }}
h1 {{ font-size: 1.5rem; }}
img {{ max-width: 100%; height: auto; }}
table {{ border-collapse: collapse; margin-top: 1rem; }}
th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.8rem; text-align: left; }}
</style>
</head>
<body>
<h1>BYD Atto 2 Stock Monitor</h1>
<p>Latest counts by state &amp; variant:</p>
<table>
<tr><th>State / Variant</th><th>Latest count</th></tr>
{rows_html}
</table>
<p><img src="{graph_file.name}" alt="BYD Atto 2 stock over time"></p>
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
    render_graph(series, GRAPH_FILE)
    render_html(series, GRAPH_FILE, INDEX_FILE)
    print(f"Rendered {len(series)} series to {GRAPH_FILE.name} and {INDEX_FILE.name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
