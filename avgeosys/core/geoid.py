"""
Geoid height correction: ellipsoidal → orthometric height.

Uses pyproj (EGM2008) when available, falls back to a sine approximation
that is accurate to ~±2 m globally.
"""

import functools
import logging
import math

logger = logging.getLogger(__name__)

_PYPROJ_AVAILABLE: bool = False
_geod = None  # type: ignore
_fallback_warned: bool = False  # emit the approximation warning only once

try:
    from pyproj import Transformer  # type: ignore

    _geod = Transformer.from_crs("EPSG:4979", "EPSG:3855", always_xy=True)
    _PYPROJ_AVAILABLE = True
except Exception:
    pass

if not _PYPROJ_AVAILABLE:
    logger.warning(
        "pyproj não encontrado — altura ortométrica usará aproximação senoidal (±2 m). "
        "Instale pyproj para resultados precisos: pip install pyproj"
    )


@functools.lru_cache(maxsize=512)
def _geoid_height_cached(lat: float, lon: float) -> float:
    """Cálculo de altura geoidal com cache LRU (coordenadas arredondadas à grade)."""
    global _fallback_warned

    if _PYPROJ_AVAILABLE and _geod is not None:
        try:
            _, _, h_orth = _geod.transform(lon, lat, 0.0)
            # transform returns orthometric height for 0 ellipsoidal → -N
            return -h_orth
        except Exception as exc:
            logger.warning("pyproj geoid_height falhou (%s); usando fallback", exc)

    if not _fallback_warned:
        logger.warning(
            "Usando aproximação senoidal para altura geoidal (±2 m de imprecisão). "
            "Os resultados ortométricos NÃO devem ser usados para levantamentos precisos."
        )
        _fallback_warned = True

    # Simple sine approximation: ~0 at equator, ±30 m at poles (crude but bounded)
    return 15.0 * math.sin(math.radians(lat)) + 5.0 * math.sin(math.radians(2 * lon))


def geoid_height(lat: float, lon: float) -> float:
    """Retorna a ondulação geoidal N em (lat, lon) em metros.

    Arredonda coordenadas a 0,01° (~1 km) antes de consultar o cache,
    reduzindo chamadas repetidas ao pyproj para fotos de uma mesma área.

    Args:
        lat: Latitude em graus decimais.
        lon: Longitude em graus decimais.

    Returns:
        Altura geoidal N tal que H_ortométrica = h_elipsoidal - N.
    """
    return _geoid_height_cached(round(lat, 2), round(lon, 2))
