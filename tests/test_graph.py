import csv
import json
from pathlib import Path

import graph


def write_history(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "history.csv"
    fieldnames = ["timestamp_utc", "state", "variant", "count", "stock_numbers"]
    with p.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return p


def test_build_series_groups_by_state_variant(tmp_path):
    p = write_history(
        tmp_path,
        [
            {"timestamp_utc": "2026-01-01 00:00:00 UTC", "state": "VIC", "variant": "Dynamic", "count": "2", "stock_numbers": "1;2"},
            {"timestamp_utc": "2026-01-01 00:00:00 UTC", "state": "WA", "variant": "Premium", "count": "1", "stock_numbers": "3"},
            {"timestamp_utc": "2026-01-01 00:10:00 UTC", "state": "VIC", "variant": "Dynamic", "count": "3", "stock_numbers": "1;2;4"},
        ],
    )
    rows = graph.load_history(p)
    series = graph.build_series(rows)
    assert "VIC Dynamic" in series
    assert "WA Premium" in series
    vic = series["VIC Dynamic"]
    assert vic[0] == ["2026-01-01 00:00:00 UTC", "2026-01-01 00:10:00 UTC"]
    assert vic[1] == [2, 3]


def test_series_to_traces_uses_dates_on_x_axis():
    series = {
        "VIC Dynamic": (["2026-01-01 00:00:00 UTC", "2026-01-02 05:30:00 UTC"], [2, 3]),
    }
    traces = graph.series_to_traces(series)
    assert len(traces) == 1
    trace = traces[0]
    assert trace["name"] == "VIC Dynamic"
    assert trace["x"] == ["2026-01-01T00:00:00Z", "2026-01-02T05:30:00Z"]
    assert trace["y"] == [2, 3]


def test_render_html_embeds_plotly_chart(tmp_path):
    p = write_history(tmp_path, [{"timestamp_utc": "2026-01-01 00:00:00 UTC", "state": "VIC", "variant": "Dynamic", "count": "2", "stock_numbers": "1;2"}])
    series = graph.build_series(graph.load_history(p))
    out = tmp_path / "index.html"
    graph.render_html(series, out)
    assert out.exists()
    text = out.read_text()
    assert "plotly" in text.lower()
    assert "VIC Dynamic" in text
    assert "graph.png" not in text


def test_render_html_data_matches_series(tmp_path):
    p = write_history(
        tmp_path,
        [
            {"timestamp_utc": "2026-01-01 00:00:00 UTC", "state": "VIC", "variant": "Dynamic", "count": "2", "stock_numbers": "1;2"},
            {"timestamp_utc": "2026-01-01 00:00:00 UTC", "state": "QLD", "variant": "Premium", "count": "5", "stock_numbers": "3"},
        ],
    )
    series = graph.build_series(graph.load_history(p))
    out = tmp_path / "index.html"
    graph.render_html(series, out)
    text = out.read_text()
    traces = json.loads(text.split("const TRACES = ")[1].split(";")[0])
    assert {t["name"] for t in traces} == {"VIC Dynamic", "QLD Premium"}
    vic = next(t for t in traces if t["name"] == "VIC Dynamic")
    assert vic["y"] == [2]
    assert vic["x"] == ["2026-01-01T00:00:00Z"]
