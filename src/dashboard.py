from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import PROCESSED_DB_FILE

PAGE_OPTIONS = (
    "Resumo Executivo",
    "Selic Diaria",
    "IPCA Mensal",
    "Cotacoes B3",
)

STOCK_RETURN_COLUMNS = [
    "ticker",
    "data_inicial",
    "data_final",
    "preco_ajustado_inicial",
    "preco_ajustado_final",
    "retorno_pct",
]


st.set_page_config(
    page_title="Brazilian Financial Data Pipeline",
    layout="wide",
    initial_sidebar_state="expanded",
)


def validate_database_exists(database_file: Path) -> None:
    if database_file.exists():
        return

    st.error(
        "Banco SQLite final nao encontrado.\n\n"
        f"Caminho esperado: `{database_file}`\n\n"
        "Rode primeiro: `python src\\load_processed_data.py`"
    )
    st.stop()


@st.cache_data(show_spinner=False)
def read_sql_query(database_path: str, query: str) -> pd.DataFrame:
    with sqlite3.connect(database_path) as conn:
        return pd.read_sql_query(query, conn)


@st.cache_data(show_spinner=True)
def load_selic_data(database_path: str) -> pd.DataFrame:
    query = """
        SELECT reference_date, value AS selic_daily_value
        FROM vw_bcb_series_values
        WHERE series_name = 'selic_daily'
        ORDER BY reference_date
    """

    df = read_sql_query(database_path, query)
    df["reference_date"] = pd.to_datetime(df["reference_date"])
    return df


@st.cache_data(show_spinner=True)
def load_ipca_data(database_path: str) -> pd.DataFrame:
    query = """
        SELECT reference_date, value AS ipca_monthly_value
        FROM vw_bcb_series_values
        WHERE series_name = 'ipca_monthly'
        ORDER BY reference_date
    """

    df = read_sql_query(database_path, query)
    df["reference_date"] = pd.to_datetime(df["reference_date"])
    return df


@st.cache_data(show_spinner=True)
def load_stock_data(database_path: str) -> pd.DataFrame:
    query = """
        SELECT
            reference_date,
            ticker,
            open_price,
            high_price,
            low_price,
            close_price,
            adjusted_close_price,
            volume
        FROM vw_b3_stock_prices
        WHERE ticker IN ('PETR4.SA', 'VALE3.SA', 'ITUB4.SA')
        ORDER BY reference_date, ticker
    """

    df = read_sql_query(database_path, query)
    df["reference_date"] = pd.to_datetime(df["reference_date"])
    return df


def calculate_ipca_accumulated(ipca_df: pd.DataFrame, year: int = 2024) -> float | None:
    filtered_df = ipca_df[ipca_df["reference_date"].dt.year == year].copy()

    if filtered_df.empty:
        return None

    accumulated = ((filtered_df["ipca_monthly_value"] / 100 + 1).prod() - 1) * 100
    return float(accumulated)


def calculate_stock_returns(stocks_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    if stocks_df.empty:
        return pd.DataFrame(columns=STOCK_RETURN_COLUMNS)

    for ticker, ticker_df in stocks_df.groupby("ticker"):
        ticker_df = ticker_df.sort_values("reference_date")

        first_row = ticker_df.iloc[0]
        last_row = ticker_df.iloc[-1]

        first_price = float(first_row["adjusted_close_price"])
        last_price = float(last_row["adjusted_close_price"])

        if first_price == 0:
            return_pct = None
        else:
            return_pct = ((last_price / first_price) - 1) * 100

        rows.append(
            {
                "ticker": ticker,
                "data_inicial": first_row["reference_date"],
                "data_final": last_row["reference_date"],
                "preco_ajustado_inicial": first_price,
                "preco_ajustado_final": last_price,
                "retorno_pct": return_pct,
            }
        )

    return pd.DataFrame(rows, columns=STOCK_RETURN_COLUMNS).sort_values("ticker")


def filter_by_date_range(
    df: pd.DataFrame,
    date_column: str,
    start_date,
    end_date,
) -> pd.DataFrame:
    start_timestamp = pd.to_datetime(start_date)
    end_timestamp = pd.to_datetime(end_date)

    return df[
        (df[date_column] >= start_timestamp)
        & (df[date_column] <= end_timestamp)
    ].copy()


def normalize_date_range(selected_range) -> tuple[Any, Any] | None:
    if not isinstance(selected_range, tuple) or len(selected_range) != 2:
        return None

    return selected_range


def stop_if_empty(df: pd.DataFrame, message: str) -> None:
    if not df.empty:
        return

    st.warning(message)
    st.stop()


def format_pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "N/D"

    return f"{value:.2f}%"


def format_number(value: float | int | None, decimals: int = 2) -> str:
    if value is None or pd.isna(value):
        return "N/D"

    return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def render_header() -> None:
    st.title("Brazilian Financial Data Pipeline")


def render_sidebar() -> str:
    st.sidebar.title("Navegacao")

    page = st.sidebar.radio(
        "Pagina",
        options=PAGE_OPTIONS,
    )

    st.sidebar.markdown("---")
    st.sidebar.caption(f"Banco: `{PROCESSED_DB_FILE}`")

    return page


def render_executive_summary(
    selic_df: pd.DataFrame,
    ipca_df: pd.DataFrame,
    stocks_df: pd.DataFrame,
) -> None:
    st.header("Resumo Executivo")

    latest_selic = selic_df.sort_values("reference_date").iloc[-1]
    ipca_accumulated_2024 = calculate_ipca_accumulated(ipca_df, year=2024)
    stock_returns_df = calculate_stock_returns(stocks_df)

    min_date = min(
        selic_df["reference_date"].min(),
        ipca_df["reference_date"].min(),
        stocks_df["reference_date"].min(),
    )

    max_date = max(
        selic_df["reference_date"].max(),
        ipca_df["reference_date"].max(),
        stocks_df["reference_date"].max(),
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Ultima Selic diaria", f"{latest_selic['selic_daily_value']:.6f}")
    col2.metric("Data da ultima Selic", latest_selic["reference_date"].strftime("%d/%m/%Y"))
    col3.metric("IPCA acumulado 2024", format_pct(ipca_accumulated_2024))
    col4.metric("Tickers B3", stocks_df["ticker"].nunique())

    st.markdown("---")
    st.subheader("Cobertura do pipeline")

    coverage_col1, coverage_col2, coverage_col3, coverage_col4 = st.columns(4)
    coverage_col1.metric("Inicio dos dados", min_date.strftime("%d/%m/%Y"))
    coverage_col2.metric("Fim dos dados", max_date.strftime("%d/%m/%Y"))
    coverage_col3.metric("Registros BCB", len(selic_df) + len(ipca_df))
    coverage_col4.metric("Registros B3", len(stocks_df))

    st.markdown("---")
    st.subheader("Retorno das acoes no periodo")

    display_returns_df = stock_returns_df.copy()
    display_returns_df["data_inicial"] = display_returns_df["data_inicial"].dt.strftime("%d/%m/%Y")
    display_returns_df["data_final"] = display_returns_df["data_final"].dt.strftime("%d/%m/%Y")
    display_returns_df["preco_ajustado_inicial"] = display_returns_df["preco_ajustado_inicial"].round(2)
    display_returns_df["preco_ajustado_final"] = display_returns_df["preco_ajustado_final"].round(2)
    display_returns_df["retorno_pct"] = display_returns_df["retorno_pct"].round(2)

    st.dataframe(display_returns_df, use_container_width=True, hide_index=True)

    fig_returns = px.bar(
        stock_returns_df,
        x="ticker",
        y="retorno_pct",
        text="retorno_pct",
        title="Retorno percentual por acao no periodo",
        labels={"ticker": "Ticker", "retorno_pct": "Retorno (%)"},
    )
    fig_returns.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
    fig_returns.update_layout(yaxis_ticksuffix="%", uniformtext_minsize=8, uniformtext_mode="hide")

    st.plotly_chart(fig_returns, use_container_width=True)


def render_selic_page(selic_df: pd.DataFrame) -> None:
    st.header("Selic Diaria")

    min_date = selic_df["reference_date"].min().date()
    max_date = selic_df["reference_date"].max().date()

    selected_range = st.date_input(
        "Intervalo",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        key="selic_date_range",
    )
    date_range = normalize_date_range(selected_range)

    if date_range is None:
        st.warning("Selecione data inicial e data final.")
        st.stop()

    filtered_df = filter_by_date_range(selic_df, "reference_date", date_range[0], date_range[1])
    stop_if_empty(filtered_df, "Nao ha registros de Selic no intervalo selecionado.")

    col1, col2, col3 = st.columns(3)
    col1.metric("Registros", len(filtered_df))
    col2.metric("Media no periodo", f"{filtered_df['selic_daily_value'].mean():.6f}")
    col3.metric("Ultimo valor", f"{filtered_df['selic_daily_value'].iloc[-1]:.6f}")

    fig = px.line(
        filtered_df,
        x="reference_date",
        y="selic_daily_value",
        title="Selic diaria no periodo selecionado",
        labels={"reference_date": "Data", "selic_daily_value": "Selic diaria"},
        markers=True,
    )
    fig.update_layout(hovermode="x unified", xaxis_title="Data", yaxis_title="Selic diaria")

    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Tabela completa da Selic"):
        display_df = filtered_df.copy()
        display_df["reference_date"] = display_df["reference_date"].dt.strftime("%d/%m/%Y")
        display_df["selic_daily_value"] = display_df["selic_daily_value"].round(6)
        st.dataframe(display_df, use_container_width=True, hide_index=True)


def render_ipca_page(ipca_df: pd.DataFrame) -> None:
    st.header("IPCA Mensal")

    min_date = ipca_df["reference_date"].min().date()
    max_date = ipca_df["reference_date"].max().date()

    selected_range = st.date_input(
        "Intervalo",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        key="ipca_date_range",
    )
    date_range = normalize_date_range(selected_range)

    if date_range is None:
        st.warning("Selecione data inicial e data final.")
        st.stop()

    filtered_df = filter_by_date_range(ipca_df, "reference_date", date_range[0], date_range[1])
    stop_if_empty(filtered_df, "Nao ha registros de IPCA no intervalo selecionado.")

    accumulated_ipca = ((filtered_df["ipca_monthly_value"] / 100 + 1).prod() - 1) * 100

    col1, col2, col3 = st.columns(3)
    col1.metric("Meses", len(filtered_df))
    col2.metric("IPCA acumulado", format_pct(float(accumulated_ipca)))
    col3.metric("Media mensal", format_pct(float(filtered_df["ipca_monthly_value"].mean())))

    fig = px.bar(
        filtered_df,
        x="reference_date",
        y="ipca_monthly_value",
        text="ipca_monthly_value",
        title="IPCA mensal no periodo selecionado",
        labels={"reference_date": "Mes", "ipca_monthly_value": "IPCA mensal (%)"},
    )
    fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
    fig.update_layout(yaxis_ticksuffix="%", hovermode="x unified", xaxis_title="Mes", yaxis_title="IPCA mensal (%)")

    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Tabela completa do IPCA"):
        display_df = filtered_df.copy()
        display_df["reference_date"] = display_df["reference_date"].dt.strftime("%d/%m/%Y")
        display_df["ipca_monthly_value"] = display_df["ipca_monthly_value"].round(2)
        st.dataframe(display_df, use_container_width=True, hide_index=True)


def render_stocks_page(stocks_df: pd.DataFrame) -> None:
    st.header("Cotacoes B3")

    available_tickers = sorted(stocks_df["ticker"].unique().tolist())
    selected_tickers = st.multiselect("Tickers", options=available_tickers, default=available_tickers)

    if not selected_tickers:
        st.warning("Selecione pelo menos um ticker.")
        st.stop()

    min_date = stocks_df["reference_date"].min().date()
    max_date = stocks_df["reference_date"].max().date()

    selected_range = st.date_input(
        "Intervalo",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        key="stocks_date_range",
    )
    date_range = normalize_date_range(selected_range)

    if date_range is None:
        st.warning("Selecione data inicial e data final.")
        st.stop()

    filtered_df = stocks_df[stocks_df["ticker"].isin(selected_tickers)].copy()
    filtered_df = filter_by_date_range(filtered_df, "reference_date", date_range[0], date_range[1])
    stop_if_empty(filtered_df, "Nao ha cotacoes B3 no intervalo selecionado.")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Registros", len(filtered_df))
    col2.metric("Tickers selecionados", filtered_df["ticker"].nunique())
    col3.metric("Volume total", format_number(int(filtered_df["volume"].sum()), 0))
    col4.metric("Preco medio fechamento", f"R$ {format_number(float(filtered_df['close_price'].mean()), 2)}")

    fig = px.line(
        filtered_df.sort_values(["ticker", "reference_date"]),
        x="reference_date",
        y="close_price",
        color="ticker",
        title="Fechamento diario comparado",
        labels={"reference_date": "Data", "close_price": "Preco de fechamento", "ticker": "Ticker"},
        markers=True,
    )
    fig.update_layout(hovermode="x unified", xaxis_title="Data", yaxis_title="Preco de fechamento", legend_title_text="Ticker")

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Retorno por ticker")
    returns_df = calculate_stock_returns(filtered_df)
    stop_if_empty(returns_df, "Nao ha dados suficientes para calcular retorno no intervalo selecionado.")

    fig_returns = px.bar(
        returns_df,
        x="ticker",
        y="retorno_pct",
        text="retorno_pct",
        title="Retorno percentual no intervalo selecionado",
        labels={"ticker": "Ticker", "retorno_pct": "Retorno (%)"},
    )
    fig_returns.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
    fig_returns.update_layout(yaxis_ticksuffix="%")

    st.plotly_chart(fig_returns, use_container_width=True)

    with st.expander("Tabela completa de cotacoes"):
        display_df = filtered_df.copy()
        display_df["reference_date"] = display_df["reference_date"].dt.strftime("%d/%m/%Y")

        for column in ["open_price", "high_price", "low_price", "close_price", "adjusted_close_price"]:
            display_df[column] = display_df[column].round(2)

        st.dataframe(display_df, use_container_width=True, hide_index=True)


def main() -> None:
    validate_database_exists(PROCESSED_DB_FILE)

    database_path = str(PROCESSED_DB_FILE)
    selic_df = load_selic_data(database_path)
    ipca_df = load_ipca_data(database_path)
    stocks_df = load_stock_data(database_path)

    stop_if_empty(selic_df, "Nao ha dados de Selic no banco final.")
    stop_if_empty(ipca_df, "Nao ha dados de IPCA no banco final.")
    stop_if_empty(stocks_df, "Nao ha cotacoes B3 no banco final.")

    render_header()
    page = render_sidebar()

    if page == "Resumo Executivo":
        render_executive_summary(selic_df, ipca_df, stocks_df)
    elif page == "Selic Diaria":
        render_selic_page(selic_df)
    elif page == "IPCA Mensal":
        render_ipca_page(ipca_df)
    elif page == "Cotacoes B3":
        render_stocks_page(stocks_df)


if __name__ == "__main__":
    main()
