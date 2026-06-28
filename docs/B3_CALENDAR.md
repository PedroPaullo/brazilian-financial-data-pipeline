# B3 Calendar

## Scope

The B3 calendar is controlled locally and auditable.

File:

```text
data/reference/b3_trading_calendar.csv
```

Columns:

- `date`
- `is_trading_day`
- `market`
- `reason`
- `source`
- `updated_at`

## Covered Years

- 2024
- 2025
- 2026

## Usage

Python helper:

```text
src/reference_data/b3_calendar.py
```

Main functions:

- `load_b3_calendar()`
- `is_b3_trading_day(date)`
- `get_b3_expected_trading_dates(start_date, end_date)`
- `get_missing_trading_dates(actual_dates, start_date, end_date)`
- `classify_b3_gap(date)`

## Fallback

If the CSV is missing, the helper generates a fallback calendar based on weekdays and known B3-relevant holidays. The validation layer records a WARN when fallback is used.

## Consumers

- market-data validation
- historical coverage report
- dashboard coverage view
- future reconciliation logic in Improvement 10
