# Local Terminal Usage

PowerShell commands from the repository root.

```powershell
cd C:\Users\pedro\brazilian-financial-data-pipeline
```

Update project:

```powershell
git fetch origin
git pull --ff-only origin main
```

Test entrypoints:

```powershell
python collect_data.py --help
python run_pipeline.py --help
```

Run pipeline without external collection:

```powershell
python run_pipeline.py --skip-collection
```

Run traceability and reconciliation:

```powershell
python run_pipeline.py --skip-collection --enable-manifest --reconcile
python run_pipeline.py --reconcile-only
```

Run historical backfill collection:

```powershell
python collect_data.py --start-date 2024-01-01 --end-date 2026-06-28
```

Run optional CVM:

```powershell
python collect_data.py --include-cvm --cvm-year-month 2024-12 --cvm-top-n 100
```

Run ANBIMA safely:

```powershell
$env:ANBIMA_ENABLE="false"
python -m src.collectors.anbima_prices
```

The backfill command depends on internet access. It should not be used as an offline test.
