# Operations

## Run Full Pipeline

```powershell
python src\run_pipeline.py --start 2024-01-01 --end 2024-12-31
```

Without external collection:

```powershell
python src\run_pipeline.py --start 2024-01-01 --end 2024-12-31 --skip-collection
```

Specific modules:

```powershell
python src\run_pipeline.py --start 2024-01-01 --end 2024-12-31 --modules validate load report
```

## Scheduler

```powershell
python src\scheduler.py
```

One-off scheduler execution:

```powershell
python src\scheduler.py --run-now
```

## Alerts

```powershell
python src\alerts.py
```

Alerts are written to:

- `reports/operations/alerts.json`
- `reports/operations/alerts.csv`

Alert severities:

- `INFO`: informational status.
- `WARNING`: review recommended.
- `CRITICAL`: action required before trusting outputs.

## Dashboard

```powershell
python -m streamlit run src\dashboard.py
```

Use `PYTHONNOUSERSITE=1` if local user-site packages conflict with the selected Python environment.

```powershell
$env:PYTHONNOUSERSITE="1"
```

## Operational Tables

Inspect recent runs:

```sql
SELECT * FROM pipeline_runs ORDER BY run_id DESC;
```

Inspect freshness:

```sql
SELECT * FROM source_freshness ORDER BY source_name, dataset_name;
```

Inspect artifacts:

```sql
SELECT * FROM data_artifacts ORDER BY artifact_id DESC;
```
