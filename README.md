## Brazilian Financial Data Pipeline

![Python 3.10](https://img.shields.io/badge/python-3.10-blue.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)
![Last commit](https://img.shields.io/github/last-commit/PedroPaullo/brazilian-financial-data-pipeline)

Pipeline completo de dados financeiros brasileiros: coleta automatizada, fontes institucionais opcionais, validação de qualidade, armazenamento normalizado, rastreabilidade, reconciliação, observabilidade operacional, dashboard web e relatório Excel executivo.

## Problema

Dados financeiros públicos brasileiros (Selic, IPCA, cotações B3) estão dispersos em múltiplas fontes, sem padronização, sem rastreabilidade e sem validação de qualidade. Analistas perdem horas consolidando e verificando dados manualmente.

## Solução

Pipeline modular em Python que automatiza todo o ciclo: coleta → validação → armazenamento → cobertura histórica → observabilidade → alertas → analytics → dashboard → relatório.

## Impacto

- 771 registros BCB/SGS coletados: Selic, IPCA, dólar PTAX venda e CDI
- 1004 cotações B3/Yahoo Finance coletadas: PETR4, VALE3, ITUB4 e Ibovespa
- 45 checagens de qualidade executadas com status PASS/WARN/FAIL
- Dashboard operacional com freshness, qualidade de dados, benchmarks e histórico de execução
- Orquestrador único, cobertura histórica, calendário B3 controlado, CVM Fundos opcional, ANBIMA adapter, lineage, reconciliação, manifests e analytics de mercado

## Arquitetura

coleta (APIs públicas) → validação (SQL + Python) → armazenamento (SQLite normalizado) → cobertura histórica → manifests/versionamento → reconciliação → observabilidade/SLA → alertas → analytics → dashboard Streamlit → relatório Excel

## Módulos

| Módulo | Descrição | Arquivo |
|--------|-----------|---------|
| 1 — Coleta | Selic, IPCA, dólar PTAX e CDI via BCB/SGS; ações e Ibovespa via yfinance | src/collect_data.py |
| 2 — Validação | 45 checagens SQL + Python, relatório de qualidade | src/validate_data.py |
| 3 — Armazenamento | Schema SQLite normalizado com views analíticas | src/load_processed_data.py |
| 4 — Relatório | Excel automático com abas executivas, séries e benchmarks | src/generate_report.py |
| 5 — Observabilidade | Histórico de execuções e freshness por fonte | src/monitoring.py |
| 6 — Dashboard | Streamlit com resumo, status, qualidade, benchmarks e séries | src/dashboard.py |
| 7 — Orquestração | Execução mestre com módulos selecionáveis | src/run_pipeline.py |
| 8 — Cobertura | Backfill histórico, calendário esperado e percentual de preenchimento | src/coverage_report.py |
| 9 — Fontes institucionais | Calendário B3, CVM Fundos e ANBIMA adapter | src/reference_data/b3_calendar.py; src/collectors/cvm_funds.py |
| 10 — Rastreabilidade | Manifests, auditoria, versionamento lógico e reconciliação | src/metadata/; src/validation/reconciliation.py |
| 11 — Alertas | Alertas operacionais em JSON/CSV | src/alerts.py |
| 12 — Analytics | Retorno, risco, drawdown, correlação e benchmark | src/analytics/market_metrics.py |

## Fontes de dados

- BCB/SGS — Selic diária (série 11), IPCA mensal (série 433), dólar PTAX venda diário (série 1) e CDI diário (série 12)
- Yahoo Finance via yfinance — PETR4.SA, VALE3.SA, ITUB4.SA e Ibovespa (^BVSP)
- CVM Dados Abertos — Informe Diário de Fundos e cadastro de fundos/classes, opcional
- ANBIMA — adapter preparado para credenciais, desabilitado por padrão

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

python src/run_pipeline.py --start 2024-01-01 --end 2024-12-31
```

Entrypoints equivalentes tambem existem na raiz:

```powershell
python collect_data.py --help
python run_pipeline.py --help
python run_pipeline.py --skip-collection
```

Também é possível rodar por módulo:

```powershell
python src/collect_data.py --start 2024-01-01 --end 2024-12-31
python src/validate_data.py
python src/load_processed_data.py
python src/coverage_report.py --start 2024-01-01 --end 2024-12-31
python src/generate_report.py
```

Rastreabilidade e reconciliacao:

```powershell
python run_pipeline.py --skip-collection --enable-manifest --reconcile
python run_pipeline.py --reconcile-only
```

Backfill historico real:

```powershell
python collect_data.py --start-date 2024-01-01 --end-date 2026-06-28
```

Nao afirmar cobertura historica real de dois anos enquanto esse backfill nao for executado e validado.

Coleta opcional de CVM Fundos:

```powershell
python src/collect_data.py --start 2024-01-01 --end 2024-12-31 --include-cvm --cvm-year-month 202401
```

## Dashboard

O dashboard Streamlit lê o SQLite final e os artefatos de validação/cobertura para exibir visão executiva, indicadores de freshness, qualidade dos dados, cobertura histórica, benchmarks, Selic, IPCA e cotações B3.

```powershell
python -m streamlit run src\dashboard.py
```

## Agendamento

O scheduler executa coleta, validação, carga, cobertura, relatório e alertas automaticamente em dias úteis às 07:00.

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
- `data_artifacts`: artefatos gerados pelo pipeline e status local.

O dashboard usa essas tabelas na página `Status do Pipeline`.

## Cobertura Histórica

```powershell
python src/coverage_report.py --start 2024-01-01 --end 2024-12-31
```

A cobertura é salva em:

- `reports/coverage/data_coverage_report.csv`
- `reports/coverage/data_coverage_summary.json`
- `reports/coverage/data_coverage_missing_dates.csv`

O dashboard inclui a página `Cobertura Historica` e o Excel inclui a aba `Cobertura`.

## Fontes Institucionais

- Calendário B3 auditável: `data/reference/b3_trading_calendar.csv`
- Coletor CVM Fundos: `python src/collectors/cvm_funds.py --year-month 202401`
- ANBIMA adapter: `ANBIMA_ENABLE=false` por padrão, com retorno SKIPPED sem credenciais

O dashboard inclui a página `Fundos CVM` e o Excel inclui a aba `Fundos CVM`.

## Alertas e Analytics

```powershell
python src/alerts.py
```

Os alertas são salvos em `reports/operations/alerts.json` e `reports/operations/alerts.csv`.

O dashboard inclui páginas de performance, risco, correlação e alertas operacionais.

## Documentação

- `docs/ARCHITECTURE.md`
- `docs/OPERATIONS.md`
- `docs/DATA_QUALITY.md`
- `docs/DATA_COVERAGE.md`
- `docs/B3_CALENDAR.md`
- `docs/CVM_FUNDS.md`
- `docs/ANBIMA.md`
- `docs/LOCAL_TERMINAL_USAGE.md`
- `docs/DATA_LINEAGE.md`
- `docs/DATA_VERSIONING.md`
- `docs/RECONCILIATION.md`
- `docs/POSTGRESQL.md`
- `docs/PROJECT_HISTORY.md`

## Resultados

- Selic 2024: 0.045513% ao dia (última leitura: 31/12/2024)
- IPCA acumulado 2024: 4.83%
- Dólar PTAX venda e CDI diário integrados como benchmarks macro
- Ibovespa (^BVSP) integrado como benchmark de mercado
- Relatório gerado em reports/financial_report.xlsx

## Autor

Pedro Paullo Azevedo· Engenharia de Controle e Automação · https://linkedin.com/in/pedropaullosazevedo
