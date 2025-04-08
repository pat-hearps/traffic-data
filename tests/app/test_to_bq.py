from datetime import datetime

import polars as pl
import polars.testing as pltest
import pytz

import tests.utils as tu
from app import to_bq
from core.config import TZ_MELB


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
    pltest.assert_frame_equal(result_comparison_columns, df_exp)

    # make sure we've added the batch uid column correctly
    assert (df_proc["batch_uid"] == "test_uid").all()
