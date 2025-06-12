import json
from pathlib import Path
import zipfile
import pytest
from avgeosys.core.report import generate_report_and_kmz

def write_interpolated(ppk_dir: Path, data):
    ppk_dir.mkdir(parents=True, exist_ok=True)
    interp_file = ppk_dir / "interpolated_data.json"
    interp_file.write_text(json.dumps(data))

@pytest.fixture
def setup_report(tmp_path):
    root = tmp_path
    # site1 with 2 points: one fixed (Q=1), one float (Q=2)
    site1 = root / "site1"
    write_interpolated(site1 / "PPK_Results", [
        {"lon": 10.0, "lat": 20.0, "quality": 1},
        {"lon": 30.0, "lat": 40.0, "quality": 2},
    ])
    # site2 with 1 point: unknown quality (Q=3)
    site2 = root / "site2"
    write_interpolated(site2 / "PPK_Results", [
        {"lon": 50.0, "lat": 60.0, "quality": 3},
    ])
    return root

def test_generate_report_and_kmz(tmp_path, setup_report):
    root = setup_report
    # Generate report and KMZ
    generate_report_and_kmz(root)

    # Check report file
    report_file = root / "relatorio_processamento.txt"
    assert report_file.exists(), "Relatório não foi criado"
    content = report_file.read_text()
    # Site1 checks
    assert "Pasta: " in content
    assert "site1" in content
    assert "- Total de pontos: 2" in content
    assert "- Fixos (Q=1): 1 (50.00%)" in content
    assert "- Flutuantes (Q=2): 1 (50.00%)" in content
    # Site2 checks
    assert "site2" in content
    assert "- Total de pontos: 1" in content
    assert "- Desconhecidos: 1 (100.00%)" in content
    # Summary general
    assert "Resumo Geral" in content
    assert "Total de pontos: 3" in content
    assert "Fixos: 1 (33.33%)" in content
    assert "Flutuantes: 1 (33.33%)" in content
    assert "Desconhecidos: 1 (33.33%)" in content

    # Check KMZ file
    kmz_file = root / "resultado_interpolado.kmz"
    assert kmz_file.exists(), "KMZ não foi criado"
    # Optionally, open zip and check there are 3 placemarks (one per point)
    with zipfile.ZipFile(kmz_file) as kz:
        namelist = kz.namelist()
        # KMZ contains a KML, ensure presence of a .kml file
        kml_names = [n for n in namelist if n.endswith('.kml')]
        assert kml_names, "KML não encontrado dentro do KMZ"
        # Further KML content checks could be added here
