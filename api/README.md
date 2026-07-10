# API ORC

Backend compartilhado do sistema ORC: **autenticação**, **composições próprias**, **etapas pré-definidas** e **orçamentos customizados**.

Banco: **PostgreSQL**. Empacotamento recomendado: **Docker Compose** (API + Postgres).

## Subida rápida (Linux / WSL / servidor)

Na raiz do repositório:

```bash
cp .env.example api/.env
# Edite api/.env: SECRET_KEY e ADMIN_PASSWORD (obrigatório em produção)

docker compose up -d --build
```

Pronto:

| Serviço | URL |
|---------|-----|
| API / docs | http://localhost:8000/docs |
| Health | http://localhost:8000/api/health |
| Postgres | `localhost:5432` (usuário/senha/db: `orc` / `orc_dev` / `orc`) |

Parar: `docker compose down`  
Logs da API: `docker compose logs -f api`

Na **primeira** subida com tabelas vazias, o seed cria o `admin` e importa os JSON de `dados_usuario/` (montados no container). Inclua nessa pasta os arquivos atualizados de composições, etapas e orçamentos antes do `up`, se quiser a carga inicial dos testes.

Os desktops ORC usam `http://IP_DO_SERVIDOR:8000` no login.

## Desenvolvimento no Windows (API no host)

Útil quando você quer `--reload` no código Python sem rebuild da imagem:

1. `docker compose up -d db` — só o Postgres  
2. `api\run_dev.bat` — uvicorn no Windows com reload  

`DATABASE_URL` em `api/.env` deve apontar para `localhost:5432`.

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

## Produção (TI)

Preferência: o mesmo `docker compose up -d --build` no servidor Linux.

Checklist: [`LANCAMENTO.md`](LANCAMENTO.md).

1. Definir em `api/.env` (ou variáveis do Compose): `SECRET_KEY`, `ADMIN_PASSWORD` fortes  
2. Opcional: trocar `POSTGRES_PASSWORD` (e alinhar no Compose)  
3. Firewall: liberar **8000** na LAN (Postgres 5432 só se a TI precisar acesso externo ao banco)  
4. Desktops: URL `http://IP_DO_SERVIDOR:8000`  
5. Backup periódico do Postgres (abaixo)

Se a TI já tiver Postgres gerenciado, pode rodar só a imagem da API apontando `DATABASE_URL` para esse host (sem o serviço `db`).

## Backup com `pg_dump`

```bash
# Com o stack Compose no ar:
docker exec orc-postgres pg_dump -U orc -d orc -F c -f /tmp/orc.dump
docker cp orc-postgres:/tmp/orc.dump ./api/backups/orc_YYYYMMDD.dump
```

Restore (banco de destino já criado):

```bash
docker cp ./api/backups/orc_YYYYMMDD.dump orc-postgres:/tmp/orc.dump
docker exec orc-postgres pg_restore -U orc -d orc --clean --if-exists /tmp/orc.dump
```

**Frequência sugerida (LAN):** diário + retenção 7–14 dias, cópia fora do disco do servidor. Teste o restore em homologação.

## Orçamentos customizados

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
