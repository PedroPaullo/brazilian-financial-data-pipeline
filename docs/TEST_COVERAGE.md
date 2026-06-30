# Cobertura de Testes

Este documento registra a cobertura automatizada atual do projeto e as lacunas que dependem de validacao manual ou CI.

## Resumo atual

- Testes locais esperados: `31 passed, 1 skipped`
- O teste ignorado por padrao e o de integracao real com PostgreSQL, que exige `DATABASE_URL` e `RUN_POSTGRES_INTEGRATION=1`.
- A suite local nao exige Docker, servidor PostgreSQL ativo, Streamlit em execucao ou rede externa.

## Arquivos de teste

| Arquivo | Cobertura principal |
| --- | --- |
| `tests/test_module_01_collection.py` | Artefatos de coleta e arquivos brutos esperados. |
| `tests/test_module_02_validation.py` | Validacao de dados e relatorios de qualidade. |
| `tests/test_module_03_storage.py` | Banco SQLite processado, views principais e dados carregados. |
| `tests/test_module_04_report.py` | Workbook Excel e abas esperadas. |
| `tests/test_module_05_monitoring.py` | Banco operacional e freshness de fontes. |
| `tests/test_module_06_operational_maturity.py` | CLI do pipeline, alertas, banco operacional e compilacao de modulos operacionais. |
| `tests/test_module_07_financial_analytics.py` | Metricas financeiras de retorno, volatilidade, drawdown, correlacao e excesso contra benchmark. |
| `tests/test_module_08_data_coverage.py` | Cobertura historica, faixa dinamica e arquivos de cobertura. |
| `tests/test_module_09_institutional_sources.py` | Fontes institucionais, CVM, ANBIMA e calendario B3. |
| `tests/test_module_09_intelligence.py` | Loader da camada de inteligencia, seis views, colunas e idempotencia. |
| `tests/test_module_10_traceability_reconciliation_versioning.py` | Manifest, auditoria, versionamento, reconciliacao e wrappers CLI. |
| `tests/test_module_10_scheduler.py` | Import seguro do scheduler, `--help` e proximo horario util. |
| `tests/test_module_11_source_availability.py` | Disponibilidade esperada por fonte, status estruturado, validacao e reconciliacao. |
| `tests/test_module_11_postgres.py` | Assinatura do loader PostgreSQL, parsing da URL default e integracao real opt-in. |
| `tests/test_module_12_artifact_retention.py` | Retencao de artefatos, manifest diario, reconciliacao diaria e status de coleta. |
| `tests/test_module_12_dashboard_data.py` | Funcoes de carga de dados do dashboard e banco vazio com schema/views. |

## Matriz por modulo

| Modulo | Teste correspondente | Situacao |
| --- | --- | --- |
| `src/__init__.py` | N/A | Marcador de pacote. |
| `src/alerts.py` | `test_module_06_operational_maturity.py` | Executado via CLI e compilado. |
| `src/analytics/__init__.py` | N/A | Marcador de pacote. |
| `src/analytics/market_metrics.py` | `test_module_07_financial_analytics.py` | Cobertura direta. |
| `src/artifact_retention.py` | `test_module_12_artifact_retention.py` | Cobertura direta. |
| `src/collect_data.py` | `test_module_01_collection.py`, `test_module_11_source_availability.py`, `test_module_12_artifact_retention.py` | Cobertura direta e indireta. |
| `src/collectors/__init__.py` | N/A | Marcador de pacote. |
| `src/collectors/anbima_client.py` | `test_module_09_institutional_sources.py` | Cobertura direta sem chamada externa real. |
| `src/collectors/anbima_prices.py` | `test_module_09_institutional_sources.py` | Compilacao automatizada. |
| `src/collectors/b3_yfinance.py` | `test_module_01_collection.py` | Cobertura indireta por artefatos de coleta. |
| `src/collectors/bcb_sgs.py` | `test_module_11_source_availability.py` | Cobertura direta com mocks/status. |
| `src/collectors/cvm_funds.py` | `test_module_09_institutional_sources.py` | Cobertura direta de normalizacao. |
| `src/config.py` | Diversos testes | Cobertura indireta por constantes e paths. |
| `src/coverage_report.py` | `test_module_08_data_coverage.py` | Cobertura direta. |
| `src/dashboard.py` | `test_module_12_dashboard_data.py`, `test_module_06_operational_maturity.py` | Carga de dados testada; UI Streamlit manual. |
| `src/database/__init__.py` | N/A | Marcador de pacote. |
| `src/database/postgres_loader.py` | `test_module_11_postgres.py` | Assinatura e URL local; conexao real opt-in/CI. |
| `src/financial_calendar.py` | `test_module_06_operational_maturity.py`, `test_module_10_scheduler.py`, `test_module_09_institutional_sources.py` | Cobertura indireta e regras de dia util. |
| `src/generate_report.py` | `test_module_04_report.py` | Cobertura por artefato gerado. |
| `src/intelligence/__init__.py` | N/A | Marcador de pacote. |
| `src/intelligence/loader.py` | `test_module_09_intelligence.py` | Cobertura direta. |
| `src/load_processed_data.py` | `test_module_03_storage.py` | Cobertura por banco processado e views. |
| `src/logger.py` | Execucoes de CLI e pipeline | Cobertura indireta. |
| `src/metadata/__init__.py` | N/A | Marcador de pacote. |
| `src/metadata/audit.py` | `test_module_10_traceability_reconciliation_versioning.py` | Cobertura direta. |
| `src/metadata/dataset_versioning.py` | `test_module_10_traceability_reconciliation_versioning.py` | Cobertura direta. |
| `src/metadata/manifest.py` | `test_module_10_traceability_reconciliation_versioning.py`, `test_module_12_artifact_retention.py` | Cobertura direta. |
| `src/monitoring.py` | `test_module_05_monitoring.py` | Cobertura direta. |
| `src/reference_data/__init__.py` | N/A | Marcador de pacote. |
| `src/reference_data/b3_calendar.py` | `test_module_09_institutional_sources.py`, `test_module_10_scheduler.py` | Cobertura direta/indireta. |
| `src/reports/__init__.py` | N/A | Marcador de pacote. |
| `src/reports/excel_report.py` | `test_module_04_report.py` | Cobertura por workbook gerado. |
| `src/run_pipeline.py` | `test_module_06_operational_maturity.py`, `test_module_10_traceability_reconciliation_versioning.py`, `test_module_11_source_availability.py` | CLI e fluxos parciais cobertos. |
| `src/scheduler.py` | `test_module_10_scheduler.py` | Import, help e calculo do proximo disparo cobertos; loop bloqueante manual. |
| `src/source_availability.py` | `test_module_11_source_availability.py` | Cobertura direta. |
| `src/storage/__init__.py` | N/A | Marcador de pacote. |
| `src/storage/database.py` | `test_module_03_storage.py` | Cobertura indireta por banco processado. |
| `src/storage/load_processed_sqlite.py` | `test_module_03_storage.py` | Cobertura indireta por carga SQLite. |
| `src/validate_data.py` | `test_module_02_validation.py`, `test_module_11_source_availability.py` | Cobertura por validacao e ausencia estruturada. |
| `src/validation/__init__.py` | N/A | Marcador de pacote. |
| `src/validation/reconciliation.py` | `test_module_10_traceability_reconciliation_versioning.py`, `test_module_12_artifact_retention.py` | Cobertura direta. |
| `src/validators/__init__.py` | N/A | Marcador de pacote. |
| `src/validators/load_raw_to_sqlite.py` | `test_module_11_source_availability.py` | Cobertura direta para tabelas vazias/status. |
| `src/validators/quality_checks.py` | `test_module_02_validation.py`, `test_module_11_source_availability.py` | Cobertura direta/indireta. |

## Lacunas residuais

- Renderizacao visual completa do Streamlit deve ser validada manualmente com `streamlit run src/dashboard.py`.
- Loop bloqueante do APScheduler nao e iniciado em teste automatizado; os testes cobrem import seguro, `--help` e calculo do proximo horario.
- Integracao real PostgreSQL fica fora da suite local por padrao e deve rodar no GitHub Actions ou com `DATABASE_URL` e `RUN_POSTGRES_INTEGRATION=1`.
- Chamadas externas reais de BCB, yfinance, CVM e ANBIMA continuam melhor validadas por execucoes controladas do pipeline/CI, nao por testes unitarios offline.
- Modulos de pacote `__init__.py` nao precisam de teste dedicado enquanto permanecerem sem logica.
