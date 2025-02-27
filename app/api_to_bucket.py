from collections import defaultdict
from datetime import datetime

from fastapi import FastAPI
import polars as pl
import requests
import uvicorn

from core.config import API_KEY_TRAFFIC, URL_TRAFFIC, FWY_TOPIC, FWY_FILTER, MELB_TZ_NAME, GCS_BUCKET, TZ_MELB
from core.log_config import get_logger

app = FastAPI()

log = get_logger(__name__)
log.info("Initiating traffic api to storage module")

headers = {
    "Cache-Control": "no-cache",
    "Ocp-Apim-Subscription-Key": API_KEY_TRAFFIC
}

@app.get("/")
def main():
    now = datetime.now(tz=TZ_MELB)
    log.info(f"Hitting traffic API at {now.isoformat()}") 

    resp = requests.get(url=URL_TRAFFIC, headers=headers)

    if resp.status_code != 200:
        raise Exception(resp.text)

    
    # initial processing into format needed to log by topic=freeway, key=segment
    resp_dict = resp.json()
    segment_properties = features_as_segment_dict(resp_dict['features'])
    freeway_segments = group_segments_by_freeway(segment_properties)
    filtered_segments = freeway_segments[FWY_FILTER]

    parsed_segments = [parse_data(data) for data in filtered_segments.values()]
    
    df = pl.DataFrame(parsed_segments)
    df = dateparse_df(df)
    log.info(f"Writing current data (len={len(df)}) to storage at {now.isoformat()}")
    log.info(f"dataframe=\n{df}")
    filepath = f'{now.strftime("%Y/%m/%d")}/traffic_{FWY_TOPIC}_{now.strftime("%H%M%S")}.pqt'
    destination = f"gs://{GCS_BUCKET}/raw1/{filepath}"

    from app.cloud import write_df_pqt
    write_df_pqt(df, destination)

    log.info("Completed latest data dump to storage")



def features_as_segment_dict(features: list[dict]) -> dict:
    """Turn list of individual road segment (feature) dictionaries into
    a dictionary with keys = each unique segment name.
    """
    properties_by_segment = {}
    for feat in features:
        properties = feat.get('properties')       
        if seg_name := properties.get('segmentName'):
            properties_by_segment[seg_name] = properties
    log.info(f"Found {len(properties_by_segment)} features with properties")
    return properties_by_segment


def group_segments_by_freeway(properties_by_segment: dict) -> dict:
    """Reorganise segments to nested dict by each freeway"""
    freeway_segments = defaultdict(dict)
    for segment, properties in properties_by_segment.items():
        freeway = properties["freewayName"]
        freeway_segments[freeway][segment] = properties
    return dict(freeway_segments)



def dateparse_df(df: pl.DataFrame, dt_col: str = 'publishedTime') -> pl.DataFrame:
    df = df.with_columns(publishedTime=pl.col(dt_col).str.to_datetime().cast(pl.Datetime).dt.replace_time_zone(MELB_TZ_NAME))
    return df

def parse_data(data: dict) -> dict:
    """A few basic data type transformations"""
    data["id"] = int(data["source"]["sourceId"])
    data["parentPathId"] = int(data["parentPathId"])
    del data["freewayName"]  # it's only ended up here because we've filtered to this freeway name
    del data["source"]  # don't need, we have id, and extra dict nesting will be more confusing
    return data


if __name__ == '__main__':
    uvicorn.run("app.api_to_bucket:app", host="0.0.0.0", port=8080)
