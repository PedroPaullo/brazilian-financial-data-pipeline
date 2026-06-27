from pathlib import Path
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SELIC_FILE = PROJECT_ROOT / "data" / "raw" / "bcb" / "selic_daily.csv"
IPCA_FILE = PROJECT_ROOT / "data" / "raw" / "bcb" / "ipca_monthly.csv"
STOCKS_FILE = PROJECT_ROOT / "data" / "raw" / "b3" / "stock_prices_daily.csv"

def main():
    for f in [SELIC_FILE, IPCA_FILE, STOCKS_FILE]:
        assert f.exists(), f"Arquivo nao encontrado: {f}"

    selic_df = pd.read_csv(SELIC_FILE)
    ipca_df = pd.read_csv(IPCA_FILE)
    stocks_df = pd.read_csv(STOCKS_FILE)

    assert not selic_df.empty
    assert not ipca_df.empty
    assert not stocks_df.empty

    expected_tickers = {"PETR4.SA", "VALE3.SA", "ITUB4.SA"}
    assert expected_tickers.issubset(set(stocks_df["ticker"].unique()))

    print("\nTeste do Modulo 1 concluido com sucesso.")
    print(f"Selic: {len(selic_df)} linhas")
    print(f"IPCA: {len(ipca_df)} linhas")
    print(f"Acoes: {len(stocks_df)} linhas")

if __name__ == "__main__":
    main()
