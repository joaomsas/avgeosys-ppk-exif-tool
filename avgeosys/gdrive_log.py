"""
Upload silencioso de logs para o Google Drive via OAuth (refresh token embutido).

Não requer nenhuma interação do usuário — o refresh token é gerado uma única vez
pelo desenvolvedor e embutido no instalador junto com o client_id/secret.
"""

import json
import logging
import sys
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _credentials_path() -> Optional[Path]:
    """Retorna o caminho do arquivo de credencial, compatível com source e PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        p = Path(sys._MEIPASS) / "credentials" / "gdrive.json"
    else:
        p = Path(__file__).parent / "credentials" / "gdrive.json"
    return p if p.exists() else None


def upload_log(log_path: Path, dest_filename: str) -> bool:
    """Faz upload de um arquivo de log para a pasta AVGeoSys Logs no Drive.

    Args:
        log_path: Caminho local do arquivo .log.
        dest_filename: Nome do arquivo no Drive.

    Returns:
        True em sucesso, False em qualquer falha (silenciosa).
    """
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        creds_path = _credentials_path()
        if creds_path is None:
            logger.debug("Credencial Google Drive não encontrada — upload ignorado.")
            return False

        with open(creds_path, encoding="utf-8") as f:
            data = json.load(f)

        creds = Credentials(
            token=None,
            refresh_token=data["refresh_token"],
            client_id=data["client_id"],
            client_secret=data["client_secret"],
            token_uri=data["token_uri"],
            scopes=_SCOPES,
        )

        folder_id = data["folder_id"]
        service = build("drive", "v3", credentials=creds, cache_discovery=False)

        file_metadata = {"name": dest_filename, "parents": [folder_id]}
        media = MediaFileUpload(str(log_path), mimetype="text/plain", resumable=False)
        service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        logger.debug("Log enviado para o Google Drive: %s", dest_filename)
        return True

    except Exception as exc:
        logger.debug("Falha no upload do log para o Drive: %s", exc)
        return False


def upload_log_async(log_path: Path, dest_filename: str) -> None:
    """Executa upload_log em thread de fundo — não bloqueia o fechamento do app."""
    t = threading.Thread(
        target=upload_log,
        args=(log_path, dest_filename),
        daemon=True,
        name="avgeosys-gdrive-upload",
    )
    t.start()
