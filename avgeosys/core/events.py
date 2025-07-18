"""Utilities for handling MRK event files for PPK."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

GPS_EPOCH = datetime(1980, 1, 6, tzinfo=timezone.utc)


def _parse_time(t_str: str) -> float:
    """Parse time string as seconds of day."""
    t_str = t_str.replace(",", ".")
    if ":" in t_str:
        try:
            h, m, s = t_str.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
        except ValueError:
            logger.debug("Could not parse HH:MM:SS format: %s", t_str)
            return float("nan")
    try:
        return float(t_str)
    except ValueError:
        logger.debug("Could not parse float time: %s", t_str)
        return float("nan")


def read_mrk_events(mrk_file: Path) -> List[float]:
    """Return list of event times (seconds of day or week) from .MRK file."""
    times: List[float] = []
    for line in mrk_file.read_text().splitlines():
        if not line.strip():
            continue
        m = re.match(r"\s*\d+[,\s]+([0-9:]+(?:[,.][0-9]+)?)", line)
        if not m:
            continue
        t = _parse_time(m.group(1))
        if not (t != t):  # not NaN
            times.append(t)
    return times


def write_event_file(events: List[float], out_file: Path) -> None:
    out_file.write_text("\n".join(f"{t:.3f}" for t in events) + "\n")


def datetime_to_gpsweek_sow(dt: datetime) -> Tuple[int, float]:
    dt = dt.replace(tzinfo=timezone.utc)
    delta = dt - GPS_EPOCH
    week = delta.days // 7
    sow = (delta - timedelta(weeks=week)).total_seconds()
    return week, sow


def obs_time_bounds(obs_file: Path) -> Tuple[float, float]:
    first = last = None
    for line in obs_file.read_text().splitlines():
        if "TIME OF FIRST OBS" in line:
            first = line[:43].strip()
        elif "TIME OF LAST OBS" in line:
            last = line[:43].strip()
        if first and last:
            break

    def to_sow(val: str) -> float:
        parts = val.split()
        if len(parts) < 6:
            return float("nan")
        sec = float(parts[5])
        dt = datetime(
            int(parts[0]),
            int(parts[1]),
            int(parts[2]),
            int(parts[3]),
            int(parts[4]),
            int(sec),
            int((sec - int(sec)) * 1_000_000),
            tzinfo=timezone.utc,
        )
        _, sow = datetime_to_gpsweek_sow(dt)
        return sow
    if first is None or last is None:
        return float("nan"), float("nan")
    return to_sow(first), to_sow(last)


def validate_event_times(events: List[float], obs_file: Path) -> None:
    if not events:
        logger.warning("Nenhum evento encontrado no .MRK")
        return
    obs_start, obs_end = obs_time_bounds(obs_file)
    if obs_start != obs_start or obs_end != obs_end:
        logger.warning("Intervalo de tempo do OBS não pôde ser determinado")
        return
    e_start = min(events)
    e_end = max(events)
    if e_start < obs_start or e_end > obs_end:
        logger.warning(
            "Eventos fora do intervalo do OBS: %.3f-%.3f / %.3f-%.3f",
            e_start,
            e_end,
            obs_start,
            obs_end,
        )


def convert_mrk_to_events_file(
    mrk_file: Path, output_dir: Path, obs_file: Path
) -> Path:
    events = read_mrk_events(mrk_file)
    out_file = output_dir / f"{mrk_file.stem}.events"
    write_event_file(events, out_file)
    if events:
        logger.info(
            "Eventos lidos: %d (%.3f - %.3f)",
            len(events),
            events[0],
            events[-1],
        )
    else:
        logger.warning("Arquivo de eventos gerado vazio")
    validate_event_times(events, obs_file)
    return out_file
