"""
Módulo de leitura de MRK e interpolação de posições.
"""

import logging
from pathlib import Path
from typing import List, Dict

import pandas as pd

logger = logging.getLogger(__name__)


def preprocess_and_read_mrk(
    mrk_file: Path,
    output_dir: Path,
) -> pd.DataFrame:
    """
    Lê o .MRK, substitui vírgulas por tabulação e retorna
    DataFrame com colunas: index, time, lat, lon, height.
    """
    temp_file = output_dir / mrk_file.name.replace(
        ".MRK", "_temp.MRK"
    )
    try:
        text = mrk_file.read_text()
        text = text.replace(",", "\t")
        temp_file.write_text(text)
        mrk_data = pd.read_csv(
            temp_file,
            sep=r"\s+",
            header=None,
            usecols=[0, 1, 9, 11, 13],
            names=[
                "index",
                "time",
                "lat",
                "lon",
                "height",
            ],
        )
        mrk_data.dropna(inplace=True)
        logger.info(
            f".MRK carregado: {len(mrk_data)} registros de "
            f"{mrk_file.name}"
        )
    except Exception as e:
        logger.error(
            f"Erro ao ler .MRK {mrk_file.name}: {e}"
        )
        mrk_data = pd.DataFrame(
            columns=[
                "index",
                "time",
                "lat",
                "lon",
                "height",
            ]
        )
    return mrk_data


def load_pos_data(pos_file: Path) -> pd.DataFrame:
    """
    Lê o arquivo .pos, ignora comentários e retorna
    DataFrame com colunas: week, seconds, lat, lon, height, quality.
    """
    try:
        df = pd.read_csv(
            pos_file,
            comment="%",
            skiprows=10,
            sep=r"\s+",
            names=[
                "week",
                "seconds",
                "lat",
                "lon",
                "height",
                "quality",
            ],
            usecols=[0, 1, 2, 3, 4, 5],
        )
        df = df.apply(
            pd.to_numeric,
            errors="coerce"
        ).dropna()
        logger.info(
            f".pos carregado: {len(df)} registros de "
            f"{pos_file.name}"
        )
    except Exception as e:
        logger.error(
            f"Erro ao ler .pos {pos_file.name}: {e}"
        )
        df = pd.DataFrame(
            columns=[
                "week",
                "seconds",
                "lat",
                "lon",
                "height",
                "quality",
            ]
        )
    return df


def interpolate_positions(
    pos_data: pd.DataFrame,
    mrk_data: pd.DataFrame,
) -> List[Dict]:
    """
    Interpola coordenadas para cada registro MRK com base em pos_data.
    Retorna lista de dicts com: index, photo, lat, lon, height, time, quality.
    """
    if pos_data.empty or mrk_data.empty:
        logger.warning(
            "Dados insuficientes para interpolação."
        )
        return []

    interpolated: List[Dict] = []
    for _, row in mrk_data.iterrows():
        diffs = (
            pos_data["seconds"] - row["time"]
        ).abs()
        if len(diffs) < 2:
            continue

        nearest = pos_data.iloc[
            diffs.nsmallest(2).index
        ]
        t1, t2 = nearest["seconds"].values
        lat1, lat2 = nearest["lat"].values
        lon1, lon2 = nearest["lon"].values
        h1, h2 = nearest["height"].values
        q1, q2 = nearest["quality"].values

        if t1 == t2:
            continue

        w = (row["time"] - t1) / (t2 - t1)
        interp = {
            "index": int(row["index"]),
            "photo": (
                f"_{int(row['index']):04}_V.JPG"
            ),
            "lat": float(
                lat1 + w * (lat2 - lat1)
            ),
            "lon": float(
                lon1 + w * (lon2 - lon1)
            ),
            "height": float(
                h1 + w * (h2 - h1)
            ),
            "time": float(row["time"]),
            "quality": int(
                round(q1 + w * (q2 - q1))
            ),
        }
        interpolated.append(interp)

    logger.info(
        f"Interpolação concluída: {len(interpolated)} "
        "pontos gerados."
    )
    return interpolated
