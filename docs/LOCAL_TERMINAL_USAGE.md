# Local Terminal Usage

PowerShell commands from the repository root.

```powershell
cd C:\Users\pedro\brazilian-financial-data-pipeline
```

Official local environment:

```powershell
.\.venv\Scripts\Activate.ps1
python --version
python -c "import sys; print(sys.executable)"
python -c "import numpy, pandas; print('numpy', numpy.__version__); print('pandas', pandas.__version__)"
```

Use the project `.venv` as the official environment. Do not run the project from Anaconda base directly and do not use the Python executable installed by Microsoft Store for homologation. The expected stack pins `numpy==1.26.4` and `pandas==2.2.3`.

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

Archive every run only when needed:

```powershell
python run_pipeline.py --skip-collection --enable-manifest --reconcile --archive-runs
python run_pipeline.py --reconcile-only --archive-runs
```

Artifact policy:

- `latest.*` is always the most recent state.
- `daily/YYYYMMDD.*` is overwritten throughout the same day.
- `runs/<run_id>.*` is created only when `--archive-runs` is used.
- `--retention-days 30` or `PIPELINE_RETENTION_DAYS=30` removes old files from `daily/` and `runs/`.
- Retention never removes `latest.*`, raw data files, SQLite databases, or Excel reports.

Generated DBs, Excel files, manifests and report artifacts are local execution outputs and should not be committed.

Safe ignored-artifact cleanup preview:

```powershell
git status --short
git clean -ndX
```

Only after reviewing the preview:

```powershell
git clean -fdX
```

Run historical backfill collection:

```powershell
python collect_data.py --start-date 2024-01-01 --end-date 2026-06-28
```

Recent monthly series:

```powershell
python collect_data.py --start-date 2026-06-01 --end-date 2026-06-28
```

Monthly BCB series such as IPCA (`ipca_monthly`, SGS 433) may be unavailable for an open month or for a month still inside its publication lag. In that case the collection status must be `NOT_YET_AVAILABLE` with severity `WARNING`; the pipeline writes an empty CSV with the correct header to avoid reusing stale data and records the reason in:

```powershell
reports\collection\latest_collection_status.json
reports\collection\latest_collection_status.md
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
