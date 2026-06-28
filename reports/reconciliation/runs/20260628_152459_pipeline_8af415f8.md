# Reconciliation Report

- run_id: `20260628_152459_pipeline_8af415f8`
- git_commit: `8bf6d3a885285ccd6d89a55c39bf9969e5262161`
- command: `run_pipeline.py --reconcile-only`
- overall_status: `PASSED`
- PASSED: 44
- FAILED: 0
- SKIPPED: 2

## Failed Checks
No failed checks.

## Known Limitations
- CVM and ANBIMA are optional institutional sources.
- PostgreSQL is prepared as an optional backend and is not required by default.
- Historical coverage for more than 2024 depends on executing and validating the real backfill.