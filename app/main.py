
from fastapi import FastAPI
from pydantic import BaseModel

import uvicorn

from app.api_to_bucket import api_to_bucket
from app.to_bq import raw_to_loaded

app = FastAPI()


@app.get("/")
def hit_api_to_bucket():
    api_to_bucket()


class LoadPost(BaseModel):
    dt_glob: str | None = None


@app.post("/bq_load")
def load_bucket_to_bq(loadpost: LoadPost):
    raw_to_loaded(dt_glob=loadpost.dt_glob)


if __name__ == '__main__':
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080)
