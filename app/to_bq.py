
from datetime import datetime, date
import uuid

import polars as pl

import app.cloud as acl
from core.config import TZ_MELB, GCS_BUCKET, BQ_RAW_ZONE
from core.log_config import get_logger

log = get_logger(__name__)


def raw_to_loaded(
    dt_glob: str | None = None, raw_dir: str = "raw1", read_dir: str = "read1"
):
    now = datetime.now(tz=TZ_MELB)
    uid = str(uuid.uuid4())

    lbl_filepath = "raw_file_path"

    if dt_glob:
        try:
            date.fromisoformat(dt_glob.replace("/","-"))
        except ValueError:
            log.error(f"dt_glob should be format YYYY/mm/dd - received {dt_glob}", exc_info=True)
    else:
        dt_glob="**"

    gs_path = f"gs://{GCS_BUCKET}/{raw_dir}/{dt_glob}/*"
    log.info(f"Reading from {gs_path}")

    df = pl.scan_parquet(gs_path, include_file_paths=lbl_filepath).collect()
    log.info(f"read df from google cloud storage: {df.shape}")
    if len(df) == 0:
        log.info("No data found")
        return None

    # to send for moving to 'read' at end, get list prior to deduplication
    all_file_paths = list(df.get_column(lbl_filepath).unique())

    # exclude raw_file_path col
    dupe_cols = list(set(df.columns) - {lbl_filepath})

    df=df.unique(keep="last",subset=dupe_cols)
    df = df.with_columns(pl.lit(uid).alias("batch_uid"))
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

    acl.write_to_bigquery(df, tablename=f"{BQ_RAW_ZONE}.loaded")
    log.info("data written to bigquery 'loaded' table")

    acl.write_to_bigquery(df_batch, tablename=f"{BQ_RAW_ZONE}.batches")
    log.info("batch load metadata written to 'batches' table")

    acl.move_gs_files(all_file_paths, src_dir=raw_dir, trg_dir=read_dir)

    log.info("Done")
