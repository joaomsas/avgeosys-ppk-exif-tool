"""
Persistência de configurações da GUI entre sessões.

Salva em ``~/.avgeosys/settings.json``.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

_SETTINGS_DIR = Path.home() / ".avgeosys"
_SETTINGS_FILE = _SETTINGS_DIR / "settings.json"

DEFAULTS: Dict[str, Any] = {
    "solution_type": "forward",
    "elevation_mask": 15,
    "ar_threshold": 2.0,
    "nav_systems": "G,R,E,C",
    "orthometric": False,
    "last_project": "",
    "update_channel": "stable",  # "stable" | "beta"
    "logs_central_dir": "",     # caminho absoluto para a pasta Logs/ central (OneDrive)
}


def load() -> Dict[str, Any]:
    """Carrega configurações salvas, mesclando com os defaults."""
    try:
        if _SETTINGS_FILE.exists():
            with open(_SETTINGS_FILE, encoding="utf-8") as fh:
                saved = json.load(fh)
            return {**DEFAULTS, **saved}
    except Exception as exc:
        logger.debug("Não foi possível carregar configurações: %s", exc)
    return dict(DEFAULTS)


def save(data: Dict[str, Any]) -> None:
    """Salva configurações em disco."""
    try:
        _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(_SETTINGS_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
    except Exception as exc:
        logger.debug("Não foi possível salvar configurações: %s", exc)
