import zipfile
from pathlib import Path
import pytest
from avgeosys.core.fieldupload import field_upload

def touch(p: Path):
    p.write_text("conteúdo qualquer")

@pytest.fixture
def setup_env(tmp_path):
    root = tmp_path

    # cria PPK_Results para remoção
    (root / "sub1" / "PPK_Results").mkdir(parents=True)

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
    assert zip_path.exists() and zip_path.parent == fotos

    # Conteúdo do ZIP inclui .B, .O e .P
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        assert any(name.endswith(".B") for name in names)
        assert any(name.endswith(".O") for name in names)
        assert any(name.endswith(".P") for name in names)

    # Arquivos base originais devem ter sido apagados
    assert not any(root.glob("*.B"))
    assert not any(root.glob("*.O"))
    assert not any(root.glob("*.P"))

    # Arquivos de relatório/KMZ não devem existir
    for fn in [
        "compilado_exif_data.kmz",
        "relatorio_processamento.txt",
        "resultado_interpolado.kmz",
    ]:
        assert not (root / fn).exists()

def test_field_upload_no_photos(tmp_path):
    root = tmp_path
    # cria somente arquivos base
    for ext in ("B", "O", "P"):
        touch(root / f"site.00{ext}")
    # sem pasta de fotos, deve falhar
    with pytest.raises(FileNotFoundError):
        field_upload(root)
