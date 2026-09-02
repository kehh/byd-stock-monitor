import csv

import monitor


def sample_cards():
    return [
        {
            "stock_number": "1001", "title": "BYD ATTO 2", "variant": "Dynamic",
            "price": None, "location": None, "year": None, "status": "available",
            "model": "Atto 2", "colour": "Thaumas Black",
            "state": ["do-allmodel", "do-atto-2", "do-vic", "do-dynamic",
                      "do-thaumasblack", "do-available-now"],
        },
        {
            "stock_number": "1002", "title": "BYD ATTO 2", "variant": "Dynamic",
            "price": None, "location": None, "year": None, "status": "in-transit",
            "model": "Atto 2", "colour": "Aurora White",
            "state": ["do-allmodel", "do-atto-2", "do-wa", "do-dynamic",
                      "do-aurorawhite", "do-in-transit"],
        },
        {
            "stock_number": "1003", "title": "BYD ATTO 2", "variant": "Premium",
            "price": None, "location": None, "year": None, "status": "available",
            "model": "Atto 2", "colour": "Thaumas Black",
            "state": ["do-allmodel", "do-atto-2", "do-wa", "do-premium",
                      "do-thaumasblack", "do-available-now"],
        },
    ]


def test_variant_of_labels():
    dyn = sample_cards()[0]
    assert monitor.variant_of(dyn) == "Dynamic"
    prem = sample_cards()[2]
    assert monitor.variant_of(prem) == "Premium"


def test_collect_counts_keys_cells_by_state_model_variant_colour():
    cells = monitor.collect_counts(sample_cards())
    assert ("VIC", "Atto 2", "Dynamic", "Thaumas Black") in cells
    assert cells[("VIC", "Atto 2", "Dynamic", "Thaumas Black")] == ["1001"]
    assert cells[("WA", "Atto 2", "Dynamic", "Aurora White")] == ["1002"]
    assert cells[("WA", "Atto 2", "Premium", "Thaumas Black")] == ["1003"]


def test_collect_counts_skips_invalid_cards():
    bad = {
        "stock_number": None, "title": "BYD ATTO 2", "variant": "Dynamic",
        "price": None, "location": None, "year": None, "status": "available",
        "model": "Atto 2", "colour": "Black",
        "state": ["do-allmodel", "do-atto-2", "do-vic", "do-dynamic"],
    }
    assert monitor.collect_counts([bad]) == {}


def test_append_history_writes_rows(monkeypatch, tmp_path):
    monkeypatch.setattr(monitor, "HISTORY_FILE", tmp_path / "history.csv")
    rows = monitor.append_history(sample_cards(), timestamp="2026-01-01 00:00:00 UTC")
    assert rows == 3

    with monitor.HISTORY_FILE.open(newline="") as f:
        data = list(csv.DictReader(f))
    assert data[0]["state"] == "VIC"
    assert data[0]["model"] == "Atto 2"
    assert data[0]["variant"] == "Dynamic"
    assert data[0]["colour"] == "Thaumas Black"
    assert data[0]["count"] == "1"
    assert data[0]["stock_numbers"] == "1001"
    assert data[0]["timestamp_utc"] == "2026-01-01 00:00:00 UTC"
    # WA has two distinct cells -> two rows
    wa_rows = [r for r in data if r["state"] == "WA"]
    assert len(wa_rows) == 2


def test_append_history_appends_not_overwrites(monkeypatch, tmp_path):
    monkeypatch.setattr(monitor, "HISTORY_FILE", tmp_path / "history.csv")
    monitor.append_history(sample_cards(), timestamp="2026-01-01 00:00:00 UTC")
    monitor.append_history(sample_cards(), timestamp="2026-01-01 00:05:00 UTC")
    with monitor.HISTORY_FILE.open(newline="") as f:
        data = list(csv.DictReader(f))
    assert len(data) == 6
    assert data[3]["timestamp_utc"] == "2026-01-01 00:05:00 UTC"


def test_header_includes_model_and_colour(monkeypatch, tmp_path):
    monkeypatch.setattr(monitor, "HISTORY_FILE", tmp_path / "history.csv")
    monitor.append_history(sample_cards(), timestamp="2026-01-01 00:00:00 UTC")
    with monitor.HISTORY_FILE.open(newline="") as f:
        reader = csv.DictReader(f)
        assert "model" in reader.fieldnames
        assert "colour" in reader.fieldnames
