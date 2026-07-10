# API ORC

Backend compartilhado do sistema ORC: **autenticação**, **composições próprias**, **etapas pré-definidas** e **orçamentos customizados**.

Banco padrão: **PostgreSQL**.

## Pré-requisitos

- Python 3.10+
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (recomendado para o Postgres local)
- Ou um PostgreSQL já instalado (mesma URL do `.env.example`)

## 1. Banco de dados (PostgreSQL)

Na raiz do projeto:

```bat
docker compose up -d
```

Isso sobe o container `orc-postgres` na porta `5432` (usuário/senha/db: `orc` / `orc_dev` / `orc`).

### Configurar `api/.env`

```bat
copy .env.example api\.env
```

Ou, se você ainda usa SQLite no `.env` antigo:

```bat
api\switch_to_postgres.bat
```

URL padrão:

```
DATABASE_URL=postgresql+psycopg2://orc:orc_dev@localhost:5432/orc
```

### Migrar dados do SQLite (opcional)

Se você já tem `api/orc_dev.db` com usuários/orçamentos de teste:

1. Postgres no ar (`docker compose up -d`)
2. `api\.env` apontando para PostgreSQL
3. Na raiz, com o venv ativo:

```bat
.venv\Scripts\python.exe -m api.migrate_sqlite_to_postgres
```

Se o Postgres já tiver dados e você quiser substituir:

```bat
.venv\Scripts\python.exe -m api.migrate_sqlite_to_postgres --force
```

Na **primeira** subida sem migração, o seed cria o admin e importa JSONs de `dados_usuario/` se as tabelas estiverem vazias.

## 2. Instalar dependências da API

```bat
pip install -r api\requirements.txt
```

## 3. Iniciar a API

```bat
api\run_dev.bat
```

O script tenta subir o Docker Compose e depois o uvicorn em `0.0.0.0:8000`.

- Neste PC: http://localhost:8000/docs  
- Colegas na rede: `http://SEU_IPV4:8000`  

Se o Firewall do Windows perguntar, permita o Python em redes privadas.

## 4. Login no ORC desktop

- **URL da API:** `http://localhost:8000` (dev) ou `http://IPV4:8000` (rede)
- **Usuário inicial:** `admin` (ou `ADMIN_USERNAME` em `api\.env`)
- **Senha inicial:** valor de `ADMIN_PASSWORD` em `api\.env`

## Administração de usuários (somente admin)

Abra http://localhost:8000/docs, faça login em **POST `/api/auth/login`** e clique em **Authorize** colando o `access_token`.

| Ação | Endpoint | Corpo de exemplo |
|------|----------|------------------|
| Listar usuários | `GET /api/auth/users` | — |
| Criar usuário | `POST /api/auth/users` | `{"username": "maria", "password": "senha-segura"}` |
| Criar já como admin | `POST /api/auth/users` | `{"username": "joao", "password": "...", "permissions": {"admin": true}}` |
| Promover / remover admin | `PATCH /api/auth/users/{id}/permissions` | `{"admin": true}` ou `{"admin": false}` |
| Redefinir senha | `POST /api/auth/users/{id}/reset-password` | `{"senha_nova": "nova-senha"}` |
| Desativar / reativar | `PATCH /api/auth/users/{id}/active` | `{"is_active": false}` |
| Excluir | `DELETE /api/auth/users/{id}` | — |

## Produção (servidor da TI)

1. Instalar PostgreSQL e criar banco `orc` (e usuário com privilégios)
2. Definir em `api/.env` (ou variáveis de ambiente do serviço):
   - `DATABASE_URL=postgresql+psycopg2://USER:SENHA@HOST:5432/orc`
   - `SECRET_KEY=` chave longa e aleatória (nunca o valor de exemplo)
   - `ADMIN_PASSWORD=` senha forte do admin inicial
3. Rodar **sem** `--reload`, preferencialmente como serviço:
   ```bat
   uvicorn api.main:app --host 0.0.0.0 --port 8000
   ```
4. Firewall: liberar a porta da API só na rede interna
5. Nos desktops ORC: URL `http://IP_DO_SERVIDOR:8000`
6. Backup periódico do Postgres (ver abaixo)

## Backup com `pg_dump`

O Postgres guarda usuários, composições, etapas e orçamentos. É importante o Backup periódico principalmente por conta de orçamentos em andamento, que são realizados múltiplas vezes por semana.

**Frequência sugerida (LAN):** diário + retenção de 7–14 dias, em pasta fora do disco do servidor (NAS / outro HD).

```bat
REM Backup (formato custom — recomendado)
pg_dump -h localhost -U orc -d orc -F c -f backups\orc_YYYYMMDD.dump

REM Restore (banco de destino já criado)
pg_restore -h localhost -U orc -d orc --clean --if-exists backups\orc_YYYYMMDD.dump
```

Ajuste `-h`, `-U` e `-d` conforme o `DATABASE_URL` de produção. Em Docker local, use o host/porta publicados pelo Compose (`localhost:5432`).

**Importante:** Testar o restore pelo menos uma vez em homologação.

## Orçamentos customizados

Orçamentos compartilhados entre usuários autenticados. Conteúdo em JSON; metadados em colunas.

### Endpoints (JWT)

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/api/orcamentos` | Lista (`?q=` filtra por nome) |
| `GET` | `/api/orcamentos/{id}` | Detalhe + `versao` |
| `POST` | `/api/orcamentos` | Cria: `{"nome": "..."}` |
| `PUT` | `/api/orcamentos/{id}` | Salva: `{"orcamento": {...}, "versao": N}` |
| `PATCH` | `/api/orcamentos/{id}/nome` | Renomeia |
| `POST` | `/api/orcamentos/{id}/duplicar` | Cópia |
| `DELETE` | `/api/orcamentos/{id}` | Exclui |

Conflito de edição simultânea → HTTP **409** (`Recarregue…`).

## SQLite (apenas emergência)

Não use com vários usuários. Se precisar isoladamente, comente a URL Postgres em `api/.env` e use:

```
DATABASE_URL=sqlite:///./api/orc_dev.db
```
