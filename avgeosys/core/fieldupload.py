"""
Limpeza in-place de pastas de voo para upload no FieldUpload.

Remove arquivos gerados pelo AVGeoSys de cada pasta de voo, deixando apenas
os arquivos originais (imagens JPEG, RINEX rover .obs/.nav/.bin, .MRK) e
zipa os arquivos de base RINEX na primeira pasta de voo.

Arquivos removidos das pastas de voo:
  .pos  — resultado PPK gerado pelo rnx2rtkp
  .tmp  — arquivos temporários

A pasta PPK_Results/ e eventuais subpastas geradas também são removidas
do diretório raiz do projeto.
"""

import logging
import shutil
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Extensões de arquivos GERADOS — devem ser removidos das pastas de voo
_GENERATED_EXTS = {".pos", ".tmp"}


def _is_generated(path: Path) -> bool:
    """Retorna True se o arquivo foi gerado pelo AVGeoSys e deve ser removido."""
    return path.is_file() and path.suffix.lower() in _GENERATED_EXTS


def _find_flight_folders(project_path: Path) -> List[Path]:
    """Busca recursiva de pastas de voo (contêm RINEX de observação)."""
    from avgeosys.core.ppk import find_flight_folders
    return find_flight_folders(project_path)


def _find_base_files(project_path: Path, base_dir: Optional[Path] = None) -> List[Path]:
    """Retorna arquivos RINEX da estação base (obs e nav) do diretório raiz."""
    from avgeosys.core.ppk import _is_obs_file, _is_nav_file

    search = Path(base_dir) if base_dir else project_path
    base_files = []
    for p in sorted(search.iterdir()):
        if not p.is_file():
            continue
        # Ignora arquivos do rover DJI
        if "_PPKOBS" in p.stem.upper() or "_PPKNAV" in p.stem.upper():
            continue
        if _is_obs_file(p) or _is_nav_file(p):
            base_files.append(p)
    return base_files


def prepare_field_upload(
    project_path: Path,
    base_dir: Optional[Path] = None,
    cancel_event=None,
    progress_callback=None,
) -> Tuple[int, int, int]:
    """Limpa pastas de voo in-place para upload no FieldUpload.

    Remove arquivos gerados (.pos, .tmp) de cada pasta de voo e zipa os
    arquivos de base RINEX na primeira pasta de voo. Também remove a pasta
    PPK_Results/ gerada pelo AVGeoSys.

    Args:
        project_path: Diretório raiz do projeto.
        base_dir: Diretório com arquivos de base (padrão: ``project_path``).
        cancel_event: threading.Event opcional para cancelamento.
        progress_callback: Callable(done, total) opcional.

    Returns:
        Tupla (pastas_limpas, arquivos_removidos, arquivos_base_zipados).
    """
    project_path = Path(project_path)

    flight_folders = _find_flight_folders(project_path)
    if not flight_folders:
        logger.warning("Nenhuma pasta de voo encontrada em %s", project_path)
        return 0, 0, 0

    base_files = _find_base_files(project_path, base_dir)
    if not base_files:
        logger.warning(
            "Nenhum arquivo de base RINEX encontrado em %s",
            base_dir or project_path,
        )

    logger.info("Iniciando limpeza FieldUpload in-place em: %s", project_path)

    # Total de operações para progresso: pastas + 1 (zip base) + 1 (PPK_Results)
    total_steps = len(flight_folders) + (1 if base_files else 0) + 1
    done = 0
    folders_cleaned = 0
    files_removed = 0

    # --- Limpar pastas de voo ---
    for folder in flight_folders:
        if cancel_event is not None and cancel_event.is_set():
            logger.warning("FieldUpload cancelado pelo usuário.")
            break

        removed_here = 0
        for f in sorted(folder.iterdir()):
            if _is_generated(f):
                try:
                    f.unlink()
                    files_removed += 1
                    removed_here += 1
                except OSError as exc:
                    logger.warning("Não foi possível remover %s: %s", f.name, exc)

        logger.info(
            "  %-50s → %d arquivo(s) removido(s)", folder.name[:50], removed_here
        )
        folders_cleaned += 1
        done += 1
        if progress_callback:
            progress_callback(done, total_steps)

    # --- Zipar arquivos de base na primeira pasta de voo ---
    base_files_zipped = 0
    if base_files and folders_cleaned > 0:
        if cancel_event is None or not cancel_event.is_set():
            first_folder = flight_folders[0]
            zip_path = first_folder / "base_station.zip"
            try:
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for bf in base_files:
                        zf.write(bf, bf.name)
                        base_files_zipped += 1
                logger.info(
                    "  Base zipada → %s/%s (%d arquivo(s))",
                    first_folder.name,
                    zip_path.name,
                    base_files_zipped,
                )
            except OSError as exc:
                logger.warning("Não foi possível criar base_station.zip: %s", exc)
            done += 1
            if progress_callback:
                progress_callback(done, total_steps)

    # --- Remover pasta PPK_Results/ ---
    ppk_results = project_path / "PPK_Results"
    if ppk_results.exists() and ppk_results.is_dir():
        if cancel_event is None or not cancel_event.is_set():
            try:
                shutil.rmtree(ppk_results)
                logger.info("  PPK_Results/ removida")
            except OSError as exc:
                logger.warning("Não foi possível remover PPK_Results/: %s", exc)
    done += 1
    if progress_callback:
        progress_callback(done, total_steps)

    logger.info(
        "FieldUpload concluído: %d pasta(s) limpas | %d arquivo(s) removido(s) | "
        "%d arquivo(s) de base zipado(s)",
        folders_cleaned,
        files_removed,
        base_files_zipped,
    )
    return folders_cleaned, files_removed, base_files_zipped
