DROP VIEW IF EXISTS vw_macro_indicators_summary CASCADE;
DROP VIEW IF EXISTS vw_source_availability_summary CASCADE;
DROP VIEW IF EXISTS vw_pipeline_health_daily CASCADE;
DROP VIEW IF EXISTS vw_data_freshness_status CASCADE;
DROP VIEW IF EXISTS vw_asset_returns_ranking CASCADE;
DROP VIEW IF EXISTS vw_market_latest_indicators CASCADE;
DROP VIEW IF EXISTS fact_bcb_series CASCADE;
DROP VIEW IF EXISTS vw_b3_asset_returns CASCADE;
DROP VIEW IF EXISTS vw_bcb_latest_snapshot CASCADE;
DROP VIEW IF EXISTS vw_b3_stock_monthly_summary CASCADE;
DROP VIEW IF EXISTS vw_bcb_series_monthly_summary CASCADE;
DROP VIEW IF EXISTS vw_b3_stock_prices CASCADE;
DROP VIEW IF EXISTS vw_bcb_series_values CASCADE;
DROP TABLE IF EXISTS fact_cvm_fund_daily_report CASCADE;
DROP TABLE IF EXISTS fact_b3_stock_prices CASCADE;
DROP TABLE IF EXISTS fact_bcb_series_values CASCADE;
DROP TABLE IF EXISTS dim_cvm_fund CASCADE;
DROP TABLE IF EXISTS dim_b3_ticker CASCADE;
DROP TABLE IF EXISTS dim_bcb_series CASCADE;
DROP TABLE IF EXISTS dim_source CASCADE;

CREATE TABLE dim_source (
    source_id SERIAL PRIMARY KEY,
    source_name TEXT NOT NULL UNIQUE,
    source_type TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE dim_bcb_series (
    series_id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES dim_source(source_id),
    series_code INTEGER NOT NULL,
    series_name TEXT NOT NULL,
    description TEXT,
    frequency TEXT NOT NULL,
    unit TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_dim_bcb_series_code UNIQUE (source_id, series_code)
);

CREATE TABLE dim_b3_ticker (
    ticker_id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES dim_source(source_id),
    ticker TEXT NOT NULL,
    market TEXT NOT NULL DEFAULT 'B3',
    currency TEXT NOT NULL DEFAULT 'BRL',
    asset_type TEXT NOT NULL DEFAULT 'EQUITY',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_dim_b3_ticker UNIQUE (source_id, ticker)
);

CREATE TABLE fact_bcb_series_values (
    observation_id SERIAL PRIMARY KEY,
    series_id INTEGER NOT NULL REFERENCES dim_bcb_series(series_id),
    reference_date DATE NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    collected_at TIMESTAMP WITH TIME ZONE,
    loaded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_fact_bcb_series_date UNIQUE (series_id, reference_date)
);

CREATE TABLE fact_b3_stock_prices (
    price_id SERIAL PRIMARY KEY,
    ticker_id INTEGER NOT NULL REFERENCES dim_b3_ticker(ticker_id),
    reference_date DATE NOT NULL,
    open_price DOUBLE PRECISION NOT NULL CHECK (open_price >= 0),
    high_price DOUBLE PRECISION NOT NULL CHECK (high_price >= 0),
    low_price DOUBLE PRECISION NOT NULL CHECK (low_price >= 0),
    close_price DOUBLE PRECISION NOT NULL CHECK (close_price >= 0),
    adjusted_close_price DOUBLE PRECISION NOT NULL CHECK (adjusted_close_price >= 0),
    volume BIGINT NOT NULL CHECK (volume >= 0),
    collected_at TIMESTAMP WITH TIME ZONE,
    loaded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_fact_b3_ticker_date UNIQUE (ticker_id, reference_date),
    CONSTRAINT ck_high_greater_equal_low CHECK (high_price >= low_price)
);

CREATE TABLE dim_cvm_fund (
    fund_id SERIAL PRIMARY KEY,
    fund_cnpj TEXT NOT NULL UNIQUE,
    fund_name TEXT,
    fund_status TEXT,
    registration_date DATE,
    fund_type TEXT,
    target_investor TEXT,
    source TEXT NOT NULL DEFAULT 'CVM',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE fact_cvm_fund_daily_report (
    fund_report_id SERIAL PRIMARY KEY,
    fund_id INTEGER NOT NULL REFERENCES dim_cvm_fund(fund_id),
    reference_date DATE NOT NULL,
    total_portfolio_value DOUBLE PRECISION,
    net_asset_value DOUBLE PRECISION NOT NULL CHECK (net_asset_value >= 0),
    quota_value DOUBLE PRECISION NOT NULL CHECK (quota_value > 0),
    daily_subscriptions DOUBLE PRECISION,
    daily_redemptions DOUBLE PRECISION,
    number_of_shareholders INTEGER CHECK (number_of_shareholders >= 0),
    collected_at TIMESTAMP WITH TIME ZONE,
    loaded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_fact_cvm_fund_date UNIQUE (fund_id, reference_date)
);

CREATE INDEX idx_fact_bcb_series_date ON fact_bcb_series_values(series_id, reference_date);
CREATE INDEX idx_fact_b3_ticker_date ON fact_b3_stock_prices(ticker_id, reference_date);
CREATE INDEX idx_fact_b3_reference_date ON fact_b3_stock_prices(reference_date);
CREATE INDEX idx_fact_cvm_fund_date ON fact_cvm_fund_daily_report(fund_id, reference_date);

CREATE VIEW fact_bcb_series AS
SELECT * FROM fact_bcb_series_values;

CREATE VIEW vw_bcb_series_values AS
SELECT src.source_name, s.series_code, s.series_name, s.description, s.frequency,
       f.reference_date, f.value, f.collected_at, f.loaded_at
FROM fact_bcb_series_values f
JOIN dim_bcb_series s ON f.series_id = s.series_id
JOIN dim_source src ON s.source_id = src.source_id;

CREATE VIEW vw_b3_stock_prices AS
SELECT src.source_name, t.ticker, t.market, t.currency, t.asset_type,
       f.reference_date, f.open_price, f.high_price, f.low_price, f.close_price,
       f.adjusted_close_price, f.volume, f.collected_at, f.loaded_at
FROM fact_b3_stock_prices f
JOIN dim_b3_ticker t ON f.ticker_id = t.ticker_id
JOIN dim_source src ON t.source_id = src.source_id;

CREATE VIEW vw_bcb_series_monthly_summary AS
SELECT series_name,
       TO_CHAR(reference_date, 'YYYY-MM') AS reference_month,
       COUNT(*) AS observations,
       ROUND(AVG(value)::numeric, 6) AS avg_value,
       ROUND(MIN(value)::numeric, 6) AS min_value,
       ROUND(MAX(value)::numeric, 6) AS max_value
FROM vw_bcb_series_values
GROUP BY series_name, TO_CHAR(reference_date, 'YYYY-MM');

CREATE VIEW vw_b3_stock_monthly_summary AS
SELECT ticker,
       TO_CHAR(reference_date, 'YYYY-MM') AS reference_month,
       COUNT(*) AS trading_days,
       ROUND(AVG(close_price)::numeric, 6) AS avg_close_price,
       SUM(volume) AS total_volume
FROM vw_b3_stock_prices
GROUP BY ticker, TO_CHAR(reference_date, 'YYYY-MM');

CREATE VIEW vw_bcb_latest_snapshot AS
SELECT DISTINCT ON (series_name)
       series_name, description, frequency,
       reference_date AS last_available_date,
       value AS latest_value
FROM vw_bcb_series_values
ORDER BY series_name, reference_date DESC;

CREATE VIEW vw_b3_asset_returns AS
WITH ranked AS (
    SELECT ticker, asset_type, reference_date, adjusted_close_price,
           FIRST_VALUE(reference_date) OVER (PARTITION BY ticker ORDER BY reference_date) AS start_date,
           FIRST_VALUE(reference_date) OVER (PARTITION BY ticker ORDER BY reference_date DESC) AS end_date,
           FIRST_VALUE(adjusted_close_price) OVER (PARTITION BY ticker ORDER BY reference_date) AS first_adjusted_close,
           FIRST_VALUE(adjusted_close_price) OVER (PARTITION BY ticker ORDER BY reference_date DESC) AS last_adjusted_close,
           ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY reference_date DESC) AS rn
    FROM vw_b3_stock_prices
)
SELECT ticker, asset_type, start_date, end_date,
       first_adjusted_close, last_adjusted_close,
       ROUND((((last_adjusted_close / NULLIF(first_adjusted_close, 0)) - 1) * 100)::numeric, 4) AS return_pct
FROM ranked
WHERE rn = 1;

CREATE VIEW vw_market_latest_indicators AS
WITH ranked AS (
    SELECT series_name, reference_date, value,
           LEAD(value) OVER (PARTITION BY series_name ORDER BY reference_date DESC) AS previous_value,
           ROW_NUMBER() OVER (PARTITION BY series_name ORDER BY reference_date DESC) AS row_number
    FROM vw_bcb_series_values
)
SELECT series_name,
       reference_date AS latest_date,
       ROUND(value::numeric, 6) AS latest_value,
       ROUND(previous_value::numeric, 6) AS previous_value,
       CASE
           WHEN previous_value IS NULL OR previous_value = 0 THEN NULL
           ELSE ROUND((((value / previous_value) - 1) * 100)::numeric, 6)
       END AS change_pct
FROM ranked
WHERE row_number = 1;

CREATE VIEW vw_asset_returns_ranking AS
WITH bounds AS (
    SELECT ticker, MIN(reference_date) AS period_start, MAX(reference_date) AS period_end
    FROM vw_b3_stock_prices
    GROUP BY ticker
),
prices AS (
    SELECT b.ticker, b.period_start, b.period_end,
           (SELECT adjusted_close_price FROM vw_b3_stock_prices p WHERE p.ticker = b.ticker ORDER BY p.reference_date ASC LIMIT 1) AS first_full_price,
           (SELECT adjusted_close_price FROM vw_b3_stock_prices p WHERE p.ticker = b.ticker ORDER BY p.reference_date DESC LIMIT 1) AS last_price,
           (SELECT adjusted_close_price FROM vw_b3_stock_prices p WHERE p.ticker = b.ticker AND p.reference_date >= b.period_end - INTERVAL '30 days' ORDER BY p.reference_date ASC LIMIT 1) AS first_30d_price,
           (SELECT adjusted_close_price FROM vw_b3_stock_prices p WHERE p.ticker = b.ticker AND p.reference_date >= b.period_end - INTERVAL '90 days' ORDER BY p.reference_date ASC LIMIT 1) AS first_90d_price
    FROM bounds b
)
SELECT ticker,
       ROUND((((last_price / NULLIF(first_30d_price, 0)) - 1) * 100)::numeric, 4) AS return_30d_pct,
       ROUND((((last_price / NULLIF(first_90d_price, 0)) - 1) * 100)::numeric, 4) AS return_90d_pct,
       ROUND((((last_price / NULLIF(first_full_price, 0)) - 1) * 100)::numeric, 4) AS return_full_pct,
       period_start,
       period_end
FROM prices
ORDER BY return_full_pct DESC;

CREATE VIEW vw_data_freshness_status AS
WITH source_dates AS (
    SELECT source_name, series_name, MAX(reference_date) AS last_date
    FROM vw_bcb_series_values
    GROUP BY source_name, series_name
    UNION ALL
    SELECT source_name, ticker AS series_name, MAX(reference_date) AS last_date
    FROM vw_b3_stock_prices
    GROUP BY source_name, ticker
),
freshness AS (
    SELECT source_name, series_name, last_date, (CURRENT_DATE - last_date) AS days_since_update
    FROM source_dates
)
SELECT source_name, series_name, last_date, days_since_update,
       CASE
           WHEN days_since_update <= 1 THEN 'FRESH'
           WHEN days_since_update <= 7 THEN 'RECENT'
           ELSE 'STALE'
       END AS freshness_status
FROM freshness
ORDER BY source_name, series_name;

CREATE VIEW vw_pipeline_health_daily AS
SELECT CURRENT_DATE AS execution_date,
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
    SELECT source_name, COUNT(*) AS total_loaded, MAX(reference_date) AS last_update
    FROM vw_bcb_series_values
    GROUP BY source_name
    UNION ALL
    SELECT source_name, COUNT(*) AS total_loaded, MAX(reference_date) AS last_update
    FROM vw_b3_stock_prices
    GROUP BY source_name
)
SELECT source_name, total_loaded, last_update, (CURRENT_DATE - last_update) AS days_since_update
FROM source_summary
ORDER BY source_name;

CREATE VIEW vw_macro_indicators_summary AS
SELECT TO_CHAR(reference_date, 'YYYY-MM') AS reference_month,
       ROUND(AVG(CASE WHEN series_name = 'selic_daily' THEN value END)::numeric, 6) AS selic_avg,
       ROUND(MAX(CASE WHEN series_name = 'ipca_monthly' THEN value END)::numeric, 6) AS ipca_value,
       ROUND(AVG(CASE WHEN series_name = 'cdi_daily' THEN value END)::numeric, 6) AS cdi_avg,
       ROUND(AVG(CASE WHEN series_name = 'usd_brl_ptax_sell_daily' THEN value END)::numeric, 6) AS usd_brl_avg
FROM vw_bcb_series_values
WHERE series_name IN ('selic_daily', 'ipca_monthly', 'cdi_daily', 'usd_brl_ptax_sell_daily')
GROUP BY TO_CHAR(reference_date, 'YYYY-MM')
ORDER BY reference_month;
