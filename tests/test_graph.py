import csv
import json

import graph


def write_history(tmp_path, rows):
    p = tmp_path / "history.csv"
    fieldnames = ["timestamp_utc", "state", "model", "variant", "colour", "count", "stock_numbers"]
    with p.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return p


EXAMPLE_ROWS = [
    {"timestamp_utc": "2026-01-01 00:00:00 UTC", "state": "VIC", "model": "Atto 2",
     "variant": "Dynamic", "colour": "Thaumas Black", "count": "2", "stock_numbers": "1;2"},
    {"timestamp_utc": "2026-01-01 00:00:00 UTC", "state": "WA", "model": "Atto 2",
     "variant": "Premium", "colour": "Aurora White", "count": "1", "stock_numbers": "3"},
    {"timestamp_utc": "2026-01-01 00:00:00 UTC", "state": "VIC", "model": "Sealion 8",
     "variant": "Premium", "colour": "Cosmos Black", "count": "4", "stock_numbers": "4;5;6;7"},
    {"timestamp_utc": "2026-01-01 00:10:00 UTC", "state": "VIC", "model": "Atto 2",
     "variant": "Dynamic", "colour": "Thaumas Black", "count": "3", "stock_numbers": "1;2;8"},
    {"timestamp_utc": "2026-01-01 00:10:00 UTC", "state": "WA", "model": "Atto 2",
     "variant": "Dynamic", "colour": "Thaumas Black", "count": "2", "stock_numbers": "9;10"},
]


def test_load_history_new_schema(tmp_path):
    p = write_history(tmp_path, EXAMPLE_ROWS)
    rows = graph.load_history(p)
    assert len(rows) == 5
    assert "model" in rows[0]


def test_load_history_rejects_old_schema(tmp_path):
    p = tmp_path / "history.csv"
    with p.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp_utc", "state", "variant", "count", "stock_numbers"])
        writer.writeheader()
        writer.writerow({"timestamp_utc": "2026-01-01 00:00:00 UTC", "state": "VIC",
                         "variant": "Dynamic", "count": "1", "stock_numbers": "1"})
    assert graph.load_history(p) == []


def test_latest_timestamp_returns_max(tmp_path):
    rows = graph.load_history(write_history(tmp_path, EXAMPLE_ROWS))
    assert graph.latest_timestamp(rows) == "2026-01-01 00:10:00 UTC"


def test_colour_snapshot_filters_to_latest_ts_and_model(tmp_path):
    rows = graph.load_history(write_history(tmp_path, EXAMPLE_ROWS))
    snap = graph.colour_snapshot(rows, "Atto 2", "2026-01-01 00:10:00 UTC")
    assert snap == {"Thaumas Black": 5}


def test_variant_series_sums_cells_per_poll(tmp_path):
    rows = graph.load_history(write_history(tmp_path, EXAMPLE_ROWS))
    series = graph.variant_series(rows, "Atto 2")
    assert series["Dynamic"][0] == ["2026-01-01 00:00:00 UTC", "2026-01-01 00:10:00 UTC"]
    assert series["Dynamic"][1] == [2, 5]


def test_per_state_counts_latest_only(tmp_path):
    rows = graph.load_history(write_history(tmp_path, EXAMPLE_ROWS))
    counts = graph.per_state_counts(rows, "Atto 2", "2026-01-01 00:10:00 UTC")
    assert counts == {"VIC": 3, "WA": 2}


def test_series_to_traces_uses_dates_on_x_axis():
    series = {
        "VIC Dynamic": (["2026-01-01 00:00:00 UTC", "2026-01-02 05:30:00 UTC"], [2, 3]),
    }
    traces = graph.series_to_traces(series)
    assert traces[0]["name"] == "VIC Dynamic"
    assert traces[0]["x"] == ["2026-01-01T00:00:00Z", "2026-01-02T05:30:00Z"]
    assert traces[0]["y"] == [2, 3]


def test_render_html_embeds_dashboard_data(tmp_path):
    p = write_history(tmp_path, EXAMPLE_ROWS)
    rows = graph.load_history(p)
    out = tmp_path / "index.html"
    graph.render_html(rows, out)
    text = out.read_text()
    assert "tailwindcss" in text.lower()
    assert "alpine" in text.lower()
    assert "plotly" in text.lower()
    assert "const MODELS = " in text
    data = json.loads(text.split("const MODELS = ")[1].split(";")[0])
    assert set(data["models"]) == {"Atto 2", "Sealion 8"}
    assert data["snapshots"]["Atto 2"] == {"Thaumas Black": 5}
    assert data["timeseries"]["Atto 2"]["Dynamic"] == {
        "dates": ["2026-01-01T00:00:00Z", "2026-01-01T00:10:00Z"],
        "counts": [2, 5],
    }
    assert data["per_state"]["Atto 2"] == {"VIC": 3, "WA": 2}
    assert "graph.png" not in text


def test_render_html_empty_state(tmp_path):
    out = tmp_path / "index.html"
    graph.render_html([], out)
    assert out.exists()
    assert "No data" in out.read_text()
