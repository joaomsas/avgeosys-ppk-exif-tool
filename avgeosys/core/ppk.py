"""
Módulo de processamento PPK usando RTKLIB.
"""

import os
import subprocess
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple, Optional

from avgeosys.config import RINEX2RTKP_PATH


def find_base_files(
    root_folder: Path,
) -> Tuple[Path, Path]:
    """
    Busca arquivos base de observações (sufixo 'YYO') e efemérides ('YYP'),
    selecionando automaticamente os de maior ano disponível.
    Retorna (obs_file, nav_file).
    """
    obs_candidates = list(root_folder.glob("*[0-9][0-9]O"))
    nav_candidates = list(root_folder.glob("*[0-9][0-9]P"))
    if not obs_candidates or not nav_candidates:
        raise FileNotFoundError(
            f"Arquivos base (YYO e YYP) não encontrados em {root_folder}"
        )

    def year_from_path(path: Path) -> int:
        try:
            return int(path.suffix[1:3])
        except ValueError:
            return -1

    base_obs = max(obs_candidates, key=year_from_path)
    base_nav = max(nav_candidates, key=year_from_path)
    logging.info(
        f"Selecionados arquivos base: OBS={base_obs.name}, "
        f"NAV={base_nav.name}"
    )
    return base_obs, base_nav


def process_single_folder(
    folder: Path,
    base_obs: Path,
    base_nav: Path,
) -> Path:
    """
    Executa o processamento PPK em uma única subpasta usando rnx2rtkp.
    Gera o arquivo .pos em folder/PPK_Results.
    Retorna o Path do .pos gerado.
    """
    output_dir = folder / "PPK_Results"
    output_dir.mkdir(parents=True, exist_ok=True)

    rover_obs = next(folder.glob("*.obs"), None)
    if rover_obs is None:
        raise FileNotFoundError(f"Arquivo .obs não encontrado em {folder}")

    pos_output = output_dir / f"{rover_obs.stem}_PPKOBS.pos"
    cmd = [
        str(RINEX2RTKP_PATH),
        "-o",
        str(pos_output),
        str(rover_obs),
        str(base_obs),
        str(base_nav),
    ]
    logging.debug(
        f"Executando comando PPK: {' '.join(cmd)}"
    )

    # Oculta janela no Windows
    si = subprocess.STARTUPINFO() if os.name == "nt" else None
    if si:
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE

    subprocess.run(
        cmd,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        startupinfo=si,
    )
    return pos_output


def process_all_folders(
    root_folder: Path,
    max_workers: Optional[int] = None,
) -> None:
    """
    Processa todas as subpastas em root_folder que contenham
    arquivos _Timestamp.MRK.
    Paraleliza via ThreadPoolExecutor.
    """
    base_obs, base_nav = find_base_files(root_folder)
    workers = max_workers or os.cpu_count()

    futures = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for folder, _, files in os.walk(root_folder):
            if any(f.endswith("_Timestamp.MRK") for f in files):
                folder_path = Path(folder)
                futures[
                    executor.submit(
                        process_single_folder,
                        folder_path,
                        base_obs,
                        base_nav,
                    )
                ] = folder_path

        for future in as_completed(futures):
            folder_path = futures[future]
            try:
                pos_file = future.result()
                logging.info(f"PPK concluído: {pos_file}")
            except Exception as exc:
                logging.error(f"Erro no processamento de {folder_path}: {exc}")
