# Deploy reproduzível

## Escopo

O `docker-compose.yml` sobe três componentes: PostgreSQL persistente, API
FastAPI e dashboard Streamlit. Os diretórios `data`, `reports` e `logs` são
montados como volumes do host para que a reinicialização dos containers não
apague os artefatos locais.

## Estado da validação

Localmente, a API e os testes Python são validados usando o ambiente oficial
`.venv`. Docker não está instalado nesta máquina, portanto a stack Docker não
é declarada como validada localmente.

No GitHub Actions, o workflow `Docker validation` valida a sintaxe do Compose,
constrói a imagem, sobe PostgreSQL, API e dashboard, verifica `GET /health`
com resposta HTTP 200, confirma os três serviços em execução, verifica os
logs de inicialização do dashboard e encerra os serviços com remoção dos
volumes de teste. O workflow `CI`, o `PostgreSQL validation` e o `Daily
pipeline operations` permanecem independentes e devem continuar verdes.

## Subida

Na raiz do projeto, se o Docker Engine estiver instalado:

```powershell
docker compose build
docker compose up -d postgres
docker compose up -d api dashboard
```

Para validar somente a configuração sem subir containers:

```powershell
docker compose config -q
```

Verifique:

```powershell
Invoke-WebRequest http://localhost:8000/health
Start-Process http://localhost:8501
```

A API fica em `http://localhost:8000`, a documentação OpenAPI em
`http://localhost:8000/docs` e o dashboard em `http://localhost:8501`.

## Carga dos dados

Os containers de API e dashboard não coletam dados automaticamente. Execute o
pipeline agendado em um worker persistente ou pelo workflow operacional, e
monte os mesmos volumes de dados no serviço que produz os artefatos. O
PostgreSQL do compose persiste em `postgres_data`.

## Promocao para nuvem

Para publicar o site, use um provedor que ofereça volumes persistentes ou
PostgreSQL gerenciado. Publique API e dashboard como servicos separados e
configure o health check da API em `/health`. O pipeline agendado deve usar
os mesmos secrets de Gmail e a mesma base persistente; sem isso, a nuvem pode
subir o site, mas não garante continuidade dos dados. Não há provedor de
deploy configurado neste repositório; portanto o site não é considerado
publicado.
