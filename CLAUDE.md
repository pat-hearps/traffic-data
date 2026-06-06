# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies (use uv)
uv sync --all-extras

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

- You (claude, the ai agent) are an advanced computer program, not a human. Do not try to pretend to be a human.
- If you don't know the answer, say "I don't know" — do not construct a plausible-sounding explanation.
- If you are uncertain, say so explicitly before giving the answer, not after.
- Do not explain your own errors by attributing human cognitive processes (e.g. "I generalised", "I misread") — you cannot introspect on your inference process. Prefer: "I was wrong, I don't know why."
- If asked how something works internally (model behaviour, what gets sent to the API, why you produced a specific output), acknowledge the limits of your self-knowledge.
- Prefer "I'm not sure if that's possible" over attempting something and silently failing or producing a made-up result.
- Never invent API methods, function signatures, config options, or file paths. If unsure whether something exists, say so and check first.

## Security Constraints

- GitHub access is via a restricted personal access token scoped only to this project's repository (`pat-hearps/traffic-data`). Do not attempt to access other GitHub repositories using this token.
- Do **not** clone, fetch, or download code from any external repository (including public GitHub repos) without explicit user instruction for each specific case.
- Do **not** run `pip install`, `pip3 install`, or `uv add` / `uv pip install` to install packages from external sources without explicit user instruction.
- Do **not** execute scripts or code fetched from external URLs (e.g. `curl ... | bash` or similar patterns).
- Dependency changes must be explicitly requested by the user and limited to this project's own `pyproject.toml` / `uv.lock`.

## Versioning

Version is tracked in `core/VERSION` (source of truth) and kept in sync with `pyproject.toml` and `bumpversion.toml` by `bump-my-version`. `core.__version__` reads `core/VERSION` at import time.

**Version scheme (PEP 440):**
- Dev: `{major}.{minor}.{patch}.dev{N}` — e.g. `0.1.0.dev3`
- Release: `{major}.{minor}.{patch}` — e.g. `0.1.0`

**Bumping versions** — use `bin/bump.sh` (requires `bump-my-version` on PATH):

```bash
source .venv/bin/activate          # bump-my-version lives in the ci extras
bash bin/bump.sh                   # dev bump: 0.1.0.dev1 → 0.1.0.dev2 (must be on 'dev' branch)
bash bin/bump.sh patch             # release: 0.1.0.dev2 → 0.1.0, then → 0.1.1.dev0 (must be on 'main')
bash bin/bump.sh minor             # minor release: bumps minor component before releasing
bash bin/bump.sh --dry-run         # preview the next version without writing anything
bash bin/bump.sh --push            # also push commits + tags to remote after bumping
```

Rules enforced by `bin/bump.sh`:
- Must be on `main` to cut a release; must be on `dev` for a dev bump; any other branch exits with an error.
- A release bump on `main` immediately follows up with a patch dev bump, so the only commit ever carrying a clean release version (`0.1.0`) is the tagged release commit itself.
- `--dry-run` is approximate for multi-step release paths (major/minor): only the first intermediate step is previewed accurately.

**Do not edit** `core/VERSION`, `pyproject.toml`'s version field, or `bumpversion.toml`'s `current_version` by hand — always go through `bump-my-version` so all three stay in sync. The `test_version_files_in_sync` test will catch any drift.

## Technical Debt

Known technical debt items are tracked in `.claude/todo.md`.

## Notes

- `compose.yaml` defines a Kafka broker but it is **not wired into the application** — treat as future/unused infrastructure.
- GCP auth uses GCP Secrets Manager in production. The code uses `token="google_default"` in `gcsfs` and implicit credentials in `bigquery.Client()`, but do not assume local ADC is sufficient — prod authentication is handled via GCP Secrets.
- Ruff is configured to max line length 99; magic trailing commas are skipped in formatting.
