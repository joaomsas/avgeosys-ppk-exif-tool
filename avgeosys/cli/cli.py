"""
Interface de linha de comando para AVGeoSys.
"""

import argparse
import json
import logging
from pathlib import Path

from avgeosys import __version__
from avgeosys.core.ppk import process_all_folders
from avgeosys.core.interpolator import (
    preprocess_and_read_mrk,
    load_pos_data,
    interpolate_positions,
)
from avgeosys.core.exif import update_exif, generate_exif_kmz
from avgeosys.core.report import generate_report_and_kmz


def setup_logging(debug: bool):
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        level=level,
    )


def cmd_ppk(path: Path):
    logging.info("Iniciando PPK...")
    process_all_folders(path)


def cmd_interpolate(path: Path):
    logging.info("Iniciando interpolação...")
    for rd in path.rglob("PPK_Results"):
        mrk = next(rd.parent.glob("*_Timestamp.MRK"), None)
        pos = next(rd.glob("*.pos"), None)
        if not mrk or not pos:
            continue
        mrk_df = preprocess_and_read_mrk(mrk, rd)
        pos_df = load_pos_data(pos)
        if mrk_df.empty or pos_df.empty:
            continue
        interp = interpolate_positions(pos_df, mrk_df)
        output_file = rd / "interpolated_data.json"
        with open(output_file, "w") as f:
            json.dump(interp, f, indent=4)
        logging.info(
            f"Interpolação salva em {output_file}"
        )


def cmd_geotag(path: Path):
    logging.info("Iniciando geotagging...")
    for rd in path.rglob("PPK_Results"):
        jf = rd / "interpolated_data.json"
        if not jf.exists():
            continue
        data = json.loads(jf.read_text())
        for e in data:
            photo = next(rd.parent.glob(f"*{e['photo']}"), None)
            if photo:
                update_exif(photo, e["lat"], e["lon"], e["height"])
    kmz_path = generate_exif_kmz(path)
    logging.info(f"KMZ de EXIF: {kmz_path}")


def cmd_report(path: Path):
    logging.info("Gerando relatório e KMZ de interpolação...")
    generate_report_and_kmz(path)
    logging.info("Relatório e KMZ gerados.")


def main():
    p = argparse.ArgumentParser(
        prog="avgeosys",
        description="AVGeoSys - PPK & EXIF Tool",
    )
    p.add_argument(
        "path",
        type=Path,
        help="Diretório raiz do projeto",
    )
    p.add_argument(
        "--version",
        action="version",
        version=__version__,
    )
    p.add_argument(
        "--ppk",
        action="store_true",
        help="Processamento PPK",
    )
    p.add_argument(
        "--interpolate",
        action="store_true",
        help="Interpolação de posições",
    )
    p.add_argument(
        "--geotag",
        action="store_true",
        help="Atualizar EXIF e gerar KMZ",
    )
    p.add_argument(
        "--report",
        action="store_true",
        help="Gerar relatório de PPK",
    )
    p.add_argument(
        "--all",
        action="store_true",
        help="Executar todas as etapas",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Logs em DEBUG",
    )
    args = p.parse_args()

    setup_logging(args.verbose)

    if args.all or args.ppk:
        cmd_ppk(args.path)
    if args.all or args.interpretate:
        cmd_interpolate(args.path)
    if args.all or args.geotag:
        cmd_geotag(args.path)
    if args.all or args.report:
        cmd_report(args.path)


if __name__ == "__main__":
    main()
