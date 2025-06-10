import zipfile
from pathlib import Path
import sys
import pytest
from avgeosys.core.fieldupload import field_upload


def touch(p: Path):
    p.write_text("conteúdo qualquer")

@pytest.fixture
def setup_env(tmp_path):
    root = tmp_path

    # cria PPK_Results para remoção\    (root / "sub1" / "PPK_Results").mkdir(parents=True)

    # cria arquivos base .B, .O, .P com sufixos 20 e 21
    for ext in ("B", "O", "P"):    
        touch(root / f"site.20{ext}")
        touch(root / f"site.21{ext}")

    # cria subpasta com fotos
    fotos = root / "fotos"
    fotos.mkdir()
    touch(fotos / "img001.jpg")

    return root, fotos


def test_field_upload_happy_path(setup_env):
    root, fotos = setup_env
    zip_path = field_upload(root)

    # PPK_Results deve ter sido removido
    assert not (root / "sub1" / "PPK_Results").exists()

    # Zip deve existir na pasta de fotos
    assert zip_path.exists()
    assert zip_path.parent == fotos

    # Conteúdo do ZIP inclui arquivos com sufixos B, O e P
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        for ext in ("B", "O", "P"):
            assert any(name.endswith(ext) for name in names), \
                f"ZIP não contém arquivo com extensão {ext}"

    # Arquivos base originais devem ter sido apagados
    assert not any(root.glob("*.B"))
    assert not any(root.glob("*.O"))
    assert not any(root.glob("*.P"))

    # Arquivos de relatório/KMZ não devem existir
    for fn in (
        "compilado_exif_data.kmz",
        "relatorio_processamento.txt",
        "resultado_interpolado.kmz",
    ):
        assert not (root / fn).exists()


def test_field_upload_no_photos(tmp_path):
    root = tmp_path
    # cria somente arquivos base
    for ext in ("B", "O", "P"):
        touch(root / f"site.00{ext}")
    # sem pasta de fotos, deve falhar
    with pytest.raises(FileNotFoundError):
        field_upload(root)


def test_cli_field_upload_invoked(monkeypatch, tmp_path):
    from avgeosys.cli import cli as cli_mod
    called = {}

    def fake_field_upload(path: Path):
        called["path"] = path

    monkeypatch.setattr(cli_mod, "cmd_ppk", lambda p: None)
    monkeypatch.setattr(cli_mod, "cmd_interpolate", lambda p: None)
    monkeypatch.setattr(cli_mod, "cmd_geotag", lambda p: None)
    monkeypatch.setattr(cli_mod, "cmd_report", lambda p: None)
    monkeypatch.setattr(cli_mod, "field_upload", fake_field_upload)
    monkeypatch.setattr(sys, "argv", ["avgeosys", str(tmp_path), "--field-upload"])

    cli_mod.main()

    assert called.get("path") == tmp_path


def test_cli_field_upload_with_all(monkeypatch, tmp_path):
    from avgeosys.cli import cli as cli_mod
    calls = []

    monkeypatch.setattr(cli_mod, "cmd_ppk", lambda p: calls.append("ppk"))
    monkeypatch.setattr(cli_mod, "cmd_interpolate", lambda p: calls.append("interp"))
    monkeypatch.setattr(cli_mod, "cmd_geotag", lambda p: calls.append("geo"))
    monkeypatch.setattr(cli_mod, "cmd_report", lambda p: calls.append("report"))
    monkeypatch.setattr(cli_mod, "field_upload", lambda p: calls.append("fu"))
    monkeypatch.setattr(sys, "argv", ["avgeosys", str(tmp_path), "--all", "--field-upload"])

    cli_mod.main()

    assert "fu" in calls

