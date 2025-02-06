import gcsfs

from core.config import GCS_PROJECT
from core.log_config import get_logger

log = get_logger(__name__)

log.debug("Trying to acquire gc filesystem")
fs = gcsfs.GCSFileSystem(token="google_default",
                         project=GCS_PROJECT,
                         access="read_write")
log.info("GCSFS acquired")

def write_df_pqt(df, destination: str):
    log.debug(f"Attempting to open fs destination: {destination}")
    # Write the DataFrame to a Parquet file directly in GCS
    with fs.open(destination, mode='wb') as f:
        log.debug("Destination open, writing parquet")
        df.write_parquet(f)
    
    log.debug(f"Dataframe written to {destination}")
