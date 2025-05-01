import sys
from pathlib import Path

import pandas as pd
import pytest

from avgeosys.cli.cli import main as cli_main
import avgeosys.core.ppk as ppk_mod
import avgeosys.core.interpolator as interp_mod
import avgeosys.core.exif as exif_mod

@pytest.fixture
def setup_full(tmp_path):
    root = tmp_path
    # Cria um arquivo .MRK para reconhecimento pelo PPK
    mrk = root / "site_Timestamp.MRK"
    mrk.write_text("dummy")

    # Cria uma foto de exemplo que será geotagueada
    photo = root / "_0001_V.JPG"
    photo.write_text("")

    return root

def test_full_pipeline(tmp_path, setup_full, monkeypatch):
    root = setup_full

    # 1) Monkeypatch do PPK: cria PPK_Results e .pos
    def fake_process_single_folder(folder, base_obs, base_nav):
        out = folder / "PPK_Results"
        out.mkdir(parents=True, exist_ok=True)
        pos = out / "site_PPKOBS.pos"
        pos.write_text("dummy")
        return pos

    monkeypatch.setattr(ppk_mod, "process_single_folder", fake_process_single_folder)
    monkeypatch.setattr(ppk_mod, "find_base_files", lambda r: (Path("b"), Path("c")))

    # 2) Monkeypatch da interpolação
    monkeypatch.setattr(
        interp_mod, "preprocess_and_read_mrk",
        lambda mrk, od: pd.DataFrame({"index":[1],"time":[0],"lat":[0],"lon":[0],"height":[0]})
    )
    monkeypatch.setattr(
        interp_mod, "load_pos_data",
        lambda pos: pd.DataFrame({"seconds":[0],"lat":[0],"lon":[0],"height":[0],"quality":[1]})
    )
    monkeypatch.setattr(
        interp_mod, "interpolate_positions",
        lambda pos, mrk: [{
            "photo":"_0001_V.JPG",
            "lat":10.0,
            "lon":20.0,
            "height":30.0,
            "time":0.0,
            "quality":1
        }]
    )

    # 3) Monkeypatch do EXIF: não faz nada
    monkeypatch.setattr(exif_mod, "update_exif", lambda photo_path, lat, lon, height: None)

    # 4) Executa o CLI com --all
    monkeypatch.setattr(sys, "argv", ["avgeosys", str(root), "--all"])
    cli_main()

    # 5) Verifica artefatos finais
    assert (root / "relatorio_processamento.txt").exists(), "Relatório não gerado"
    assert (root / "resultado_interpolado.kmz").exists(), "KMZ de interpolação não gerado"
    assert (root / "compilado_exif_data.kmz").exists(), "KMZ de EXIF não gerado"
