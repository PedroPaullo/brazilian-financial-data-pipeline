from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import OPERATIONS_DB_FILE, PROCESSED_DB_FILE, VALIDATION_OUTPUT_FILES

PAGE_OPTIONS = (
    "Resumo Executivo",
    "Status do Pipeline",
    "Qualidade dos Dados",
    "Benchmarks",
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


def stop_if_missing_file(file_path: Path, message: str) -> None:
    if file_path.exists():
        return

    st.warning(f"{message}\n\nArquivo esperado: `{file_path}`")
    st.stop()


@st.cache_data(show_spinner=False)
def read_sql_query(database_path: str, query: str) -> pd.DataFrame:
    with sqlite3.connect(database_path) as conn:
        return pd.read_sql_query(query, conn)


@st.cache_data(show_spinner=False)
def load_quality_summary(summary_path: str) -> dict[str, Any]:
    with open(summary_path, "r", encoding="utf-8") as file:
        return json.load(file)


@st.cache_data(show_spinner=True)
def load_quality_results(results_path: str) -> pd.DataFrame:
    return pd.read_csv(results_path)


@st.cache_data(show_spinner=True)
def load_date_gaps(gaps_path: str) -> pd.DataFrame:
    return pd.read_csv(gaps_path)


@st.cache_data(show_spinner=True)
def load_bcb_series_data(database_path: str) -> pd.DataFrame:
    query = """
        SELECT series_name, description, frequency, reference_date, value
        FROM vw_bcb_series_values
        ORDER BY series_name, reference_date
    """

    df = read_sql_query(database_path, query)
    df["reference_date"] = pd.to_datetime(df["reference_date"])
    return df


@st.cache_data(show_spinner=True)
def load_pipeline_runs(operations_db_path: str) -> pd.DataFrame:
    database_file = Path(operations_db_path)
    if not database_file.exists():
        return pd.DataFrame()

    query = """
        SELECT
            run_id,
            module_name,
            started_at,
            finished_at,
            status,
            records_input,
            records_output,
            warnings_count,
            errors_count,
            execution_time_seconds,
            error_message
        FROM pipeline_runs
        ORDER BY run_id DESC
        LIMIT 20
    """

    return read_sql_query(operations_db_path, query)


@st.cache_data(show_spinner=True)
def load_operational_source_freshness(operations_db_path: str) -> pd.DataFrame:
    database_file = Path(operations_db_path)
    if not database_file.exists():
        return pd.DataFrame()

    query = """
        SELECT
            source_name,
            dataset_name,
            last_available_date,
            expected_frequency,
            status,
            records_count,
            updated_at
        FROM source_freshness
        ORDER BY source_name, dataset_name
    """

    return read_sql_query(operations_db_path, query)


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


def calculate_benchmark_returns(
    bcb_series_df: pd.DataFrame,
    stocks_df: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for ticker, ticker_df in stocks_df.groupby("ticker"):
        ticker_df = ticker_df.sort_values("reference_date")
        first_value = float(ticker_df.iloc[0]["adjusted_close_price"])
        last_value = float(ticker_df.iloc[-1]["adjusted_close_price"])
        return_pct = ((last_value / first_value) - 1) * 100 if first_value else None
        rows.append({
            "benchmark": ticker,
            "tipo": "mercado",
            "data_inicial": ticker_df.iloc[0]["reference_date"],
            "data_final": ticker_df.iloc[-1]["reference_date"],
            "valor_inicial": first_value,
            "valor_final": last_value,
            "retorno_pct": return_pct,
        })

    for series_name, series_df in bcb_series_df.groupby("series_name"):
        series_df = series_df.sort_values("reference_date")
        first_value = float(series_df.iloc[0]["value"])
        last_value = float(series_df.iloc[-1]["value"])
        if series_name in {"selic_daily", "cdi_daily", "ipca_monthly"}:
            return_pct = ((series_df["value"] / 100 + 1).prod() - 1) * 100
        else:
            return_pct = ((last_value / first_value) - 1) * 100 if first_value else None

        rows.append({
            "benchmark": series_name,
            "tipo": "macro",
            "data_inicial": series_df.iloc[0]["reference_date"],
            "data_final": series_df.iloc[-1]["reference_date"],
            "valor_inicial": first_value,
            "valor_final": last_value,
            "retorno_pct": return_pct,
        })

    return pd.DataFrame(rows).sort_values(["tipo", "benchmark"])


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


def latest_row_or_none(df: pd.DataFrame, sort_column: str) -> pd.Series | None:
    if df.empty:
        return None

    return df.sort_values(sort_column).iloc[-1]


def format_pct(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "N/D"

    return f"{value:.2f}%"


def format_number(value: float | int | None, decimals: int = 2) -> str:
    if value is None or pd.isna(value):
        return "N/D"

    return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def classify_freshness(reference_date: pd.Timestamp, max_age_days: int, warning_age_days: int) -> str:
    age_days = (pd.Timestamp.today().normalize() - reference_date.normalize()).days

    if age_days <= max_age_days:
        return "OK"
    if age_days <= warning_age_days:
        return "Atencao"
    return "Desatualizado"


def build_freshness_df(
    selic_df: pd.DataFrame,
    ipca_df: pd.DataFrame,
    stocks_df: pd.DataFrame,
    bcb_series_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    latest_selic_date = selic_df["reference_date"].max()
    rows.append(
        {
            "fonte": "BCB Selic diaria",
            "ultima_data": latest_selic_date,
            "registros": len(selic_df),
            "status": classify_freshness(latest_selic_date, max_age_days=3, warning_age_days=7),
        }
    )

    latest_ipca_date = ipca_df["reference_date"].max()
    rows.append(
        {
            "fonte": "BCB IPCA mensal",
            "ultima_data": latest_ipca_date,
            "registros": len(ipca_df),
            "status": classify_freshness(latest_ipca_date, max_age_days=45, warning_age_days=75),
        }
    )

    for ticker, ticker_df in stocks_df.groupby("ticker"):
        latest_stock_date = ticker_df["reference_date"].max()
        rows.append(
            {
                "fonte": f"B3 {ticker}",
                "ultima_data": latest_stock_date,
                "registros": len(ticker_df),
                "status": classify_freshness(latest_stock_date, max_age_days=3, warning_age_days=7),
            }
        )

    if bcb_series_df is not None:
        known_series = {"selic_daily", "ipca_monthly"}
        for series_name, series_df in bcb_series_df[~bcb_series_df["series_name"].isin(known_series)].groupby("series_name"):
            latest_bcb_date = series_df["reference_date"].max()
            frequency = str(series_df["frequency"].iloc[0])
            rows.append(
                {
                    "fonte": f"BCB {series_name}",
                    "ultima_data": latest_bcb_date,
                    "registros": len(series_df),
                    "status": classify_freshness(
                        latest_bcb_date,
                        max_age_days=45 if frequency == "monthly" else 3,
                        warning_age_days=75 if frequency == "monthly" else 7,
                    ),
                }
            )

    freshness_df = pd.DataFrame(rows)
    freshness_df["dias_desde_ultima_data"] = (
        pd.Timestamp.today().normalize() - freshness_df["ultima_data"].dt.normalize()
    ).dt.days
    freshness_df["ultima_data"] = freshness_df["ultima_data"].dt.strftime("%d/%m/%Y")

    return freshness_df


def build_operational_freshness_display(source_freshness_df: pd.DataFrame) -> pd.DataFrame:
    display_df = source_freshness_df.copy()
    display_df["fonte"] = display_df["source_name"] + " - " + display_df["dataset_name"]
    display_df["ultima_data"] = pd.to_datetime(display_df["last_available_date"]).dt.strftime("%d/%m/%Y")
    display_df["dias_desde_ultima_data"] = (
        pd.Timestamp.today().normalize()
        - pd.to_datetime(display_df["last_available_date"]).dt.normalize()
    ).dt.days
    display_df = display_df.rename(
        columns={
            "expected_frequency": "frequencia_esperada",
            "records_count": "registros",
            "updated_at": "atualizado_em",
        }
    )
    return display_df[
        [
            "fonte",
            "ultima_data",
            "frequencia_esperada",
            "status",
            "registros",
            "dias_desde_ultima_data",
            "atualizado_em",
        ]
    ]


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
    bcb_series_df: pd.DataFrame,
    selic_df: pd.DataFrame,
    ipca_df: pd.DataFrame,
    stocks_df: pd.DataFrame,
) -> None:
    st.header("Resumo Executivo")

    latest_selic = selic_df.sort_values("reference_date").iloc[-1]
    latest_usd = latest_row_or_none(bcb_series_df[bcb_series_df["series_name"] == "usd_brl_ptax_sell_daily"], "reference_date")
    latest_cdi = latest_row_or_none(bcb_series_df[bcb_series_df["series_name"] == "cdi_daily"], "reference_date")
    latest_ibov = latest_row_or_none(stocks_df[stocks_df["ticker"] == "^BVSP"], "reference_date")
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
    col2.metric("CDI diario", f"{latest_cdi['value']:.6f}" if latest_cdi is not None else "N/D")
    col3.metric("Dolar PTAX venda", f"R$ {format_number(float(latest_usd['value']), 4)}" if latest_usd is not None else "N/D")
    col4.metric("Ibovespa", format_number(float(latest_ibov["close_price"]), 2) if latest_ibov is not None else "N/D")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("IPCA acumulado 2024", format_pct(ipca_accumulated_2024))
    col6.metric("Data Selic", latest_selic["reference_date"].strftime("%d/%m/%Y"))
    col7.metric("Tickers/benchmarks B3", stocks_df["ticker"].nunique())
    col8.metric("Series BCB", bcb_series_df["series_name"].nunique())

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


def render_benchmarks_page(
    bcb_series_df: pd.DataFrame,
    stocks_df: pd.DataFrame,
) -> None:
    st.header("Benchmarks")

    returns_df = calculate_benchmark_returns(bcb_series_df, stocks_df)
    display_df = returns_df.copy()
    display_df["data_inicial"] = display_df["data_inicial"].dt.strftime("%d/%m/%Y")
    display_df["data_final"] = display_df["data_final"].dt.strftime("%d/%m/%Y")
    display_df["valor_inicial"] = display_df["valor_inicial"].round(4)
    display_df["valor_final"] = display_df["valor_final"].round(4)
    display_df["retorno_pct"] = display_df["retorno_pct"].round(2)

    col1, col2, col3 = st.columns(3)
    col1.metric("Benchmarks", len(returns_df))
    col2.metric("Macro", int((returns_df["tipo"] == "macro").sum()))
    col3.metric("Mercado", int((returns_df["tipo"] == "mercado").sum()))

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    fig_returns = px.bar(
        returns_df,
        x="benchmark",
        y="retorno_pct",
        color="tipo",
        text="retorno_pct",
        title="Retorno acumulado no periodo",
        labels={"benchmark": "Benchmark", "retorno_pct": "Retorno (%)", "tipo": "Tipo"},
    )
    fig_returns.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
    fig_returns.update_layout(yaxis_ticksuffix="%")
    st.plotly_chart(fig_returns, use_container_width=True)

    b3_line_df = stocks_df.sort_values(["ticker", "reference_date"]).copy()
    b3_line_df["base_100"] = b3_line_df.groupby("ticker")["adjusted_close_price"].transform(lambda s: s / s.iloc[0] * 100)

    fig_b3 = px.line(
        b3_line_df,
        x="reference_date",
        y="base_100",
        color="ticker",
        title="Ativos B3 e Ibovespa em base 100",
        labels={"reference_date": "Data", "base_100": "Base 100", "ticker": "Ticker"},
    )
    fig_b3.update_layout(hovermode="x unified")
    st.plotly_chart(fig_b3, use_container_width=True)

    macro_df = bcb_series_df.sort_values(["series_name", "reference_date"]).copy()
    macro_df["base_100"] = macro_df.groupby("series_name")["value"].transform(lambda s: s / s.iloc[0] * 100)
    fig_macro = px.line(
        macro_df,
        x="reference_date",
        y="base_100",
        color="series_name",
        title="Indicadores macro em base 100",
        labels={"reference_date": "Data", "base_100": "Base 100", "series_name": "Serie"},
    )
    fig_macro.update_layout(hovermode="x unified")
    st.plotly_chart(fig_macro, use_container_width=True)


def render_pipeline_status_page(
    bcb_series_df: pd.DataFrame,
    selic_df: pd.DataFrame,
    ipca_df: pd.DataFrame,
    stocks_df: pd.DataFrame,
) -> None:
    st.header("Status do Pipeline")

    pipeline_runs_df = load_pipeline_runs(str(OPERATIONS_DB_FILE))
    source_freshness_df = load_operational_source_freshness(str(OPERATIONS_DB_FILE))

    if source_freshness_df.empty:
        freshness_df = build_freshness_df(selic_df, ipca_df, stocks_df, bcb_series_df)
        st.info("Freshness calculado em tempo real. Execute o pipeline para popular o historico operacional.")
    else:
        freshness_df = build_operational_freshness_display(source_freshness_df)

    status_counts = freshness_df["status"].value_counts().to_dict()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Fontes monitoradas", len(freshness_df))
    col2.metric("OK", status_counts.get("OK", 0))
    col3.metric("Atencao", status_counts.get("Atencao", 0))
    col4.metric("Desatualizado", status_counts.get("Desatualizado", 0))

    st.markdown("---")
    st.subheader("Freshness por fonte")
    st.dataframe(freshness_df, use_container_width=True, hide_index=True)

    fig = px.bar(
        freshness_df,
        x="fonte",
        y="dias_desde_ultima_data",
        color="status",
        title="Dias desde a ultima data disponivel",
        labels={"fonte": "Fonte", "dias_desde_ultima_data": "Dias", "status": "Status"},
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader("Historico recente de execucoes")

    if pipeline_runs_df.empty:
        st.info("Nenhuma execucao registrada em pipeline_runs ainda.")
        return

    latest_run = pipeline_runs_df.iloc[0]
    run_col1, run_col2, run_col3, run_col4 = st.columns(4)
    run_col1.metric("Ultima execucao", latest_run["module_name"])
    run_col2.metric("Status", latest_run["status"])
    run_col3.metric("Duracao (s)", format_number(latest_run["execution_time_seconds"], 2))
    run_col4.metric("Falhas recentes", int((pipeline_runs_df["status"] == "FAILED").sum()))

    st.dataframe(pipeline_runs_df, use_container_width=True, hide_index=True)

    duration_df = pipeline_runs_df.dropna(subset=["execution_time_seconds"]).copy()
    if not duration_df.empty:
        fig_runs = px.bar(
            duration_df.sort_values("run_id"),
            x="run_id",
            y="execution_time_seconds",
            color="status",
            hover_data=["module_name", "records_input", "records_output"],
            title="Duracao das ultimas execucoes registradas",
            labels={"run_id": "Run", "execution_time_seconds": "Segundos", "status": "Status"},
        )
        st.plotly_chart(fig_runs, use_container_width=True)


def render_data_quality_page() -> None:
    st.header("Qualidade dos Dados")

    quality_summary_file = VALIDATION_OUTPUT_FILES["quality_summary"]
    quality_results_file = VALIDATION_OUTPUT_FILES["quality_results"]
    date_gaps_file = VALIDATION_OUTPUT_FILES["date_gaps_detail"]

    stop_if_missing_file(quality_summary_file, "Resumo de qualidade nao encontrado.")
    stop_if_missing_file(quality_results_file, "Resultados de qualidade nao encontrados.")
    stop_if_missing_file(date_gaps_file, "Detalhe de gaps de datas nao encontrado.")

    summary = load_quality_summary(str(quality_summary_file))
    results_df = load_quality_results(str(quality_results_file))
    gaps_df = load_date_gaps(str(date_gaps_file))

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Status geral", summary.get("overall_status", "N/D"))
    col2.metric("Checks", summary.get("total_checks", 0))
    col3.metric("PASS", summary.get("pass", 0))
    col4.metric("WARN", summary.get("warn", 0))
    col5.metric("FAIL", summary.get("fail", 0))

    st.caption(f"Ultima validacao: {summary.get('generated_at', 'N/D')}")

    st.markdown("---")
    st.subheader("Checks por status")

    status_df = (
        results_df.groupby(["status", "severity"], dropna=False)
        .size()
        .reset_index(name="checks")
        .sort_values(["status", "severity"])
    )
    st.dataframe(status_df, use_container_width=True, hide_index=True)

    fig = px.bar(
        status_df,
        x="status",
        y="checks",
        color="severity",
        title="Distribuicao dos checks de qualidade",
        labels={"status": "Status", "checks": "Checks", "severity": "Severidade"},
    )
    st.plotly_chart(fig, use_container_width=True)

    relevant_checks_df = results_df[results_df["status"].isin(["WARN", "FAIL"])].copy()
    st.subheader("Alertas e falhas")
    if relevant_checks_df.empty:
        st.success("Nenhum WARN ou FAIL encontrado.")
    else:
        st.dataframe(
            relevant_checks_df[
                [
                    "check_id",
                    "check_category",
                    "check_name",
                    "dataset",
                    "severity",
                    "status",
                    "rows_affected",
                    "details",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Gaps de datas")
    if gaps_df.empty:
        st.success("Nenhum gap de data encontrado.")
    else:
        gaps_summary_df = (
            gaps_df.groupby(["dataset", "key", "check_name"], dropna=False)
            .size()
            .reset_index(name="gaps")
            .sort_values("gaps", ascending=False)
        )
        st.dataframe(gaps_summary_df, use_container_width=True, hide_index=True)

        with st.expander("Detalhe dos gaps"):
            st.dataframe(gaps_df, use_container_width=True, hide_index=True)


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
    bcb_series_df = load_bcb_series_data(database_path)
    selic_df = load_selic_data(database_path)
    ipca_df = load_ipca_data(database_path)
    stocks_df = load_stock_data(database_path)

    stop_if_empty(bcb_series_df, "Nao ha series BCB no banco final.")
    stop_if_empty(selic_df, "Nao ha dados de Selic no banco final.")
    stop_if_empty(ipca_df, "Nao ha dados de IPCA no banco final.")
    stop_if_empty(stocks_df, "Nao ha cotacoes B3 no banco final.")

    render_header()
    page = render_sidebar()

    if page == "Resumo Executivo":
        render_executive_summary(bcb_series_df, selic_df, ipca_df, stocks_df)
    elif page == "Status do Pipeline":
        render_pipeline_status_page(bcb_series_df, selic_df, ipca_df, stocks_df)
    elif page == "Qualidade dos Dados":
        render_data_quality_page()
    elif page == "Benchmarks":
        render_benchmarks_page(bcb_series_df, stocks_df)
    elif page == "Selic Diaria":
        render_selic_page(selic_df)
    elif page == "IPCA Mensal":
        render_ipca_page(ipca_df)
    elif page == "Cotacoes B3":
        render_stocks_page(stocks_df)


if __name__ == "__main__":
    main()
