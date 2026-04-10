"""
Organização de entregas SeeTree.

Fluxo:
1. Parseia os polígonos de FAZENDA do KMZ para determinar o nome da fazenda.
2. Para cada pasta de voo (DJI_*), extrai o número do talhão do nome da pasta
   ou dos pontos GPS do MRK cruzados com os polígonos de talhão do KMZ.
3. Agrupa voos pelo mesmo número de talhão (merged se > 1 voo).
4. Gera estrutura de entrega:

       CS_QUATRIRMAS_20260407/
           55.8_rgb_4/           (voo único, talhão 4)
           55.8_rgb_6_merged/    (3 voos, talhão 6)
               1/
               2/
               3/

5. Após confirmação, move arquivos in-place e renomeia a pasta raiz.
"""

import logging
import re
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------------

Polygon = List[Tuple[float, float]]  # lista de (lon, lat) — padrão KML


@dataclass
class FarmPolygon:
    name: str       # e.g. "FAZENDA QUATRIRMAS"
    polygon: Polygon


@dataclass
class TalhaoPolygon:
    name: str       # e.g. "4", "17" (conforme KMZ)
    polygon: Polygon


@dataclass
class FlightInfo:
    folder: Path
    mrk_points: List[Tuple[float, float]]   # (lat, lon) de cada evento
    talhao: str = ""                         # número do talhão (sem zeros)
    talhao_source: str = ""                  # "folder_name" ou "kmz"


@dataclass
class DeliveryGroup:
    talhao: str                 # número único do talhão
    flights: List[FlightInfo]   # voos neste talhão (ordenados por timestamp)
    folder_name: str = ""       # e.g. "55.8_rgb_4" ou "55.8_rgb_6_merged"
    is_merged: bool = False


@dataclass
class DeliveryPlan:
    project_dir: Path
    new_project_name: str       # e.g. "CS_QUATRIRMAS_20260407"
    farm_name: str              # e.g. "QUATRIRMAS"
    groups: List[DeliveryGroup]
    unmatched_flights: List[FlightInfo]
    imagens_dir: Path
    base_dir: Optional[Path]


# ---------------------------------------------------------------------------
# KMZ parsing (apenas fazendas; talhões como fallback)
# ---------------------------------------------------------------------------

def _parse_coords(raw: str) -> Polygon:
    """Converte string de coordenadas KML em lista de (lon, lat)."""
    polygon: Polygon = []
    for token in raw.split():
        parts = token.split(",")
        if len(parts) >= 2:
            try:
                polygon.append((float(parts[0]), float(parts[1])))
            except ValueError:
                pass
    return polygon


def parse_kmz(
    kmz_path: Path,
    include_talhoes: bool = False,
) -> Tuple[List[FarmPolygon], List[TalhaoPolygon]]:
    """Parseia um arquivo KMZ.

    Sempre retorna polígonos de fazenda.  Se ``include_talhoes=True``, parseia
    também os polígonos de talhão (mais lento — 6000+ polígonos).

    Os nomes de talhão são normalizados: strip ' active', strip zeros à esquerda
    para nomes puramente numéricos.  Duplicatas com o mesmo nome normalizado são
    deduplicas mantendo a versão 'active' (polígono operacional).
    """
    kmz_path = Path(kmz_path)
    with zipfile.ZipFile(kmz_path) as zf:
        kml_name = next(
            (n for n in zf.namelist() if n.lower().endswith(".kml")),
            "doc.kml",
        )
        with zf.open(kml_name) as fh:
            kml_bytes = fh.read()

    kml = kml_bytes.decode("utf-8", errors="replace")

    pm_pattern = re.compile(r"<Placemark[^>]*>(.*?)</Placemark>", re.DOTALL)
    name_pat = re.compile(r"<name>([^<]+)</name>")
    coords_pat = re.compile(r"<coordinates>\s*(.*?)\s*</coordinates>", re.DOTALL)
    poly_tag = re.compile(r"<Polygon[\s>]")

    farms: List[FarmPolygon] = []
    # Para talhões: dict norm_name → (is_active, TalhaoPolygon)
    talhao_dict: Dict[str, Tuple[bool, TalhaoPolygon]] = {}

    for pm_match in pm_pattern.finditer(kml):
        body = pm_match.group(1)
        if not poly_tag.search(body):
            continue

        nm = name_pat.search(body)
        if nm is None:
            continue
        raw_name = nm.group(1).strip()

        coords_m = coords_pat.search(body)
        if coords_m is None:
            continue

        polygon = _parse_coords(coords_m.group(1))
        if len(polygon) < 3:
            continue

        if raw_name.upper().startswith("FAZENDA "):
            farms.append(FarmPolygon(name=raw_name, polygon=polygon))
            continue

        if not include_talhoes:
            continue

        # Normaliza nome do talhão
        is_active = raw_name.endswith(" active")
        clean = raw_name.removesuffix(" active").strip()
        if not clean or clean.startswith("#"):
            continue
        # Strip leading zeros de nomes puramente numéricos
        if re.match(r"^\d+$", clean):
            clean = str(int(clean))

        existing = talhao_dict.get(clean)
        if existing is None or (is_active and not existing[0]):
            talhao_dict[clean] = (is_active, TalhaoPolygon(name=clean, polygon=polygon))

    talhoes = [t for _, t in talhao_dict.values()]
    logger.debug("KMZ: %d fazendas, %d talhões", len(farms), len(talhoes))
    return farms, talhoes


# ---------------------------------------------------------------------------
# Point-in-polygon (ray casting) — usado para fazendas e fallback de talhões
# ---------------------------------------------------------------------------

def point_in_polygon(lat: float, lon: float, polygon: Polygon) -> bool:
    """Ray-casting: (lat, lon) dentro do polígono (lon, lat) no padrão KML."""
    x, y = lon, lat
    inside = False
    px, py = polygon[-1]
    for qx, qy in polygon:
        if ((py > y) != (qy > y)) and (
            x < (qx - px) * (y - py) / (qy - py) + px
        ):
            inside = not inside
        px, py = qx, qy
    return inside


# ---------------------------------------------------------------------------
# MRK parsing
# ---------------------------------------------------------------------------

def read_mrk_coords(mrk_path: Path) -> List[Tuple[float, float]]:
    """Lê arquivo .MRK e retorna lista de (lat, lon) de cada evento."""
    points: List[Tuple[float, float]] = []
    lat_pat = re.compile(r"([-\d.]+),Lat")
    lon_pat = re.compile(r"([-\d.]+),Lon")
    try:
        with open(mrk_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                lm = lat_pat.search(line)
                lnm = lon_pat.search(line)
                if lm and lnm:
                    points.append((float(lm.group(1)), float(lnm.group(1))))
    except OSError as exc:
        logger.warning("Não foi possível ler MRK %s: %s", mrk_path, exc)
    return points


def _find_mrk(folder: Path) -> Optional[Path]:
    for f in folder.iterdir():
        if f.suffix.upper() == ".MRK":
            return f
    return None


# ---------------------------------------------------------------------------
# Extração do número do talhão a partir do nome da pasta DJI
# ---------------------------------------------------------------------------

# Padrão SeeTree: DJI_TIMESTAMP_SEQ_SeeTreeYYYY-FARMCODE-TALHAO-SEGMENT
_SEETREE_PATTERN = re.compile(r"-(\d{2,4})-\d+$")


def extract_talhao_from_folder(folder_name: str) -> str:
    """Extrai o número do talhão (sem zeros) do nome de uma pasta DJI.

    Para o padrão SeeTree ``*-NN-NN``, retorna o primeiro NN sem zeros.
    Retorna '' se o padrão não for reconhecido.
    """
    m = _SEETREE_PATTERN.search(folder_name)
    if m:
        return str(int(m.group(1)))  # strip leading zeros
    return ""


# ---------------------------------------------------------------------------
# Análise de voos
# ---------------------------------------------------------------------------

def analyze_flights(
    imagens_dir: Path,
    talhoes: Optional[List[TalhaoPolygon]] = None,
    threshold: float = 0.15,
) -> List[FlightInfo]:
    """Determina o talhão de cada pasta de voo em ``imagens_dir``.

    Estratégia:
    1. Tenta extrair o talhão do nome da pasta (padrão SeeTree).
    2. Se não encontrar e ``talhoes`` fornecido, usa point-in-polygon com MRK.
    """
    imagens_dir = Path(imagens_dir)
    flights: List[FlightInfo] = []

    dji_folders = sorted(
        p for p in imagens_dir.iterdir()
        if p.is_dir() and p.name.upper().startswith("DJI")
    )

    for folder in dji_folders:
        # --- Estratégia 1: nome da pasta ---
        talhao = extract_talhao_from_folder(folder.name)
        if talhao:
            mrk = _find_mrk(folder)
            pts = read_mrk_coords(mrk) if mrk else []
            flights.append(
                FlightInfo(
                    folder=folder,
                    mrk_points=pts,
                    talhao=talhao,
                    talhao_source="folder_name",
                )
            )
            logger.debug("  %s → talhão %s (pasta)", folder.name, talhao)
            continue

        # --- Estratégia 2: KMZ point-in-polygon ---
        mrk = _find_mrk(folder)
        if mrk is None:
            logger.warning("Sem .MRK e sem padrão SeeTree: %s", folder.name)
            flights.append(FlightInfo(folder=folder, mrk_points=[]))
            continue

        pts = read_mrk_coords(mrk)
        if not pts or talhoes is None:
            logger.warning(
                "Sem talhão para: %s (MRK=%d pts, talhoes_kmz=%s)",
                folder.name, len(pts), "fornecido" if talhoes else "não fornecido",
            )
            flights.append(FlightInfo(folder=folder, mrk_points=pts))
            continue

        best_talhao, best_frac = "", 0.0
        n_pts = len(pts)
        lats = [p[0] for p in pts]
        lons = [p[1] for p in pts]
        bbox = (min(lats) - 0.005, max(lats) + 0.005,
                min(lons) - 0.005, max(lons) + 0.005)

        for t in talhoes:
            # bbox pré-filtro
            t_lons = [p[0] for p in t.polygon]
            t_lats = [p[1] for p in t.polygon]
            if not (min(t_lons) <= bbox[3] and max(t_lons) >= bbox[2] and
                    min(t_lats) <= bbox[1] and max(t_lats) >= bbox[0]):
                continue
            inside = sum(1 for lat, lon in pts if point_in_polygon(lat, lon, t.polygon))
            frac = inside / n_pts
            if frac >= threshold and frac > best_frac:
                best_frac = frac
                best_talhao = t.name

        if best_talhao:
            logger.debug(
                "  %s → talhão %s (kmz %.1f%%)", folder.name, best_talhao, best_frac * 100
            )
        else:
            logger.warning("Sem talhão (kmz): %s", folder.name)

        flights.append(
            FlightInfo(
                folder=folder,
                mrk_points=pts,
                talhao=best_talhao,
                talhao_source="kmz" if best_talhao else "",
            )
        )

    return flights


# ---------------------------------------------------------------------------
# Determinação do nome da fazenda
# ---------------------------------------------------------------------------

def determine_farm_name(
    flights: List[FlightInfo],
    farms: List[FarmPolygon],
) -> str:
    """Retorna nome da fazenda (sem 'FAZENDA ') com base no centro dos voos."""
    if not farms:
        return "DESCONHECIDA"

    # Centróide de todos os pontos MRK
    all_lats, all_lons = [], []
    for fi in flights:
        for lat, lon in fi.mrk_points:
            all_lats.append(lat)
            all_lons.append(lon)

    if not all_lats:
        return "DESCONHECIDA"

    c_lat = sum(all_lats) / len(all_lats)
    c_lon = sum(all_lons) / len(all_lons)

    for farm in farms:
        if point_in_polygon(c_lat, c_lon, farm.polygon):
            return _strip_fazenda_prefix(farm.name)

    # Fallback: fazenda mais próxima
    def _dist(farm: FarmPolygon) -> float:
        avg_lon = sum(p[0] for p in farm.polygon) / len(farm.polygon)
        avg_lat = sum(p[1] for p in farm.polygon) / len(farm.polygon)
        return (avg_lat - c_lat) ** 2 + (avg_lon - c_lon) ** 2

    return _strip_fazenda_prefix(min(farms, key=_dist).name)


def _strip_fazenda_prefix(name: str) -> str:
    n = name.strip().upper()
    if n.startswith("FAZENDA "):
        n = n[8:]
    return n.strip()


# ---------------------------------------------------------------------------
# Agrupamento e nomenclatura
# ---------------------------------------------------------------------------

def _talhao_sort_key(name: str):
    try:
        return (0, int(name))
    except ValueError:
        return (1, name)


def group_flights(
    flights: List[FlightInfo],
) -> Tuple[List[DeliveryGroup], List[FlightInfo]]:
    """Agrupa voos pelo mesmo número de talhão.

    Retorna (grupos_ordenados, voos_sem_talhao).
    """
    matched: Dict[str, List[FlightInfo]] = {}
    unmatched: List[FlightInfo] = []

    for fi in flights:
        if not fi.talhao:
            unmatched.append(fi)
        else:
            matched.setdefault(fi.talhao, []).append(fi)

    groups: List[DeliveryGroup] = []
    for talhao in sorted(matched.keys(), key=_talhao_sort_key):
        group_flights_list = sorted(
            matched[talhao], key=lambda f: f.folder.name
        )
        groups.append(DeliveryGroup(talhao=talhao, flights=group_flights_list))

    return groups, unmatched


def build_folder_names(
    groups: List[DeliveryGroup],
    height: str,
    sensor: str = "rgb",
) -> None:
    """Preenche folder_name e is_merged em cada grupo (in-place)."""
    for g in groups:
        g.is_merged = len(g.flights) > 1
        suffix = "_merged" if g.is_merged else ""
        g.folder_name = f"{height}_{sensor}_{g.talhao}{suffix}"


# ---------------------------------------------------------------------------
# Data do projeto via EXIF
# ---------------------------------------------------------------------------

def get_project_date(flights: List[FlightInfo]) -> str:
    """Retorna data do projeto como AAAAMMDD via EXIF do primeiro JPEG."""
    for fi in sorted(flights, key=lambda f: f.folder.name):
        for jpg in sorted(fi.folder.iterdir()):
            if jpg.suffix.upper() not in (".JPG", ".JPEG"):
                continue
            date = _read_exif_date(jpg)
            if date:
                return date
    return ""


def _read_exif_date(jpg_path: Path) -> str:
    """Extrai DateTimeOriginal do EXIF. Retorna 'AAAAMMDD' ou ''."""
    try:
        import piexif
        exif = piexif.load(str(jpg_path))
        dto = exif.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal, b"")
        if isinstance(dto, bytes):
            dto = dto.decode("ascii", errors="replace")
        m = re.match(r"(\d{4}):(\d{2}):(\d{2})", dto)
        if m:
            return f"{m.group(1)}{m.group(2)}{m.group(3)}"
    except Exception:
        pass
    return ""


# ---------------------------------------------------------------------------
# Plano de entrega
# ---------------------------------------------------------------------------

def build_delivery_plan(
    project_dir: Path,
    kmz_path: Path,
    height: str,
    client_prefix: str,
    sensor: str = "rgb",
    threshold: float = 0.15,
) -> DeliveryPlan:
    """Analisa o projeto e retorna um plano de reorganização SeeTree."""
    project_dir = Path(project_dir)
    imagens_dir = project_dir / "IMAGENS"
    base_dir = project_dir / "BASE" if (project_dir / "BASE").exists() else None

    if not imagens_dir.exists():
        raise FileNotFoundError(f"Pasta IMAGENS não encontrada em: {project_dir}")

    # Parseia KMZ — apenas fazendas (rápido); talhões opcionais como fallback
    farms, _ = parse_kmz(kmz_path, include_talhoes=False)

    # Analisa voos (usa nome da pasta como fonte primária)
    flights = analyze_flights(imagens_dir, talhoes=None, threshold=threshold)

    # Se algum voo ficou sem talhão, tenta KMZ como fallback
    unresolved = [fi for fi in flights if not fi.talhao]
    if unresolved:
        logger.info(
            "%d voo(s) sem talhão no nome da pasta — carregando KMZ...", len(unresolved)
        )
        _, talhoes_kmz = parse_kmz(kmz_path, include_talhoes=True)
        if talhoes_kmz:
            for fi in unresolved:
                # Re-analisa individualmente via KMZ
                result = analyze_flights(
                    fi.folder.parent,
                    talhoes=talhoes_kmz,
                    threshold=threshold,
                )
                for r in result:
                    if r.folder == fi.folder and r.talhao:
                        fi.talhao = r.talhao
                        fi.talhao_source = "kmz"
                        break

    farm_name = determine_farm_name(flights, farms)

    date_str = get_project_date(flights)
    if not date_str:
        m = re.search(r"(\d{4})(\d{2})(\d{2})", project_dir.name)
        if m:
            date_str = f"{m.group(1)}{m.group(2)}{m.group(3)}"
        else:
            from datetime import date
            date_str = date.today().strftime("%Y%m%d")

    groups, unmatched = group_flights(flights)
    build_folder_names(groups, height=height, sensor=sensor)

    new_project_name = f"{client_prefix}_{farm_name}_{date_str}"

    return DeliveryPlan(
        project_dir=project_dir,
        new_project_name=new_project_name,
        farm_name=farm_name,
        groups=groups,
        unmatched_flights=unmatched,
        imagens_dir=imagens_dir,
        base_dir=base_dir,
    )


# ---------------------------------------------------------------------------
# Execução do plano
# ---------------------------------------------------------------------------

def execute_delivery(
    plan: DeliveryPlan,
    cancel_event=None,
    progress_callback=None,
) -> None:
    """Executa a reorganização de pastas conforme o plano.

    Operações (in-place, sem cópias):
    1. Move conteúdo de cada pasta DJI para a subpasta de entrega
       (remove .pos e _events.pos durante a movimentação)
    2. Zipa arquivos de base na primeira subpasta
    3. Remove PPK_Results/ e arquivos gerados na raiz de IMAGENS/
    4. Remove BASE/ (após zipar) e IMAGENS/ se vazia
    5. Renomeia pasta raiz do projeto
    """
    project_dir = plan.project_dir
    imagens_dir = plan.imagens_dir

    total_flights = sum(len(g.flights) for g in plan.groups)
    total_steps = total_flights + 4
    done = 0

    def _prog():
        nonlocal done
        done += 1
        if progress_callback:
            progress_callback(done, total_steps)

    def _cancelled():
        return cancel_event is not None and cancel_event.is_set()

    # 1. Mover conteúdo dos voos
    for group in plan.groups:
        for idx, fi in enumerate(group.flights, start=1):
            if _cancelled():
                return

            dest_dir = (
                imagens_dir / group.folder_name / str(idx)
                if group.is_merged
                else imagens_dir / group.folder_name
            )
            dest_dir.mkdir(parents=True, exist_ok=True)

            for item in list(fi.folder.iterdir()):
                name_lower = item.name.lower()
                # Remove arquivos PPK gerados — não vão para entrega
                if item.suffix.lower() == ".pos" or name_lower.endswith("_events.pos"):
                    try:
                        item.unlink()
                    except OSError:
                        pass
                    continue
                try:
                    shutil.move(str(item), str(dest_dir / item.name))
                except OSError as exc:
                    logger.warning("Erro ao mover %s: %s", item, exc)

            try:
                fi.folder.rmdir()
            except OSError:
                pass

            rel = dest_dir.relative_to(project_dir)
            logger.info("  %s → %s", fi.folder.name, rel)
            _prog()

    # 2. Zipar base
    if plan.base_dir and plan.base_dir.exists() and not _cancelled():
        base_files = [
            p for p in sorted(plan.base_dir.iterdir())
            if p.is_file() and not p.name.lower().endswith(".zip")
        ]
        if base_files and plan.groups:
            g0 = plan.groups[0]
            zip_dir = (
                imagens_dir / g0.folder_name / "1"
                if g0.is_merged
                else imagens_dir / g0.folder_name
            )
            zip_dir.mkdir(parents=True, exist_ok=True)
            zip_path = zip_dir / "base_station.zip"
            try:
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for bf in base_files:
                        zf.write(bf, bf.name)
                logger.info("  Base → %s", zip_path.relative_to(project_dir))
            except OSError as exc:
                logger.warning("Erro ao zipar base: %s", exc)
    _prog()

    # 3. Limpeza PPK_Results e arquivos gerados
    if not _cancelled():
        ppk = project_dir / "PPK_Results"
        if ppk.exists():
            try:
                shutil.rmtree(ppk)
            except OSError as exc:
                logger.warning("Erro ao remover PPK_Results/: %s", exc)
        for f in list(imagens_dir.iterdir()):
            if f.is_file() and f.suffix.lower() in (".pos", ".txt", ".kmz"):
                try:
                    f.unlink()
                except OSError:
                    pass
    _prog()

    # 4. Remover BASE/ e arquivos auxiliares da raiz
    if not _cancelled():
        if plan.base_dir and plan.base_dir.exists():
            for p in list(plan.base_dir.iterdir()):
                if p.is_file():
                    try:
                        p.unlink()
                    except OSError:
                        pass
            try:
                plan.base_dir.rmdir()
            except OSError:
                pass
        for fname in ("sync.ffs_db",):
            f = project_dir / fname
            if f.exists():
                try:
                    f.unlink()
                except OSError:
                    pass
    _prog()

    # 5. Renomear pasta raiz
    if not _cancelled():
        new_path = project_dir.parent / plan.new_project_name
        if new_path != project_dir:
            try:
                project_dir.rename(new_path)
                logger.info("%s → %s", project_dir.name, plan.new_project_name)
            except OSError as exc:
                logger.warning("Erro ao renomear projeto: %s", exc)
    _prog()

    logger.info(
        "Entrega organizada: %d grupo(s), %d voo(s)",
        len(plan.groups),
        total_flights,
    )
