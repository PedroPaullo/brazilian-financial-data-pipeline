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
python src\run_pipeline.py --start 2024-01-01 --end 2024-12-31 --modules validate load coverage report
```

Run collection with optional CVM funds:

```powershell
python src\run_pipeline.py --start 2024-01-01 --end 2024-12-31 --include-cvm --cvm-year-month 202401 --cvm-top-n 100
```

## B3 Calendar

The controlled B3 calendar is stored at:

```text
data/reference/b3_trading_calendar.csv
```

Validation and coverage use this file when available. If it is missing, the project uses a fallback weekday/holiday calendar and records a WARN in validation.

## CVM Funds

Collect CVM funds independently:

```powershell
python src\collectors\cvm_funds.py --year-month 202401 --top-n 100
```

Then run validation, load, coverage and report:

```powershell
python src\run_pipeline.py --start 2024-01-01 --end 2024-12-31 --skip-collection
```

If CVM files are absent, validation and storage skip CVM without failing the base pipeline.

## ANBIMA

The adapter is disabled by default:

```powershell
$env:ANBIMA_ENABLE="false"
python src\collectors\anbima_prices.py
```

Without credentials, it returns a controlled SKIPPED status.

## Coverage

```powershell
python src\coverage_report.py --start 2024-01-01 --end 2024-12-31
```

Coverage artifacts are written to:

- `reports/coverage/data_coverage_report.csv`
- `reports/coverage/data_coverage_summary.json`
- `reports/coverage/data_coverage_missing_dates.csv`

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

Coverage warnings and critical gaps are also included in operational alerts.

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
