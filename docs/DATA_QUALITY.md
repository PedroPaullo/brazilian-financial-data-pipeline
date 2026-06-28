# Data Quality

## Validation Outputs

Validation artifacts are generated under `reports/validation/`:

- `data_quality_results.csv`
- `data_quality_summary.json`
- `date_gaps_detail.csv`

## Status Model

- `PASS`: rule passed.
- `WARN`: non-critical issue, usually calendar or market holiday gaps.
- `FAIL`: critical issue that should stop the pipeline.

## Current Rule Families

- Completeness: required columns cannot be null or blank.
- Uniqueness: natural keys cannot be duplicated.
- Validity: invalid negative values are blocked except IPCA deflation.
- Consistency: IPCA dates and OHLC stock fields are checked.
- Coverage: business-day or monthly gaps are reported.

## Freshness SLA

Freshness is stored in `source_freshness` with:

- expected frequency
- maximum accepted lag
- observed lag
- freshness status

Statuses:

- `OK`
- `WARNING`
- `CRITICAL`
- `UNKNOWN`

Daily business/trading-day sources use a default SLA of 2 business days. IPCA monthly uses 60 calendar days. Pipeline artifacts use 7 calendar days.

## Known Limitations

This project is a local professional DataOps portfolio project. It is inspired by regulated financial data practices, but it is not a certified banking production system.
