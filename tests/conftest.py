import json
import os
from pathlib import Path

import pytest

# Must be set before any app/core module is imported, as core.config reads them at import time.
os.environ.setdefault("API_KEY_TRAFFIC", "test-key")
os.environ.setdefault("GCS_PROJECT", "test-project")
os.environ.setdefault("GCS_BUCKET", "test-bucket")
os.environ.setdefault("ENVIRONMENT", "test")

import tests.utils as tu  # noqa: E402 — import after env vars are set


@pytest.fixture
def vicroads_response():
    path = Path("tests/data_files/vicroads_api_sample.json")
    return json.loads(path.read_text())


@pytest.fixture
def raw_traffic_df():
    return tu.read_test_data("tests/data_files/bucket_raw.txt")
