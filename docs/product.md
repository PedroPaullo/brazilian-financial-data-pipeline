# Visao de Produto

## Problema que resolve

Dados financeiros brasileiros importantes ficam espalhados em diferentes sites, formatos e calendarios. Para uma pessoa ou equipe acompanhar mercado, juros, inflacao, dolar e ativos da B3, normalmente e preciso baixar planilhas, conferir datas, juntar arquivos e torcer para nada estar desatualizado.

Esse projeto resolve esse trabalho repetitivo. Ele organiza a coleta, checagem, armazenamento e entrega dos dados em um fluxo unico, com evidencias do que foi executado.

## Como funciona

### Coleta automatica

O pipeline busca dados nas fontes certas e salva o material bruto para consulta posterior. Ele pode ser executado manualmente ou por agendamento em dias uteis.

### Validacao de qualidade

Antes de usar os dados, o projeto verifica se eles fazem sentido. Se uma serie ainda nao foi publicada, como pode acontecer com o IPCA mensal, isso aparece como aviso claro e nao como sucesso falso.

### Armazenamento confiavel

Depois da validacao, os dados entram em um banco organizado. Isso evita depender de planilhas soltas e facilita consultas consistentes para relatorios, dashboard e auditoria.

### Relatorios e dashboard

O resultado fica disponivel em Excel e em dashboard interativo. Assim, gestores, recrutadores e analistas conseguem enxergar indicadores, retornos, cobertura e status do pipeline sem precisar ler o codigo.

## Resultados reais

Backfill validado de `2024-01-01` a `2026-06-28`.

| Indicador | Resultado |
| --- | ---: |
| `selic_daily` | 625 registros |
| `ipca_monthly` | 29 registros |
| `usd_brl_ptax_sell_daily` | 625 registros |
| `cdi_daily` | 624 registros |
| Acoes B3 | 2484 registros |
| `fact_bcb_series` | 1903 registros |
| `fact_b3_stock_prices` | 2484 registros |
| Cobertura | 8 datasets, 99.56% media, `overall_status: OK` |
| Reconciliacao | `PASSED` |
| Validacao | 47 checks, 44 PASS, 2 WARN, 0 FAIL |

## Diferencial

Este projeto nao e apenas um script que baixa dados. Ele funciona como um pipeline operacional, com coleta, validacao, armazenamento, relatorios, dashboard, agendamento, logs, manifest, versionamento e reconciliacao.

Na pratica, isso significa que o resultado pode ser conferido. Se algo falha, o projeto registra onde falhou; se uma fonte ainda nao publicou o dado, isso aparece como aviso; se os dados foram carregados, a reconciliacao confirma se os totais esperados batem.

## Capturas de tela

![Dashboard - Resumo Executivo](docs/screenshots/dashboard_resumo.png)

![Dashboard - Inteligência Financeira](docs/screenshots/dashboard_inteligencia.png)

![Relatório Excel](docs/screenshots/excel_report.png)
