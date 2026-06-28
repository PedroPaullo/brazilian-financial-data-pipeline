# CVM Funds

## Scope

The CVM funds layer adds an optional institutional source to the pipeline.

It supports:

- Informe Diario de Fundos
- Cadastro de Fundos, Classes e Subclasses

The basic BCB/Yahoo pipeline does not depend on CVM files.

## Commands

Collect one CVM month:

```powershell
python src\collectors\cvm_funds.py --year-month 202401
```

Collect only the largest funds in that month:

```powershell
python src\collectors\cvm_funds.py --year-month 202401 --top-n 100
```

Run the main collection with CVM enabled:

```powershell
python src\collect_data.py --start 2024-01-01 --end 2024-12-31 --include-cvm --cvm-year-month 202401
```

## Outputs

- `data/raw/cvm/funds_daily_reports.csv`
- `data/raw/cvm/funds_registry.csv`

These raw files are local runtime artifacts and are not intended to be committed when large.

## Storage

When CVM files exist, `load_processed_data.py` loads:

- `dim_cvm_fund`
- `fact_cvm_fund_daily_report`

Views:

- `vw_cvm_fund_daily_reports`
- `vw_cvm_fund_latest_snapshot`
- `vw_cvm_top_funds_by_net_asset`
- `vw_cvm_fund_flows_monthly`

## Validation

When CVM files exist, validation checks:

- required CNPJ and date
- non-negative net asset value
- positive quota value
- non-negative shareholders
- duplicate fund/date rows
- missing registry rows as WARN
- extreme net asset values as WARN

If CVM files do not exist, validation records a controlled `SKIPPED` status.
