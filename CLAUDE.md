# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies (use uv)
uv pip install -r pyproject.toml --all-extras

# Run tests
pytest

# Run a single test
pytest tests/app/test_to_bq.py::test_process

# Lint / format
ruff check .
ruff format .

# Run the FastAPI app locally
python -m app.main
```

## Architecture

This is a two-stage data pipeline that fetches Melbourne freeway traffic data and loads it into BigQuery, exposed via a FastAPI app.

**Stage 1 — API → GCS** (`app/api_to_bucket.py`):
Hits the VicRoads freeway travel time API, filters to Eastern Freeway only (`FWY_FILTER` in `core/config.py`), parses segment properties into a Polars DataFrame, and writes a parquet file to GCS under `raw1/YYYY/mm/dd/traffic_Eastern_Fwy_HHMMSS.pqt`.

**Stage 2 — GCS → BigQuery** (`app/to_bq.py`):
Scans all parquet files from GCS `raw1/` (or a specific `YYYY/mm/dd` date prefix), deduplicates rows by keeping only the first timestamp where any fact value changed (excluding `publishedTime` and `raw_file_path` from the comparison), loads into `raw_fetched_traffic_api.loaded`, writes batch metadata to `raw_fetched_traffic_api.batches`, then moves processed files from `raw1/` to `read1/` in the same bucket.

**GCP I/O** (`app/cloud.py`):
- `write_df_pqt`: writes Polars DataFrame → parquet directly to GCS via `gcsfs` (no temp disk)
- `write_to_bigquery`: streams DataFrame → parquet bytestream → BigQuery load job (no temp disk)
- `move_gs_files`: copy-then-delete move in batches of 100 blobs

**FastAPI endpoints** (`app/main.py`):
- `GET /` — triggers Stage 1
- `GET|POST /bq_load` — triggers Stage 2; POST body accepts `{"dt_glob": "YYYY/mm/dd"}` to restrict to one day

**Config** (`core/config.py`): all environment variables loaded via `python-decouple`. Required: `API_KEY_TRAFFIC`, `GCS_PROJECT`, `GCS_BUCKET`. Optional: `ENVIRONMENT` (defaults to `"local"`). BigQuery dataset location is hardcoded to `europe-north1`.

## Testing

Tests use pytest with fixed-width `.txt` files as test data (human-readable, git-friendly). `tests/utils.py` handles reading/writing these files with datetime inference. The current test (`tests/app/test_to_bq.py`) exercises the deduplication logic in `to_bq.process()` without requiring GCP access.

Test data files live in `tests/data_files/`. To add new test data, use `tests/utils.py` helpers to write/read the fixed-width format — do not hand-edit the `.txt` files.

## Epistemic Honesty

- If you don't know the answer, say "I don't know" — do not construct a plausible-sounding explanation.
- If you are uncertain, say so explicitly before giving the answer, not after.
- Do not explain your own errors by attributing human cognitive processes (e.g. "I generalised", "I misread") — you cannot introspect on your inference process. Prefer: "I was wrong, I don't know why."
- If asked how something works internally (model behaviour, what gets sent to the API, why you produced a specific output), acknowledge the limits of your self-knowledge.
- Prefer "I'm not sure if that's possible" over attempting something and silently failing or producing a made-up result.
- Never invent API methods, function signatures, config options, or file paths. If unsure whether something exists, say so and check first.

## Notes

- `compose.yaml` defines a Kafka broker but it is **not wired into the application** — treat as future/unused infrastructure.
- GCP auth uses GCP Secrets Manager in production. The code uses `token="google_default"` in `gcsfs` and implicit credentials in `bigquery.Client()`, but do not assume local ADC is sufficient — prod authentication is handled via GCP Secrets.
- Ruff is configured to max line length 99; magic trailing commas are skipped in formatting.
