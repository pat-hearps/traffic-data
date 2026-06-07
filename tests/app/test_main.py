import warnings
from datetime import datetime
from unittest.mock import MagicMock, patch

import polars as pl
import pytest
from fastapi.testclient import TestClient

# httpx + starlette emit a DeprecationWarning about httpx2; suppress for the whole module
warnings.filterwarnings("ignore", category=DeprecationWarning, module="starlette")

from app.main import app  # noqa: E402

client = TestClient(app)


# ---------------------------------------------------------------------------
# Endpoint smoke tests
# ---------------------------------------------------------------------------


def test_get_root_returns_200():
    with patch("app.main.api_to_bucket"):
        resp = client.get("/")
    assert resp.status_code == 200


def test_get_root_calls_api_to_bucket():
    with patch("app.main.api_to_bucket") as mock_fn:
        client.get("/")
    mock_fn.assert_called_once()


def test_get_bq_load_returns_200():
    with patch("app.main.raw_to_loaded"):
        resp = client.get("/bq_load")
    assert resp.status_code == 200


def test_get_bq_load_calls_raw_to_loaded_no_dt_glob():
    with patch("app.main.raw_to_loaded") as mock_fn:
        client.get("/bq_load")
    mock_fn.assert_called_once_with(dt_glob=None)


def test_post_bq_load_passes_dt_glob():
    with patch("app.main.raw_to_loaded") as mock_fn:
        client.post("/bq_load", json={"dt_glob": "2025/03/05"})
    mock_fn.assert_called_once_with(dt_glob="2025/03/05")


def test_post_bq_load_no_body_uses_none():
    with patch("app.main.raw_to_loaded") as mock_fn:
        client.post("/bq_load")
    mock_fn.assert_called_once_with(dt_glob=None)


# ---------------------------------------------------------------------------
# fetch_vicroads_data — requests.get mock
# ---------------------------------------------------------------------------


def test_fetch_vicroads_data_returns_json_and_datetime():
    from app.api_to_bucket import fetch_vicroads_data

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"features": []}

    with patch("app.api_to_bucket.requests.get", return_value=mock_resp):
        result_dict, result_dt = fetch_vicroads_data()

    assert result_dict == {"features": []}
    assert result_dt.tzinfo is not None


def test_fetch_vicroads_data_raises_on_non_200():
    from app.api_to_bucket import fetch_vicroads_data

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    with patch("app.api_to_bucket.requests.get", return_value=mock_resp):
        with pytest.raises(Exception, match="Internal Server Error"):
            fetch_vicroads_data()


# ---------------------------------------------------------------------------
# api_to_bucket orchestration
# ---------------------------------------------------------------------------


def test_api_to_bucket_chains_fetch_process_save():
    from app.api_to_bucket import api_to_bucket

    fake_resp = {"features": []}
    fake_now = datetime.now()
    fake_df = pl.DataFrame({"x": [1]})

    with (
        patch(
            "app.api_to_bucket.fetch_vicroads_data", return_value=(fake_resp, fake_now)
        ) as mock_fetch,
        patch("app.api_to_bucket.process_traffic_data", return_value=fake_df) as mock_process,
        patch("app.api_to_bucket.save_to_gcs_bucket") as mock_save,
    ):
        api_to_bucket()

    mock_fetch.assert_called_once()
    mock_process.assert_called_once_with(fake_resp)
    mock_save.assert_called_once_with(fake_df, fake_now)


# ---------------------------------------------------------------------------
# raw_to_loaded orchestration
# ---------------------------------------------------------------------------


def test_raw_to_loaded_writes_loaded_then_batches_then_moves(raw_traffic_df):
    from app.to_bq import raw_to_loaded

    call_order = []

    def fake_write(df, tablename, **_):
        call_order.append(tablename)

    def fake_move(files, **_):
        call_order.append("move")

    with (
        patch("app.to_bq.load_from_bucket", return_value=raw_traffic_df),
        patch("app.to_bq.acl.write_to_bigquery", side_effect=fake_write),
        patch("app.to_bq.acl.move_gs_files", side_effect=fake_move),
    ):
        raw_to_loaded()

    assert "raw_fetched_traffic_api.loaded" in call_order
    assert "raw_fetched_traffic_api.batches" in call_order
    loaded_idx = call_order.index("raw_fetched_traffic_api.loaded")
    batches_idx = call_order.index("raw_fetched_traffic_api.batches")
    assert loaded_idx < batches_idx < call_order.index("move")


def test_raw_to_loaded_moves_pre_dedup_file_list(raw_traffic_df):
    # Files moved should be the unique paths from the raw data, not post-dedup
    from app.to_bq import raw_to_loaded, LBL_FILEPATH

    expected_paths = set(raw_traffic_df[LBL_FILEPATH].unique().to_list())
    moved = {}

    def capture_move(files, **_):
        moved["files"] = files

    with (
        patch("app.to_bq.load_from_bucket", return_value=raw_traffic_df),
        patch("app.to_bq.acl.write_to_bigquery"),
        patch("app.to_bq.acl.move_gs_files", side_effect=capture_move),
    ):
        raw_to_loaded()

    assert set(moved["files"]) == expected_paths
