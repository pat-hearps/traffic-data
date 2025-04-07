import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

from app.api_to_bucket import api_to_bucket
from app.to_bq import raw_to_loaded
from core.log_config import get_logger

log = get_logger(__name__)

app = FastAPI()


@app.get("/")
def hit_api_to_bucket():
    api_to_bucket()


class LoadPost(BaseModel):
    dt_glob: str | None = None


@app.get("/bq_load")
@app.post("/bq_load")
def load_bucket_to_bq(loadpost: LoadPost | None = None):
    """Load the contents of the GCS bucket 'raw1' folder into BigQuery,
    then move the read files into separate 'read1' folder in same bucket.
    If dt_glob is provided (in YYYY/mm/dd format), only files in this folder
    will be loaded.
    If no dt_glob, the entire contents of 'raw1' will be loaded.
    """
    if loadpost and loadpost.dt_glob:
        dt_glob = loadpost.dt_glob
    else:
        dt_glob = None

    log.info(f"Received {dt_glob = }")
    raw_to_loaded(dt_glob=dt_glob)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080)
