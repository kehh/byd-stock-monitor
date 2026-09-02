#!/usr/bin/env python3
"""Render history.csv into an interactive index.html for GitHub Pages."""

from __future__ import annotations

import csv
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "index.html"
HISTORY_FILE = BASE_DIR / "history.csv"
DATA_FILE = BASE_DIR / "data.json"

PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.35.2.min.js"

COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    "#393b79", "#9c9ede",
]


def load_history(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    if rows and "model" not in rows[0]:
        return []  # old schema
    return rows


def latest_timestamp(rows: list[dict]) -> str:
    return max(r["timestamp_utc"] for r in rows)


def variant_series(rows: list[dict], model: str) -> dict[str, tuple[list[str], list[int]]]:
    points: dict[str, dict[str, int]] = {}
    for r in rows:
        if r["model"] != model:
            continue
        bucket = points.setdefault(r["variant"], {})
        bucket[r["timestamp_utc"]] = bucket.get(r["timestamp_utc"], 0) + int(r["count"])
    series: dict[str, tuple[list[str], list[int]]] = {}
    for variant, ts_counts in points.items():
        ordered = sorted(ts_counts.items())
        series[variant] = ([ts for ts, _ in ordered], [c for _, c in ordered])
    return series


def per_state_counts(rows: list[dict], model: str, ts: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in rows:
        if r["timestamp_utc"] == ts and r["model"] == model:
            counts[r["state"]] = counts.get(r["state"], 0) + int(r["count"])
    return counts


def series_by_state(rows: list[dict], model: str) -> dict[str, dict[str, tuple[list[str], list[int]]]]:
    buckets: dict[str, dict[str, dict[str, int]]] = {}
    for r in rows:
        if r["model"] != model:
            continue
        state_points = buckets.setdefault(r["state"], {})
        variant_points = state_points.setdefault(r["variant"], {})
        variant_points[r["timestamp_utc"]] = variant_points.get(r["timestamp_utc"], 0) + int(r["count"])
    result: dict[str, dict[str, tuple[list[str], list[int]]]] = {}
    for state, state_points in buckets.items():
        series: dict[str, tuple[list[str], list[int]]] = {}
        for variant, ts_counts in state_points.items():
            ordered = sorted(ts_counts.items())
            series[variant] = ([ts for ts, _ in ordered], [c for _, c in ordered])
        result[state] = series
    return result


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


def _build_dashboard_data(rows: list[dict]) -> dict:
    ts = latest_timestamp(rows)
    models = sorted({r["model"] for r in rows})
    timeseries = {}
    for m in models:
        ts_series = {}
        for variant, (dates, counts) in variant_series(rows, m).items():
            ts_series[variant] = {
                "dates": [to_iso(d) for d in dates],
                "counts": counts,
            }
        timeseries[m] = ts_series
    per_state = {m: per_state_counts(rows, m, ts) for m in models}
    per_model_series = {}
    for m in models:
        m_series: dict[str, dict[str, dict]] = {}
        for state, state_series in series_by_state(rows, m).items():
            m_series[state] = {
                variant: {
                    "dates": [to_iso(d) for d in dates],
                    "counts": counts,
                }
                for variant, (dates, counts) in state_series.items()
            }
        per_model_series[m] = m_series
    states = sorted({r["state"] for r in rows})
    return {
        "models": models,
        "latest_ts": ts,
        "timeseries": timeseries,
        "per_state": per_state,
        "series_by_state": per_model_series,
        "states": states,
    }


def write_data_json(rows: list[dict], out_path: Path) -> dict:
    if not rows:
        out_path.write_text("{}")
        return {}
    data = _build_dashboard_data(rows)
    out_path.write_text(json.dumps(data))
    return data


TAILWIND_CDN = "https://cdn.tailwindcss.com"
ALPINE_CDN = "https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js"


def render_html(rows: list[dict], out_path: Path) -> Path:
    if not rows:
        out_path.write_text(
            "<!DOCTYPE html>\n<html><body><h1>BYD Stock Monitor</h1>"
            "<p>No data yet.</p></body></html>\n"
        )
        return out_path

    data = _build_dashboard_data(rows)
    data_json = json.dumps(data)
    first_model = data["models"][0]

    content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BYD Stock Monitor</title>
<script src="{TAILWIND_CDN}"></script>
<script src="{PLOTLY_CDN}"></script>
<script src="{ALPINE_CDN}" defer></script>
</head>
<body class="bg-slate-100 text-slate-800" x-data="dashboard()" x-init="init()">
<header class="bg-white border-b border-slate-200">
  <div class="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between">
    <div>
      <h1 class="text-2xl font-bold">BYD Stock Monitor</h1>
      <p class="text-sm text-slate-500">Australian dealership inventory by model, variant &amp; colour. Times shown in your local timezone.</p>
    </div>
    <div class="text-right text-sm text-slate-500" x-text="'Latest poll: ' + latestDisplay"></div>
  </div>
  <nav class="max-w-5xl mx-auto px-6 pb-3 flex flex-wrap gap-2">
    <template x-for="m in model.models" :key="m">
      <button
        type="button"
        class="px-4 py-1.5 rounded-full text-sm font-medium transition"
        :class="selected === m ? 'bg-sky-600 text-white shadow' : 'bg-slate-200 text-slate-700 hover:bg-slate-300'"
        x-text="m"
        @click="select(m)"></button>
    </template>
  </nav>
</header>

<main class="max-w-5xl mx-auto px-6 py-6 space-y-6">
  <section class="bg-white rounded-xl shadow-sm p-6">
    <div class="flex items-center justify-between mb-1">
      <h2 class="text-lg font-semibold" x-text="selected + ' — units over time'"></h2>
    </div>
    <p class="text-sm text-slate-500 mb-4">Click a legend entry to show or hide that variant. Filter the lines by state with the pills below; picking a new model resets to all states.</p>
    <div class="flex flex-wrap gap-2 mb-4">
      <template x-for="s in model.states" :key="s">
        <button
          type="button"
          class="px-3 py-1 rounded-full text-xs font-medium transition"
          :class="seriesState === s ? 'bg-sky-600 text-white shadow' : 'bg-slate-200 text-slate-600 hover:bg-slate-300'"
          x-text="s"
          @click="setState(s)"></button>
      </template>
    </div>
    <div id="seriesChart" class="h-80"></div>
  </section>

  <section class="bg-white rounded-xl shadow-sm p-6">
    <h2 class="text-lg font-semibold mb-4" x-text="selected + ' — counts by state'"></h2>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
      <template x-for="(count, state) in stateCounts" :key="state">
        <div class="bg-slate-50 rounded-lg p-3 border border-slate-200">
          <div class="text-sm text-slate-500" x-text="state"></div>
          <div class="text-2xl font-semibold" x-text="count"></div>
        </div>
      </template>
      <div x-show="Object.keys(stateCounts).length === 0" class="col-span-full text-slate-400 text-sm">No state counts yet.</div>
    </div>
  </section>
</main>

<script>
const MODELS = {data_json};
const REFRESH_MS = 60000;

function toLocal(iso) {{
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) + "T" + pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
}}

function dashboard() {{
  return {{
    selected: null,
    seriesState: "All states",
    model: MODELS,
    get stateCounts() {{ return this.model.per_state[this.selected] || {{}}; }},
    get latestDisplay() {{
      if (!this.model.latest_ts) return "—";
      const iso = this.model.latest_ts.replace(" UTC", "Z");
      return new Date(iso).toLocaleString();
    }},
    init() {{
      const params = new URLSearchParams(location.hash.slice(1));
      this.selected = MODELS.models.includes(params.get("model")) ? params.get("model") : MODELS.models[0];
      this.seriesState = MODELS.states.includes(params.get("state")) ? params.get("state") : "All states";
      this.renderSeries();
      this.syncHash();
      setInterval(() => this.refresh(), REFRESH_MS);
    }},
    syncHash() {{
      const params = new URLSearchParams();
      params.set("model", this.selected);
      if (this.seriesState !== "All states") params.set("state", this.seriesState);
      history.replaceState(null, "", "#" + params.toString());
    }},
    select(name) {{
      this.selected = name;
      this.seriesState = "All states";
      this.syncHash();
      this.renderSeries();
    }},
    setState(s) {{
      this.seriesState = s;
      this.syncHash();
      this.renderSeries();
    }},
    async refresh() {{
      try {{
        const res = await fetch("data.json?t=" + Date.now(), {{ cache: "no-store" }});
        if (!res.ok) return;
        const fresh = await res.json();
        this.model = fresh;
        if (!fresh.states.includes(this.seriesState)) this.seriesState = "All states";
        if (!fresh.models.includes(this.selected)) this.selected = fresh.models[0];
        this.syncHash();
        this.renderSeries();
      }} catch (e) {{ /* keep current view on network error */ }}
    }},
    renderSeries() {{
      const name = this.selected;
      const ts = this.seriesState === "All states"
        ? this.model.timeseries[name] || {{}}
        : (this.model.series_by_state[name] || {{}})[this.seriesState] || {{}};
      const traces = Object.entries(ts).map(([variant, {{dates, counts}}], i) => ({{
        name: variant,
        x: dates.map(toLocal),
        y: counts,
        mode: "lines+markers",
        line: {{ width: 2 }},
        marker: {{ size: 6 }},
        color: ["#0ea5e9", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#14b8a6"][i % 6],
      }}));
      Plotly.react("seriesChart", traces, {{
        xaxis: {{ title: "Time (local)", type: "date" }},
        yaxis: {{ title: "Units available" }},
        legend: {{ orientation: "h", y: -0.25 }},
        margin: {{ t: 10, r: 10, b: 50, l: 50 }},
      }});
    }},
  }};
}}
</script>
</body>
</html>
"""
    out_path.write_text(content)
    return out_path


def main() -> int:
    rows = load_history(HISTORY_FILE)
    if not rows:
        print("No valid history yet; rendering empty state.", flush=True)
        render_html([], INDEX_FILE)
        write_data_json([], DATA_FILE)
        return 0
    data = _build_dashboard_data(rows)
    render_html(rows, INDEX_FILE)
    write_data_json(rows, DATA_FILE)
    n_models = len(data["models"])
    print(f"Rendered dashboard ({n_models} models) to {INDEX_FILE.name} and {DATA_FILE.name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
