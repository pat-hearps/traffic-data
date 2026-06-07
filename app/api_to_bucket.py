import time
from collections import defaultdict
from datetime import datetime

import polars as pl
import requests

from core.config import (
    API_KEY_TRAFFIC,
    FWY_FILTER,
    FWY_TOPIC,
    GCS_BUCKET,
    MELB_TZ_NAME,
    TZ_MELB,
    URL_TRAFFIC,
)
from core.log_config import get_logger
from core.utils import hide_keys, ms_since

log = get_logger(__name__)
log.info("Initiating traffic api to storage module")

headers = {"Cache-Control": "no-cache", "KeyID": API_KEY_TRAFFIC, "Accept": "application/json"}


def api_to_bucket():
    """Fetch traffic data from VicRoads API, process it, and write to GCS."""
    resp_dict, now = fetch_vicroads_data()
    df = process_traffic_data(resp_dict)
    save_to_gcs_bucket(df, now)


def fetch_vicroads_data() -> tuple[dict, datetime]:
    """Hit the VicRoads API and return the raw JSON response dict and request timestamp."""
    now = datetime.now(tz=TZ_MELB)
    log.info(f"Hitting traffic API at {now.isoformat()}")
    log.debug(f"Requesting URL: '{URL_TRAFFIC}'\nwith headers={hide_keys(headers)}")
    t0 = time.perf_counter()
    resp = requests.get(url=URL_TRAFFIC, headers=headers)
    log.info(f"status={resp.status_code}")
    log.debug(
        f"API call elapsed_ms={ms_since(t0)}\n"
        f"response_size_bytes={len(resp.content)}\n"
        f"resp.headers={hide_keys(dict(resp.headers))}"
    )
    if resp.status_code != 200:
        raise Exception(resp.text)
    return resp.json(), now


def process_traffic_data(resp_dict: dict) -> pl.DataFrame:
    """Transform raw API response JSON into a filtered, parsed Polars DataFrame."""
    t0 = time.perf_counter()
    segment_properties = features_as_segment_dict(resp_dict["features"])
    freeway_segments = group_segments_by_freeway(segment_properties)
    log.debug(
        f"Freeway distribution={{{', '.join(f'{k}: {len(v)}' for k, v in freeway_segments.items())}}}\n"
        f"Filtering to FWY_FILTER={FWY_FILTER!r}"
    )
    filtered_segments = freeway_segments[FWY_FILTER]
    first_segment_name = next(iter(filtered_segments))
    log.debug(
        f"filtered_segment_count={len(filtered_segments)}\n"
        f"first_segment_name={first_segment_name!r}"
    )
    parsed_segments = [parse_data(data) for data in filtered_segments.values()]
    log.debug(
        f"parsed_segment_count={len(parsed_segments)}\n"
        f"first_parsed_record={parsed_segments[0]}"
    )
    df = pl.DataFrame(parsed_segments)
    result = dateparse_df(df)
    log.debug(f"process_traffic_data elapsed_ms={ms_since(t0)}")
    return result


def save_to_gcs_bucket(df: pl.DataFrame, now: datetime) -> None:
    """Write DataFrame to GCS as a timestamped parquet file under raw1/."""
    filepath = f"{now.strftime('%Y/%m/%d')}/traffic_{FWY_TOPIC}_{now.strftime('%H%M%S')}.pqt"
    destination = f"gs://{GCS_BUCKET}/raw1/{filepath}"
    log.info(f"Writing current data (len={len(df)}) to storage at {now.isoformat()}")
    log.debug(
        f"{destination=}\n"
        f"df.shape={df.shape}\n"
        f"df.schema={df.schema}\n"
        f"dataframe=\n{df.head(3)}"
    )
    from app.cloud import write_df_pqt

    t0 = time.perf_counter()
    write_df_pqt(df, destination)
    log.debug(f"GCS write elapsed_ms={ms_since(t0)}")
    log.info("Completed latest data dump to storage")


def features_as_segment_dict(features: list[dict]) -> dict:
    """Turn list of individual road segment (feature) dictionaries into
    a dictionary with keys = each unique segment name.
    """
    properties_by_segment = {}
    for feat in features:
        properties = feat.get("properties")
        if seg_name := properties.get("segmentName"):
            properties_by_segment[seg_name] = properties
    log.info(f"Found {len(properties_by_segment)} features with properties")
    if properties_by_segment:
        sample_keys = list(next(iter(properties_by_segment.values())).keys())
        log.debug(f"sample_property_keys={sample_keys}")
    return properties_by_segment


def group_segments_by_freeway(properties_by_segment: dict) -> dict:
    """Reorganise segments to nested dict by each freeway"""
    freeway_segments = defaultdict(dict)
    for segment, properties in properties_by_segment.items():
        freeway = properties["freewayName"]
        freeway_segments[freeway][segment] = properties
    result = dict(freeway_segments)
    log.debug(f"freeway_segment_counts={ {k: len(v) for k, v in result.items()} }")
    return result


def dateparse_df(df: pl.DataFrame, dt_col: str = "publishedTime") -> pl.DataFrame:
    log.debug(f"dateparse_df input dtype: {dt_col}={df[dt_col].dtype}, sample={df[dt_col][0]!r}")
    df = df.with_columns(
        pl.col(dt_col)
        .str.to_datetime()
        .cast(pl.Datetime)
        .dt.replace_time_zone(MELB_TZ_NAME)
        .alias(dt_col)
    )
    log.debug(f"dateparse_df output dtype: {dt_col}={df[dt_col].dtype}, sample={df[dt_col][0]!r}")
    return df


def parse_data(data: dict) -> dict:
    """A few basic data type transformations"""
    data["id"] = int(data["source"]["sourceId"])
    data["parentPathId"] = int(data["parentPathId"])
    del data["freewayName"]  # it's only ended up here because we've filtered to this freeway name
    del data["source"]  # don't need, we have id, and extra dict nesting will be more confusing
    return data
