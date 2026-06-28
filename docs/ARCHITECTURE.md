# Architecture

## Layers

The project is organized as a local DataOps pipeline for Brazilian financial data.

1. Collection: public APIs from BCB/SGS and Yahoo Finance through `yfinance`.
2. Validation: raw-data quality checks, gaps, duplicates, nulls, invalid values and OHLC consistency.
3. Storage: normalized SQLite model in `data/processed/financial_data.db`.
4. Observability: operational SQLite in `data/operations/pipeline_operations.db`.
5. Consumption: Excel report and Streamlit dashboard.
6. Automation: APScheduler and the master command `src/run_pipeline.py`.

## Databases

`data/processed/financial_data.db` stores analytical financial data and views.

`data/operations/pipeline_operations.db` stores local operational metadata:

- `pipeline_runs`
- `source_freshness`
- `data_artifacts`

The operational database is ignored by Git because it is local runtime state.

## Main Modules

- `src/collect_data.py`: collects raw market and macro data.
- `src/validate_data.py`: validates raw files and writes validation artifacts.
- `src/load_processed_data.py`: loads normalized SQLite tables and freshness.
- `src/generate_report.py`: creates the Excel report.
- `src/run_pipeline.py`: orchestrates the full pipeline.
- `src/alerts.py`: generates operational alerts.
- `src/dashboard.py`: exposes executive, operational and market analytics pages.
- `src/analytics/market_metrics.py`: pure financial analytics functions.

## Artifacts

The pipeline produces raw CSVs, validation reports, processed SQLite, Excel report and operational alerts. Runtime operational artifacts are registered in `data_artifacts`.
