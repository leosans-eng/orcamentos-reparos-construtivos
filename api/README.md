# API ORC

Backend compartilhado do sistema ORC: **autenticação**, **composições próprias**, **etapas pré-definidas** e **orçamentos customizados**.

Banco: **PostgreSQL**.

## Pré-requisitos

- Python 3.10+
- PostgreSQL (em desenvolvimento local: [Docker Desktop](https://www.docker.com/products/docker-desktop/) + `docker compose up -d`)

## 1. Banco de dados

Na raiz do projeto (homologação / PC de desenvolvimento):

```bat
docker compose up -d
```

Container `orc-postgres` na porta `5432` (usuário/senha/db: `orc` / `orc_dev` / `orc`).

### Configurar `api/.env`

```bat
copy .env.example api\.env
```

URL de desenvolvimento:

```
DATABASE_URL=postgresql+psycopg2://orc:orc_dev@localhost:5432/orc
```

Na **primeira** subida com tabelas vazias, o seed cria o admin e pode importar JSONs de `dados_usuario/` (se existirem).

## 2. Instalar dependências

```bat
pip install -r api\requirements.txt
```

## 3. Iniciar a API (desenvolvimento)

```bat
api\run_dev.bat
```

Sobe o Compose (se o Docker estiver no PATH) e o uvicorn em `0.0.0.0:8000` com reload.

- Neste PC: http://localhost:8000/docs  
- Colegas na rede: `http://SEU_IPV4:8000`  

## 4. Login no ORC desktop

- **URL da API:** `http://localhost:8000` ou `http://IPV4:8000`
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

Checklist completo: [`LANCAMENTO.md`](LANCAMENTO.md).

## Backup com `pg_dump`

O Postgres guarda usuários, composições, etapas e orçamentos. Backup periódico é importante principalmente por orçamentos em andamento.

**Frequência sugerida (LAN):** diário + retenção de 7–14 dias, em pasta fora do disco do servidor (NAS / outro HD).

```bat
REM Backup (formato custom — recomendado)
pg_dump -h localhost -U orc -d orc -F c -f backups\orc_YYYYMMDD.dump

REM Restore (banco de destino já criado)
pg_restore -h localhost -U orc -d orc --clean --if-exists backups\orc_YYYYMMDD.dump
```

Ajuste `-h`, `-U` e `-d` conforme o `DATABASE_URL` de produção.

**Importante:** testar o restore pelo menos uma vez em homologação.

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
