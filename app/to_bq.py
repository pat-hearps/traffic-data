import io

import polars as pl
from google.cloud import bigquery

from core.config import GCS_PROJECT
from core.log_config import get_logger

log = get_logger(__name__)

client = bigquery.Client()

def write_to_bigquery(df: pl.DataFrame, tablename: str, project: str = GCS_PROJECT):
    # Write DataFrame to stream as parquet file; does not hit disk
    with io.BytesIO() as stream:
        df.write_parquet(stream)
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