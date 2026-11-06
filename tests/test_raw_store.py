"""Tests for the opt-in raw packet/session CSV log (raw_store.py)."""

import csv
import importlib.util
import json
import logging
import pathlib
import sys

import pytest

BASE = pathlib.Path(__file__).parents[1] / "custom_components" / "hume_pod"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, BASE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


raw_store = _load("raw_store")


class _FakeConfig:
    """Just enough of hass.config for RawPacketStore."""

    def __init__(self, root):
        self._root = root

    def path(self, *parts):
        return str(pathlib.Path(self._root).joinpath(*parts))


class _FakeHass:
    def __init__(self, root):
        self.config = _FakeConfig(root)


@pytest.fixture
def store(tmp_path):
    return raw_store.RawPacketStore(_FakeHass(tmp_path), "entry1")


def _dir(tmp_path):
    return pathlib.Path(tmp_path) / "hume_pod_raw" / "entry1"


def packet(**overrides):
    kwargs = {
        "ts_iso": "2026-06-11T07:30:00+00:00",
        "mac": "AA:BB:CC:DD:EE:FF",
        "session_id": "sess1",
        "frame_hex": "cf0000ce18000000010018",
        "frame_type": "cf",
        "index": None,
        "length": 11,
        "checksum_ok": True,
        "decoded": {"weight_kg": 63.5, "stable": True},
    }
    kwargs.update(overrides)
    return kwargs


def session(**overrides):
    kwargs = {
        "ts_iso": "2026-06-11T07:30:10+00:00",
        "mac": "AA:BB:CC:DD:EE:FF",
        "session_id": "sess1",
        "matched_person": "Dan",
        "match_distance": 0.12,
        "weight_kg": 93.6,
        "cf_hex": "cf0000ce18000000010018",
        "be_low_hex": "be00ed0cbd0c0e0103091109 00".replace(" ", ""),
        "be_high_hex": "",
        "df_00_hex": "dfabc00000",
        "df_10_hex": "",
        "df_01_hex": "",
        "df_11_hex": "",
    }
    kwargs.update(overrides)
    return kwargs


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_header_written_once_across_restarts(tmp_path):
    first = raw_store.RawPacketStore(_FakeHass(tmp_path), "entry1")
    first.append_packet(**packet())
    # A reload (options toggled, HA restarted) builds a new store; it must
    # append to the file without duplicating the header.
    second = raw_store.RawPacketStore(_FakeHass(tmp_path), "entry1")
    second.append_packet(**packet(frame_hex="cf0000ab1800000001017c"))
    lines = (_dir(tmp_path) / "packets.csv").read_text().splitlines()
    assert lines[0].split(",") == list(raw_store.PACKETS_COLUMNS)
    assert sum(line.startswith("ts_iso,") for line in lines) == 1
    assert len(lines) == 3


def test_known_frame_values(store, tmp_path):
    store.append_packet(**packet())
    (row,) = rows(_dir(tmp_path) / "packets.csv")
    assert row["ts_iso"] == "2026-06-11T07:30:00+00:00"
    assert row["mac"] == "AA:BB:CC:DD:EE:FF"
    assert row["session_id"] == "sess1"
    assert row["frame_type"] == "cf"
    assert row["length"] == "11"
    assert row["checksum_ok"] == "true"
    assert row["frame_hex"] == "cf0000ce18000000010018"
    assert json.loads(row["decoded_json"]) == {"weight_kg": 63.5, "stable": True}
    # Empty values are blank, never the string "None".
    assert row["index"] == ""
    assert "None" not in row.values()


def test_unknown_and_malformed_frames_are_stored(store, tmp_path):
    store.append_packet(
        **packet(
            frame_hex="ab12ff",
            frame_type="ab",
            length=3,
            checksum_ok=False,
            decoded=None,
        )
    )
    store.append_packet(
        **packet(
            frame_hex="be00ed", frame_type="be", index=0, length=3, checksum_ok=False, decoded=None
        )
    )
    got = rows(_dir(tmp_path) / "packets.csv")
    assert [r["frame_type"] for r in got] == ["ab", "be"]
    assert [r["frame_hex"] for r in got] == ["ab12ff", "be00ed"]
    assert [r["checksum_ok"] for r in got] == ["false", "false"]
    assert [r["decoded_json"] for r in got] == ["", ""]


def test_checksum_not_available_is_blank(store, tmp_path):
    store.append_packet(**packet(frame_type="adv", checksum_ok=None, decoded={"rssi": -70}))
    (row,) = rows(_dir(tmp_path) / "packets.csv")
    assert row["checksum_ok"] == ""
    assert json.loads(row["decoded_json"]) == {"rssi": -70}


def test_session_summary_row(store, tmp_path):
    store.append_session(**session())
    (row,) = rows(_dir(tmp_path) / "sessions.csv")
    assert row["session_id"] == "sess1"
    assert row["matched_person"] == "Dan"
    assert row["weight_kg"] == "93.6"
    assert row["be_low_hex"] == "be00ed0cbd0c0e010309110900"
    assert row["be_high_hex"] == ""
    assert row["df_10_hex"] == ""


def test_unmatched_session_keeps_match_info(store, tmp_path):
    store.append_session(**session(matched_person="", match_distance=2.75))
    (row,) = rows(_dir(tmp_path) / "sessions.csv")
    assert row["matched_person"] == ""
    assert row["match_distance"] == "2.75"
    assert row["cf_hex"] == "cf0000ce18000000010018"


def test_io_error_is_swallowed(store, tmp_path, caplog):
    dest = _dir(tmp_path)
    dest.mkdir(parents=True)
    (dest / "packets.csv").mkdir()  # a directory where the file should be
    with caplog.at_level(logging.WARNING):
        store.append_packet(**packet())  # must not raise
        store.append_session(**session())
    assert "couldn't write" in caplog.text
    # The other file is unaffected: one bad path doesn't stop capture.
    assert (dest / "sessions.csv").exists()
    assert len(rows(dest / "sessions.csv")) == 1
