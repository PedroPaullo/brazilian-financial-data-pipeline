PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS dim_source (
    source_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL UNIQUE,
    source_type TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dim_bcb_series (
    series_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    series_code INTEGER NOT NULL,
    series_name TEXT NOT NULL,
    description TEXT,
    frequency TEXT NOT NULL,
    unit TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_dim_bcb_series_source FOREIGN KEY (source_id) REFERENCES dim_source(source_id),
    CONSTRAINT uq_dim_bcb_series_code UNIQUE (source_id, series_code)
);

CREATE TABLE IF NOT EXISTS dim_b3_ticker (
    ticker_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    market TEXT NOT NULL DEFAULT 'B3',
    currency TEXT NOT NULL DEFAULT 'BRL',
    asset_type TEXT NOT NULL DEFAULT 'EQUITY',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_dim_b3_ticker_source FOREIGN KEY (source_id) REFERENCES dim_source(source_id),
    CONSTRAINT uq_dim_b3_ticker UNIQUE (source_id, ticker)
);

CREATE TABLE IF NOT EXISTS fact_bcb_series_values (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id INTEGER NOT NULL,
    reference_date TEXT NOT NULL,
    value REAL NOT NULL,
    collected_at TEXT,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_fact_bcb_series FOREIGN KEY (series_id) REFERENCES dim_bcb_series(series_id),
    CONSTRAINT uq_fact_bcb_series_date UNIQUE (series_id, reference_date),
    CONSTRAINT ck_fact_bcb_reference_date_format CHECK (length(reference_date) = 10)
);

CREATE TABLE IF NOT EXISTS fact_b3_stock_prices (
    price_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker_id INTEGER NOT NULL,
    reference_date TEXT NOT NULL,
    open_price REAL NOT NULL,
    high_price REAL NOT NULL,
    low_price REAL NOT NULL,
    close_price REAL NOT NULL,
    adjusted_close_price REAL NOT NULL,
    volume INTEGER NOT NULL,
    collected_at TEXT,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_fact_b3_ticker FOREIGN KEY (ticker_id) REFERENCES dim_b3_ticker(ticker_id),
    CONSTRAINT uq_fact_b3_ticker_date UNIQUE (ticker_id, reference_date),
    CONSTRAINT ck_fact_b3_reference_date_format CHECK (length(reference_date) = 10),
    CONSTRAINT ck_open_non_negative CHECK (open_price >= 0),
    CONSTRAINT ck_high_non_negative CHECK (high_price >= 0),
    CONSTRAINT ck_low_non_negative CHECK (low_price >= 0),
    CONSTRAINT ck_close_non_negative CHECK (close_price >= 0),
    CONSTRAINT ck_adjusted_close_non_negative CHECK (adjusted_close_price >= 0),
    CONSTRAINT ck_volume_non_negative CHECK (volume >= 0),
    CONSTRAINT ck_high_greater_equal_low CHECK (high_price >= low_price)
);

CREATE TABLE IF NOT EXISTS dim_cvm_fund (
    fund_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_cnpj TEXT NOT NULL UNIQUE,
    fund_name TEXT,
    fund_status TEXT,
    registration_date TEXT,
    fund_type TEXT,
    target_investor TEXT,
    source TEXT NOT NULL DEFAULT 'CVM',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fact_cvm_fund_daily_report (
    fund_report_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fund_id INTEGER NOT NULL,
    reference_date TEXT NOT NULL,
    total_portfolio_value REAL,
    net_asset_value REAL NOT NULL,
    quota_value REAL NOT NULL,
    daily_subscriptions REAL,
    daily_redemptions REAL,
    number_of_shareholders INTEGER,
    collected_at TEXT,
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_fact_cvm_fund FOREIGN KEY (fund_id) REFERENCES dim_cvm_fund(fund_id),
    CONSTRAINT uq_fact_cvm_fund_date UNIQUE (fund_id, reference_date),
    CONSTRAINT ck_cvm_reference_date_format CHECK (length(reference_date) = 10),
    CONSTRAINT ck_cvm_net_asset_non_negative CHECK (net_asset_value >= 0),
    CONSTRAINT ck_cvm_quota_positive CHECK (quota_value > 0),
    CONSTRAINT ck_cvm_shareholders_non_negative CHECK (number_of_shareholders >= 0)
);

CREATE INDEX IF NOT EXISTS idx_fact_bcb_series_date ON fact_bcb_series_values(series_id, reference_date);
CREATE INDEX IF NOT EXISTS idx_fact_b3_ticker_date ON fact_b3_stock_prices(ticker_id, reference_date);
CREATE INDEX IF NOT EXISTS idx_fact_b3_reference_date ON fact_b3_stock_prices(reference_date);
CREATE INDEX IF NOT EXISTS idx_fact_cvm_fund_date ON fact_cvm_fund_daily_report(fund_id, reference_date);
CREATE INDEX IF NOT EXISTS idx_fact_cvm_reference_date ON fact_cvm_fund_daily_report(reference_date);

DROP VIEW IF EXISTS vw_bcb_series_values;
CREATE VIEW vw_bcb_series_values AS
SELECT src.source_name, s.series_code, s.series_name, s.description, s.frequency,
       f.reference_date, f.value, f.collected_at, f.loaded_at
FROM fact_bcb_series_values f
INNER JOIN dim_bcb_series s ON f.series_id = s.series_id
INNER JOIN dim_source src ON s.source_id = src.source_id;

DROP VIEW IF EXISTS vw_b3_stock_prices;
CREATE VIEW vw_b3_stock_prices AS
SELECT src.source_name, t.ticker, t.market, t.currency, t.asset_type,
       f.reference_date, f.open_price, f.high_price, f.low_price,
       f.close_price, f.adjusted_close_price, f.volume, f.collected_at, f.loaded_at
FROM fact_b3_stock_prices f
INNER JOIN dim_b3_ticker t ON f.ticker_id = t.ticker_id
INNER JOIN dim_source src ON t.source_id = src.source_id;

DROP VIEW IF EXISTS vw_bcb_series_monthly_summary;
CREATE VIEW vw_bcb_series_monthly_summary AS
SELECT series_name, strftime('%Y-%m', reference_date) AS reference_month,
       COUNT(*) AS observations,
       ROUND(AVG(value), 6) AS avg_value,
       ROUND(MIN(value), 6) AS min_value,
       ROUND(MAX(value), 6) AS max_value
FROM vw_bcb_series_values
GROUP BY series_name, strftime('%Y-%m', reference_date);

DROP VIEW IF EXISTS vw_b3_stock_monthly_summary;
CREATE VIEW vw_b3_stock_monthly_summary AS
WITH ranked_prices AS (
    SELECT ticker, strftime('%Y-%m', reference_date) AS reference_month,
           reference_date, close_price, volume,
           ROW_NUMBER() OVER (PARTITION BY ticker, strftime('%Y-%m', reference_date) ORDER BY reference_date ASC) AS rn_first,
           ROW_NUMBER() OVER (PARTITION BY ticker, strftime('%Y-%m', reference_date) ORDER BY reference_date DESC) AS rn_last
    FROM vw_b3_stock_prices
),
monthly AS (
    SELECT ticker, reference_month,
           COUNT(*) AS trading_days,
           ROUND(AVG(close_price), 6) AS avg_close_price,
           ROUND(MIN(close_price), 6) AS min_close_price,
           ROUND(MAX(close_price), 6) AS max_close_price,
           SUM(volume) AS total_volume,
           MAX(CASE WHEN rn_first = 1 THEN close_price END) AS first_close_price,
           MAX(CASE WHEN rn_last = 1 THEN close_price END) AS last_close_price
    FROM ranked_prices
    GROUP BY ticker, reference_month
)
SELECT ticker, reference_month, trading_days, avg_close_price, min_close_price,
       max_close_price, total_volume,
       ROUND(first_close_price, 6) AS first_close_price,
       ROUND(last_close_price, 6) AS last_close_price,
       CASE WHEN first_close_price > 0
            THEN ROUND(((last_close_price / first_close_price) - 1) * 100, 4)
            ELSE NULL END AS monthly_return_pct
FROM monthly;

DROP VIEW IF EXISTS vw_bcb_latest_snapshot;
CREATE VIEW vw_bcb_latest_snapshot AS
WITH ranked AS (
    SELECT series_name, description, frequency, reference_date, value,
           ROW_NUMBER() OVER (PARTITION BY series_name ORDER BY reference_date DESC) AS rn
    FROM vw_bcb_series_values
)
SELECT series_name, description, frequency, reference_date AS last_available_date,
       value AS latest_value
FROM ranked
WHERE rn = 1;

DROP VIEW IF EXISTS vw_b3_asset_returns;
CREATE VIEW vw_b3_asset_returns AS
WITH ranked AS (
    SELECT ticker, asset_type, reference_date, adjusted_close_price,
           ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY reference_date ASC) AS rn_first,
           ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY reference_date DESC) AS rn_last
    FROM vw_b3_stock_prices
),
first_last AS (
    SELECT ticker, asset_type,
           MAX(CASE WHEN rn_first = 1 THEN reference_date END) AS start_date,
           MAX(CASE WHEN rn_last = 1 THEN reference_date END) AS end_date,
           MAX(CASE WHEN rn_first = 1 THEN adjusted_close_price END) AS first_adjusted_close,
           MAX(CASE WHEN rn_last = 1 THEN adjusted_close_price END) AS last_adjusted_close
    FROM ranked
    GROUP BY ticker, asset_type
)
SELECT ticker, asset_type, start_date, end_date,
       ROUND(first_adjusted_close, 6) AS first_adjusted_close,
       ROUND(last_adjusted_close, 6) AS last_adjusted_close,
       CASE WHEN first_adjusted_close > 0
            THEN ROUND(((last_adjusted_close / first_adjusted_close) - 1) * 100, 4)
            ELSE NULL END AS return_pct
FROM first_last;

DROP VIEW IF EXISTS vw_cvm_fund_daily_reports;
CREATE VIEW vw_cvm_fund_daily_reports AS
SELECT d.fund_cnpj, d.fund_name, d.fund_status, d.registration_date, d.fund_type,
       d.target_investor, f.reference_date, f.total_portfolio_value,
       f.net_asset_value, f.quota_value, f.daily_subscriptions,
       f.daily_redemptions, f.number_of_shareholders, f.collected_at, f.loaded_at
FROM fact_cvm_fund_daily_report f
INNER JOIN dim_cvm_fund d ON f.fund_id = d.fund_id;

DROP VIEW IF EXISTS vw_cvm_fund_latest_snapshot;
CREATE VIEW vw_cvm_fund_latest_snapshot AS
WITH ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY fund_cnpj ORDER BY reference_date DESC) AS rn
    FROM vw_cvm_fund_daily_reports
)
SELECT fund_cnpj, fund_name, fund_status, fund_type, target_investor,
       reference_date AS last_available_date, total_portfolio_value,
       net_asset_value, quota_value, daily_subscriptions,
       daily_redemptions, number_of_shareholders
FROM ranked
WHERE rn = 1;

DROP VIEW IF EXISTS vw_cvm_top_funds_by_net_asset;
CREATE VIEW vw_cvm_top_funds_by_net_asset AS
SELECT *
FROM vw_cvm_fund_latest_snapshot
ORDER BY net_asset_value DESC;

DROP VIEW IF EXISTS vw_cvm_fund_flows_monthly;
CREATE VIEW vw_cvm_fund_flows_monthly AS
SELECT strftime('%Y-%m', reference_date) AS reference_month,
       COUNT(DISTINCT fund_cnpj) AS funds_count,
       ROUND(SUM(daily_subscriptions), 2) AS total_subscriptions,
       ROUND(SUM(daily_redemptions), 2) AS total_redemptions,
       ROUND(SUM(daily_subscriptions) - SUM(daily_redemptions), 2) AS net_flow
FROM vw_cvm_fund_daily_reports
GROUP BY strftime('%Y-%m', reference_date);
