"""Geoid height utilities."""

from __future__ import annotations

import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from pyproj import Transformer
except ImportError:  # pragma: no cover - optional dependency missing
    logger.info("pyproj not available; using fallback sine model")
    _TRANSFORMER: Optional["Transformer"] = None
else:
    try:
        _TRANSFORMER = Transformer.from_crs(
            "EPSG:4979",  # WGS84 3D
            "EPSG:4326+5773",  # WGS84 horizontal + EGM96 height
            always_xy=True,
        )
    except Exception as exc:  # pragma: no cover - initialization failure
        logger.warning("Failed to initialise Transformer: %s", exc)
        _TRANSFORMER = None


def geoid_height(lat: float, lon: float) -> float:
    """Return geoid-ellipsoid separation for the given coordinate in metres."""
    if _TRANSFORMER is not None:
        try:
            _, _, h = _TRANSFORMER.transform(lon, lat, 0.0)
            return float(h)
        except Exception as exc:  # pragma: no cover - runtime pyproj failure
            logger.warning("pyproj transformation failed: %s", exc)
    # Fallback simple sine approximation (~17 m amplitude for Brazil)
    return 17.0 * math.sin(math.radians(lat))
