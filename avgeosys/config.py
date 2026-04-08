"""
Configurações gerais do AVGeoSys.
"""

import os
import sys
from pathlib import Path

# Determina diretório base (suporte a PyInstaller)
BASE_DIR: Path = (
    Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(__file__).parent.parent
)

# Caminho para o executável RTKLIB
RTKLIB_PATH: Path = BASE_DIR / "rnx2rtkp.exe"

# Número máximo de threads para processamento paralelo
MAX_WORKERS: int = os.cpu_count() or 4

# Timeout (segundos) para cada chamada ao rnx2rtkp; None = sem limite
PPK_TIMEOUT: int = 600

# ---------------------------------------------------------------------------
# Parâmetros de processamento PPK (passados via linha de comando ao rnx2rtkp)
# ---------------------------------------------------------------------------

# Máscara de elevação mínima dos satélites (graus)
PPK_ELEVATION_MASK: int = 15

# Threshold de validação AR (Ambiguity Resolution); 0 = desabilitado
# 2.0 oferece bom equilíbrio: mais épocas fixadas sem comprometer precisão
PPK_AR_THRESHOLD: float = 2.0

# Sistemas de navegação a usar: G=GPS, R=GLONASS, E=Galileo, C=BeiDou, J=QZSS
PPK_NAV_SYSTEMS: str = "G,R,E,C"
