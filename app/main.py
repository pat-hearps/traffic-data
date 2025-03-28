
from fastapi import FastAPI

import uvicorn

from app.api_to_bucket import api_to_bucket
from app.to_bq import raw_to_loaded

app = FastAPI()


@app.get("/")
def hit_api_to_bucket():
    api_to_bucket()


@app.get("/bq_load")
def load_bucket_to_bq(dt_glob: str | None = None):
    raw_to_loaded(dt_glob=dt_glob)


if __name__ == '__main__':
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080)
