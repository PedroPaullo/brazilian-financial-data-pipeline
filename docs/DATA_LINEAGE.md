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
data/manifests/runs/
```

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
