"""
RTKLIB wrapper — runs rnx2rtkp to produce .pos PPK solution files.
"""

import logging
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional

from avgeosys import config

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when a required configuration value is missing or invalid."""


def _is_obs_file(path: Path) -> bool:
    """Return True if *path* looks like a RINEX observation file."""
    s = path.suffix.upper()
    return (s.endswith("O") and len(s) == 4) or s == ".OBS"


def _is_nav_file(path: Path) -> bool:
    """Return True if *path* looks like a RINEX navigation file."""
    s = path.suffix.upper()
    return (s.endswith(("P", "N")) and len(s) == 4) or s in (".NAV", ".P")


def _is_ppkobs(path: Path) -> bool:
    """True if filename contains _PPKOBS (rover observation, DJI convention)."""
    return "_PPKOBS" in path.stem.upper()


def _is_ppknav(path: Path) -> bool:
    """True if filename contains _PPKNAV (rover navigation, DJI convention)."""
    return "_PPKNAV" in path.stem.upper()


_SKIP_DIRS = {"PPK_Results", "FieldUpload", "_internal", "__pycache__", ".git"}


def find_flight_folders(
    project_path: Path,
    only_folder: Optional[str] = None,
) -> List[Path]:
    """Busca recursiva de pastas de voo contendo arquivos RINEX de observação.

    Percorre subpastas em qualquer profundidade, ignorando pastas geradas pelo
    AVGeoSys (PPK_Results, FieldUpload) e pastas de sistema.

    Args:
        project_path: Raiz do projeto.
        only_folder: Se informado, retorna apenas a pasta com esse nome.

    Returns:
        Lista ordenada de caminhos de pastas de voo.
    """
    project_path = Path(project_path)
    seen: set = set()
    folders: List[Path] = []

    for p in sorted(project_path.rglob("*")):
        if not p.is_file():
            continue
        # Ignora arquivos dentro de pastas geradas ou de sistema
        rel_parts = p.relative_to(project_path).parts
        if any(part in _SKIP_DIRS for part in rel_parts):
            continue
        if _is_ppkobs(p) or _is_obs_file(p):
            folder = p.parent
            if folder not in seen and folder != project_path:
                if only_folder is None or folder.name == only_folder:
                    seen.add(folder)
                    folders.append(folder)

    return sorted(folders)


def find_base_files(
    folder: Path,
    base_dir: Optional[Path] = None,
) -> Dict[str, Optional[Path]]:
    """Locate RINEX observation, navigation and MRK files.

    Searches *folder* for rover files, and *base_dir* (or *folder*'s parent)
    for base station files when not found inside *folder*.

    Returns a dict with keys:
        ``rover_obs``  — rover RINEX observation (.YYO / _PPKOBS.obs)
        ``rover_nav``  — rover RINEX navigation (_PPKNAV.nav), may be None
        ``base_obs``   — base station RINEX observation
        ``base_nav``   — base station RINEX navigation
        ``mrk``        — MRK timestamp file
    """
    folder = Path(folder)
    result: Dict[str, Optional[Path]] = {
        "rover_obs": None,
        "rover_nav": None,
        "base_obs": None,
        "base_nav": None,
        "mrk": None,
    }

    # --- Search rover folder ---
    folder_obs: List[Path] = []
    folder_navs: List[Path] = []
    for p in folder.iterdir():
        if not p.is_file():
            continue
        if _is_ppkobs(p):
            result["rover_obs"] = p
        elif _is_ppknav(p):
            result["rover_nav"] = p
        elif _is_obs_file(p):
            folder_obs.append(p)
        elif _is_nav_file(p):
            folder_navs.append(p)
        elif p.suffix.upper() == ".MRK":
            result["mrk"] = p

    # Fallback: if no _PPKOBS found, use obs files sorted (first = rover)
    if result["rover_obs"] is None and folder_obs:
        folder_obs.sort()
        result["rover_obs"] = folder_obs[0]
        if len(folder_obs) >= 2:
            result["base_obs"] = folder_obs[1]

    # --- Search for base station RINEX ---
    # Look in base_dir (if provided), then project root (folder.parent)
    if result["base_obs"] is None:
        search_dirs: List[Path] = []
        if base_dir:
            search_dirs.append(Path(base_dir))
        search_dirs.append(folder.parent)

        for d in search_dirs:
            if not d.is_dir():
                continue
            base_obs_found: List[Path] = []
            base_nav_found: List[Path] = []
            for p in d.iterdir():
                if not p.is_file():
                    continue
                # Skip files that look like rover/DJI files
                if "_PPKOBS" in p.stem.upper() or "_PPKNAV" in p.stem.upper():
                    continue
                if _is_obs_file(p):
                    base_obs_found.append(p)
                elif _is_nav_file(p):
                    base_nav_found.append(p)
            if base_obs_found:
                result["base_obs"] = sorted(base_obs_found)[0]
                if base_nav_found:
                    result["base_nav"] = sorted(base_nav_found)[0]
                logger.debug("RINEX da base encontrado em %s: obs=%s", d, result["base_obs"])
                break

    return result


def _read_approx_xyz(rinex_path: Path) -> Optional[bytes]:
    """Return the raw APPROX POSITION XYZ line bytes from a RINEX file, or None."""
    MARKER = b"END OF HEADER"
    try:
        with open(rinex_path, "rb") as fh:
            for line in fh:
                if MARKER in line:
                    break
                if b"APPROX POSITION XYZ" in line:
                    return line
    except OSError:
        pass
    return None


def _strip_rinex_padding(src: Path, dst: Path, approx_xyz: Optional[bytes] = None) -> None:
    """Copy a RINEX obs file to *dst* with DJI-specific fixes applied.

    Two issues are corrected:

    1. **Blank padding**: DJI Mavic RINEX 3.05 files contain ~14 KB of blank/space
       lines between the END OF HEADER marker and the first epoch record.  RTKLIB
       demo5 stops reading when it encounters these lines and reports
       "error : no obs data".

    2. **Zero APPROX POSITION XYZ**: DJI fills this field with zeros.  RTKLIB uses
       this value to compute satellite elevation angles for the elevation mask; with
       all zeros (geocenter) the mask rejects almost all satellites.  When the
       rover's APPROX POSITION XYZ is zero and *approx_xyz* (base station
       coordinates) is provided, the rover header line is replaced so that RTKLIB
       has a reasonable starting position.
    """
    MARKER = b"END OF HEADER"
    APPROX_TAG = b"APPROX POSITION XYZ"
    ZERO_XYZ = b"        0.0000        0.0000        0.0000"

    with open(src, "rb") as fh:
        raw = fh.read()

    marker_pos = raw.find(MARKER)
    if marker_pos == -1:
        dst.write_bytes(raw)
        return

    eoh_line_end = raw.find(b"\n", marker_pos)
    if eoh_line_end == -1:
        dst.write_bytes(raw)
        return

    # Split into header lines and patch if needed
    header_raw = raw[: eoh_line_end + 1]
    if approx_xyz is not None and ZERO_XYZ in header_raw:
        # Replace the APPROX POSITION XYZ line with the base station line
        lines = header_raw.split(b"\n")
        patched = []
        for line in lines:
            if APPROX_TAG in line and ZERO_XYZ in line:
                patched.append(approx_xyz.rstrip(b"\r\n"))
            else:
                patched.append(line)
        header_raw = b"\n".join(patched)

    # Skip blank/whitespace-only content until the first epoch marker '>'
    data_start = eoh_line_end + 1
    while data_start < len(raw) and raw[data_start : data_start + 1] in (
        b" ", b"\t", b"\r", b"\n",
    ):
        data_start += 1

    with open(dst, "wb") as fh:
        fh.write(header_raw)
        fh.write(raw[data_start:])


def process_single_folder(
    folder: Path,
    config_override: dict,
    base_dir: Optional[Path] = None,
    solution_type: str = "forward",
) -> Optional[Path]:
    """Run rnx2rtkp on a single folder and return the path to the .pos output.

    Args:
        folder: Directory containing RINEX + MRK files.
        config_override: Reserved for future per-folder config overrides.
        base_dir: Optional directory to search for base station RINEX files.
                  Defaults to searching the project root (folder.parent).
        solution_type: ``"forward"`` (default), ``"backward"``, or
                       ``"combined"`` (forward + backward merged).

    Returns:
        Path to the generated .pos file, or ``None`` on failure.
    """
    folder = Path(folder)
    rtklib = Path(config.RTKLIB_PATH)

    if not rtklib.exists():
        logger.error(
            "rnx2rtkp não encontrado em %s — configure RTKLIB_PATH em avgeosys/config.py",
            rtklib,
        )
        return None

    files = find_base_files(folder, base_dir=base_dir)
    if not files["rover_obs"]:
        logger.warning("Nenhum arquivo de observação rover encontrado em %s", folder)
        return None

    if not files["base_obs"]:
        logger.warning(
            "RINEX da estação base não encontrado para %s — PPK requer base+rover. "
            "Coloque os arquivos .obs/.nav da base na raiz do projeto ou use --base-dir.",
            folder.name,
        )
        # Continua mesmo assim — rnx2rtkp processará em modo SPP (posicionamento simples)

    output_pos = folder / (folder.name + ".pos")

    # Ler parâmetros PPK: config_override tem prioridade sobre config.py
    elev_mask = str(config_override.get(
        "elevation_mask", getattr(config, "PPK_ELEVATION_MASK", 15)
    ))
    ar_threshold = str(config_override.get(
        "ar_threshold", getattr(config, "PPK_AR_THRESHOLD", 3.0)
    ))
    nav_systems = str(config_override.get(
        "nav_systems", getattr(config, "PPK_NAV_SYSTEMS", "G,R,E,C")
    ))

    # Arquivos DJI RINEX têm ~14 KB de espaços em branco após END OF HEADER e
    # APPROX POSITION XYZ = 0/0/0. Copia para temp corrigido antes de processar.
    base_approx_xyz = _read_approx_xyz(files["base_obs"]) if files["base_obs"] else None

    # Usa TemporaryDirectory para garantir limpeza mesmo em caso de erro
    with tempfile.TemporaryDirectory(prefix="avgeosys_ppk_") as _tmpdir:
        tmp_rover = Path(_tmpdir) / files["rover_obs"].name
        _strip_rinex_padding(files["rover_obs"], tmp_rover, approx_xyz=base_approx_xyz)

        # NOTA: Flag -k conf NÃO é usado — este binário rnx2rtkp (demo5 b34k)
        # produz apenas 2-3 épocas quando carrega conf via -k (bug do binário).
        # Todas as opções são passadas diretamente como flags de linha de comando.
        cmd = [
            str(rtklib),
            "-p", "2",              # modo cinemático PPK
            "-f", "2",              # L1+L2
            "-m", elev_mask,        # máscara de elevação
            "-sys", nav_systems,    # sistemas de navegação
            "-v", ar_threshold,     # threshold AR
        ]
        if solution_type == "backward":
            cmd.append("-b")
        elif solution_type == "combined":
            cmd.append("-c")

        cmd += ["-o", str(output_pos)]
        cmd.append(str(tmp_rover))
        if files["base_obs"]:
            cmd.append(str(files["base_obs"]))
        if files["base_nav"]:
            cmd.append(str(files["base_nav"]))
        if files["rover_nav"]:
            cmd.append(str(files["rover_nav"]))

        kwargs: dict = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

        # Mostra path relativo (pai/nome) para distinguir pastas com mesmo nome
        display_name = f"{folder.parent.name}/{folder.name}" if folder.parent != folder else folder.name
        logger.info("Processando PPK: %s", display_name)
        logger.debug("Comando: %s", " ".join(cmd))
        try:
            timeout = getattr(config, "PPK_TIMEOUT", None)
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout,
                **kwargs,
            )
        except subprocess.TimeoutExpired:
            logger.error(
                "Timeout (%ds) ao processar %s — verifique os arquivos RINEX",
                getattr(config, "PPK_TIMEOUT", "?"),
                folder.name,
            )
            return None
        except Exception as exc:
            logger.error("Falha ao executar rnx2rtkp em %s: %s", folder, exc)
            return None

    # --- Temp dir já foi limpo pelo context manager ---

    if result.returncode != 0:
        logger.error(
            "rnx2rtkp retornou %d para %s\nstderr: %s",
            result.returncode,
            folder.name,
            result.stderr.decode("utf-8", errors="replace"),
        )
        return None

    # Valida que o .pos contém dados reais com campos suficientes
    lines_with_data = 0
    try:
        with open(output_pos, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("%") or not line.strip():
                    continue
                parts = line.split()
                if len(parts) >= 6:
                    lines_with_data += 1
    except OSError:
        pass

    if lines_with_data == 0:
        logger.warning(
            "PPK gerou .pos vazio para %s — verifique o RINEX da estação base",
            folder.name,
        )
        return None

    logger.info("PPK concluído: %s/%s (%d épocas)", folder.parent.name, output_pos.name, lines_with_data)
    return output_pos


def process_all_folders(
    project_path: Path,
    config_override: dict,
    base_dir: Optional[Path] = None,
    solution_type: str = "forward",
    only_folder: Optional[Path] = None,
    progress_callback=None,
) -> List[Path]:
    """Process sub-folders of *project_path* in parallel.

    Args:
        project_path: Root project directory containing sub-folders with RINEX data.
        config_override: Passed through to :func:`process_single_folder`.
        base_dir: Optional explicit directory with base station RINEX files.
                  Defaults to *project_path* itself.
        solution_type: ``"forward"``, ``"backward"``, or ``"combined"``.
        only_folder: If set, process only this specific sub-folder.
        progress_callback: Callable(done, total) opcional para progresso granular.

    Returns:
        List of successfully generated .pos file paths.
    """
    project_path = Path(project_path)
    effective_base_dir = Path(base_dir) if base_dir else project_path

    if only_folder is not None:
        folders = [Path(only_folder)]
    else:
        folders = find_flight_folders(project_path)

    if not folders:
        logger.warning("Nenhuma subpasta encontrada em %s", project_path)
        return []

    total = len(folders)
    done_count = 0
    results: List[Path] = []
    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as executor:
        futures = {
            executor.submit(
                process_single_folder, f, config_override, effective_base_dir, solution_type
            ): f
            for f in folders
        }
        for future in as_completed(futures):
            pos = future.result()
            done_count += 1
            if pos is not None:
                results.append(pos)
            if progress_callback is not None:
                progress_callback(done_count, total)

    if results:
        _log_ppk_quality_summary(results, project_path=project_path)

    return results


def _log_ppk_quality_summary(pos_files: List[Path], project_path: Optional[Path] = None) -> None:
    """Read all .pos files and log a quality summary (epochs, Fixed%, Float%)."""
    total = fixed = float_ = unknown = 0
    per_folder = []

    for pos_path in sorted(pos_files):
        f_total = f_fixed = f_float = f_unk = 0
        try:
            with open(pos_path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if line.startswith("%") or not line.strip():
                        continue
                    parts = line.split()
                    if len(parts) < 6:
                        continue
                    try:
                        q = int(parts[5])
                    except ValueError:
                        continue
                    f_total += 1
                    if q == 1:
                        f_fixed += 1
                    elif q == 2:
                        f_float += 1
                    else:
                        f_unk += 1
        except OSError:
            continue

        total += f_total
        fixed += f_fixed
        float_ += f_float
        unknown += f_unk
        # Caminho relativo à raiz do projeto para distinguir pastas com mesmo nome
        if project_path:
            try:
                display = str(pos_path.parent.relative_to(project_path))
            except ValueError:
                display = f"{pos_path.parent.parent.name}/{pos_path.parent.name}"
        else:
            display = f"{pos_path.parent.parent.name}/{pos_path.parent.name}"
        per_folder.append((display, f_total, f_fixed, f_float, f_unk))

    if total == 0:
        logger.warning("PPK summary: nenhuma época válida encontrada nos arquivos .pos")
        return

    logger.info(
        "PPK summary — %d pastas  |  %d épocas totais  |  "
        "Fixed: %d (%.1f%%)  Float: %d (%.1f%%)  Other: %d (%.1f%%)",
        len(pos_files),
        total,
        fixed, fixed / total * 100,
        float_, float_ / total * 100,
        unknown, unknown / total * 100,
    )
    logger.info("%-52s  %7s  %8s  %8s", "Pasta", "Épocas", "Fixed%", "Float%")
    logger.info("-" * 80)
    for name, ft, ff, fl, fu in per_folder:
        logger.info(
            "  %-50s  %7d  %7.1f%%  %7.1f%%",
            name[:50],
            ft,
            ff / ft * 100 if ft else 0,
            fl / ft * 100 if ft else 0,
        )
