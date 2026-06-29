# Data Lineage

Data lineage is recorded through run manifests and SQLite audit tables.

## Run ID

`run_id` identifies a pipeline or reconciliation execution.

Example:

```text
20260628_153000_pipeline_ab12cd34
```

## Manifest

Run manifests are JSON files under:

```text
data/manifests/latest.json
data/manifests/daily/YYYYMMDD.json
data/manifests/runs/<run_id>.json
```

`latest.json` is always overwritten with the most recent execution. `daily/YYYYMMDD.json` is overwritten during the same day. `runs/<run_id>.json` is created only when `--archive-runs` is used.

Each manifest records command, parameters, backend, enabled/skipped sources, inputs, outputs, checksums, date range, warnings and errors.

## Audit Tables

The processed SQLite database contains:

- `etl_run`
- `etl_dataset_version`
- `etl_reconciliation_check`
- `etl_source_file`

Useful views:

- `vw_etl_runs_latest`
- `vw_dataset_versions_latest`
- `vw_reconciliation_summary`
- `vw_reconciliation_failures`

## SKIPPED Controlado

Optional sources such as CVM and ANBIMA can be recorded as `SKIPPED` without failing the base pipeline.
