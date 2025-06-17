"""
Módulo de leitura de MRK e interpolação de posições.
"""

import logging
from pathlib import Path
from typing import List, Dict

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def preprocess_and_read_mrk(
    mrk_file: Path,
    output_dir: Path,
) -> pd.DataFrame:
    """
    Lê o arquivo .MRK e retorna DataFrame com colunas
    ``index``, ``time``, ``lat``, ``lon`` e ``height``.
    """
    try:
        mrk_data = pd.read_csv(
            mrk_file,
            sep=r"[\s,]+",
            engine="python",
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
        logger.warning("Dados insuficientes para interpolação.")
        return []

    # ordena por tempo para garantir monotonicidade no interp
    pos_sorted = pos_data.sort_values("seconds")

    times = pos_sorted["seconds"].values
    mrk_times = mrk_data["time"].values

    lat_vals = pos_sorted["lat"].values
    lon_vals = pos_sorted["lon"].values
    height_vals = pos_sorted["height"].values
    quality_vals = pos_sorted["quality"].values

    lat_interp = np.interp(mrk_times, times, lat_vals)
    lon_interp = np.interp(mrk_times, times, lon_vals)
    height_interp = np.interp(mrk_times, times, height_vals)
    quality_interp = np.interp(mrk_times, times, quality_vals)

    result_df = pd.DataFrame({
        "index": mrk_data["index"].astype(int).values,
        "photo": mrk_data["index"].astype(int).apply(
            lambda i: f"_{i:04}_V.JPG"
        ),
        "lat": lat_interp.astype(float),
        "lon": lon_interp.astype(float),
        "height": height_interp.astype(float),
        "time": mrk_times.astype(float),
        "quality": np.rint(quality_interp).astype(int),
    })

    logger.info(
        f"Interpolação concluída: {len(result_df)} pontos gerados."
    )
    return result_df.to_dict(orient="records")
