
from datetime import datetime, date
import subprocess
import uuid

import polars as pl

from app.cloud import write_to_bigquery
from core.config import TZ_MELB, GCS_BUCKET, BQ_RAW_ZONE
from core.log_config import get_logger

log = get_logger(__name__)


def raw_to_loaded(dt_glob: str | None = None,
                  raw_dir:str = "raw1",
                  read_dir: str = "read1"):
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

    df = pl.scan_parquet(gs_path, include_file_paths='raw_file_path').collect()
    log.info(f"read df from google cloud storage: {df.shape}")
    if len(df) == 0:
        log.info("No data found")
        return None

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

    write_to_bigquery(df, tablename=f"{BQ_RAW_ZONE}.loaded")
    log.info("data written to bigquery 'loaded' table")

    write_to_bigquery(df_batch, tablename=f"{BQ_RAW_ZONE}.batches")
    log.info("batch load metadata written to 'batches' table")

    # copy over loaded files, 
    if dt_glob == "**":
        src_dir = f"gs://{GCS_BUCKET}/{raw_dir}/*"
    else:
        src_dir = gs_path

    trg_dir = src_dir.replace(raw_dir, read_dir).replace("/*", "/")

    cmd = f"gcloud storage cp {src_dir} {trg_dir} --recursive"
    log.info(f"running command: {cmd}")

    subprocess.run(cmd.split(sep=" "))
    log.info("Done")
