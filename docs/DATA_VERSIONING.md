# Data Versioning

The project uses logical dataset versioning. It does not duplicate large data files.

## Dataset Version ID

`dataset_version_id` is deterministic and derived from:

```text
dataset_name + source_name + period_start + period_end + checksum + schema_hash
```

## Checksum

Checksums use SHA-256.

- Files: binary SHA-256.
- DataFrames: CSV representation with stable column ordering.

## Schema Hash

`schema_hash` represents the column and dtype signature of a dataset.

## Registered Datasets

The reconciliation flow registers metadata for:

- BCB series values
- B3 market prices
- CVM funds, when available
- B3 calendar reference file
- Excel and coverage exports

## Storage

Dataset versions are stored in:

```text
etl_dataset_version
```
