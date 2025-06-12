"""
Módulo de geotagging e geração de KMZ via EXIF.
"""

import logging
from pathlib import Path
from math import floor
from typing import Tuple, List, Dict, Optional

import piexif
import simplekml

logger = logging.getLogger(__name__)


def convert_to_dms(
    value: float,
) -> Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int]]:
    deg = floor(abs(value))
    mn = floor((abs(value) - deg) * 60)
    sec = round((abs(value) - deg - mn / 60) * 3600, 5)
    return ((deg, 1), (mn, 1), (int(sec * 100), 100))


def convert_from_dms(dms, ref: str) -> float:
    try:
        deg = dms[0][0] / dms[0][1]
        mn = dms[1][0] / dms[1][1]
        sc = dms[2][0] / dms[2][1]
        dec = deg + mn / 60 + sc / 3600
        if ref in ["S", "W"]:
            dec = -dec
        return dec
    except Exception as e:
        logger.error(f"Erro em convert_from_dms: {e}")
        return 0.0


def update_exif(
    photo_path: Path,
    lat: float,
    lon: float,
    height: float,
) -> None:
    """
    Atualiza EXIF GPS de uma foto específica.
    """
    try:
        exif_dict = piexif.load(str(photo_path))

        # Define referências de hemisfério com base no sinal da coordenada
        lat_ref = "N" if lat >= 0 else "S"
        lon_ref = "E" if lon >= 0 else "W"

        exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = convert_to_dms(lat)
        exif_dict["GPS"][piexif.GPSIFD.GPSLatitudeRef] = lat_ref.encode()
        exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = convert_to_dms(lon)
        exif_dict["GPS"][piexif.GPSIFD.GPSLongitudeRef] = lon_ref.encode()
        exif_dict["GPS"][piexif.GPSIFD.GPSAltitude] = (int(height * 100), 100)

        piexif.insert(piexif.dump(exif_dict), str(photo_path))
        logger.info(f"EXIF atualizado: {photo_path.name}")
    except Exception as e:
        logger.error(f"Erro ao atualizar EXIF {photo_path.name}: {e}")


def extract_exif_coordinates(root_folder: Path) -> List[Dict]:
    """
    Extrai coordenadas GPS de todas as .jpg em root_folder via EXIF.
    """
    results: List[Dict] = []

    for img in root_folder.rglob("*.jpg"):
        try:
            gps_data = piexif.load(str(img)).get("GPS", {})
            lat = gps_data.get(piexif.GPSIFD.GPSLatitude)
            lon = gps_data.get(piexif.GPSIFD.GPSLongitude)
            alt = gps_data.get(piexif.GPSIFD.GPSAltitude)
            lat_ref = gps_data.get(
                piexif.GPSIFD.GPSLatitudeRef, b"N"
            ).decode()
            lon_ref = gps_data.get(
                piexif.GPSIFD.GPSLongitudeRef, b"E"
            ).decode()

            if lat and lon:
                dec_lat = convert_from_dms(lat, lat_ref)
                dec_lon = convert_from_dms(lon, lon_ref)
                dec_alt = alt[0] / alt[1] if alt else None

                results.append({
                    "lat": dec_lat,
                    "lon": dec_lon,
                    "height": dec_alt,
                    "filename": str(img),
                })
        except Exception as e:
            logger.warning(f"Falha ao ler EXIF {img.name}: {e}")

    logger.info(
        f"EXIF extraído: {len(results)} imagens processadas."
    )
    return results


def generate_exif_kmz(
    root_folder: Path,
    kmz_path: Optional[Path] = None,
) -> Path:
    """
    Gera KMZ com pontos EXIF extraídos em root_folder.
    """
    data = extract_exif_coordinates(root_folder)

    if kmz_path is None:
        kmz_path = root_folder / "compilado_exif_data.kmz"

    kml = simplekml.Kml()
    for pt in data:
        kml.newpoint(coords=[(pt["lon"], pt["lat"])])

    kml.savekmz(str(kmz_path))
    logger.info(
        f"KMZ de EXIF salvo em {kmz_path.name}"
    )
    return kmz_path
