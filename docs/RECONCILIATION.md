# Reconciliation

Reconciliation validates local artifacts, SQLite tables, metadata and optional institutional sources.

## Commands

```powershell
python run_pipeline.py --skip-collection --enable-manifest --reconcile
python run_pipeline.py --reconcile-only
```

## Outputs

Latest:

- `reports/reconciliation/latest.md`
- `reports/reconciliation/latest.csv`
- `reports/reconciliation/latest.json`

By run:

- `reports/reconciliation/runs/{run_id}.md`
- `reports/reconciliation/runs/{run_id}.csv`
- `reports/reconciliation/runs/{run_id}.json`

## Check Status

- `PASSED`: check succeeded.
- `FAILED`: check found a real issue.
- `SKIPPED`: optional source or unavailable context was safely skipped.

## Current Checks

- expected local files
- SQLite database
- required tables
- row counts
- duplicate natural keys
- future dates
- critical nulls
- CVM optional status
- ANBIMA optional status
- manifest creation
- dataset version registration
- coverage summary

## Limitations

Reconciliation is local and offline by design. It does not contact external providers and does not validate a real two-year backfill unless that backfill has already been executed.
