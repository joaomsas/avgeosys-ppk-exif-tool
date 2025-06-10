"""
Configurações gerais do AVGeoSys
"""

from pathlib import Path
import sys

__version__ = "0.3.02"

# Determina o diretório base, considerando PyInstaller
BASE_DIR: Path = (
    Path(sys._MEIPASS) if hasattr(sys, "_MEIPASS") else Path(__file__).parent
)

# Caminho para o executável do RTKLIB (rnx2rtkp.exe)
RINEX2RTKP_PATH: Path = BASE_DIR / "rnx2rtkp.exe"
