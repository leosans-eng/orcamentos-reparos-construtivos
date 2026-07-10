# Pré-lançamento / entrega da API ORC à TI

## Repositório App × API

**Manter monorepo** por enquanto. Separar só quando o instalador do ORC e o deploy da API tiverem ciclos bem independentes.

## Checklist de entrega

### Segurança e configuração

- [ ] `SECRET_KEY` de produção longa e aleatória (não o valor de `.env.example`)
- [ ] `ADMIN_PASSWORD` forte; trocar após o primeiro login
- [ ] `DATABASE_URL` apontando para o Postgres **do servidor**
- [ ] API **sem** `--reload` em produção
- [ ] Firewall liberando a porta só na rede interna
- [ ] `api/.env` e dumps **fora** do Git

### Banco

- [ ] Postgres provisionado pela TI
- [ ] Backup automático (`pg_dump`) e teste de restore — ver `api/README.md`
- [ ] Primeira subida da API (`create_all` + seed) ou restore de dump



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

- [ ] `docker compose up -d` (homologação) ou Postgres da TI no ar
- [ ] API sobe; `/docs` e `/api/health` OK
- [ ] Login admin; criar usuário; promover admin
- [ ] Orçamento: criar, editar, copiar, excluir; conflito em 2 PCs
- [ ] Composições e etapas: CRUD + botão Atualizar
- [ ] Reiniciar API; dados persistem no Postgres