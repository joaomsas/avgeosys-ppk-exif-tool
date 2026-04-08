"""
AVGeoSys command-line interface.

Usage:
    avgeosys PATH [--ppk] [--interpolate] [--geotag] [--report] [--all]
                  [--orthometric] [--verbose] [--skip-rover-nav] [--base-dir DIR]
                  [--folder NAME] [--dry-run] [--solution-type TYPE]

``--all`` runs the full pipeline: PPK → interpolate → geotag → report.
``--field-upload`` is reserved for spec-002 and is not implemented here.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

def _flight_folders(project_path: Path, only_folder: Optional[str] = None) -> List[Path]:
    """Busca recursiva de pastas de voo com RINEX de observação."""
    from avgeosys.core.ppk import find_flight_folders
    return find_flight_folders(project_path, only_folder=only_folder)


def _find_pos_for_folder(folder: Path) -> Optional[Path]:
    """Return the PPK .pos file for *folder* (excludes *_events.pos)."""
    candidates = [
        p for p in folder.iterdir()
        if p.suffix.lower() == ".pos"
        and "_events" not in p.stem.lower()
        and p.stat().st_size > 500  # skip empty/header-only files
    ]
    return candidates[0] if candidates else None


def _find_mrk_for_folder(folder: Path) -> Optional[Path]:
    """Return the MRK timestamp file in *folder*."""
    mrks = [p for p in folder.iterdir() if p.suffix.upper() == ".MRK"]
    # Prefer *_Timestamp.MRK if multiple
    timestamp_mrks = [m for m in mrks if "timestamp" in m.name.lower()]
    return timestamp_mrks[0] if timestamp_mrks else (mrks[0] if mrks else None)


# -----------------------------------------------------------------------
# Dry-run validation
# -----------------------------------------------------------------------

def _run_dry_run(
    project_path: Path,
    only_folder: Optional[str],
    base_dir: Optional[Path],
) -> None:
    """Validate project structure without processing anything."""
    from avgeosys.core.ppk import find_base_files

    logger = logging.getLogger(__name__)
    logger.info("=== DRY RUN — nenhum arquivo será modificado ===")

    folders = _flight_folders(project_path, only_folder)
    if not folders:
        logger.error("Nenhuma pasta de voo encontrada em %s", project_path)
        return

    effective_base_dir = Path(base_dir) if base_dir else project_path
    all_ok = True

    for folder in folders:
        files = find_base_files(folder, base_dir=effective_base_dir)
        mrk = _find_mrk_for_folder(folder)
        pos = _find_pos_for_folder(folder)

        issues = []
        if not files["rover_obs"]:
            issues.append("SEM rover RINEX obs")
        if not files["base_obs"]:
            issues.append("SEM base RINEX obs")
        if not files["base_nav"]:
            issues.append("SEM base RINEX nav")
        if not mrk:
            issues.append("SEM arquivo MRK")

        if issues:
            logger.warning("%-50s  ✗  %s", folder.name, " | ".join(issues))
            all_ok = False
        else:
            logger.info(
                "%-50s  ✓  rover=%s  base=%s  mrk=%s  pos=%s",
                folder.name,
                files["rover_obs"].name,
                files["base_obs"].name,
                mrk.name if mrk else "—",
                pos.name if pos else "— (não gerado ainda)",
            )

    if all_ok:
        logger.info("Todos os voos OK — projeto pronto para processamento.")
    else:
        logger.warning("Alguns voos têm problemas. Corrija antes de processar.")


# -----------------------------------------------------------------------
# Pipeline steps
# -----------------------------------------------------------------------

def _run_ppk(
    project_path: Path,
    config_override: dict,
    base_dir: Optional[Path] = None,
    solution_type: str = "forward",
    only_folder: Optional[str] = None,
) -> None:
    from avgeosys.core.ppk import process_all_folders

    logger = logging.getLogger(__name__)
    logger.info("Iniciando PPK em %s (solução: %s)", project_path, solution_type)

    only_path = (project_path / only_folder) if only_folder else None
    results = process_all_folders(
        project_path,
        config_override,
        base_dir=base_dir,
        solution_type=solution_type,
        only_folder=only_path,
    )
    logger.info("PPK concluído: %d arquivo(s) .pos gerado(s)", len(results))


def _run_interpolate(
    project_path: Path,
    orthometric: bool,
    only_folder: Optional[str] = None,
) -> Path:
    """Interpolate positions for every flight sub-folder and write combined JSON."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from avgeosys.core.interpolator import (
        interpolate_positions,
        load_pos_data,
        preprocess_and_read_mrk,
    )
    from avgeosys import config

    logger = logging.getLogger(__name__)
    folders = _flight_folders(project_path, only_folder)
    if not folders:
        logger.error("Nenhuma subpasta de voo encontrada em %s", project_path)
        sys.exit(1)

    def _interp_folder(folder: Path):
        mrk_path = _find_mrk_for_folder(folder)
        pos_path = _find_pos_for_folder(folder)
        if not mrk_path:
            logger.warning("Sem arquivo MRK em %s — ignorando", folder.name)
            return None
        if not pos_path:
            logger.warning("Sem arquivo .pos em %s — execute --ppk primeiro", folder.name)
            return None
        try:
            mrk_df = preprocess_and_read_mrk(mrk_path)
            pos_df = load_pos_data(pos_path)
            if pos_df.empty:
                logger.warning(".pos vazio para %s — ignorando", folder.name)
                return None
            records = interpolate_positions(mrk_df, pos_df, orthometric=orthometric)
            rel_folder = folder.relative_to(project_path).as_posix()
            for rec in records:
                rec["folder"] = rel_folder
            logger.info("Interpolado %s → %d fotos", folder.name, len(records))
            return records
        except Exception as exc:
            logger.error("Falha na interpolação de %s: %s", folder.name, exc)
            return None

    all_results: List[Dict] = []
    skipped = 0

    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
        futures = {executor.submit(_interp_folder, f): f for f in folders}
        for future in as_completed(futures):
            result = future.result()
            if result is None:
                skipped += 1
            else:
                all_results.extend(result)

    if not all_results:
        logger.error("Nenhum resultado produzido — verifique se o PPK foi executado com sucesso")
        sys.exit(1)

    if skipped:
        logger.warning("%d pasta(s) ignorada(s)", skipped)

    output_dir = project_path / "PPK_Results"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "interpolated_data.json"
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(all_results, fh, indent=2, ensure_ascii=False)

    logger.info("Wrote %d total records to %s", len(all_results), json_path)
    return json_path


def _run_geotag(project_path: Path, json_path: Path) -> None:
    from avgeosys.core.exif import batch_update_exif

    logger = logging.getLogger(__name__)
    with open(json_path, encoding="utf-8") as fh:
        data = json.load(fh)

    written, skipped = batch_update_exif(data, project_path)
    logger.info("Geotagging EXIF: %d gravado(s), %d ignorado(s)", written, skipped)


def _run_report(project_path: Path, json_path: Path) -> None:
    from avgeosys.core.report import generate_report_and_kmz

    logger = logging.getLogger(__name__)
    with open(json_path, encoding="utf-8") as fh:
        data = json.load(fh)
    output_dir = project_path / "PPK_Results"
    report, kmz1, kmz2 = generate_report_and_kmz(data, output_dir)
    logger.info("Relatório: %s", report)
    logger.info("KMZ (interpolado): %s", kmz1)
    logger.info("KMZ (EXIF): %s", kmz2)


# -----------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="avgeosys",
        description="AVGeoSys — PPK & EXIF Geotagging Tool",
    )
    parser.add_argument("PATH", type=Path, help="Project directory")
    parser.add_argument("--ppk", action="store_true", help="Run PPK processing")
    parser.add_argument("--interpolate", action="store_true", help="Interpolate positions")
    parser.add_argument("--geotag", action="store_true", help="Write GPS EXIF tags")
    parser.add_argument("--report", action="store_true", help="Generate quality report + KMZ")
    parser.add_argument(
        "--all", action="store_true", dest="run_all", help="Run full pipeline"
    )
    parser.add_argument(
        "--orthometric",
        action="store_true",
        help="Apply geoid correction (requires pyproj or uses approximation)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--skip-rover-nav",
        action="store_true",
        help="Skip rover navigation file (use base NAV only)",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help="Directory containing base station RINEX files (default: project root)",
    )
    parser.add_argument(
        "--folder",
        default=None,
        metavar="NAME",
        help="Process only the sub-folder with this name (e.g. DJI_202409240919_001)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate project structure without processing any files",
    )
    parser.add_argument(
        "--solution-type",
        choices=["forward", "backward", "combined"],
        default="forward",
        help="PPK solution type: forward (default), backward, or combined",
    )
    parser.add_argument(
        "--elevation-mask",
        type=int,
        default=None,
        metavar="DEG",
        help="Máscara de elevação de satélites em graus (padrão: 15)",
    )
    parser.add_argument(
        "--ar-threshold",
        type=float,
        default=None,
        metavar="VAL",
        help="Threshold de validação AR (padrão: 3.0; 0=desabilitado)",
    )
    parser.add_argument(
        "--nav-systems",
        default=None,
        metavar="SYS",
        help="Sistemas de navegação: G=GPS,R=GLONASS,E=Galileo,C=BeiDou (padrão: G,R,E,C)",
    )

    args = parser.parse_args()
    _setup_logging(args.verbose)

    project_path = Path(args.PATH).resolve()
    if not project_path.exists():
        print(f"ERRO: Caminho não existe: {project_path}", file=sys.stderr)
        sys.exit(1)
    if not project_path.is_dir():
        print(f"ERRO: Caminho não é um diretório: {project_path}", file=sys.stderr)
        sys.exit(1)

    # Dry run — validate and exit
    if args.dry_run:
        _setup_logging(True)  # always verbose in dry-run
        _run_dry_run(project_path, args.folder, args.base_dir)
        return

    config_override: dict = {}
    if args.skip_rover_nav:
        config_override["skip_rover_nav"] = True
    if args.elevation_mask is not None:
        config_override["elevation_mask"] = args.elevation_mask
    if args.ar_threshold is not None:
        config_override["ar_threshold"] = args.ar_threshold
    if args.nav_systems is not None:
        config_override["nav_systems"] = args.nav_systems

    run_ppk = args.ppk or args.run_all
    run_interp = args.interpolate or args.run_all
    run_geotag = args.geotag or args.run_all
    run_report = args.report or args.run_all

    if not any([run_ppk, run_interp, run_geotag, run_report]):
        parser.print_help()
        sys.exit(0)

    base_dir: Optional[Path] = args.base_dir
    only_folder: Optional[str] = args.folder

    json_path = project_path / "PPK_Results" / "interpolated_data.json"

    if run_ppk:
        _run_ppk(
            project_path,
            config_override,
            base_dir=base_dir,
            solution_type=args.solution_type,
            only_folder=only_folder,
        )

    if run_interp:
        json_path = _run_interpolate(project_path, args.orthometric, only_folder=only_folder)

    if run_geotag:
        if not json_path.exists():
            logging.getLogger(__name__).error(
                "interpolated_data.json não encontrado; execute --interpolate primeiro"
            )
            sys.exit(1)
        _run_geotag(project_path, json_path)

    if run_report:
        if not json_path.exists():
            logging.getLogger(__name__).error(
                "interpolated_data.json não encontrado; execute --interpolate primeiro"
            )
            sys.exit(1)
        _run_report(project_path, json_path)


if __name__ == "__main__":
    main()
