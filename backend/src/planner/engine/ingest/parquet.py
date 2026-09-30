from __future__ import annotations

from pathlib import Path

import polars as pl


def to_parquet(df: pl.DataFrame, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(p)


def read_parquet(path: str | Path) -> pl.DataFrame:
    p = Path(path)
    return pl.read_parquet(p)
