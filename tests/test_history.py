import csv
import tempfile
from pathlib import Path

import monitor


def sample_cards():
    return [
        {
            "stock_number": "1001", "title": "BYD ATTO 2",
            "variant": "Dynamic", "price": None, "location": None,
            "year": None, "status": "available",
            "state": ["do-allmodel", "do-atto-2", "do-vic", "do-dynamic", "do-available-now"],
        },
        {
            "stock_number": "1002", "title": "BYD ATTO 2",
            "variant": "Dynamic", "price": None, "location": None,
            "year": None, "status": "in-transit",
            "state": ["do-allmodel", "do-atto-2", "do-wa", "do-dynamic", "do-in-transit"],
        },
        {
            "stock_number": "1003", "title": "BYD ATTO 2",
            "variant": "Premium", "price": None, "location": None,
            "year": None, "status": "available",
            "state": ["do-allmodel", "do-atto-2", "do-wa", "do-premium", "do-available-now"],
        },
    ]


def test_variant_of_labels():
    dyn = sample_cards()[0]
    assert monitor.variant_of(dyn) == "Dynamic"
    prem = sample_cards()[2]
    assert monitor.variant_of(prem) == "Premium"


def test_append_history_writes_rows(monkeypatch, tmp_path):
    monkeypatch.setattr(monitor, "HISTORY_FILE", tmp_path / "history.csv")
    counts = monitor.count_by_state(sample_cards())
    rows = monitor.append_history(sample_cards(), counts)
    assert rows == 3  # VIC/Dynamic, WA/Dynamic, WA/Premium

    with monitor.HISTORY_FILE.open(newline="") as f:
        data = list(csv.DictReader(f))
    assert data[0]["state"] == "VIC"
    assert data[0]["variant"] == "Dynamic"
    assert data[0]["count"] == "1"
    assert data[0]["stock_numbers"] == "1001"
    assert data[0]["timestamp_utc"].endswith("UTC")
    # WA has two variants -> two rows
    wa_rows = [r for r in data if r["state"] == "WA"]
    assert len(wa_rows) == 2


def test_append_history_appends_not_overwrites(monkeypatch, tmp_path):
    monkeypatch.setattr(monitor, "HISTORY_FILE", tmp_path / "history.csv")
    counts = monitor.count_by_state(sample_cards())
    monitor.append_history(sample_cards(), counts, timestamp="2026-01-01 00:00:00 UTC")
    monitor.append_history(sample_cards(), counts, timestamp="2026-01-01 00:05:00 UTC")
    with monitor.HISTORY_FILE.open(newline="") as f:
        data = list(csv.DictReader(f))
    assert len(data) == 6
    assert data[3]["timestamp_utc"] == "2026-01-01 00:05:00 UTC"