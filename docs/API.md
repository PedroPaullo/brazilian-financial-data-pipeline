# API REST

## Objetivo

A API expõe a camada de inteligência financeira do pipeline para consumo por
dashboards, aplicações internas e integrações externas. Ela lê o banco
processado local (`data/processed/financial_data.db`) e retorna JSON validado
por schemas Pydantic.

## Execução local

Na raiz do projeto, com o ambiente virtual ativo:

```powershell
uvicorn src.api:app --reload
```

Documentação interativa e contrato OpenAPI:

- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

## Contrato de disponibilidade

`GET /health` responde `200` quando a aplicação está ativa. Os endpoints de
dados respondem `503` quando o banco processado não existe ou está
indisponível. Quando o banco existe, mas a view não possui linhas, a resposta
é `200` com uma lista vazia; ausência de dados não é convertida em dado falso.

## Endpoints

| Método e rota | Fonte | Retorno |
|---|---|---|
| `GET /health` | Aplicação | `status` e `timestamp` UTC |
| `GET /indicators/latest` | `vw_market_latest_indicators` | Indicador mais recente por série |
| `GET /assets/returns` | `vw_asset_returns_ranking` | Retornos de ativos em 30, 90 dias e período total |
| `GET /data/freshness` | `vw_data_freshness_status` | Atualização e frescor por fonte/série |
| `GET /pipeline/health` | `vw_pipeline_health_daily` | Saúde diária das execuções |
| `GET /sources/availability` | `vw_source_availability_summary` | Disponibilidade agregada por fonte |
| `GET /indicators/macro/monthly` | `vw_macro_indicators_summary` | Indicadores macroeconômicos mensais |

## Exemplos de resposta

Indicadores atuais:

```json
[
  {
    "series_name": "selic_daily",
    "latest_date": "2026-06-26",
    "latest_value": 15.0,
    "previous_value": 15.0,
    "change_pct": 0.0
  }
]
```

Saúde da aplicação:

```json
{
  "status": "ok",
  "timestamp": "2026-07-22T12:00:00+00:00"
}
```

## Rastreabilidade

Cada rota de dados declara explicitamente a view SQLite de origem. Para
reproduzir uma resposta, registre o commit do pipeline, o período da coleta e
o conteúdo do banco processado usado na execução. O endpoint não substitui a
reconciliação operacional nem o manifest; ele é uma camada de consumo desses
dados já processados.

## Limitações atuais

Nesta versão não há autenticação, paginação, filtros por período ou suporte a
escrita. Esses recursos devem ser adicionados somente após definir requisitos
de segurança, volume e compatibilidade do contrato.
