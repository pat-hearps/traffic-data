from datetime import datetime
from unittest.mock import MagicMock, patch

import polars as pl
import polars.testing as pltest
import pytest
import pytz

import tests.utils as tu
from app import to_bq
from app.to_bq import LBL_FILEPATH
from core.config import GCS_BUCKET, TZ_MELB


def test_process():
    """Data with duplicate values (excluding publishedTime and filepath)
    should be deduplicated to only include earliest rows where a value
    of fact data has changed.
    """
    df_raw = tu.read_test_data("tests/data_files/bucket_raw.txt")

    dt_348 = TZ_MELB.localize(datetime(2025, 3, 5, 3, 48)).astimezone(pytz.UTC)
    dt_354 = TZ_MELB.localize(datetime(2025, 3, 5, 3, 54)).astimezone(pytz.UTC)

    CHA_2_HDL, HDL_2_CHA = "Chandler_Hwy_to_Hoddle_St", "Hoddle_St_to_Chandler_Hwy"
    exp_data = {
        "segmentName": [CHA_2_HDL, CHA_2_HDL, HDL_2_CHA],
        "publishedTime": [dt_348, dt_354, dt_348],
        "actualTravelTime": [125, 127, 111],
    }
    df_exp = pl.DataFrame(exp_data)

    # run function being tested
    df_proc = to_bq.process("test_uid", df_raw)

    # check result
    result_comparison_columns = df_proc.select(
        ["segmentName", "publishedTime", "actualTravelTime"]
    )
    pltest.assert_frame_equal(result_comparison_columns, df_exp, check_row_order=False)

    # make sure we've added the batch uid column correctly
    assert (df_proc["batch_uid"] == "test_uid").all()


# ---------------------------------------------------------------------------
# process — edge cases
# ---------------------------------------------------------------------------


def test_process_already_unique_data_unchanged():
    # When every row has distinct fact values, no rows should be dropped
    dt1 = TZ_MELB.localize(datetime(2025, 1, 1, 1, 0)).astimezone(pytz.UTC)
    dt2 = TZ_MELB.localize(datetime(2025, 1, 1, 1, 6)).astimezone(pytz.UTC)
    df = pl.DataFrame(
        {
            "segmentName": ["A", "A"],
            "publishedTime": [dt1, dt2],
            "actualTravelTime": [100, 200],  # different values → both rows kept
            "raw_file_path": ["f1.pqt", "f2.pqt"],
        }
    )
    result = to_bq.process("uid", df)
    assert len(result) == 2


def test_process_excludes_raw_file_path_from_dedup(raw_traffic_df):
    # Rows from different files but identical fact data should still be deduped
    df = raw_traffic_df.with_columns(pl.lit("some/other/path.pqt").alias(LBL_FILEPATH))
    result = to_bq.process("uid", df)
    # All rows now have identical fact data → only one row per segment should remain
    assert len(result) < len(df)


def test_process_keeps_earliest_row_on_dedup():
    # When two rows have identical fact values, the one with the earlier publishedTime is kept
    dt_early = TZ_MELB.localize(datetime(2025, 1, 1, 1, 0)).astimezone(pytz.UTC)
    dt_late = TZ_MELB.localize(datetime(2025, 1, 1, 1, 6)).astimezone(pytz.UTC)
    df = pl.DataFrame(
        {
            "segmentName": ["A", "A"],
            "publishedTime": [dt_late, dt_early],  # late row first to test sort-before-dedup
            "actualTravelTime": [100, 100],  # identical → should be deduplicated to one row
            "raw_file_path": ["f1.pqt", "f2.pqt"],
        }
    )
    result = to_bq.process("uid", df)
    assert len(result) == 1
    assert result["publishedTime"][0] == dt_early


def test_process_adds_batch_uid(raw_traffic_df):
    result = to_bq.process("my-batch", raw_traffic_df)
    assert (result["batch_uid"] == "my-batch").all()


# ---------------------------------------------------------------------------
# make_batch_metadata_df
# ---------------------------------------------------------------------------


def test_make_batch_metadata_df_shape(raw_traffic_df):
    now = TZ_MELB.localize(datetime(2025, 3, 5, 4, 0))
    df_proc = to_bq.process("uid-1", raw_traffic_df)
    result = to_bq.make_batch_metadata_df(now, "uid-1", df_proc)
    assert result.shape[0] == 1


def test_make_batch_metadata_df_values(raw_traffic_df):
    now = TZ_MELB.localize(datetime(2025, 3, 5, 4, 0))
    df_proc = to_bq.process("uid-1", raw_traffic_df)
    result = to_bq.make_batch_metadata_df(now, "uid-1", df_proc)

    assert result["batch_uid"][0] == "uid-1"
    assert result["n_rows"][0] == df_proc.shape[0]
    assert result["n_columns"][0] == df_proc.shape[1]
    # raw_traffic_df has 3 distinct file paths
    assert result["n_raw_files"][0] == df_proc.n_unique(subset=[LBL_FILEPATH])


def test_make_batch_metadata_df_schema_is_dict(raw_traffic_df):
    now = TZ_MELB.localize(datetime(2025, 3, 5, 4, 0))
    df_proc = to_bq.process("uid-1", raw_traffic_df)
    result = to_bq.make_batch_metadata_df(now, "uid-1", df_proc)
    schema = result["schema"][0]
    assert isinstance(schema, dict)
    assert set(schema.keys()) == set(df_proc.columns)
    # Values are dtype strings
    for v in schema.values():
        assert isinstance(v, str)


# ---------------------------------------------------------------------------
# load_from_bucket
# ---------------------------------------------------------------------------


def _make_mock_scan(df):
    """Return a mock for pl.scan_parquet that yields df when .collect() is called."""
    mock_lazy = MagicMock()
    mock_lazy.collect.return_value = df
    return mock_lazy


def test_load_from_bucket_valid_date_builds_correct_path(raw_traffic_df):
    with patch("app.to_bq.pl.scan_parquet", return_value=_make_mock_scan(raw_traffic_df)) as mock:
        to_bq.load_from_bucket("2025/03/05", "raw1")
    called_path = mock.call_args[0][0]
    assert called_path == f"gs://{GCS_BUCKET}/raw1/2025/03/05/*"


def test_load_from_bucket_none_uses_glob_star(raw_traffic_df):
    with patch("app.to_bq.pl.scan_parquet", return_value=_make_mock_scan(raw_traffic_df)) as mock:
        to_bq.load_from_bucket(None, "raw1")
    called_path = mock.call_args[0][0]
    assert "**" in called_path


def test_load_from_bucket_invalid_glob_raises():
    with pytest.raises(ValueError, match="YYYY/mm/dd"):
        to_bq.load_from_bucket("garbage", "raw1")


def test_load_from_bucket_invalid_date_raises():
    with pytest.raises(ValueError, match="YYYY/mm/dd"):
        to_bq.load_from_bucket("2025/99/99", "raw1")


def test_load_from_bucket_scan_parquet_not_called_on_invalid_glob():
    with patch("app.to_bq.pl.scan_parquet") as mock:
        with pytest.raises(ValueError):
            to_bq.load_from_bucket("not-a-date", "raw1")
    mock.assert_not_called()


def test_load_from_bucket_empty_result_returns_none():
    empty_df = pl.DataFrame({"col": []})
    with patch("app.to_bq.pl.scan_parquet", return_value=_make_mock_scan(empty_df)):
        result = to_bq.load_from_bucket("2025/03/05", "raw1")
    assert result is None
