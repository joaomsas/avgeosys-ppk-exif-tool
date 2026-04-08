"""
Position interpolation: MRK timestamps × RTKLIB .pos solution → per-photo coordinates.

GPS time reference
------------------
MRK files store *GPS seconds-of-week* (e.g. 432100.123).
RTKLIB .pos files store *calendar datetime in GPST* (e.g. 2023/11/03 00:01:20.000).

Conversion from GPST calendar datetime to GPS seconds-of-week:
    gps_seconds = weekday_gps * 86400 + hours*3600 + minutes*60 + seconds

where ``weekday_gps`` is 0 (Sunday) … 6 (Saturday) — GPS week starts on Sunday.
Python's datetime.weekday() returns 0=Monday … 6=Sunday, so we remap:
    weekday_gps = (python_weekday + 1) % 7

This logic is ported from the validated V0.3.x implementation.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

from avgeosys.core.geoid import geoid_height

logger = logging.getLogger(__name__)


def _gpst_datetime_to_seconds_of_week(dt: pd.Timestamp) -> float:
    """Convert a GPST calendar timestamp to GPS seconds-of-week.

    GPS week starts on Sunday.  Python weekday: Monday=0 … Sunday=6.
    GPS weekday: Sunday=0 … Saturday=6.
    """
    gps_weekday = (dt.weekday() + 1) % 7
    return (
        gps_weekday * 86400
        + dt.hour * 3600
        + dt.minute * 60
        + dt.second
        + dt.microsecond / 1_000_000
    )


def preprocess_and_read_mrk(mrk_path: Path) -> pd.DataFrame:
    """Parse a MRK file into a DataFrame with normalized GPS seconds.

    Delegates to :func:`avgeosys.core.events.read_mrk_events` so that both
    simple space-separated and DJI tab-separated formats are handled correctly.

    Columns: ``gps_week``, ``gps_seconds``, ``filename``.
    """
    from avgeosys.core.events import read_mrk_events

    events = read_mrk_events(mrk_path)
    df = pd.DataFrame(
        [
            {
                "gps_week": e.gps_week,
                "gps_seconds": e.gps_seconds,
                "filename": e.filename,
            }
            for e in events
        ]
    )
    return df


def _parse_pos_line(parts: list) -> dict:
    """Parse a single data line from a RTKLIB .pos file.

    Handles two time formats emitted by rnx2rtkp:

    **HMS format** (``out-timeform=hms``, default):
        ``YYYY/MM/DD HH:MM:SS.SSS  lat lon height Q ns ...``
        → parts[0]=date, parts[1]=time, data starts at parts[2]

    **TOW format** (``out-timeform=tow``):
        ``GPS_Week GPS_Seconds  lat lon height Q ns ...``
        → parts[0]=week (integer), parts[1]=seconds, data starts at parts[2]
    """
    # Detect TOW vs HMS: TOW first field is a numeric GPS week (0–9999).
    # HMS first field is a date string like "2024/09/24" (always contains "/").
    _p0 = parts[0]
    _is_tow = (
        "/" not in _p0
        and _p0.lstrip("-").isdigit()
        and 0 <= int(_p0) <= 9999
        and len(parts) >= 7
    )
    if _is_tow:
        # TOW format: GPS_Week GPS_Seconds lat lon height Q ns
        gps_seconds = float(parts[1])
        lat = float(parts[2])
        lon = float(parts[3])
        height = float(parts[4])
        quality = int(parts[5])
    else:
        # HMS format: YYYY/MM/DD HH:MM:SS.SSS lat lon height Q ns
        if len(parts) < 8:
            raise ValueError(f"HMS line has only {len(parts)} fields")
        date_str = parts[0]
        time_str = parts[1]
        lat = float(parts[2])
        lon = float(parts[3])
        height = float(parts[4])
        quality = int(parts[5])
        dt = pd.Timestamp(f"{date_str} {time_str}")
        gps_seconds = _gpst_datetime_to_seconds_of_week(dt)

    return {
        "gps_seconds": gps_seconds,
        "latitude": lat,
        "longitude": lon,
        "height": height,
        "quality": quality,
    }


def load_pos_data(pos_path: Path) -> pd.DataFrame:
    """Parse a RTKLIB .pos file into a DataFrame.

    Columns: ``gps_seconds``, ``latitude``, ``longitude``, ``height``, ``quality``.

    Supports both ``out-timeform=hms`` (calendar datetime) and
    ``out-timeform=tow`` (GPS week + seconds-of-week) output formats.
    """
    pos_path = Path(pos_path)
    rows = []
    with open(pos_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("%") or not line:
                continue
            parts = line.split()
            if len(parts) < 7:
                continue
            try:
                rows.append(_parse_pos_line(parts))
            except (ValueError, IndexError) as exc:
                logger.warning("Ignorando linha .pos malformada: %r (%s)", line, exc)
                continue

    df = pd.DataFrame(rows)
    return df


def interpolate_positions(
    mrk_df: pd.DataFrame,
    pos_df: pd.DataFrame,
    orthometric: bool = False,
) -> List[Dict]:
    """Assign interpolated lat/lon/height to each MRK event.

    Uses ``numpy.interp`` on the GPS-seconds axis.  Events outside the .pos
    range receive ``quality = 3`` (Unknown/extrapolated).

    Args:
        mrk_df: DataFrame from :func:`preprocess_and_read_mrk`.
        pos_df: DataFrame from :func:`load_pos_data`.
        orthometric: If True, subtract geoid height to obtain orthometric height.

    Returns:
        List of dicts matching the ``interpolated_data.json`` schema.
    """
    pos_t = pos_df["gps_seconds"].to_numpy()
    pos_lat = pos_df["latitude"].to_numpy()
    pos_lon = pos_df["longitude"].to_numpy()
    pos_h = pos_df["height"].to_numpy()
    pos_q = pos_df["quality"].to_numpy().astype(float)

    pos_min = pos_t.min()
    pos_max = pos_t.max()

    results = []
    for _, row in mrk_df.iterrows():
        t = float(row["gps_seconds"])
        lat = float(np.interp(t, pos_t, pos_lat))
        lon = float(np.interp(t, pos_t, pos_lon))
        h = float(np.interp(t, pos_t, pos_h))
        q = int(round(float(np.interp(t, pos_t, pos_q))))

        if t < pos_min or t > pos_max:
            q = 5  # Single — evento fora da janela .pos (sem correção PPK)

        if orthometric:
            h = h - geoid_height(lat, lon)

        results.append(
            {
                "filename": str(row["filename"]),
                "gps_week": int(row["gps_week"]),
                "gps_seconds": t,
                "latitude": lat,
                "longitude": lon,
                "height": h,
                "quality": q,
            }
        )

    return results


def run_interpolation(
    mrk_path: Path,
    pos_path: Path,
    output_dir: Path,
    orthometric: bool = False,
) -> Path:
    """Full pipeline: parse MRK + pos, interpolate, write JSON.

    Args:
        mrk_path: Path to the .MRK file.
        pos_path: Path to the RTKLIB .pos file.
        output_dir: Directory where ``interpolated_data.json`` is written.
        orthometric: Whether to apply geoid correction.

    Returns:
        Path to the written JSON file.
    """
    mrk_df = preprocess_and_read_mrk(mrk_path)
    pos_df = load_pos_data(pos_path)
    results = interpolate_positions(mrk_df, pos_df, orthometric=orthometric)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "interpolated_data.json"
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)

    logger.info("Gravados %d registros interpolados em %s", len(results), json_path)
    return json_path
