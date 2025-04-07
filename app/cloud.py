import io
import math
from itertools import batched

import gcsfs
import polars as pl
from google.api_core.exceptions import NotFound
from google.cloud import bigquery, storage

from core.config import GCS_BUCKET, GCS_PROJECT
from core.log_config import get_logger

log = get_logger(__name__)


def write_df_pqt(df: pl.DataFrame, destination: str) -> None:
    log.debug("Trying to acquire gc filesystem")
    fs = gcsfs.GCSFileSystem(token="google_default", project=GCS_PROJECT, access="read_write")
    log.info("GCSFS acquired")
    log.debug(f"Attempting to open fs destination: {destination}")
    # Write the DataFrame to a Parquet file directly in GCS
    with fs.open(destination, mode="wb") as f:
        log.debug("Destination open, writing parquet")
        df.write_parquet(f)

    log.debug(f"Dataframe written to {destination}")


def write_to_bigquery(df: pl.DataFrame, tablename: str, project: str = GCS_PROJECT):
    client = bigquery.Client()
    # Write DataFrame to stream as parquet file; does not hit disk
    with io.BytesIO() as stream:
        df.write_parquet(stream, use_pyarrow=True)
        log.info("df written to bytestream")
        stream.seek(0)  # reset to start of bytestream
        parquet_options = bigquery.ParquetOptions()
        parquet_options.enable_list_inference = True
        job = client.load_table_from_file(
            stream,
            destination=tablename,
            project=project,
            job_config=bigquery.LoadJobConfig(
                source_format=bigquery.SourceFormat.PARQUET, parquet_options=parquet_options
            ),
        )
        log.info("job created, calling, waiting")
    job.result()  # Waits for the job to complete
    log.info("load job finished")


def move_gs_files(
    files: list[str],
    src_dir: str = "raw1",
    trg_dir: str = "read1",
    bucket_name=GCS_BUCKET,
    n_per_batch: int = 100,
):
    """Move specific list of files to a new folder,
    first copies then deletes.
    """
    client = storage.Client(project=GCS_PROJECT)
    bucket = client.get_bucket(bucket_name)

    n_batches = int(math.ceil((n_files := len(files)) / n_per_batch))
    log.info(f"Moving {n_files} files in {n_batches} batches")

    len_bucket_name = len(bucket_name) + 1  # +1 for '/' sign
    file_names = [fn[fn.index(bucket_name) + len_bucket_name :] for fn in files]

    for ib, batch_files in enumerate(batched(file_names, 100)):
        log.info(f"processing batch {ib + 1} / {n_batches}")
        batch_blobs = [bucket.get_blob(filename) for filename in batch_files]
        log.info(f"retrieved {len(batch_blobs)} blobs")

        with client.batch(raise_exception=False):
            log.info("starting to move blobs")
            for i, blob in enumerate(batch_blobs):
                log.debug(f"trying to move {i} {blob.name}")
                new_name = blob.name.replace(src_dir, trg_dir)
                bucket.copy_blob(blob, destination_bucket=bucket, new_name=new_name)

        log.info("blobs copied, deleting originals")
        bucket.delete_blobs(batch_blobs)

        log.info(f"batch {ib + 1} of {n_batches} done")
