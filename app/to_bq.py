
from datetime import datetime
import uuid
import polars as pl
from core.config import TZ_MELB, GCS_BUCKET
from core.log_config import get_logger

log = get_logger(__name__)


def raw_to_loaded():
    now = datetime.now(tz=TZ_MELB)
    uid = uuid.uuid4()

    lbl_filepath = "raw_file_path"

    # todo make this reading gcfs
    gs_path = f"gs://{GCS_BUCKET}/raw1/**/*.pqt"
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


