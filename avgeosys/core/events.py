"""
MRK event file parsing and conversion utilities.

Supports two formats:

**Simple format** (space-separated, 3+ fields):
    GPS_Week  GPS_Seconds  Filename

**DJI format** (tab-separated, Mavic/Phantom Timestamp.MRK):
    SeqNum<TAB>GPS_Seconds<TAB>[GPS_Week]<TAB>...extra fields...
    e.g.: 1	217331.220108	[2333]	   -18,N	...
    Filename is mapped from SeqNum → matching JPEG in the same folder.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MRKEvent:
    gps_week: int
    gps_seconds: float
    filename: str


# -----------------------------------------------------------------------
# Format detection
# -----------------------------------------------------------------------

def _is_dji_format(first_line: str) -> bool:
    """Return True if the first line looks like DJI tab-separated MRK format."""
    parts = first_line.split("\t")
    if len(parts) < 3:
        return False
    # DJI: field[0] is an integer seq number, field[1] is float GPS seconds,
    # field[2] matches '[NNNN]'
    try:
        int(parts[0].strip())
        float(parts[1].strip())
        return bool(re.match(r"^\s*\[\d+\]", parts[2]))
    except (ValueError, IndexError):
        return False


# -----------------------------------------------------------------------
# DJI format helpers
# -----------------------------------------------------------------------

def _find_jpegs_sorted(folder: Path) -> List[Path]:
    """Return all JPEG files in *folder* sorted by name (which sorts by timestamp prefix)."""
    return sorted(p for p in folder.iterdir() if p.suffix.upper() in (".JPG", ".JPEG"))


def _parse_dji_mrk(mrk_path: Path) -> List[MRKEvent]:
    """Parse a DJI tab-separated Timestamp.MRK file.

    Filename is matched from the sequence number: row N corresponds to the
    Nth JPEG in the same folder (sorted by name, which = sorted by timestamp).
    """
    folder = mrk_path.parent
    jpegs = _find_jpegs_sorted(folder)
    if not jpegs:
        logger.warning("Nenhum JPEG encontrado em %s — eventos MRK não terão nome de arquivo", folder)

    events: List[MRKEvent] = []
    with open(mrk_path, encoding="utf-8", errors="replace") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                logger.warning("MRK DJI linha %d malformada: %r", line_no, line)
                continue
            try:
                seq = int(parts[0].strip())
                gps_seconds = float(parts[1].strip())
                week_str = parts[2].strip()  # e.g. '[2333]'
                gps_week = int(week_str.strip("[]"))
            except (ValueError, IndexError):
                logger.warning("MRK DJI linha %d não pôde ser lida: %r", line_no, line)
                continue

            # Match by sequence number (1-based) to sorted JPEG list
            jpeg_index = seq - 1
            if 0 <= jpeg_index < len(jpegs):
                filename = jpegs[jpeg_index].name
            else:
                filename = f"__seq_{seq:04d}__.JPG"
                logger.warning(
                    "MRK DJI seq %d sem JPEG correspondente (pasta tem %d imagens)",
                    seq, len(jpegs),
                )

            events.append(MRKEvent(gps_week=gps_week, gps_seconds=gps_seconds, filename=filename))

    return events


# -----------------------------------------------------------------------
# Simple format helpers
# -----------------------------------------------------------------------

def _parse_simple_mrk(mrk_path: Path) -> List[MRKEvent]:
    """Parse a simple space-separated MRK file (GPS_Week GPS_Seconds Filename)."""
    events: List[MRKEvent] = []
    with open(mrk_path, encoding="utf-8", errors="replace") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 3:
                logger.warning("MRK linha %d malformada (esperado ≥3 campos): %r", line_no, line)
                continue
            try:
                gps_week = int(parts[0])
                gps_seconds = float(parts[1])
                filename = parts[2]
            except ValueError:
                logger.warning("MRK linha %d não pôde ser lida: %r", line_no, line)
                continue
            events.append(MRKEvent(gps_week=gps_week, gps_seconds=gps_seconds, filename=filename))
    return events


# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------

def read_mrk_events(mrk_path: Path) -> List[MRKEvent]:
    """Parse a MRK file and return a list of MRKEvent objects.

    Auto-detects DJI tab-separated format vs simple space-separated format.

    Args:
        mrk_path: Path to the .MRK file.

    Returns:
        List of MRKEvent, one per line (one per photo).

    Raises:
        FileNotFoundError: if the file does not exist.
    """
    mrk_path = Path(mrk_path)
    if not mrk_path.exists():
        raise FileNotFoundError(f"MRK file not found: {mrk_path}")

    # Peek at first non-empty line to detect format
    first_line: Optional[str] = None
    with open(mrk_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.strip():
                first_line = line.rstrip("\n")
                break

    if first_line and _is_dji_format(first_line):
        logger.debug("Formato MRK DJI (tab-separado) detectado: %s", mrk_path.name)
        return _parse_dji_mrk(mrk_path)
    else:
        logger.debug("Formato MRK simples (espaço-separado) detectado: %s", mrk_path.name)
        return _parse_simple_mrk(mrk_path)


def convert_mrk_to_events_file(mrk_path: Path, output_path: Path) -> None:
    """Write a RTKLIB-compatible events file from a MRK file.

    Args:
        mrk_path: Path to source .MRK file.
        output_path: Destination events file path.
    """
    events = read_mrk_events(mrk_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        for e in events:
            fh.write(f"{e.gps_week} {e.gps_seconds:.3f} {e.filename}\n")
    logger.info("Gravados %d eventos em %s", len(events), output_path)


def validate_event_times(
    events: List[MRKEvent],
    pos_start: float,
    pos_end: float,
) -> List[str]:
    """Return warning strings for events whose GPS seconds fall outside [pos_start, pos_end].

    Args:
        events: List of MRKEvent objects.
        pos_start: First GPS-seconds value in the .pos file.
        pos_end: Last GPS-seconds value in the .pos file.

    Returns:
        List of human-readable warning strings (empty list if all in range).
    """
    warnings: List[str] = []
    for e in events:
        if e.gps_seconds < pos_start or e.gps_seconds > pos_end:
            warnings.append(
                f"Event {e.filename} (GPS {e.gps_week}/{e.gps_seconds:.3f}s) "
                f"is outside POS range [{pos_start:.3f}, {pos_end:.3f}]"
            )
    return warnings
