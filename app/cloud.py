import io

import polars as pl
from google.cloud import bigquery
import gcsfs

from core.config import GCS_PROJECT
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

