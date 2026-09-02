import csv
import tempfile
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


def test_render_graph_creates_png(tmp_path):
    p = write_history(tmp_path, [{"timestamp_utc": "2026-01-01 00:00:00 UTC", "state": "VIC", "variant": "Dynamic", "count": "2", "stock_numbers": "1;2"}])
    series = graph.build_series(graph.load_history(p))
    out = tmp_path / "graph.png"
    result = graph.render_graph(series, out)
    assert result.exists()
    assert result.suffix == ".png"
    assert out.stat().st_size > 0


def test_render_html_embeds_graph(tmp_path):
    p = write_history(tmp_path, [{"timestamp_utc": "2026-01-01 00:00:00 UTC", "state": "VIC", "variant": "Dynamic", "count": "2", "stock_numbers": "1;2"}])
    series = graph.build_series(graph.load_history(p))
    gpath = tmp_path / "graph.png"
    graph.render_graph(series, gpath)
    out = tmp_path / "index.html"
    graph.render_html(series, gpath, out)
    assert out.exists()
    text = out.read_text()
    assert "graph.png" in text
    assert "VIC Dynamic" in text
