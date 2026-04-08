"""
Verificação de atualizações via GitHub (version.json).

O arquivo version.json deve ser hospedado em um repositório GitHub e ter o formato:

    {
      "stable": {
        "version": "1.0.0",
        "url": "https://github.com/USUARIO/REPO/releases/download/v1.0.0/AVGeoSys_Setup_1.0.0.exe",
        "notes": "Descrição da versão"
      },
      "beta": {
        "version": "1.1.0-beta.1",
        "url": "https://github.com/USUARIO/REPO/releases/download/v1.1.0-beta.1/AVGeoSys_Setup_1.1.0-beta.1.exe",
        "notes": "Descrição da versão beta"
      }
    }

Configure VERSION_CHECK_URL com a URL raw do seu repositório antes de distribuir.
"""

import json
import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# URL do version.json no repositório GitHub.
VERSION_CHECK_URL = (
    "https://raw.githubusercontent.com/joaomsas/avgeosys-ppk-exif-tool/main/version.json"
)


def _ver_tuple(version_str: str) -> tuple:
    """Converte string de versão semântica em tupla comparável.

    Ignora sufixos de pré-release (ex: "-beta.1") — a comparação é feita
    apenas na parte numérica (major.minor.patch).

    Exemplos:
        "1.0.0"       → (1, 0, 0)
        "1.1.0-beta.1"→ (1, 1, 0)
        "v2.0.1"      → (2, 0, 1)
    """
    base = version_str.lstrip("v").split("-")[0]
    parts = base.split(".")
    return tuple(int(x) for x in parts if x.isdigit())


def check_for_update(
    current_version: str,
    channel: str = "stable",
    timeout: int = 5,
) -> Optional[dict]:
    """Verifica se há versão mais recente disponível.

    Args:
        current_version: Versão instalada atualmente (ex: "1.0.0").
        channel: Canal de atualização — "stable" ou "beta".
        timeout: Timeout em segundos para a requisição HTTP.

    Returns:
        Dict com ``version``, ``url`` e ``notes`` se houver atualização,
        ou ``None`` se já está na versão mais recente ou a verificação falhou.
    """
    try:
        import urllib.request

        with urllib.request.urlopen(VERSION_CHECK_URL, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        channel_info = data.get(channel)
        if not channel_info or "version" not in channel_info:
            return None

        remote_ver = channel_info["version"]
        if _ver_tuple(remote_ver) > _ver_tuple(current_version):
            return {**channel_info, "channel": channel}

        return None

    except Exception:
        return None


def check_for_update_async(
    current_version: str,
    channel: str = "stable",
    callback: Optional[Callable[[Optional[dict]], None]] = None,
) -> None:
    """Executa check_for_update em thread de fundo e chama callback com o resultado.

    A thread é daemon e não bloqueia o fechamento do programa.
    O callback é chamado no thread de fundo — use root.after() para atualizar a UI.

    Args:
        current_version: Versão instalada atualmente.
        channel: Canal de atualização — "stable" ou "beta".
        callback: Função chamada com o resultado (dict ou None).
    """
    def _run() -> None:
        result = check_for_update(current_version, channel)
        if callback is not None:
            callback(result)

    t = threading.Thread(target=_run, daemon=True, name="avgeosys-update-check")
    t.start()
