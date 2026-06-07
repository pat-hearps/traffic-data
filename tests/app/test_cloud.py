import io
from contextlib import contextmanager
from unittest.mock import MagicMock, call, patch

import polars as pl

from app.cloud import move_gs_files, write_df_pqt, write_to_bigquery
from core.config import GCS_BUCKET, GCS_PROJECT


# ---------------------------------------------------------------------------
# move_gs_files
# ---------------------------------------------------------------------------


def _make_files(bucket, dir_, n):
    return [f"gs://{bucket}/{dir_}/2025/03/05/file_{i:03d}.pqt" for i in range(n)]


def test_move_gs_files_strips_bucket_prefix_correctly():
    files = _make_files(GCS_BUCKET, "raw1", 1)
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_client.get_bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_blob.name = f"{GCS_BUCKET}/raw1/2025/03/05/file_000.pqt"
    mock_bucket.get_blob.return_value = mock_blob

    with patch("app.cloud.storage.Client", return_value=mock_client):
        move_gs_files(files, src_dir="raw1", trg_dir="read1", bucket_name=GCS_BUCKET)

    # Blob name passed to get_blob should not include the bucket prefix
    called_blob_name = mock_bucket.get_blob.call_args[0][0]
    assert not called_blob_name.startswith(GCS_BUCKET)
    assert "raw1" in called_blob_name


def test_move_gs_files_new_name_replaces_src_with_trg():
    files = _make_files(GCS_BUCKET, "raw1", 1)
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_client.get_bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_blob.name = "raw1/2025/03/05/file_000.pqt"
    mock_bucket.get_blob.return_value = mock_blob

    with patch("app.cloud.storage.Client", return_value=mock_client):
        move_gs_files(files, src_dir="raw1", trg_dir="read1", bucket_name=GCS_BUCKET)

    copy_kwargs = mock_bucket.copy_blob.call_args[1]
    assert copy_kwargs["new_name"] == "read1/2025/03/05/file_000.pqt"


def test_move_gs_files_batches_correctly():
    n_files = 250
    files = _make_files(GCS_BUCKET, "raw1", n_files)
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_client.get_bucket.return_value = mock_bucket
    mock_blob = MagicMock()
    mock_blob.name = "raw1/2025/03/05/file_000.pqt"
    mock_bucket.get_blob.return_value = mock_blob

    with patch("app.cloud.storage.Client", return_value=mock_client):
        move_gs_files(files, src_dir="raw1", trg_dir="read1", bucket_name=GCS_BUCKET, n_per_batch=100)

    # 250 files / 100 per batch = 3 batches → delete_blobs called 3 times
    assert mock_bucket.delete_blobs.call_count == 3
    # copy_blob called once per file
    assert mock_bucket.copy_blob.call_count == n_files


# ---------------------------------------------------------------------------
# write_df_pqt
# ---------------------------------------------------------------------------


def test_write_df_pqt_opens_destination_in_wb_mode():
    df = pl.DataFrame({"x": [1, 2]})
    buf = io.BytesIO()
    mock_fs = MagicMock()
    # Use a real BytesIO so df.write_parquet() can write actual bytes
    mock_fs.open.return_value.__enter__ = MagicMock(return_value=buf)
    mock_fs.open.return_value.__exit__ = MagicMock(return_value=False)

    with patch("app.cloud.gcsfs.GCSFileSystem", return_value=mock_fs):
        write_df_pqt(df, "gs://bucket/path/file.pqt")

    mock_fs.open.assert_called_once_with("gs://bucket/path/file.pqt", mode="wb")


def test_write_df_pqt_writes_parquet_bytes():
    df = pl.DataFrame({"x": [1, 2]})
    buf = io.BytesIO()
    mock_fs = MagicMock()
    mock_fs.open.return_value.__enter__ = MagicMock(return_value=buf)
    mock_fs.open.return_value.__exit__ = MagicMock(return_value=False)

    with patch("app.cloud.gcsfs.GCSFileSystem", return_value=mock_fs):
        write_df_pqt(df, "gs://bucket/path/file.pqt")

    # Parquet magic bytes should be present
    assert buf.getvalue()[:4] == b"PAR1"


# ---------------------------------------------------------------------------
# write_to_bigquery
# ---------------------------------------------------------------------------


def test_write_to_bigquery_calls_load_table_from_file():
    df = pl.DataFrame({"x": [1, 2]})
    mock_client = MagicMock()
    mock_job = MagicMock()
    mock_client.load_table_from_file.return_value = mock_job

    with patch("app.cloud.bigquery.Client", return_value=mock_client):
        write_to_bigquery(df, tablename="dataset.table", project=GCS_PROJECT)

    mock_client.load_table_from_file.assert_called_once()
    call_kwargs = mock_client.load_table_from_file.call_args[1]
    assert call_kwargs["destination"] == "dataset.table"
    assert call_kwargs["project"] == GCS_PROJECT


def test_write_to_bigquery_waits_for_job_result():
    df = pl.DataFrame({"x": [1]})
    mock_client = MagicMock()
    mock_job = MagicMock()
    mock_client.load_table_from_file.return_value = mock_job

    with patch("app.cloud.bigquery.Client", return_value=mock_client):
        write_to_bigquery(df, tablename="dataset.table")

    mock_job.result.assert_called_once()
