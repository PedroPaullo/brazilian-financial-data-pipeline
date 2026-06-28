# ANBIMA Adapter

## Scope

The ANBIMA layer is an adapter prepared for future authenticated data access.

It is intentionally disabled by default:

```env
ANBIMA_ENABLE=false
```

Without credentials, the adapter returns `SKIPPED` and the pipeline continues normally.

## Environment Variables

```env
ANBIMA_CLIENT_ID=
ANBIMA_CLIENT_SECRET=
ANBIMA_ACCESS_TOKEN=
ANBIMA_ENV=sandbox
ANBIMA_ENABLE=false
```

## Commands

```powershell
python src\collectors\anbima_prices.py
```

Expected result without credentials:

```text
SKIPPED
```

## Prepared Domains

The adapter is prepared for:

- debentures secondary market
- credit curves
- public bonds, if endpoint access is contracted and documented

## Sample

A small offline sample is available at:

```text
data/sample/anbima/debentures_mercado_secundario_sample.csv
```

## Boundary

This improvement does not implement paid/production ANBIMA Feed access. Real endpoint integration depends on credentials, access grants and the contracted API surface.
