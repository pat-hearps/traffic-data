import io
from itertools import batched
import math

import polars as pl
from google.cloud import bigquery
from google.cloud import storage
import gcsfs

from core.config import GCS_PROJECT, GCS_BUCKET
from core.log_config import get_logger

log = get_logger(__name__)



def write_df_pqt(df: pl.DataFrame, destination: str) -> None:
    log.debug("Trying to acquire gc filesystem")
    fs = gcsfs.GCSFileSystem(token="google_default",
                            project=GCS_PROJECT,
                            access="read_write")
    log.info("GCSFS acquired")
    log.debug(f"Attempting to open fs destination: {destination}")
    # Write the DataFrame to a Parquet file directly in GCS
    with fs.open(destination, mode='wb') as f:
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
                source_format=bigquery.SourceFormat.PARQUET,
                parquet_options=parquet_options,
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
    client = storage.Client(project=GCS_PROJECT)
    bucket = client.get_bucket(bucket_name)

    n_batches = int(math.ceil((n_files := len(files)) / n_per_batch))
    log.info(f"Moving {n_files} files in {n_batches} batches")

    for ib, batch_files in enumerate(batched(files, 100)):
        log.info(f"processing batch {ib + 1} / {n_batches}")
        with client.batch():
            batch_blobs = [bucket.get_blob(filename) for filename in batch_files]
        log.info(f"retrieved {len(batch_blobs)} blobs")
        with client.batch():
            for blob in batch_blobs:
                new_name = blob.name.replace(src_dir, trg_dir)
                bucket.move_blob(blob, new_name=new_name)
        log.info(f"batch {ib + 1} done")
