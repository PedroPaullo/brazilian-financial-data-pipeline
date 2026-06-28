# PostgreSQL Optional Backend

SQLite remains the default backend.

PostgreSQL is prepared as an optional backend for future production-style execution.

## Environment Variables

```env
DB_BACKEND=postgres
DATABASE_URL=postgresql+psycopg://user:password@host:5432/database
```

## Optional Dependencies

```powershell
pip install -r requirements-postgres.txt
```

## Commands

SQLite default:

```powershell
python run_pipeline.py --skip-collection
```

PostgreSQL prepared mode:

```powershell
python run_pipeline.py --skip-collection --database-backend postgres --database-url postgresql+psycopg://user:password@host:5432/database
```

## Current Limitation

The project validates PostgreSQL configuration and dependency availability, but SQLite remains the stable execution path. Complex migration/loading into PostgreSQL is intentionally deferred so the existing pipeline is not broken.

To return to SQLite:

```powershell
$env:DB_BACKEND="sqlite"
python run_pipeline.py --skip-collection
```
