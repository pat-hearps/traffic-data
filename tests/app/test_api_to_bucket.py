import copy
from datetime import datetime

import polars as pl
import pytest

from app.api_to_bucket import (
    dateparse_df,
    features_as_segment_dict,
    group_segments_by_freeway,
    parse_data,
    process_traffic_data,
)
from core.config import FWY_FILTER, MELB_TZ_NAME, TZ_MELB

# ---------------------------------------------------------------------------
# features_as_segment_dict
# ---------------------------------------------------------------------------


def test_features_as_segment_dict_basic(vicroads_response):
    features = vicroads_response["features"]
    result = features_as_segment_dict(features)
    # All features that have a segmentName should appear
    expected_names = {
        f["properties"]["segmentName"] for f in features if f["properties"].get("segmentName")
    }
    assert set(result.keys()) == expected_names


def test_features_as_segment_dict_skips_no_segmentname(vicroads_response):
    features = vicroads_response["features"]
    result = features_as_segment_dict(features)
    # The fixture has one feature with no segmentName; it must not appear
    assert None not in result
    assert "" not in result
    # Confirm there really was a no-segmentName feature in the fixture
    no_seg = [f for f in features if not f["properties"].get("segmentName")]
    assert len(no_seg) >= 1, "fixture should contain a feature without segmentName"


def test_features_as_segment_dict_values_are_properties(vicroads_response):
    features = vicroads_response["features"]
    result = features_as_segment_dict(features)
    for seg_name, props in result.items():
        assert props.get("segmentName") == seg_name


# ---------------------------------------------------------------------------
# group_segments_by_freeway
# ---------------------------------------------------------------------------


def test_group_segments_by_freeway_structure(vicroads_response):
    seg_dict = features_as_segment_dict(vicroads_response["features"])
    result = group_segments_by_freeway(seg_dict)
    # Fixture has Eastern Fwy and Tullamarine Fwy
    assert "Eastern Fwy" in result
    assert "Tullamarine Fwy" in result


def test_group_segments_by_freeway_correct_nesting(vicroads_response):
    seg_dict = features_as_segment_dict(vicroads_response["features"])
    result = group_segments_by_freeway(seg_dict)
    # Every segment nested under a freeway should have that freewayName
    for freeway, segments in result.items():
        for seg_name, props in segments.items():
            assert props["freewayName"] == freeway
            assert props["segmentName"] == seg_name


def test_group_segments_by_freeway_counts(vicroads_response):
    seg_dict = features_as_segment_dict(vicroads_response["features"])
    result = group_segments_by_freeway(seg_dict)
    # Fixture: 2 Eastern Fwy segments with segmentName, 1 Tullamarine
    assert len(result["Eastern Fwy"]) == 2
    assert len(result["Tullamarine Fwy"]) == 1


# ---------------------------------------------------------------------------
# parse_data
# ---------------------------------------------------------------------------


def _sample_segment():
    return {
        "segmentName": "Blackburn Rd to Springvale Rd",
        "freewayName": "Eastern Fwy",
        "direction": "Outbound",
        "publishedTime": "2026-06-07T10:00:00.029+10:00",
        "enabled": True,
        "parentPathId": "898157",
        "pathValid": True,
        "actualTravelTime": 73,
        "nominalTravelTime": 59,
        "source": {"sourceName": "Streams", "sourceId": "898166"},
    }


def test_parse_data_id_cast_to_int():
    data = _sample_segment()
    result = parse_data(data)
    assert result["id"] == 898166
    assert isinstance(result["id"], int)


def test_parse_data_parent_path_id_cast_to_int():
    data = _sample_segment()
    result = parse_data(data)
    assert result["parentPathId"] == 898157
    assert isinstance(result["parentPathId"], int)


def test_parse_data_removes_freeway_name():
    data = _sample_segment()
    result = parse_data(data)
    assert "freewayName" not in result


def test_parse_data_removes_source():
    data = _sample_segment()
    result = parse_data(data)
    assert "source" not in result


def test_parse_data_preserves_other_fields():
    data = _sample_segment()
    result = parse_data(data)
    assert result["actualTravelTime"] == 73
    assert result["segmentName"] == "Blackburn Rd to Springvale Rd"
    assert result["direction"] == "Outbound"


def test_parse_data_mutates_input():
    # parse_data mutates the input dict in place — document this behaviour
    data = _sample_segment()
    result = parse_data(data)
    assert result is data


# ---------------------------------------------------------------------------
# dateparse_df
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def a_dt() -> datetime:
    """Python datetime object at now with Australia/Melbourne timezone"""
    return datetime.now(tz=TZ_MELB)


def test_dateparse_df_converts_default_column(a_dt: datetime):
    df = pl.DataFrame({"publishedTime": [a_dt.isoformat()]})
    result = dateparse_df(df)
    assert result["publishedTime"].dtype == pl.Datetime("us", "UTC")
    assert result["publishedTime"][0] == a_dt


def test_dateparse_df_custom_column(a_dt: datetime):
    # Fix: dt_col should be written back to the same column, not a new publishedTime col
    df = pl.DataFrame({"ts": [a_dt.isoformat()], "other": ["x"]})
    result = dateparse_df(df, dt_col="ts")
    assert result["ts"].dtype == pl.Datetime("us", "UTC")
    assert "publishedTime" not in result.columns
    assert "other" in result.columns
    assert result["ts"][0] == a_dt


def test_dateparse_df_preserves_other_columns(a_dt: datetime):
    df = pl.DataFrame(
        {"publishedTime": [a_dt.isoformat()], "actualTravelTime": [111], "segmentName": ["foo"]}
    )
    result = dateparse_df(df)
    assert set(result.columns) == {"publishedTime", "actualTravelTime", "segmentName"}


# ---------------------------------------------------------------------------
# process_traffic_data (end-to-end)
# ---------------------------------------------------------------------------


def test_process_traffic_data_filters_to_eastern_fwy(vicroads_response):
    result = process_traffic_data(copy.deepcopy(vicroads_response))
    # Fixture has 2 Eastern Fwy segments with segmentName → 2 rows
    assert len(result) == 2


def test_process_traffic_data_no_freeway_name_column(vicroads_response):
    result = process_traffic_data(copy.deepcopy(vicroads_response))
    assert "freewayName" not in result.columns


def test_process_traffic_data_no_source_column(vicroads_response):
    result = process_traffic_data(copy.deepcopy(vicroads_response))
    assert "source" not in result.columns


def test_process_traffic_data_id_is_int(vicroads_response):
    result = process_traffic_data(copy.deepcopy(vicroads_response))
    assert result["id"].dtype in (pl.Int32, pl.Int64)


def test_process_traffic_data_parent_path_id_is_int(vicroads_response):
    result = process_traffic_data(copy.deepcopy(vicroads_response))
    assert result["parentPathId"].dtype in (pl.Int32, pl.Int64)


def test_process_traffic_data_published_time_is_tz_aware(vicroads_response):
    result = process_traffic_data(copy.deepcopy(vicroads_response))
    assert result["publishedTime"].dtype == pl.Datetime("us", MELB_TZ_NAME)


def test_process_traffic_data_raises_if_fwy_missing(vicroads_response):
    # Remove all Eastern Fwy features → should raise KeyError from the filter step
    data = copy.deepcopy(vicroads_response)
    data["features"] = [
        f for f in data["features"] if f["properties"].get("freewayName") != FWY_FILTER
    ]
    with pytest.raises(KeyError):
        process_traffic_data(data)
