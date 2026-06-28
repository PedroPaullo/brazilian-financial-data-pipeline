## Brazilian Financial Data Pipeline

![Python 3.10](https://img.shields.io/badge/python-3.10-blue.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)
![Last commit](https://img.shields.io/github/last-commit/PedroPaullo/brazilian-financial-data-pipeline)

Pipeline completo de dados financeiros brasileiros: coleta automatizada, validação de qualidade, armazenamento normalizado, observabilidade operacional, dashboard web e relatório Excel executivo.

## Problema

Dados financeiros públicos brasileiros (Selic, IPCA, cotações B3) estão dispersos em múltiplas fontes, sem padronização, sem rastreabilidade e sem validação de qualidade. Analistas perdem horas consolidando e verificando dados manualmente.

## Solução

Pipeline modular em Python que automatiza todo o ciclo: coleta → validação → armazenamento → observabilidade → dashboard → relatório.

## Impacto

- 771 registros BCB/SGS coletados: Selic, IPCA, dólar PTAX venda e CDI
- 1004 cotações B3/Yahoo Finance coletadas: PETR4, VALE3, ITUB4 e Ibovespa
- 45 checagens de qualidade executadas com status PASS/WARN/FAIL
- Dashboard operacional com freshness, qualidade de dados, benchmarks e histórico de execução

## Arquitetura

coleta (APIs públicas) → validação (SQL + Python) → armazenamento (SQLite normalizado) → observabilidade → dashboard Streamlit → relatório Excel

## Módulos

| Módulo | Descrição | Arquivo |
|--------|-----------|---------|
| 1 — Coleta | Selic, IPCA, dólar PTAX e CDI via BCB/SGS; ações e Ibovespa via yfinance | src/collect_data.py |
| 2 — Validação | 45 checagens SQL + Python, relatório de qualidade | src/validate_data.py |
| 3 — Armazenamento | Schema SQLite normalizado com views analíticas | src/load_processed_data.py |
| 4 — Relatório | Excel automático com abas executivas, séries e benchmarks | src/generate_report.py |
| 5 — Observabilidade | Histórico de execuções e freshness por fonte | src/monitoring.py |
| 6 — Dashboard | Streamlit com resumo, status, qualidade, benchmarks e séries | src/dashboard.py |

## Fontes de dados

- BCB/SGS — Selic diária (série 11), IPCA mensal (série 433), dólar PTAX venda diário (série 1) e CDI diário (série 12)
- Yahoo Finance via yfinance — PETR4.SA, VALE3.SA, ITUB4.SA e Ibovespa (^BVSP)

## Stack

Python 3.10 · pandas · requests · yfinance · SQLite · openpyxl · Streamlit · Plotly · APScheduler

## Ambiente recomendado

Use Python 3.10 em um ambiente virtual dedicado ao projeto. Evite executar com o ambiente base do Anaconda ativo, porque pacotes instalados no user-site podem causar conflitos de NumPy/pandas/Plotly.

No PowerShell, se houver conflito de pacotes locais:

```powershell
$env:PYTHONNOUSERSITE="1"
```

## Como executar o pipeline

```powershell
pip install -r requirements.txt

python src/collect_data.py --start 2024-01-01 --end 2024-12-31
python src/validate_data.py
python src/load_processed_data.py
python src/generate_report.py
```

## Dashboard

O dashboard Streamlit lê o SQLite final e os artefatos de validação para exibir visão executiva, indicadores de freshness, qualidade dos dados, benchmarks, Selic, IPCA e cotações B3.

```powershell
python -m streamlit run src\dashboard.py
```

## Agendamento

O scheduler executa coleta, validação, carga e relatório automaticamente em dias úteis às 07:00.

```powershell
python src/scheduler.py
```

Para testar uma execução única sem deixar o agendador ativo:

```powershell
python src/scheduler.py --run-now
```

## Observabilidade operacional

As execuções dos módulos são registradas em `data/operations/pipeline_operations.db`, ignorado pelo Git por ser um artefato local. Esse banco armazena:

- `pipeline_runs`: histórico recente de execuções, status, duração e contagens.
- `source_freshness`: última data disponível por fonte, frequência esperada e status.

O dashboard usa essas tabelas na página `Status do Pipeline`.

## Resultados

- Selic 2024: 0.045513% ao dia (última leitura: 31/12/2024)
- IPCA acumulado 2024: 4.83%
- Dólar PTAX venda e CDI diário integrados como benchmarks macro
- Ibovespa (^BVSP) integrado como benchmark de mercado
- Relatório gerado em reports/financial_report.xlsx

## Autor

Pedro Paullo Azevedo· Engenharia de Controle e Automação · https://linkedin.com/in/pedropaullosazevedo
