"""
JPEG GPS EXIF read/write utilities using piexif.

Coordinates are stored in DMS (Degrees-Minutes-Seconds) rational format
as required by the EXIF GPS IFD specification.

Writes are atomic: the modified JPEG is built in memory and written to a
temporary file next to the original, then renamed over it.  This prevents
corruption if the process is interrupted mid-write.
"""

import io
import logging
import os
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import piexif

logger = logging.getLogger(__name__)

# piexif rational: (numerator, denominator) integer pair
Rational = Tuple[int, int]
DMSTuple = Tuple[Rational, Rational, Rational]

# Precisão: segundos como n/10000 → erro ≤1 cm
_SEC_DENOMINATOR = 10_000
_SEC_MAX = 60 * _SEC_DENOMINATOR - 1

# Tolerância para verificação de leitura EXIF após gravação (~11 metros)
_VERIFY_TOLERANCE = 1e-4

# Labels de qualidade PPK para gravação no EXIF UserComment (códigos RTKLIB)
_QUALITY_LABELS = {1: "Fixed", 2: "Float", 3: "SBAS", 4: "DGPS", 5: "Single", 6: "PPP"}


def convert_to_dms(decimal_degrees: float) -> DMSTuple:
    """Converte graus decimais para formato DMS rational piexif (valor absoluto).

    O sinal/referência de hemisfério é tratado separadamente via GPSLatitudeRef /
    GPSLongitudeRef — sempre passe o valor absoluto aqui.
    """
    dd = abs(decimal_degrees)
    degrees = int(dd)
    minutes_full = (dd - degrees) * 60.0
    minutes = int(minutes_full)
    seconds = (minutes_full - minutes) * 60.0
    sec_int = min(int(round(seconds * _SEC_DENOMINATOR)), _SEC_MAX)
    return (
        (degrees, 1),
        (minutes, 1),
        (sec_int, _SEC_DENOMINATOR),
    )


def convert_from_dms(dms: DMSTuple) -> float:
    """Converte formato DMS rational piexif de volta para graus decimais (positivo)."""
    d = dms[0][0] / dms[0][1]
    m = dms[1][0] / dms[1][1]
    s = dms[2][0] / dms[2][1]
    return d + m / 60.0 + s / 3600.0


def update_exif(
    jpg_path: Path,
    lat: float,
    lon: float,
    alt: float,
    verify: bool = True,
    ppk_quality: Optional[int] = None,
    backup_dir: Optional[Path] = None,
) -> bool:
    """Grava tags GPS EXIF em um JPEG de forma atômica.

    Constrói o JPEG modificado em memória, grava em arquivo temporário ao lado
    do original e renomeia sobre ele — o original nunca fica em estado parcial.

    Args:
        jpg_path: Caminho para o arquivo JPEG.
        lat: Latitude em graus decimais (negativo = Sul).
        lon: Longitude em graus decimais (negativo = Oeste).
        alt: Altitude em metros acima do elipsoide de referência.
        verify: Se True, relê o EXIF gravado e verifica os valores.
        ppk_quality: Código de qualidade PPK (1=Fixed, 2=Float, 3=Unknown).
                     Se fornecido, grava "PPK:Fixed" etc. no campo UserComment.
        backup_dir: Se fornecido, copia o JPEG original para este diretório
                    antes de qualquer modificação.

    Returns:
        True em sucesso, False se falha ou verificação não passa.
    """
    jpg_path = Path(jpg_path)
    try:
        # Backup opcional antes de modificar
        if backup_dir is not None:
            backup_path = Path(backup_dir) / jpg_path.name
            if not backup_path.exists():
                shutil.copy2(jpg_path, backup_path)

        # Construir GPS IFD
        gps_ifd: Dict = {}
        gps_ifd[piexif.GPSIFD.GPSLatitudeRef] = b"S" if lat < 0 else b"N"
        gps_ifd[piexif.GPSIFD.GPSLatitude] = convert_to_dms(lat)
        gps_ifd[piexif.GPSIFD.GPSLongitudeRef] = b"W" if lon < 0 else b"E"
        gps_ifd[piexif.GPSIFD.GPSLongitude] = convert_to_dms(lon)
        gps_ifd[piexif.GPSIFD.GPSAltitudeRef] = 0
        gps_ifd[piexif.GPSIFD.GPSAltitude] = (int(round(alt * 100)), 100)

        # Carregar EXIF existente dos bytes do arquivo (não-destrutivo)
        jpeg_bytes = jpg_path.read_bytes()
        try:
            exif_dict = piexif.load(jpeg_bytes)
        except Exception:
            exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}

        exif_dict["GPS"] = gps_ifd

        # Gravar qualidade PPK no campo UserComment do EXIF
        if ppk_quality is not None:
            q_label = _QUALITY_LABELS.get(ppk_quality, "Unknown")
            comment = f"PPK:{q_label}".encode("utf-8")
            # UserComment requer prefixo de 8 bytes de charset
            charset_prefix = b"ASCII\x00\x00\x00"
            exif_dict["Exif"][piexif.ExifIFD.UserComment] = charset_prefix + comment

        exif_bytes = piexif.dump(exif_dict)
        buf = io.BytesIO()
        piexif.insert(exif_bytes, jpeg_bytes, buf)
        modified_jpeg: bytes = buf.getvalue()

        # Escrita atômica: temp → rename
        parent = jpg_path.parent
        fd, tmp_path = tempfile.mkstemp(suffix=".tmp", dir=parent)
        try:
            os.write(fd, modified_jpeg)
            os.close(fd)
            os.replace(tmp_path, jpg_path)
        except Exception:
            os.close(fd)
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        # Verificação de leitura
        if verify:
            result = extract_exif_coordinates(jpg_path)
            if result is None:
                logger.warning(
                    "Verificação EXIF falhou (sem dados GPS) para %s", jpg_path.name
                )
                return False
            if (
                abs(result["latitude"] - lat) > _VERIFY_TOLERANCE
                or abs(result["longitude"] - lon) > _VERIFY_TOLERANCE
            ):
                logger.warning(
                    "Divergência EXIF em %s: gravado (%.7f, %.7f) lido (%.7f, %.7f)",
                    jpg_path.name,
                    lat, lon,
                    result["latitude"], result["longitude"],
                )
                return False

        return True

    except Exception as exc:
        logger.warning("Não foi possível gravar EXIF em %s: %s", jpg_path, exc)
        return False


def extract_exif_coordinates(jpg_path: Path) -> Optional[Dict[str, float]]:
    """Lê latitude, longitude e altitude GPS do EXIF de um JPEG.

    Returns:
        Dict com chaves ``latitude``, ``longitude``, ``altitude``, ou ``None``
        se não houver dados GPS.
    """
    jpg_path = Path(jpg_path)
    try:
        exif_dict = piexif.load(str(jpg_path))
    except Exception as exc:
        logger.warning("Não foi possível carregar EXIF de %s: %s", jpg_path, exc)
        return None

    gps = exif_dict.get("GPS", {})
    if not gps:
        return None

    try:
        lat = convert_from_dms(gps[piexif.GPSIFD.GPSLatitude])
        lat_ref = gps.get(piexif.GPSIFD.GPSLatitudeRef, b"N")
        if isinstance(lat_ref, bytes):
            lat_ref = lat_ref.decode("ascii", errors="replace")
        if lat_ref.upper() == "S":
            lat = -lat

        lon = convert_from_dms(gps[piexif.GPSIFD.GPSLongitude])
        lon_ref = gps.get(piexif.GPSIFD.GPSLongitudeRef, b"E")
        if isinstance(lon_ref, bytes):
            lon_ref = lon_ref.decode("ascii", errors="replace")
        if lon_ref.upper() == "W":
            lon = -lon

        alt_raw = gps.get(piexif.GPSIFD.GPSAltitude, (0, 1))
        denom = alt_raw[1] if alt_raw[1] != 0 else 1
        alt = alt_raw[0] / denom
        alt_ref = gps.get(piexif.GPSIFD.GPSAltitudeRef, 0)
        if alt_ref == 1:
            alt = -alt

        return {"latitude": lat, "longitude": lon, "altitude": alt}
    except (KeyError, ZeroDivisionError, TypeError) as exc:
        logger.warning("EXIF GPS incompleto em %s: %s", jpg_path, exc)
        return None


def batch_update_exif(
    records: List[Dict],
    project_path: Path,
    cancel_event=None,
    progress_callback=None,
    backup_dir: Optional[Path] = None,
) -> Tuple[int, int]:
    """Grava GPS EXIF em múltiplos JPEGs em paralelo.

    Antes de iniciar, verifica se há fotos Single (Q=5) ou fora da janela .pos
    e emite aviso — essas fotos têm coordenadas sem correção diferencial.

    Args:
        records: Lista de dicts com chaves ``filename``, ``folder`` (opcional),
                 ``latitude``, ``longitude``, ``height``, ``quality`` (opcional).
        project_path: Diretório raiz do projeto. JPEGs resolvidos como
                      ``project_path / rec["folder"] / rec["filename"]``.
        cancel_event: ``threading.Event`` opcional; para quando ativado.
        progress_callback: Callable(done, total) opcional para progresso.
        backup_dir: Se fornecido, copia os JPEGs originais aqui antes de modificar.

    Returns:
        Tupla (gravados, ignorados).
    """
    project_path = Path(project_path)

    # Aviso sobre fotos com qualidade desconhecida
    single_count = sum(1 for r in records if int(r.get("quality", 5)) == 5)
    if single_count > 0:
        logger.warning(
            "%d foto(s) com qualidade SINGLE (Q=5) — coordenadas GPS autônomas, "
            "sem correção PPK. Verifique sobreposição temporal entre rover e base.",
            single_count,
        )

    if backup_dir is not None:
        Path(backup_dir).mkdir(parents=True, exist_ok=True)
        logger.info("Backup dos JPEGs originais em: %s", backup_dir)

    def _update(rec: Dict) -> bool:
        if cancel_event is not None and cancel_event.is_set():
            return False
        folder_rel = rec.get("folder", "")
        jpg = (
            project_path / folder_rel / rec["filename"]
            if folder_rel
            else project_path / rec["filename"]
        )
        if not jpg.exists():
            logger.warning("JPEG não encontrado: %s", jpg)
            return False
        return update_exif(
            jpg,
            lat=rec["latitude"],
            lon=rec["longitude"],
            alt=rec["height"],
            ppk_quality=int(rec.get("quality", 5)),
            backup_dir=backup_dir,
        )

    from avgeosys import config

    total = len(records)
    written = 0
    skipped = 0
    done = 0
    _last_reported = [0]

    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
        futures = {executor.submit(_update, r): r["filename"] for r in records}
        for future in as_completed(futures):
            done += 1
            try:
                ok = future.result()
                if ok:
                    written += 1
                else:
                    skipped += 1
            except Exception as exc:
                skipped += 1
                logger.warning("Falha ao atualizar EXIF de %s: %s", futures[future], exc)
            # Throttle: notifica progresso a cada ~1% ou no mínimo a cada 50 arquivos
            if progress_callback is not None:
                step = max(1, total // 100)
                if done - _last_reported[0] >= step or done == total:
                    progress_callback(done, total)
                    _last_reported[0] = done

    return written, skipped
