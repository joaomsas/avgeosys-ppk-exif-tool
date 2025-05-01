"""
Geração de relatório de PPK e KMZ de interpolação.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import simplekml


def generate_report_and_kmz(
    root_folder: Path,
    kmz_path: Optional[Path] = None,
) -> None:
    """
    Gera o arquivo relatorio_processamento.txt e o KMZ
    de resultados na raiz de root_folder.
    """
    report_file = root_folder / "relatorio_processamento.txt"
    if kmz_path is None:
        kmz_path = root_folder / "resultado_interpolado.kmz"

    kml = simplekml.Kml()
    total = fixed = flt = unk = 0

    try:
        with report_file.open("w", encoding="utf-8") as rpt:
            rpt.write("Relatório de Processamento PPK\n")
            rpt.write(
                "Data e Hora: "
                f"{datetime.now():%Y-%m-%d %H:%M:%S}\n"
            )
            rpt.write("=" * 50 + "\n\n")

            for res in root_folder.rglob("PPK_Results"):
                jf = res / "interpolated_data.json"
                if not jf.exists():
                    continue

                data = json.loads(jf.read_text())
                n = len(data)
                f = sum(1 for p in data if p.get("quality") == 1)
                fl = sum(1 for p in data if p.get("quality") == 2)
                u = n - f - fl

                rpt.write(f"Pasta: {res.parent}\n")
                rpt.write(f"- Total de pontos: {n}\n")
                rpt.write(
                    f"- Fixos (Q=1): {f} ({f/n*100:.2f}%)\n"
                )
                rpt.write(
                    f"- Flutuantes (Q=2): {fl} ({fl/n*100:.2f}%)\n"
                )
                rpt.write(
                    f"- Desconhecidos: {u} ({u/n*100:.2f}%)\n\n"
                )

                total += n
                fixed += f
                flt += fl
                unk += u

                for p in data:
                    pt = kml.newpoint(coords=[(p["lon"], p["lat"])])
                    pt.style.iconstyle.color = (
                        simplekml.Color.green
                        if p.get("quality") == 1
                        else (
                            simplekml.Color.yellow
                            if p.get("quality") == 2
                            else simplekml.Color.red
                        )
                    )

            if total > 0:
                rpt.write("Resumo Geral\n")
                rpt.write("=" * 50 + "\n")
                rpt.write(f"Total de pontos: {total}\n")
                rpt.write(
                    f"Fixos: {fixed} ({fixed/total*100:.2f}%)\n"
                )
                rpt.write(
                    f"Flutuantes: {flt} ({flt/total*100:.2f}%)\n"
                )
                rpt.write(
                    f"Desconhecidos: {unk} ({unk/total*100:.2f}%)\n"
                )

        kml.savekmz(str(kmz_path))
        logging.info(f"Relatório salvo em {report_file.name}")
        logging.info(f"KMZ salvo em {kmz_path.name}")
    except Exception as e:
        logging.error(f"Erro ao gerar relatório e KMZ: {e}")
