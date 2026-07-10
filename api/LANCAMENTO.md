# Pré-lançamento da API ORC

Checklist antes de entregar a API ao servidor / time de TI, e testes após a troca SQLite → PostgreSQL.

## Separar repositório App × API?

**Recomendação agora: manter um único repositório.**


| Manter monorepo (agora)                              | Separar depois                                        |
| ---------------------------------------------------- | ----------------------------------------------------- |
| Versões de contrato (schemas/endpoints) andam juntas | Times/ciclos de release totalmente independentes      |
| Um `git clone` sobe app + API + Compose              | TI só clona a API; app vira outro artefato            |
| Mais simples no estágio atual                        | Exige versionamento de API (`/v1`) e changelog rígido |


**Separe só quando** o app for liberado por instalador/GitHub Releases com cadência própria **e** a API for deploy contínuo pelo time de TI, com contratos estáveis. Até lá, pastas `api/` + desktop no mesmo repo é o caminho mais seguro.

---



## O que falta / validar antes do lançamento



### Segurança e configuração

- [ ] `SECRET_KEY` de produção longa e aleatória (não o valor de `.env.example`)
- [ ] `ADMIN_PASSWORD` forte; trocar após o primeiro login
- [ ] `DATABASE_URL` apontando para o Postgres **do servidor** (não `orc_dev` de Docker local)
- [ ] API **sem** `--reload` em produção
- [ ] Firewall liberando a porta só na rede interna
- [ ] Confirmar que `api/.env` e dumps **não** vão no Git (já em `.gitignore`)



### Banco

- [ ] Postgres instalado/provisionado pela TI (ou Docker só em homologação)
- [ ] Backup automático (`pg_dump`) e teste de restore
- [ ] Rodar a API uma vez para `create_all` + seed (ou restaurar dump migrado)
- [ ] Se havia dados no SQLite de teste: migrou com `python -m api.migrate_sqlite_to_postgres`



### Funcional (contrato da API)

- [ ] `/api/health` responde `ok`
- [ ] Login JWT; usuários admin e comuns
- [ ] CRUD composições / etapas / orçamentos
- [ ] Conflito 409 (edição simultânea) funciona
- [ ] Promoção admin: `PATCH /api/auth/users/{id}/permissions`



### Desktop

- [ ] Instalador / build aponta para a URL de produção ou o usuário digita no login
- [ ] Teste multi-PC na URL `http://IP:8000` (não localhost nos colegas)



### Operação com a TI (entregáveis)

- [ ] Documento curto: como subir, variáveis obrigatórias, healthcheck, backup
- [ ] Credenciais iniciais (admin) entregues por canal seguro
- [ ] Acordo de quem aplica updates da API (git pull / serviço Windows / etc.)



### Ainda não bloqueia o go-live da API, mas vale planejar

- [ ] Migrações Alembic (hoje: `create_all` — ok no início; frágil se o schema evoluir)
- [ ] Restringir CORS em produção (hoje `allow_origins=["*"]` — aceitável só se a API for só desktop+rede interna)
- [ ] HTTPS / reverse proxy se a TI exigir acesso fora da LAN
- [ ] UI desktop de gestão de usuários (hoje só via `/docs`)
- [ ] Remover do README/código qualquer resto “só SQLite” em instrutivo de produção

---



## Checklist de testes (após SQLite → PostgreSQL)

Faça **no PC que hospeda a API**, com Docker Compose (ou Postgres da TI) e `api/.env` em Postgres.

### A. Subida

- [ ] `docker compose up -d` → container saudável (`pg_isready`)
- [ ] `api\run_dev.bat` sobe sem erro de conexão
- [ ] Log mostra `API ORC iniciada.`
- [ ] [http://localhost:8000/docs](http://localhost:8000/docs) abre
- [ ] `GET /api/health` → `{"status":"ok"}`



### B. Seed / migração

- [ ] Se migrou do SQLite: usuários e orçamentos antigos aparecem
- [ ] Se banco novo: login com `admin` / senha do `.env` funciona
- [ ] `GET /api/composicoes/catalogo` e `GET /api/etapas/catalogo` retornam dados (seed ou migrados)
- [ ] `GET /api/orcamentos` lista orçamentos esperados



### C. Auth

- [ ] Login OK com senha correta; falha com senha errada
- [ ] Admin cria usuário comum
- [ ] Admin promove usuário (`permissions` → `admin: true`)
- [ ] Admin remove admin de outro usuário (não do único admin ativo)
- [ ] Reset de senha e desativar/reativar usuário



### D. Orçamentos (desktop + API)

- [ ] Abrir módulo Orçamento Customizado, lista carrega
- [ ] Criar, renomear, copiar, excluir
- [ ] Editar itens, BDI, estado; salvar; reabrir em outro PC e ver a mesma versão
- [ ] **Dois PCs no mesmo orçamento**: um salva depois do outro → aviso de conflito / recarregar
- [ ] Botão Atualizar na lista e no editor



### E. Composições e etapas

- [ ] Listar, criar, editar, excluir
- [ ] Conflito de versão ao salvar em paralelo (dois usuários)
- [ ] Botão Atualizar no cabeçalho



### F. Rede

- [ ] No PC do colega: URL `http://IPV4_DO_HOST:8000` no login do ORC
- [ ] Abrir `http://IPV4:8000/docs` no navegador do colega
- [ ] Se falhar: Firewall do host (permitir Python / porta 8000) e confirmar `--host 0.0.0.0`



### G. Estabilidade

- [ ] Deixar 2–3 clientes abertos 15–30 min editando
- [ ] Reiniciar só a API; clientes fazem login de novo e dados persistem no Postgres
- [ ] `docker compose restart` (ou restart do serviço Postgres) e API volta a conectar (`pool_pre_ping`)

---



## Melhorias de otimização plausíveis (sugestões)

Ordenadas por **impacto × esforço** no estágio atual:

1. **Índices / listagem de orçamentos** — a lista já ordena por `created_at`; se a busca `?q=` crescer, garantir índice/trigram ou filtro só por prefixo. Hoje o volume costuma ser pequeno.
2. **Não devolver JSON completo na listagem** — já existe resumo (`grupos`/`itens`); manter assim e evitar carregar `dados` na listagem (já é o desenho atual).
3. **Cache no desktop** — listas com recarga em background + fingerprint (já feito em orçamentos); estender o “não redesenhar se igual” a composições/etapas se a UI piscar.
4. **Payload de orçamento** — orçamentos muito grandes (centenas de itens) → eventual compressão HTTP ou endpoint de “diff”; só se medir lentidão real.
5. **Pool SQLAlchemy** — já há `pool_size`/`max_overflow` para Postgres; em produção com dezenas de PCs, ajustar sob métrica, não “no escuro”.
6. **Alembic** — evita `create_all` cego quando o modelo mudar (adicione colunas com segurança).
7. **JWT mais curto + refresh** — hoje expire longo (12h); ok em LAN; em risco maior, reduzir TTL.
8. **Logs estruturados / request id** — facilita suporte da TI (“qual request falhou”).
9. **Health com checagem de DB** — `/api/health` valida o Postgres (`SELECT 1`) e responde **503** se o banco estiver fora; o desktop trata 5xx como “serviço indisponível” e evita tela em branco ao abrir módulos.
10. **SINAPI continua local no desktop** — correto; não colocar a base SINAPI na API (pesada). Otimizar o carregamento local (já em background) é o caminho.

Não priorize micro-otimizações de CPU na API enquanto o volume for poucas dezenas de usuários na LAN: estabilidade, backup e concorrência vêm primeiro.