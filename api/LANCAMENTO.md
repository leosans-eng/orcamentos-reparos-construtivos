# Pré-lançamento / entrega da API ORC à TI

## Repositório App × API

**Manter monorepo** por enquanto. Separar só quando o instalador do ORC e o deploy da API tiverem ciclos bem independentes.

## Checklist de entrega

### Segurança e configuração

- [ ] `SECRET_KEY` de produção longa e aleatória (não o valor de `.env.example`)
- [ ] `ADMIN_PASSWORD` forte; trocar após o primeiro login
- [ ] API **sem** `--reload` em produção (o Compose já sobe assim)
- [ ] Firewall liberando a porta **8000** só na rede interna
- [ ] `api/.env` e dumps **fora** do Git

### Banco

- [ ] Stack `docker compose up -d --build` **ou** Postgres da TI + container/imagem da API
- [ ] Backup automático (`pg_dump`) e teste de restore — ver `api/README.md`
- [ ] Primeira subida: seed via `dados_usuario/` (tabelas vazias) ou restore de dump
- [ ] JSON de seed atualizados na pasta `dados_usuario/` no servidor (se for usar seed)



### Funcional

- [ ] `/api/health` → `ok` (API + banco)
- [ ] Login JWT; usuários admin e comuns
- [ ] CRUD composições / etapas / orçamentos
- [ ] Conflito 409 (edição simultânea)
- [ ] Promoção admin: `PATCH /api/auth/users/{id}/permissions`



### Desktop / rede

- [ ] URL de produção ou IP do servidor no login do ORC
- [ ] Teste multi-PC (`http://IP:8000`, não localhost nos colegas)



### Entregáveis à TI

- [ ] Como subir, variáveis obrigatórias, healthcheck, backup (`api/README.md`)
- [ ] Credenciais iniciais por canal seguro
- [ ] Quem aplica updates da API



### Planejar depois (não bloqueia go-live)

- [ ] Migrações Alembic (hoje: `create_all`)
- [ ] CORS mais restrito se a API sair da LAN
- [ ] HTTPS / reverse proxy se a TI exigir
- [ ] UI desktop de gestão de usuários (hoje via `/docs`)



## Checklist rápido de testes

- [ ] `docker compose up -d --build` sobe `orc-postgres` e `orc-api`
- [ ] `/docs` e `/api/health` OK
- [ ] Login admin; criar usuário; promover admin
- [ ] Orçamento: criar, editar, copiar, excluir; conflito em 2 PCs
- [ ] Composições e etapas: CRUD + botão Atualizar
- [ ] `docker compose restart api`; dados persistem no Postgres