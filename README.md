## Brazilian Financial Data Pipeline

Pipeline completo de dados financeiros brasileiros: coleta automatizada, validação de qualidade, armazenamento normalizado e relatório Excel executivo.

## Problema

Dados financeiros públicos brasileiros (Selic, IPCA, cotações B3) estão dispersos em múltiplas fontes, sem padronização, sem rastreabilidade e sem validação de qualidade. Analistas perdem horas consolidando e verificando dados manualmente.

## Solução

Pipeline modular em Python que automatiza todo o ciclo: coleta → validação → armazenamento → relatório.

## Impacto

- 253 registros Selic + 12 IPCA + 753 cotações B3 coletados e validados automaticamente
- 34 checagens de qualidade executadas (nulos, duplicatas, valores negativos, gaps de datas)
- Relatório Excel executivo gerado automaticamente com gráficos e métricas

## Arquitetura

coleta (APIs públicas) → validação (SQL + Python) → armazenamento (SQLite normalizado) → relatório (Excel com gráficos)

## Módulos

| Módulo | Descrição | Arquivo |
|--------|-----------|---------|
| 1 — Coleta | Selic e IPCA via BCB/SGS, cotações B3 via yfinance | src/collect_data.py |
| 2 — Validação | 34 checagens SQL + Python, relatório de qualidade | src/validate_data.py |
| 3 — Armazenamento | Schema SQLite normalizado com views analíticas | src/load_processed_data.py |
| 4 — Relatório | Excel automático com 4 abas e gráficos | src/generate_report.py |

## Fontes de dados

- BCB/SGS — Taxa Selic diária (série 11) e IPCA mensal (série 433)
- Yahoo Finance via yfinance — PETR4.SA, VALE3.SA, ITUB4.SA

## Stack

Python 3.10 · pandas · requests · yfinance · SQLite · openpyxl

## Como executar

pip install -r requirements.txt

python src/collect_data.py --start 2024-01-01 --end 2024-12-31
python src/validate_data.py
python src/load_processed_data.py
python src/generate_report.py

## Resultados

- Selic 2024: 0.045513% ao dia (última leitura: 31/12/2024)
- IPCA acumulado 2024: 4.83%
- Relatório gerado em reports/financial_report.xlsx

## Autor

Pedro Paullo Azevedo· Engenharia de Controle e Automação · https://linkedin.com/in/pedropaullosazevedo