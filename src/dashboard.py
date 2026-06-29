from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_FILE = PROJECT_ROOT / "data" / "processed" / "financial_data.db"

PAGES = (
    "Resumo Executivo",
    "Inteligência Financeira",
    "Selic Diaria",
    "IPCA Mensal",
    "Cotacoes B3",
)


st.set_page_config(
    page_title="Brazilian Financial Data Pipeline",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _read_sql(query: str, parse_dates: list[str] | None = None) -> pd.DataFrame:
    if not DATABASE_FILE.exists():
        st.warning(f"Banco processado nao encontrado: {DATABASE_FILE}")
        return pd.DataFrame()

    try:
        with sqlite3.connect(DATABASE_FILE) as conn:
            return pd.read_sql_query(query, conn, parse_dates=parse_dates)
    except sqlite3.Error as exc:
        st.warning(f"Nao foi possivel carregar dados do banco: {exc}")
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_bcb_series() -> pd.DataFrame:
    return _read_sql(
        """
        SELECT source_name, series_code, series_name, description, frequency, reference_date, value
        FROM vw_bcb_series_values
        ORDER BY series_name, reference_date
        """,
        parse_dates=["reference_date"],
    )


@st.cache_data(show_spinner=False)
def load_b3_prices() -> pd.DataFrame:
    return _read_sql(
        """
        SELECT source_name, ticker, market, currency, asset_type, reference_date,
               open_price, high_price, low_price, close_price, adjusted_close_price, volume
        FROM vw_b3_stock_prices
        ORDER BY ticker, reference_date
        """,
        parse_dates=["reference_date"],
    )


@st.cache_data(show_spinner=False)
def load_latest_run() -> pd.DataFrame:
    if not DATABASE_FILE.exists():
        return pd.DataFrame()

    with sqlite3.connect(DATABASE_FILE) as conn:
        objects = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            ).fetchall()
        }
        if "vw_etl_runs_latest" not in objects:
            return pd.DataFrame()
        return pd.read_sql_query(
            """
            SELECT run_id, started_at, finished_at, status, command, git_commit
            FROM vw_etl_runs_latest
            ORDER BY started_at DESC
            LIMIT 1
            """,
            conn,
            parse_dates=["started_at", "finished_at"],
        )


@st.cache_data(show_spinner=False)
def load_market_latest_indicators() -> pd.DataFrame:
    return _read_sql(
        """
        SELECT series_name, latest_date, latest_value, previous_value, change_pct
        FROM vw_market_latest_indicators
        ORDER BY series_name
        """,
        parse_dates=["latest_date"],
    )


@st.cache_data(show_spinner=False)
def load_asset_returns_ranking() -> pd.DataFrame:
    return _read_sql(
        """
        SELECT ticker, return_30d_pct, return_90d_pct, return_full_pct, period_start, period_end
        FROM vw_asset_returns_ranking
        ORDER BY return_full_pct DESC
        """,
        parse_dates=["period_start", "period_end"],
    )


@st.cache_data(show_spinner=False)
def load_data_freshness_status() -> pd.DataFrame:
    return _read_sql(
        """
        SELECT source_name, series_name, last_date, days_since_update, freshness_status
        FROM vw_data_freshness_status
        ORDER BY source_name, series_name
        """,
        parse_dates=["last_date"],
    )


@st.cache_data(show_spinner=False)
def load_macro_indicators_summary() -> pd.DataFrame:
    return _read_sql(
        """
        SELECT reference_month, selic_avg, ipca_value, cdi_avg, usd_brl_avg
        FROM vw_macro_indicators_summary
        ORDER BY reference_month
        """
    )


def format_date(value) -> str:
    if pd.isna(value):
        return "N/D"
    return pd.to_datetime(value).strftime("%d/%m/%Y")


def format_pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "N/D"
    return f"{value:.2f}%"


def date_range_filter(df: pd.DataFrame, label: str) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    if df.empty:
        return None

    min_date = df["reference_date"].min().date()
    max_date = df["reference_date"].max().date()
    selected = st.date_input(label, value=(min_date, max_date), min_value=min_date, max_value=max_date)

    if not isinstance(selected, tuple) or len(selected) != 2:
        st.warning("Selecione uma data inicial e uma data final.")
        return None

    start_date, end_date = selected
    return pd.Timestamp(start_date), pd.Timestamp(end_date)


def filtered_by_period(df: pd.DataFrame, period: tuple[pd.Timestamp, pd.Timestamp] | None) -> pd.DataFrame:
    if period is None or df.empty:
        return pd.DataFrame(columns=df.columns)

    start_date, end_date = period
    return df[(df["reference_date"] >= start_date) & (df["reference_date"] <= end_date)].copy()


def calculate_ticker_returns(stocks_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    if stocks_df.empty:
        return pd.DataFrame(rows)

    for ticker, ticker_df in stocks_df.dropna(subset=["adjusted_close_price"]).groupby("ticker"):
        ticker_df = ticker_df.sort_values("reference_date")
        if ticker_df.empty:
            continue

        first = ticker_df.iloc[0]
        last = ticker_df.iloc[-1]
        first_price = float(first["adjusted_close_price"])
        last_price = float(last["adjusted_close_price"])
        return_pct = ((last_price / first_price) - 1) * 100 if first_price else None
        rows.append(
            {
                "ticker": ticker,
                "data_inicial": first["reference_date"],
                "data_final": last["reference_date"],
                "preco_inicial": first_price,
                "preco_final": last_price,
                "retorno_pct": return_pct,
            }
        )

    return pd.DataFrame(rows)


def render_executive_summary(bcb_df: pd.DataFrame, stocks_df: pd.DataFrame, latest_run_df: pd.DataFrame) -> None:
    st.title("Resumo Executivo")

    if bcb_df.empty and stocks_df.empty:
        st.warning("Nao ha dados carregados nas views do banco processado.")
        return

    selic_df = bcb_df[bcb_df["series_name"] == "selic_daily"].sort_values("reference_date")
    ipca_2024 = bcb_df[
        (bcb_df["series_name"] == "ipca_monthly")
        & (bcb_df["reference_date"].dt.year == 2024)
    ].copy()
    returns_df = calculate_ticker_returns(stocks_df)

    selic_value = None
    selic_date = None
    if not selic_df.empty:
        selic_last = selic_df.iloc[-1]
        selic_value = float(selic_last["value"])
        selic_date = selic_last["reference_date"]

    ipca_accumulated = None
    if not ipca_2024.empty:
        ipca_accumulated = ((ipca_2024["value"] / 100 + 1).prod() - 1) * 100

    latest_run = latest_run_df.iloc[0] if not latest_run_df.empty else None
    total_bcb = int(len(bcb_df))
    total_b3 = int(len(stocks_df))

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Selic mais recente", f"{selic_value:.6f}" if selic_value is not None else "N/D", format_date(selic_date))
    col2.metric("IPCA acumulado 2024", format_pct(ipca_accumulated))
    col3.metric("Registros BCB", f"{total_bcb:,}".replace(",", "."))
    col4.metric("Registros B3", f"{total_b3:,}".replace(",", "."))

    col5, col6 = st.columns(2)
    col5.metric("Ultima execucao", format_date(latest_run["finished_at"]) if latest_run is not None else "N/D")
    col6.metric("Status reconciliacao", str(latest_run["status"]) if latest_run is not None else "N/D")

    st.subheader("Retorno por ticker no periodo")
    if returns_df.empty:
        st.warning("Nao ha cotacoes suficientes para calcular retorno por ticker.")
    else:
        fig = px.bar(
            returns_df,
            x="ticker",
            y="retorno_pct",
            text="retorno_pct",
            labels={"ticker": "Ticker", "retorno_pct": "Retorno (%)"},
        )
        fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
        fig.update_layout(yaxis_ticksuffix="%", margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(
            returns_df.assign(
                data_inicial=returns_df["data_inicial"].dt.strftime("%d/%m/%Y"),
                data_final=returns_df["data_final"].dt.strftime("%d/%m/%Y"),
                preco_inicial=returns_df["preco_inicial"].round(2),
                preco_final=returns_df["preco_final"].round(2),
                retorno_pct=returns_df["retorno_pct"].round(2),
            ),
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Registros por fonte")
    source_rows = []
    if not bcb_df.empty:
        source_rows.append({"fonte": "BCB_SGS", "registros": total_bcb})
    if not stocks_df.empty:
        source_rows.append({"fonte": "YAHOO_FINANCE", "registros": total_b3})
    st.dataframe(pd.DataFrame(source_rows), use_container_width=True, hide_index=True)


def freshness_style(value: str) -> str:
    colors = {
        "FRESH": "background-color: #dcfce7; color: #166534",
        "RECENT": "background-color: #fef9c3; color: #854d0e",
        "STALE": "background-color: #fee2e2; color: #991b1b",
    }
    return colors.get(str(value), "")


def render_financial_intelligence_page() -> None:
    st.title("Inteligência Financeira")

    indicators_df = load_market_latest_indicators()
    returns_df = load_asset_returns_ranking()
    freshness_df = load_data_freshness_status()
    macro_df = load_macro_indicators_summary()

    st.subheader("Indicadores de mercado mais recentes")
    if indicators_df.empty:
        st.warning("View vw_market_latest_indicators sem dados.")
    else:
        display_df = indicators_df.copy()
        display_df["latest_date"] = display_df["latest_date"].dt.strftime("%d/%m/%Y")
        for column in ["latest_value", "previous_value", "change_pct"]:
            display_df[column] = display_df[column].round(6)
        st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.subheader("Ranking de retornos por ativo")
    if returns_df.empty:
        st.warning("View vw_asset_returns_ranking sem dados.")
    else:
        chart_df = returns_df.melt(
            id_vars=["ticker"],
            value_vars=["return_30d_pct", "return_90d_pct", "return_full_pct"],
            var_name="periodo",
            value_name="retorno_pct",
        )
        fig = px.bar(
            chart_df,
            x="ticker",
            y="retorno_pct",
            color="periodo",
            barmode="group",
            labels={"ticker": "Ticker", "retorno_pct": "Retorno (%)", "periodo": "Periodo"},
        )
        fig.update_layout(yaxis_ticksuffix="%", margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Freshness das fontes")
    if freshness_df.empty:
        st.warning("View vw_data_freshness_status sem dados.")
    else:
        freshness_display = freshness_df.copy()
        freshness_display["last_date"] = freshness_display["last_date"].dt.strftime("%d/%m/%Y")
        st.dataframe(
            freshness_display.style.map(freshness_style, subset=["freshness_status"]),
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Resumo macro mensal")
    if macro_df.empty:
        st.warning("View vw_macro_indicators_summary sem dados.")
    else:
        macro_chart_df = macro_df.melt(
            id_vars=["reference_month"],
            value_vars=["selic_avg", "ipca_value", "cdi_avg", "usd_brl_avg"],
            var_name="indicador",
            value_name="valor",
        )
        fig = px.line(
            macro_chart_df,
            x="reference_month",
            y="valor",
            color="indicador",
            labels={"reference_month": "Mes", "valor": "Valor", "indicador": "Indicador"},
        )
        fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)


def render_selic_page(bcb_df: pd.DataFrame) -> None:
    st.title("Selic Diaria")
    selic_df = bcb_df[bcb_df["series_name"] == "selic_daily"].sort_values("reference_date")
    if selic_df.empty:
        st.warning("Nao ha serie Selic disponivel em vw_bcb_series_values.")
        return

    period = date_range_filter(selic_df, "Periodo da Selic")
    filtered = filtered_by_period(selic_df, period)
    if filtered.empty:
        st.warning("Nao ha dados de Selic para o periodo selecionado.")
        return

    fig = px.line(filtered, x="reference_date", y="value", labels={"reference_date": "Data", "value": "Taxa"})
    fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

    table_df = filtered[["reference_date", "value"]].rename(columns={"reference_date": "data", "value": "valor"})
    table_df["data"] = table_df["data"].dt.strftime("%d/%m/%Y")
    st.dataframe(table_df, use_container_width=True, hide_index=True)


def render_ipca_page(bcb_df: pd.DataFrame) -> None:
    st.title("IPCA Mensal")
    ipca_df = bcb_df[bcb_df["series_name"] == "ipca_monthly"].sort_values("reference_date")
    if ipca_df.empty:
        st.warning("Nao ha serie IPCA disponivel em vw_bcb_series_values.")
        return

    years = sorted(ipca_df["reference_date"].dt.year.dropna().unique().tolist())
    selected_year = st.selectbox("Ano", options=years, index=len(years) - 1)
    filtered = ipca_df[ipca_df["reference_date"].dt.year == selected_year].copy()
    if filtered.empty:
        st.warning("Nao ha dados de IPCA para o ano selecionado.")
        return

    fig = px.bar(filtered, x="reference_date", y="value", labels={"reference_date": "Mes", "value": "IPCA mensal (%)"})
    fig.update_layout(yaxis_ticksuffix="%", margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

    table_df = filtered[["reference_date", "value"]].rename(columns={"reference_date": "data", "value": "valor"})
    table_df["data"] = table_df["data"].dt.strftime("%d/%m/%Y")
    st.dataframe(table_df, use_container_width=True, hide_index=True)


def render_b3_page(stocks_df: pd.DataFrame) -> None:
    st.title("Cotacoes B3")
    if stocks_df.empty:
        st.warning("Nao ha cotacoes disponiveis em vw_b3_stock_prices.")
        return

    tickers = ["PETR4.SA", "VALE3.SA", "ITUB4.SA", "^BVSP"]
    stocks_df = stocks_df[stocks_df["ticker"].isin(tickers)].sort_values(["ticker", "reference_date"])
    if stocks_df.empty:
        st.warning("Nao ha dados para os tickers esperados.")
        return

    period = date_range_filter(stocks_df, "Periodo das cotacoes")
    filtered = filtered_by_period(stocks_df, period)
    if filtered.empty:
        st.warning("Nao ha cotacoes para o periodo selecionado.")
        return

    fig = px.line(
        filtered,
        x="reference_date",
        y="adjusted_close_price",
        color="ticker",
        labels={"reference_date": "Data", "adjusted_close_price": "Preco ajustado", "ticker": "Ticker"},
    )
    fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

    selected_ticker = st.selectbox("Ticker da tabela OHLCV", options=tickers)
    table_df = filtered[filtered["ticker"] == selected_ticker][
        [
            "reference_date",
            "ticker",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "adjusted_close_price",
            "volume",
        ]
    ].rename(
        columns={
            "reference_date": "data",
            "open_price": "abertura",
            "high_price": "maxima",
            "low_price": "minima",
            "close_price": "fechamento",
            "adjusted_close_price": "fechamento_ajustado",
        }
    )
    table_df["data"] = table_df["data"].dt.strftime("%d/%m/%Y")
    st.dataframe(table_df, use_container_width=True, hide_index=True)


def main() -> None:
    st.sidebar.title("Navegacao")
    page = st.sidebar.radio("Pagina", PAGES)
    st.sidebar.caption(f"Banco: {DATABASE_FILE.relative_to(PROJECT_ROOT)}")

    bcb_df = load_bcb_series()
    stocks_df = load_b3_prices()
    latest_run_df = load_latest_run()

    if page == "Resumo Executivo":
        render_executive_summary(bcb_df, stocks_df, latest_run_df)
    elif page == "Inteligência Financeira":
        render_financial_intelligence_page()
    elif page == "Selic Diaria":
        render_selic_page(bcb_df)
    elif page == "IPCA Mensal":
        render_ipca_page(bcb_df)
    elif page == "Cotacoes B3":
        render_b3_page(stocks_df)


if __name__ == "__main__":
    main()
