# Architecture

## Layers

The project is organized as a local DataOps pipeline for Brazilian financial data.

1. Collection: public APIs from BCB/SGS and Yahoo Finance through `yfinance`, plus optional institutional CVM funds.
2. Validation: raw-data quality checks, gaps, duplicates, nulls, invalid values and OHLC consistency.
3. Reference data: controlled B3 calendar in `data/reference/b3_trading_calendar.csv`.
4. Storage: normalized SQLite model in `data/processed/financial_data.db`.
5. Data coverage: historical expected-versus-actual coverage by source and calendar.
6. Observability: operational SQLite in `data/operations/pipeline_operations.db`.
7. Consumption: Excel report and Streamlit dashboard.
8. Automation: APScheduler and the master command `src/run_pipeline.py`.

## Databases

`data/processed/financial_data.db` stores analytical financial data and views.

`data/operations/pipeline_operations.db` stores local operational metadata:

- `pipeline_runs`
- `source_freshness`
- `data_artifacts`

The operational database is ignored by Git because it is local runtime state.

## Main Modules

- `src/collect_data.py`: collects raw market and macro data.
- `src/collectors/cvm_funds.py`: optional CVM funds collection.
- `src/collectors/anbima_client.py`: optional ANBIMA adapter, disabled by default.
- `src/reference_data/b3_calendar.py`: controlled B3 trading calendar helpers.
- `src/validate_data.py`: validates raw files and writes validation artifacts.
- `src/load_processed_data.py`: loads normalized SQLite tables and freshness.
- `src/coverage_report.py`: creates historical coverage reports and missing-date evidence.
- `src/generate_report.py`: creates the Excel report.
- `src/run_pipeline.py`: orchestrates the full pipeline.
- `src/alerts.py`: generates operational alerts.
- `src/dashboard.py`: exposes executive, operational and market analytics pages.
- `src/analytics/market_metrics.py`: pure financial analytics functions.

## Institutional Tables

- `dim_cvm_fund`
- `fact_cvm_fund_daily_report`

Institutional views:

- `vw_cvm_fund_daily_reports`
- `vw_cvm_fund_latest_snapshot`
- `vw_cvm_top_funds_by_net_asset`
- `vw_cvm_fund_flows_monthly`

## Improvement 10 Boundary

The architecture now has clear extension points for governance, reconciliation and PostgreSQL, but those items are intentionally not implemented in Improvement 9. Future work should build on `data_artifacts`, source freshness, B3 calendar and institutional tables.

## Artifacts

The pipeline produces raw CSVs, validation reports, coverage reports, processed SQLite, Excel report and operational alerts. Runtime operational artifacts are registered in `data_artifacts`.
