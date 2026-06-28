# Architecture

## Layers

The project is organized as a local DataOps pipeline for Brazilian financial data.

1. Collection: public APIs from BCB/SGS and Yahoo Finance through `yfinance`, plus optional institutional CVM funds.
2. Validation: raw-data quality checks, gaps, duplicates, nulls, invalid values and OHLC consistency.
3. Reference data: controlled B3 calendar in `data/reference/b3_trading_calendar.csv`.
4. Storage: normalized SQLite model in `data/processed/financial_data.db`.
5. Data coverage: historical expected-versus-actual coverage by source and calendar.
6. Metadata: run manifests, dataset versions and source-file checksums.
7. Reconciliation: offline checks between artifacts, SQLite tables and metadata.
8. Observability: operational SQLite in `data/operations/pipeline_operations.db`.
9. Consumption: Excel report and Streamlit dashboard.
10. Automation: APScheduler and the master command `src/run_pipeline.py`.

## Databases

`data/processed/financial_data.db` stores analytical financial data and views.

`data/operations/pipeline_operations.db` stores local operational metadata:

- `pipeline_runs`
- `source_freshness`
- `data_artifacts`

`data/processed/financial_data.db` also contains traceability tables:

- `etl_run`
- `etl_dataset_version`
- `etl_reconciliation_check`
- `etl_source_file`

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
- `src/metadata/manifest.py`: creates run manifests and checksums.
- `src/metadata/dataset_versioning.py`: creates deterministic dataset version ids.
- `src/metadata/audit.py`: manages SQLite audit tables and views.
- `src/validation/reconciliation.py`: generates reconciliation reports.
- `src/storage/database.py`: validates optional database backend configuration.

## Institutional Tables

- `dim_cvm_fund`
- `fact_cvm_fund_daily_report`

Institutional views:

- `vw_cvm_fund_daily_reports`
- `vw_cvm_fund_latest_snapshot`
- `vw_cvm_top_funds_by_net_asset`
- `vw_cvm_fund_flows_monthly`

## Optional PostgreSQL

SQLite remains the default backend. PostgreSQL configuration is prepared and validated through `src/storage/database.py`, but complex migration/loading is intentionally not required for local tests.

## Artifacts

The pipeline produces raw CSVs, validation reports, coverage reports, processed SQLite, Excel report and operational alerts. Runtime operational artifacts are registered in `data_artifacts`.
