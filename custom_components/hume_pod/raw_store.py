"""Opt-in CSV log of every raw scale frame and one summary row per weigh-in.

Writes two append-only files under ``config/hume_pod_raw/<entry_id>/``:

- ``packets.csv``: one row per BLE notification frame — known or unknown,
  well-formed or not, duplicate or not — from every weigh-in, including
  sessions that later fail person-matching (those are scientifically
  valuable, e.g. dumbbell-loaded calibration captures).
- ``sessions.csv``: one row per completed weigh-in with the raw hex of each
  frame type, so a whole session can be replayed without the debug log.

Capture is independent of the log level: deleting the debug log changes
nothing. DF ("extended") frames are stored whole and raw because their
payload is not decoded yet; analysis happens later on the accumulated CSV.

Stdlib only, and writes never raise: an I/O problem logs a warning and the
measurement flow carries on.
"""

from __future__ import annotations

from collections.abc import Mapping
import csv
from datetime import UTC, datetime
import json
import logging
import os
import threading
from typing import Any

_LOGGER = logging.getLogger(__name__)

RAW_DIR_NAME = "hume_pod_raw"
PACKETS_FILE = "packets.csv"
SESSIONS_FILE = "sessions.csv"

PACKETS_COLUMNS = (
    "ts_iso",
    "mac",
    "session_id",
    "frame_type",
    "index",
    "length",
    "checksum_ok",
    "frame_hex",
    "decoded_json",
)
SESSIONS_COLUMNS = (
    "ts_iso",
    "mac",
    "session_id",
    "matched_person",
    "match_distance",
    "weight_kg",
    "cf_hex",
    "be_low_hex",
    "be_high_hex",
    "df_00_hex",
    "df_10_hex",
    "df_01_hex",
    "df_11_hex",
)


def utc_now_iso() -> str:
    """Current UTC time as ISO 8601."""
    return datetime.now(UTC).isoformat()


def _cell(value: Any) -> Any:
    """Empty values as empty strings, never 'None'."""
    return "" if value is None else value


def _flag(value: bool | None) -> str:
    return "" if value is None else ("true" if value else "false")


class RawPacketStore:
    """Append-only writer for the raw capture files. One per config entry.

    Files are opened, written, flushed and fsynced per append (a weigh-in is
    only tens of rows), so a crash can lose at most the row being written and
    no file handle is held between weigh-ins. Appends to existing files are
    idempotent: the header is written only when the file is missing or empty.
    """

    def __init__(self, hass: Any, entry_id: str) -> None:
        self._dir = hass.config.path(RAW_DIR_NAME, entry_id)
        self._paths = {
            PACKETS_FILE: os.path.join(self._dir, PACKETS_FILE),
            SESSIONS_FILE: os.path.join(self._dir, SESSIONS_FILE),
        }
        self._columns: dict[str, tuple[str, ...]] = {
            PACKETS_FILE: PACKETS_COLUMNS,
            SESSIONS_FILE: SESSIONS_COLUMNS,
        }
        # Notifications can arrive off the event loop thread.
        self._lock = threading.Lock()

    def append_packet(
        self,
        *,
        ts_iso: str,
        mac: str,
        session_id: str,
        frame_hex: str,
        frame_type: str,
        index: Any,
        length: int,
        checksum_ok: bool | None,
        decoded: Mapping[str, Any] | None,
    ) -> None:
        """Record one raw frame. Unknown frame types are logged whole, never skipped."""
        self._append(
            PACKETS_FILE,
            [
                ts_iso,
                mac,
                session_id,
                frame_type,
                _cell(index),
                length,
                _flag(checksum_ok),
                frame_hex,
                # default=str keeps a stray non-JSON value from ever crashing the
                # measurement flow (real frames only carry numbers/bools/strings).
                json.dumps(dict(decoded), separators=(",", ":"), default=str) if decoded else "",
            ],
        )

    def append_session(
        self,
        *,
        ts_iso: str,
        mac: str,
        session_id: str,
        matched_person: str,
        match_distance: Any,
        weight_kg: float | None,
        cf_hex: str,
        be_low_hex: str,
        be_high_hex: str,
        df_00_hex: str,
        df_10_hex: str,
        df_01_hex: str,
        df_11_hex: str,
    ) -> None:
        """Record one weigh-in summary; hex fields are blank when a frame never arrived."""
        self._append(
            SESSIONS_FILE,
            [
                ts_iso,
                mac,
                session_id,
                matched_person,
                _cell(match_distance),
                _cell(weight_kg),
                cf_hex,
                be_low_hex,
                be_high_hex,
                df_00_hex,
                df_10_hex,
                df_01_hex,
                df_11_hex,
            ],
        )

    def _append(self, filename: str, row: list[Any]) -> None:
        path = self._paths[filename]
        try:
            with self._lock:
                os.makedirs(self._dir, exist_ok=True)
                new_file = not os.path.exists(path) or os.path.getsize(path) == 0
                with open(path, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    if new_file:
                        writer.writerow(self._columns[filename])
                    writer.writerow([_cell(v) for v in row])
                    f.flush()
                    os.fsync(f.fileno())
        except OSError as err:
            _LOGGER.warning("Hume Pod raw capture: couldn't write %s: %s", path, err)
