# Technical Debt / TODOs

## Lazy import in `save_to_gcs_bucket`

`write_df_pqt` is imported inside `save_to_gcs_bucket()` (in `app/api_to_bucket.py`) rather than
at module level. This is intentional — importing `app.cloud` at module level triggers GCP
auth/connection which slows development startup significantly.

A better long-term solution should replace this pattern, e.g.:
- Lazy client initialisation inside `app/cloud.py` itself
- Dependency injection (pass the write function in)
- Deferred/cached GCP credential resolution
