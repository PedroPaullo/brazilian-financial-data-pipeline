from __future__ import annotations

import os
import py_compile
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from collectors.anbima_client import AnbimaClient
from collectors.cvm_funds import normalize_daily_reports, normalize_registry
from reference_data.b3_calendar import (
    get_b3_expected_trading_dates,
    is_b3_trading_day,
    load_b3_calendar,
)


def main():
    b3_calendar_file = PROJECT_ROOT / "data" / "reference" / "b3_trading_calendar.csv"
    assert (SRC_DIR / "reference_data" / "b3_calendar.py").exists()
    assert b3_calendar_file.exists()
    py_compile.compile(str(SRC_DIR / "reference_data" / "b3_calendar.py"), doraise=True)

    calendar_df = load_b3_calendar()
    assert not calendar_df.empty
    assert {"date", "is_trading_day", "market", "reason", "source", "updated_at"}.issubset(calendar_df.columns)
    assert is_b3_trading_day("2024-01-06") is False
    assert is_b3_trading_day("2024-01-02") is True
    expected_dates = get_b3_expected_trading_dates("2024-01-01", "2024-01-10")
    assert expected_dates

    cvm_file = SRC_DIR / "collectors" / "cvm_funds.py"
    assert cvm_file.exists()
    py_compile.compile(str(cvm_file), doraise=True)

    raw_daily = pd.DataFrame(
        {
            "CNPJ_FUNDO": ["00.000.000/0001-91"],
            "DT_COMPTC": ["2024-01-31"],
            "VL_TOTAL": ["1.234,50"],
            "VL_PATRIM_LIQ": ["1.200,10"],
            "VL_QUOTA": ["1,234567"],
            "CAPTC_DIA": ["10,00"],
            "RESG_DIA": ["5,00"],
            "NR_COTST": ["100"],
        }
    )
    daily_df = normalize_daily_reports(raw_daily)
    assert list(daily_df.columns) == [
        "fund_cnpj",
        "reference_date",
        "total_portfolio_value",
        "net_asset_value",
        "quota_value",
        "daily_subscriptions",
        "daily_redemptions",
        "number_of_shareholders",
        "source",
        "collected_at",
    ]
    assert round(float(daily_df.iloc[0]["net_asset_value"]), 2) == 1200.10
    assert int(daily_df.iloc[0]["number_of_shareholders"]) == 100

    raw_registry = pd.DataFrame(
        {
            "CNPJ_FUNDO": ["00.000.000/0001-91"],
            "DENOM_SOCIAL": ["Fundo Exemplo"],
            "SIT": ["EM FUNCIONAMENTO NORMAL"],
            "DT_REG": ["2024-01-01"],
            "TP_FUNDO": ["FI"],
            "PUBLICO_ALVO": ["GERAL"],
        }
    )
    registry_df = normalize_registry(raw_registry)
    assert registry_df.iloc[0]["fund_name"] == "Fundo Exemplo"

    schema_sql = (SRC_DIR / "storage" / "schema.sql").read_text(encoding="utf-8")
    assert "dim_cvm_fund" in schema_sql
    assert "fact_cvm_fund_daily_report" in schema_sql
    assert "vw_cvm_fund_daily_reports" in schema_sql
    assert "vw_cvm_fund_flows_monthly" in schema_sql

    anbima_file = SRC_DIR / "collectors" / "anbima_client.py"
    assert anbima_file.exists()
    py_compile.compile(str(anbima_file), doraise=True)
    os.environ["ANBIMA_ENABLE"] = "false"
    client = AnbimaClient()
    assert client.is_enabled() is False
    assert client.get_access_token()["status"] == "SKIPPED"

    py_compile.compile(str(SRC_DIR / "collectors" / "anbima_prices.py"), doraise=True)
    py_compile.compile(str(SRC_DIR / "dashboard.py"), doraise=True)

    print("\nTeste do Modulo 9 concluido com sucesso.")


def test_module_09_institutional_sources():
    main()


if __name__ == "__main__":
    main()
