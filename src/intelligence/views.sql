CREATE VIEW vw_market_latest_indicators AS
WITH ranked AS (
    SELECT
        series_name,
        reference_date,
        value,
        LEAD(value) OVER (
            PARTITION BY series_name
            ORDER BY reference_date DESC
        ) AS previous_value,
        ROW_NUMBER() OVER (
            PARTITION BY series_name
            ORDER BY reference_date DESC
        ) AS row_number
    FROM vw_bcb_series_values
)
SELECT
    series_name,
    reference_date AS latest_date,
    ROUND(value, 6) AS latest_value,
    ROUND(previous_value, 6) AS previous_value,
    CASE
        WHEN previous_value IS NULL OR previous_value = 0 THEN NULL
        ELSE ROUND(((value / previous_value) - 1) * 100, 6)
    END AS change_pct
FROM ranked
WHERE row_number = 1;

CREATE VIEW vw_asset_returns_ranking AS
WITH bounds AS (
    SELECT
        ticker,
        MIN(reference_date) AS period_start,
        MAX(reference_date) AS period_end
    FROM vw_b3_stock_prices
    GROUP BY ticker
),
prices AS (
    SELECT
        b.ticker,
        b.period_start,
        b.period_end,
        (
            SELECT adjusted_close_price
            FROM vw_b3_stock_prices p
            WHERE p.ticker = b.ticker
            ORDER BY p.reference_date ASC
            LIMIT 1
        ) AS first_full_price,
        (
            SELECT adjusted_close_price
            FROM vw_b3_stock_prices p
            WHERE p.ticker = b.ticker
            ORDER BY p.reference_date DESC
            LIMIT 1
        ) AS last_price,
        (
            SELECT adjusted_close_price
            FROM vw_b3_stock_prices p
            WHERE p.ticker = b.ticker
              AND p.reference_date >= date(b.period_end, '-30 days')
            ORDER BY p.reference_date ASC
            LIMIT 1
        ) AS first_30d_price,
        (
            SELECT adjusted_close_price
            FROM vw_b3_stock_prices p
            WHERE p.ticker = b.ticker
              AND p.reference_date >= date(b.period_end, '-90 days')
            ORDER BY p.reference_date ASC
            LIMIT 1
        ) AS first_90d_price
    FROM bounds b
)
SELECT
    ticker,
    CASE
        WHEN first_30d_price IS NULL OR first_30d_price = 0 THEN NULL
        ELSE ROUND(((last_price / first_30d_price) - 1) * 100, 4)
    END AS return_30d_pct,
    CASE
        WHEN first_90d_price IS NULL OR first_90d_price = 0 THEN NULL
        ELSE ROUND(((last_price / first_90d_price) - 1) * 100, 4)
    END AS return_90d_pct,
    CASE
        WHEN first_full_price IS NULL OR first_full_price = 0 THEN NULL
        ELSE ROUND(((last_price / first_full_price) - 1) * 100, 4)
    END AS return_full_pct,
    period_start,
    period_end
FROM prices
ORDER BY return_full_pct DESC;

CREATE VIEW vw_data_freshness_status AS
WITH source_dates AS (
    SELECT
        source_name,
        series_name,
        MAX(reference_date) AS last_date
    FROM vw_bcb_series_values
    GROUP BY source_name, series_name
    UNION ALL
    SELECT
        source_name,
        ticker AS series_name,
        MAX(reference_date) AS last_date
    FROM vw_b3_stock_prices
    GROUP BY source_name, ticker
),
freshness AS (
    SELECT
        source_name,
        series_name,
        last_date,
        CAST(julianday(date('now')) - julianday(last_date) AS INTEGER) AS days_since_update
    FROM source_dates
)
SELECT
    source_name,
    series_name,
    last_date,
    days_since_update,
    CASE
        WHEN days_since_update <= 1 THEN 'FRESH'
        WHEN days_since_update <= 7 THEN 'RECENT'
        ELSE 'STALE'
    END AS freshness_status
FROM freshness
ORDER BY source_name, series_name;

CREATE VIEW vw_pipeline_health_daily AS
SELECT
    date('now') AS execution_date,
    (SELECT COUNT(*) FROM fact_bcb_series_values) AS total_bcb_records,
    (SELECT COUNT(*) FROM fact_b3_stock_prices) AS total_stock_records,
    CASE
        WHEN (SELECT COUNT(*) FROM fact_bcb_series_values) > 0
         AND (SELECT COUNT(*) FROM fact_b3_stock_prices) > 0
        THEN 'OK'
        ELSE 'FAILED'
    END AS overall_status;

CREATE VIEW vw_source_availability_summary AS
WITH source_summary AS (
    SELECT
        source_name,
        COUNT(*) AS total_loaded,
        MAX(reference_date) AS last_update
    FROM vw_bcb_series_values
    GROUP BY source_name
    UNION ALL
    SELECT
        source_name,
        COUNT(*) AS total_loaded,
        MAX(reference_date) AS last_update
    FROM vw_b3_stock_prices
    GROUP BY source_name
)
SELECT
    source_name,
    total_loaded,
    last_update,
    CAST(julianday(date('now')) - julianday(last_update) AS INTEGER) AS days_since_update
FROM source_summary
ORDER BY source_name;

CREATE VIEW vw_macro_indicators_summary AS
SELECT
    strftime('%Y-%m', reference_date) AS reference_month,
    ROUND(AVG(CASE WHEN series_name = 'selic_daily' THEN value END), 6) AS selic_avg,
    ROUND(MAX(CASE WHEN series_name = 'ipca_monthly' THEN value END), 6) AS ipca_value,
    ROUND(AVG(CASE WHEN series_name = 'cdi_daily' THEN value END), 6) AS cdi_avg,
    ROUND(AVG(CASE WHEN series_name = 'usd_brl_ptax_sell_daily' THEN value END), 6) AS usd_brl_avg
FROM vw_bcb_series_values
WHERE series_name IN ('selic_daily', 'ipca_monthly', 'cdi_daily', 'usd_brl_ptax_sell_daily')
GROUP BY strftime('%Y-%m', reference_date)
ORDER BY reference_month;
