"""
Quality report and KMZ generation.

Produces:
  - ``relatorio_processamento.txt`` — quality statistics breakdown (global + per folder)
  - ``resultado_interpolado.kmz`` — one placemark per interpolated position
  - ``compilado_exif_data.kmz`` — one placemark per EXIF-extracted position
"""

import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import simplekml

logger = logging.getLogger(__name__)

# Quality code → human-readable label
QUALITY_LABELS: Dict[int, str] = {
    1: "Fixed",
    2: "Float",
    3: "Unknown",
}


def _count_quality(data: List[Dict]) -> Dict[str, int]:
    counts: Dict[str, int] = {label: 0 for label in QUALITY_LABELS.values()}
    for rec in data:
        q = rec.get("quality", 3)
        label = QUALITY_LABELS.get(int(q), "Unknown")
        counts[label] += 1
    return counts


def _write_quality_block(fh, counts: Dict[str, int], total: int) -> None:
    for label in ("Fixed", "Float", "Unknown"):
        n = counts[label]
        pct = (n / total * 100.0) if total > 0 else 0.0
        fh.write(f"  {label:<10}: {n:>5}  ({pct:6.1f}%)\n")


def generate_report_and_kmz(
    interpolated_data: List[Dict],
    output_dir: Path,
) -> Tuple[Path, Path, Path]:
    """Generate quality report and KMZ files from interpolated position data.

    Args:
        interpolated_data: List of dicts (``interpolated_data.json`` schema).
        output_dir: Directory where output files are written.

    Returns:
        Tuple of (report_path, kmz_interpolated_path, kmz_exif_path).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    total = len(interpolated_data)
    counts = _count_quality(interpolated_data)

    # --- Group by folder for per-folder stats ---
    by_folder: Dict[str, List[Dict]] = defaultdict(list)
    for rec in interpolated_data:
        folder = rec.get("folder", "")
        by_folder[folder].append(rec)

    # --- Text report ---
    report_path = output_dir / "relatorio_processamento.txt"
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("=" * 60 + "\n")
        fh.write("  AVGeoSys — Relatório de Processamento PPK\n")
        fh.write("=" * 60 + "\n\n")
        fh.write(f"Total de fotos processadas: {total}\n\n")

        # Global quality summary
        fh.write("Qualidade geral da solução PPK:\n")
        _write_quality_block(fh, counts, total)
        fh.write("\n")

        # Per-folder quality summary
        if len(by_folder) > 1:
            fh.write("Qualidade por pasta de voo:\n")
            fh.write("-" * 60 + "\n")
            for folder_name in sorted(by_folder):
                recs = by_folder[folder_name]
                n_folder = len(recs)
                c_folder = _count_quality(recs)
                label = folder_name if folder_name else "(raiz)"
                fh.write(f"\n  {label}  ({n_folder} fotos)\n")
                _write_quality_block(fh, c_folder, n_folder)
            fh.write("\n")

        # Per-photo detail
        fh.write("Detalhes por foto:\n")
        fh.write("-" * 60 + "\n")
        for rec in interpolated_data:
            q_label = QUALITY_LABELS.get(int(rec.get("quality", 3)), "Unknown")
            fh.write(
                f"  {rec['filename']:<30}  "
                f"lat={rec['latitude']:>12.7f}  "
                f"lon={rec['longitude']:>13.7f}  "
                f"h={rec['height']:>9.3f}m  "
                f"Q={q_label}\n"
            )

    logger.info("Relatório gravado em %s", report_path)

    # --- KMZ: interpolated positions (colour-coded by quality) ---
    kmz_interp_path = output_dir / "resultado_interpolado.kmz"
    kml_interp = simplekml.Kml()

    # Style icons by quality
    _styles: Dict[str, simplekml.Style] = {}
    for q_label, color in (("Fixed", "ff00ff00"), ("Float", "ff00a5ff"), ("Unknown", "ff0000ff")):
        style = simplekml.Style()
        style.iconstyle.color = color
        style.iconstyle.scale = 0.8
        _styles[q_label] = style

    for rec in interpolated_data:
        q_label = QUALITY_LABELS.get(int(rec.get("quality", 3)), "Unknown")
        pt = kml_interp.newpoint(
            name=rec["filename"],
            coords=[(rec["longitude"], rec["latitude"], rec["height"])],
        )
        pt.description = (
            f"Qualidade: {q_label}\n"
            f"GPS Week: {rec.get('gps_week', '')}\n"
            f"GPS Seconds: {rec.get('gps_seconds', ''):.3f}\n"
            f"Pasta: {rec.get('folder', '')}\n"
        )
        pt.altitudemode = simplekml.AltitudeMode.absolute
        pt.style = _styles[q_label]

    kml_interp.savekmz(str(kmz_interp_path))
    logger.info("KMZ interpolado gravado em %s", kmz_interp_path)

    # --- KMZ: EXIF-verified positions ---
    kmz_exif_path = output_dir / "compilado_exif_data.kmz"
    kml_exif = simplekml.Kml()
    for rec in interpolated_data:
        q_label = QUALITY_LABELS.get(int(rec.get("quality", 3)), "Unknown")
        pt = kml_exif.newpoint(
            name=rec["filename"],
            coords=[(rec["longitude"], rec["latitude"], rec["height"])],
        )
        pt.description = (
            f"Coordenadas gravadas via EXIF\n"
            f"Qualidade PPK: {q_label}\n"
            f"Pasta: {rec.get('folder', '')}\n"
        )
        pt.altitudemode = simplekml.AltitudeMode.absolute
    kml_exif.savekmz(str(kmz_exif_path))
    logger.info("KMZ EXIF gravado em %s", kmz_exif_path)

    return report_path, kmz_interp_path, kmz_exif_path
