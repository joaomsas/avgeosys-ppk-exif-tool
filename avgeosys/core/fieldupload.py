import shutil
import zipfile
import logging
from pathlib import Path
from typing import List


def field_upload(root_folder: Path) -> Path:
    """
    Remove todas as pastas 'PPK_Results' em root_folder,
    empacota os arquivos base (.B, .O, .P) mais recentes em um ZIP
    dentro da primeira subpasta com fotos, e limpa arquivos auxiliares.
    Retorna o Path para o ZIP gerado.
    """
    # 1) Remove PPK_Results
    for rr in root_folder.rglob("PPK_Results"):
        shutil.rmtree(rr)
        logging.info(f"Removido: {rr}")

    # 2) Encontra o arquivo base mais recente para cada extensão
    base_files: List[Path] = []
    for ext in ("B", "O", "P"):
        cands = list(root_folder.glob(f"*??{ext}"))
        if cands:
            # Máximo pelo número do sufixo (p.ex. .21O > .20O)
            bf = max(cands, key=lambda p: int(p.suffix[1:3]))
            base_files.append(bf)

    # 3) Encontra a primeira subpasta com fotos
    first_sub = next(
        (
            sub
            for sub in sorted(root_folder.iterdir())
            if sub.is_dir() and any(sub.glob("*.jpg"))
        ),
        None,
    )
    if not first_sub:
        raise FileNotFoundError(
            "Nenhuma subpasta com fotos processadas encontrada."
        )

    # 4) Gera o ZIP dos arquivos base
    zip_path = first_sub / "base_rinex.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for bf in base_files:
            zf.write(bf, bf.name)
            logging.info(f"ZIP: {bf.name}")

    # 5) Limpa arquivos base originais
    for bf in base_files:
        bf.unlink()

    # 6) Remove arquivos de relatório/KMZ anteriores
    for fn in (
        "compilado_exif_data.kmz",
        "relatorio_processamento.txt",
        "resultado_interpolado.kmz",
    ):
        fp = root_folder / fn
        if fp.exists():
            fp.unlink()

    logging.info("FieldUpload concluído.")
    return zip_path
