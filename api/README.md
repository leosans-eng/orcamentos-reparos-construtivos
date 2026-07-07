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
- **Senha inicial:** valor de `ADMIN_PASSWORD` em `api\.env`

Na primeira execução, o banco é populado automaticamente a partir de `dados_usuario/composicoes_proprias.json`, `dados_usuario/etapas_predefinidas.json` e `dados_usuario/orcamentos_customizados.json` (se a tabela de orçamentos estiver vazia).

## Administração de usuários (somente admin)

Abra http://localhost:8000/docs, faça login em **POST `/api/auth/login`** com o `admin` e clique em **Authorize** colando o `access_token`.

| Ação | Endpoint | Corpo de exemplo |
|------|----------|------------------|
| Listar usuários | `GET /api/auth/users` | — |
| Criar usuário | `POST /api/auth/users` | `{"username": "maria", "password": "senha-segura"}` |
| Redefinir senha (esqueceu) | `POST /api/auth/users/{id}/reset-password` | `{"senha_nova": "nova-senha"}` |
| Desativar acesso | `PATCH /api/auth/users/{id}/active` | `{"is_active": false}` |
| Reativar acesso | `PATCH /api/auth/users/{id}/active` | `{"is_active": true}` |
| Excluir usuário | `DELETE /api/auth/users/{id}` | — |

O `{id}` é o UUID do usuário, obtido em **GET `/api/auth/users`**.

**Senhas:** o sistema nunca guarda a senha em texto legível. Se alguém esquecer, o admin **define uma senha nova** (reset); não há como “recuperar” a antiga.

**Desativar vs excluir:** desativar bloqueia o login e mantém o cadastro; excluir remove o usuário do banco.

## Produção (servidor da TI)

1. Instalar PostgreSQL e criar banco `orc`
2. Definir `DATABASE_URL` e `SECRET_KEY` em `api/.env`
3. Rodar: `uvicorn api.main:app --host 0.0.0.0 --port 8000`
4. Configurar nos desktops a URL da API informada pela TI

Para trocar de Supabase para servidor próprio depois: altere apenas `DATABASE_URL` no servidor (com migração `pg_dump`/`pg_restore`).

## Fase 3 — Orçamentos customizados

Orçamentos compartilhados entre todos os usuários autenticados. O conteúdo (etapas, itens SINAPI, composições próprias) fica em JSON no banco; metadados ficam em colunas para listagem e ordenação.

### Modelo (`orcamentos_customizados`)

| Coluna | Tipo | Uso |
|--------|------|-----|
| `id` | UUID | Identificador do orçamento |
| `nome` | string (255) | Nome exibido na lista; indexado para busca |
| `dados` | JSON | `bdi_percent`, `estado_referencia`, `grupos[]` |
| `versao` | int | Controle otimista (HTTP 409 em conflito) |
| `created_at` | datetime | Ordenação na lista (mais recente primeiro) |
| `updated_at` | datetime | Última alteração real |
| `created_by_id` | UUID (opcional) | Usuário que criou ou duplicou |

O JSON em `dados` segue o mesmo formato do desktop (`grupos` → `itens` com tipos `sinapi` e `composicao_propria`). Nome, datas e versão **não** ficam duplicados dentro de `dados`.

### Endpoints

Todos exigem JWT (`Authorize` em `/docs`).

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/api/orcamentos` | Lista resumida (criado_em ↓). Query `?q=` filtra por nome |
| `GET` | `/api/orcamentos/{id}` | Orçamento completo + `versao` |
| `POST` | `/api/orcamentos` | Cria vazio: `{"nome": "..."}` |
| `PUT` | `/api/orcamentos/{id}` | Salva conteúdo: `{"orcamento": {...}, "versao": N}` |
| `PATCH` | `/api/orcamentos/{id}/nome` | Renomeia: `{"nome": "...", "versao": N}` |
| `POST` | `/api/orcamentos/{id}/duplicar` | Cópia com novos IDs: `{"nome": "..."}` (opcional) |
| `DELETE` | `/api/orcamentos/{id}` | Exclui |

### Resposta da lista (`GET /api/orcamentos`)

```json
{
  "orcamentos": [
    {
      "id": "uuid",
      "nome": "Edifício Alpha",
      "versao": 12,
      "criado_em": "2026-07-06T18:00:00+00:00",
      "atualizado_em": "2026-07-06T19:30:00+00:00",
      "grupos": 5,
      "itens": 142
    }
  ]
}
```

### Resposta completa (`GET /api/orcamentos/{id}`)

```json
{
  "id": "uuid",
  "nome": "Edifício Alpha",
  "bdi_percent": 30.62,
  "estado_referencia": "SP",
  "grupos": [ "..." ],
  "versao": 12,
  "criado_em": "...",
  "atualizado_em": "..."
}
```

### Conflito de versão (409)

Em `PUT` e `PATCH`, se `versao` enviada ≠ versão no banco:

```json
{
  "detail": {
    "detail": "conflito_versao",
    "mensagem": "Alguém alterou este orçamento. Recarregue os dados e tente novamente.",
    "versao_atual": 13
  }
}
```

### Próximos passos (desktop)

- Substituir `core/orcamento_storage.py` por cliente HTTP (como composições/etapas)
- Seed opcional a partir de `dados_usuario/orcamentos_customizados.json` na primeira subida
- Importação i9 continua no desktop; após importar, `POST /api/orcamentos` + `PUT` com o conteúdo
