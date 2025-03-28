
from datetime import datetime, date
import uuid
import polars as pl
from core.config import TZ_MELB, GCS_BUCKET
from core.log_config import get_logger

log = get_logger(__name__)


def raw_to_loaded(dt_glob: str | None = None,
                  raw_dir:str = "raw1"):
    now = datetime.now(tz=TZ_MELB)
    uid = uuid.uuid4()

    lbl_filepath = "raw_file_path"

    if dt_glob:
        try:
            date.fromisoformat("2025/03/01".replace("/","-"))
        except ValueError:
            log.error(f"dt_glob should be format YYYY/mm/dd - received {dt_glob}", exc_info=True)
    else:
        dt_glob="**"

    gs_path = f"gs://{GCS_BUCKET}/{raw_dir}/{dt_glob}/*"

    df = pl.scan_parquet(gs_path, include_file_paths='raw_file_path').collect()
    log.info(f"read df from google cloud storage: {df.shape}")

    # exclude raw_file_path col
    dupe_cols = list(set(df.columns) - {lbl_filepath})

    df=df.unique(keep="last",subset=dupe_cols)
    df = df.with_columns(pl.lit(str(uid)).alias("batch_uid"))
    log.info(f"dropped duplicates, added batch uid: {(df.shape)}")


    schema = {col:str(dtype) for col,dtype in df.collect_schema().items()}
    df_batch = pl.DataFrame({
        "dt_batch": now,
        "batch_uid": uid,
        "n_rows": df.shape[0],
        "n_columns": df.shape[1],
        "n_raw_files": df.n_unique(subset=[lbl_filepath]),
        "schema": schema
    })


