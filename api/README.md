# API ORC

Backend compartilhado do **ORC**: autenticação, composições próprias, etapas pré-definidas e orçamentos customizados.

Stack: **FastAPI + PostgreSQL** via **Docker Compose**.  
Servidor alvo: **Windows** (Docker Desktop).

Este diretório é a **raiz do repositório da API**.

## Subida (produção — Windows)

Pré-requisito: [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e aberto.

```bat
copy .env.example .env
REM Edite .env: SECRET_KEY e ADMIN_PASSWORD

run_dev.bat
```

Equivalente: `docker compose up -d --build`

| Serviço | URL |
|---------|-----|
| Docs | http://localhost:8000/docs |
| Health | http://localhost:8000/api/health |
| Postgres | localhost:5432 (`orc` / `orc_dev` / `orc`) |

Parar: `docker compose down`  
Logs: `docker compose logs -f api`

Na **primeira** subida (banco vazio), o seed cria o usuário `admin` e importa os JSON de `dados_usuario/`.

Desktops ORC: URL `http://IP_DO_SERVIDOR:8000`.

### Firewall

No Windows Defender Firewall, liberar **TCP 8000** para redes privadas. Confirmar que os clientes usam o IPv4 da LAN do servidor.

## Desenvolvimento local (PC do Léo — sem Docker Desktop no Windows, com WSL)

Fluxo típico: **Postgres no WSL** + **API no Windows**.

1. No WSL (uma vez / quando reiniciar o PC), na pasta `api`:
   ```bash
   docker compose up -d db
   # se a API do Compose estiver ocupando a porta 8000:
   docker compose stop api
   ```
2. No Windows, na pasta `api`:
   ```bat
   run_local.bat
   ```

Isso sobe o uvicorn com `--reload` (recarrega ao salvar código).  
`DATABASE_URL` no `.env` deve usar `localhost:5432` (porta publicada pelo container no WSL).

**Não use `run_local.bat` em produção.** No servidor Windows da TI: Docker Desktop + `run_dev.bat`.

## Administração de usuários (admin)

Em `/docs`: login → **Authorize** com o token.

| Ação | Endpoint | Exemplo |
|------|----------|---------|
| Listar | `GET /api/auth/users` | — |
| Criar | `POST /api/auth/users` | `{"username":"maria","password":"senha-segura"}` |
| Admin | `PATCH /api/auth/users/{id}/permissions` | `{"admin": true}` |
| Reset senha | `POST /api/auth/users/{id}/reset-password` | `{"senha_nova":"..."}` |
| Ativar/desativar | `PATCH /api/auth/users/{id}/active` | `{"is_active": false}` |

## Backup

```bat
mkdir backups 2>nul
docker exec orc-postgres pg_dump -U orc -d orc -F c -f /tmp/orc.dump
docker cp orc-postgres:/tmp/orc.dump backups\orc_YYYYMMDD.dump
```

Restore: ver [`LANCAMENTO.md`](LANCAMENTO.md). Frequência sugerida: diário, retenção 7–14 dias.

## Conteúdo deste repositório

| Item | Função |
|------|--------|
| `docker-compose.yml` | Postgres + API |
| `Dockerfile` | Imagem da API |
| `run_dev.bat` | Produção no servidor Windows (Docker Desktop: API + Postgres) |
| `run_local.bat` | Dev no seu PC: API no Windows + Postgres no WSL (sem Docker Desktop) |
| `start.sh` | Alternativa bash/WSL para o mesmo stack do `run_dev.bat` |
| `dados_usuario/*.json` | Seed inicial (só se o banco estiver vazio) |
| `routers/`, `*.py` | Código da API |
| `.env.example` | Modelo de configuração |

Checklist: [`LANCAMENTO.md`](LANCAMENTO.md).
