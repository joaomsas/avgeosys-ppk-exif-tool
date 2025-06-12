"""Utilidades de conversão de altura usando geóide.

O módulo tenta utilizar uma grade EGM96 15x15 via PROJ. Caso a grade não esteja
presente ou não possa ser baixada (por exemplo, em ambientes offline),
é utilizado um modelo simplificado apenas para fins de teste.
"""
from __future__ import annotations

from math import sin, radians

from pyproj import Transformer, network

# Tenta criar um Transformer que aplique a grade EGM96 15 minutos.
# Caso falhe (grid ausente ou sem acesso à internet), usa fallback simples.
try:
    network.set_network_enabled(True)
    _TRANSFORMER = Transformer.from_pipeline(
        "+proj=vgridshift +grids=us_nga_egm96_15.tif +multiplier=1"
    )
    # Valida se a grade está disponível
    _TRANSFORMER.transform(0.0, 0.0, 0.0)
except Exception:  # pragma: no cover - dependência externa
    network.set_network_enabled(False)
    _TRANSFORMER = None


def geoid_height(lat: float, lon: float) -> float:
    """Retorna a separação geoidal aproximada em metros."""
    if _TRANSFORMER:
        # order lon, lat, height
        try:
            _, _, gh = _TRANSFORMER.transform(lon, lat, 0.0, radians=False)
            return gh
        except Exception:  # pragma: no cover - erros de PROJ
            pass
    # Modelo simplificado: variação senoidal de até 10 m
    return 10.0 * sin(radians(lat))


def ellipsoid_to_orthometric(lat: float, lon: float, height: float) -> float:
    """Converte altura elipsoidal para ortométrica."""
    return height - geoid_height(lat, lon)

