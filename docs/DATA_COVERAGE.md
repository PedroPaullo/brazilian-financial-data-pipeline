# Data Coverage

## Objective

The historical coverage layer answers whether each dataset has enough records for the expected period and calendar.

It does not collect new data. It compares the records already loaded in `data/processed/financial_data.db` against the expected dates for each source.

## Command

```powershell
python src\coverage_report.py --start 2024-01-01 --end 2024-12-31
```

## Outputs

- `reports/coverage/data_coverage_report.csv`
- `reports/coverage/data_coverage_summary.json`
- `reports/coverage/data_coverage_missing_dates.csv`

## Calendars

- BCB daily series use Brazilian business days.
- IPCA uses monthly dates.
- Yahoo Finance B3 assets use trading-day frequency based on the current financial calendar fallback.

The controlled B3 calendar is intentionally left for the institutional-source improvement.

## Status Rules

- `OK`: coverage at or above 98% with limited missing dates.
- `WARNING`: coverage at or above 90%.
- `CRITICAL`: coverage below 90%.
- `UNKNOWN`: no expected dates available.

## Consumers

Coverage is exposed in:

- Dashboard page `Cobertura Historica`
- Excel sheet `Cobertura`
- Operational alerts
- `data_artifacts` lineage records
