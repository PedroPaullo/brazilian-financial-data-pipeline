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

CREATE INDEX IF NOT EXISTS idx_fact_bcb_series_date ON fact_bcb_series_values(series_id, reference_date);
CREATE INDEX IF NOT EXISTS idx_fact_b3_ticker_date ON fact_b3_stock_prices(ticker_id, reference_date);
CREATE INDEX IF NOT EXISTS idx_fact_b3_reference_date ON fact_b3_stock_prices(reference_date);

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