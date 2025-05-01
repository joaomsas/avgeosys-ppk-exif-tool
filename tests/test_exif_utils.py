# tests/test_exif_utils.py

import pytest
from avgeosys.core.exif import convert_to_dms, convert_from_dms

def test_convert_to_from_dms():
    # Testa conversão de valor decimal para DMS e de volta
    original = -23.55052
    dms = convert_to_dms(original)
    # Como o valor é negativo, usamos 'S' para Sul
    result = convert_from_dms(dms, 'S')
    # Permitimos pequena margem de erro por conta de arredondamentos
    assert pytest.approx(original, rel=1e-6) == result
