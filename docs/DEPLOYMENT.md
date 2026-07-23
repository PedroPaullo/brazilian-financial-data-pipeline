# Deploy reproducivel

## Escopo

O `docker-compose.yml` sobe tres componentes: PostgreSQL persistente, API
FastAPI e dashboard Streamlit. Os diretorios `data`, `reports` e `logs` sao
montados como volumes do host para que a reinicializacao dos containers nao
apague os artefatos locais.

## Subida

Na raiz do projeto:

```powershell
docker compose build
docker compose up -d postgres
docker compose up -d api dashboard
```

Verifique:

```powershell
Invoke-WebRequest http://localhost:8000/health
Start-Process http://localhost:8501
```

A API fica em `http://localhost:8000`, a documentacao OpenAPI em
`http://localhost:8000/docs` e o dashboard em `http://localhost:8501`.

## Carga dos dados

Os containers de API e dashboard nao coletam dados automaticamente. Execute o
pipeline agendado em um worker persistente ou pelo workflow operacional, e
monte os mesmos volumes de dados no serviço que produz os artefatos. O
PostgreSQL do compose persiste em `postgres_data`.

## Promocao para nuvem

Para publicar o site, use um provedor que ofereca volumes persistentes ou
PostgreSQL gerenciado. Publique API e dashboard como servicos separados e
configure o health check da API em `/health`. O pipeline agendado deve usar
os mesmos secrets de Gmail e a mesma base persistente; sem isso, a nuvem pode
subir o site, mas nao garante continuidade dos dados.
