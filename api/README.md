# API ORC — Fase 1

Backend compartilhado para **composições próprias** e **etapas pré-definidas**.

## Pré-requisitos

- Python 3.10+
- Para produção: PostgreSQL (recomendado)
- Para testes locais sem Docker: SQLite (já configurado em `api/.env`)

## 1. Banco de dados

### Opção A — SQLite (testes locais, sem instalar nada)

O arquivo `api/.env` já vem com:

```
DATABASE_URL=sqlite:///./api/orc_dev.db
```

### Opção B — PostgreSQL (produção / servidor da TI)

Na raiz do projeto, com [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado:

```bat
docker compose up -d
```

Em `api/.env`:

```
DATABASE_URL=postgresql+psycopg2://orc:orc_dev@localhost:5432/orc
```

## 2. Configurar ambiente da API

```bat
copy .env.example api\.env
```

Edite `api\.env` se necessário (padrão já funciona com Docker local).

## 3. Instalar dependências da API

```bat
pip install -r api\requirements.txt
```

## 4. Iniciar a API

```bat
api\run_dev.bat
```

A documentação interativa fica em: http://localhost:8000/docs

## 5. Login no ORC desktop

- **URL da API:** `http://localhost:8000` (dev) ou a URL fornecida pela TI em produção
- **Usuário inicial:** `admin` (definido em `api\.env`)
- **Senha inicial:** `orc-admin-change-me` (troque em produção)

Na primeira execução, o banco é populado automaticamente a partir de `dados_usuario/composicoes_proprias.json` e `dados_usuario/etapas_predefinidas.json`.

## Criar novos usuários

Com token de admin (via `/docs` ou login):

`POST /api/auth/users` com `{"username": "maria", "password": "senha-segura"}`

## Produção (servidor da TI)

1. Instalar PostgreSQL e criar banco `orc`
2. Definir `DATABASE_URL` e `SECRET_KEY` em `api/.env`
3. Rodar: `uvicorn api.main:app --host 0.0.0.0 --port 8000`
4. Configurar nos desktops a URL da API informada pela TI

Para trocar de Supabase para servidor próprio depois: altere apenas `DATABASE_URL` no servidor (com migração `pg_dump`/`pg_restore`).
