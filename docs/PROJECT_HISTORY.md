# Project History

## Melhoria 9 - Fontes institucionais financeiras

Status: concluida.

Foram adicionadas fontes institucionais complementares ao pipeline:

- Calendario B3 controlado para 2024, 2025 e 2026.
- Coletor opcional de fundos CVM.
- Estrutura inicial para dados ANBIMA, com execucao protegida por variavel de ambiente.
- Novas tabelas e views SQLite para analise de fundos CVM.
- Integracao opcional com dashboard e exportacao Excel.
- Testes sem dependencia de internet.

Commit:

```text
8bf6d3a885285ccd6d89a55c39bf9969e5262161
```

Observacao importante:

A existencia do calendario B3 para 2024, 2025 e 2026 nao significa, por si so, que todos os dados historicos foram coletados. A cobertura historica real depende da execucao e validacao do backfill.

Nao afirmar que o projeto possui cobertura historica real de dois anos enquanto o backfill real de `2024-01-01` ate `2026-06-28` nao for executado e validado.

## Melhoria 10 - Rastreabilidade, reconciliacao e versionamento dos dados

Status: implementada apos a Melhoria 9.

Esta melhoria adiciona manifests de execucao, auditoria SQLite, versionamento logico de datasets, relatorios de reconciliacao e preparacao opcional para PostgreSQL. SQLite permanece o backend padrao.
