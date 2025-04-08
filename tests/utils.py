from datetime import datetime
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl


def read_test_data(filepath: str | Path) -> pl.DataFrame:
    """Read fixed-width style test data file using pandas built-in read_fwf() method.
    Convert any datetime columns.
    Return as polars dataframe.
    """

    df = pd.read_fwf(filepath)

    dt_cols = infer_datetime_cols(df)
    if dt_cols:
        for dt_col in dt_cols:
            # we've already checked for isoformat so to_datetime array function will work
            df[dt_col] = pd.to_datetime(df[dt_col])

    return pl.from_pandas(df)


def write_test_data(
    df: pl.DataFrame | pd.DataFrame,
    filepath: str | Path,
    dt_cols: str | list[str] | None = None,
    decimals: int = 4,
) -> None:
    """Helper to write dataframes into fixed-width format files for use in testing.
    Fixed-width format is used for ease of readability and determining changes in git diffs.
    The use of this function is not intended to be committed to source control, just used temporarily while
    creating test data files.
    """
    if isinstance(df, pl.DataFrame):
        df = df.to_pandas()

    formatters = {}
    if dt_cols:
        if isinstance(dt_cols, str):
            dt_cols = [dt_cols]
    else:
        dt_cols = []
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                dt_cols.append(col)

    for dt_col in dt_cols:
        formatters[dt_col] = dt_formatter

    float_format_func = partial(float_formatter, decimals=decimals)

    df.to_string(filepath, index=False, formatters=formatters, float_format=float_format_func)


def float_formatter(value: float, decimals: int = 4) -> str:
    """Convert floats to strings with consistent number of significant figures."""
    return np.format_float_positional(
        value, precision=decimals, unique=False, fractional=False, trim="k"
    )


def dt_formatter(dt: datetime | pd.Timestamp | pl.Datetime) -> str:
    """Provide standard method of converting timestamps to strings for text output."""
    return dt.isoformat(sep="T")


def infer_datetime_cols(df: pd.DataFrame) -> list:
    """Test each str (object) column has an isoformat datetime string,
    return column names (if any) of those datetime columns."""
    inferred_dt_cols = []

    for colname, val in df.select_dtypes(object).iloc[0].items():
        try:
            datetime.fromisoformat(val)
            inferred_dt_cols.append(colname)
        except ValueError as exc:
            pass
    return inferred_dt_cols
