# Mensagem para a TI (copiar e colar)

---

Olá,

Segue o repositório/backend do **ORC** (API + PostgreSQL). É só o necessário para subir o serviço no **servidor Windows** — não inclui o aplicativo desktop.

### Pré-requisito
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e em execução no servidor (com WSL2, se o instalador pedir)

### O que sobe
- **API** HTTP na porta **8000** (login, composições, etapas, orçamentos)
- **PostgreSQL** na porta **5432** (dados persistentes)

### Como subir (2 passos)
1. Copiar `.env.example` para `.env` e editar:
   - `SECRET_KEY` — chave longa e aleatória
   - `ADMIN_PASSWORD` — senha forte do admin
2. Na pasta do repositório, dar dois cliques em **`run_dev.bat`**  
   (ou no Prompt/PowerShell: `run_dev.bat` / `docker compose up -d --build`)

Conferir no servidor: `http://localhost:8000/api/health` e `http://localhost:8000/docs`  
Na rede: `http://IP_DO_SERVIDOR:8000`

### Login inicial
- Usuário: valor de `ADMIN_USERNAME` no `.env` (padrão `admin`)
- Senha: valor de `ADMIN_PASSWORD` no `.env`

Os PCs com o ORC instalado usam no login a URL: `http://IP_DO_SERVIDOR:8000`

### Dados iniciais
Na primeira execução com banco vazio, a API importa os JSON da pasta `dados_usuario/` (composições, etapas e orçamentos de referência). Depois disso, a fonte da verdade é o Postgres.

### Backup (importante)
No Prompt, na pasta do projeto (com o Docker no ar):
```bat
mkdir backups 2>nul
docker exec orc-postgres pg_dump -U orc -d orc -F c -f /tmp/orc.dump
docker cp orc-postgres:/tmp/orc.dump backups\orc_AAAAMMDD.dump
```
Sugestão: diário (Agendador de Tarefas), guardar cópia fora do servidor, testar restore uma vez.

### Firewall do Windows
Liberar na rede interna (perfil **Privado**) a porta **TCP 8000**.  
A 5432 só se precisarem acessar o banco de outro PC.

Se outros computadores não alcançarem o IP do servidor, verificar também se o Docker Desktop está com as portas publicadas e se o IP usado é o da placa de rede da LAN (não um IP do WSL).

### Parar / logs
```bat
docker compose down
docker compose logs -f api
```
(`down` não apaga o volume do banco.)

Dúvidas: ver `README.md` e `LANCAMENTO.md` no repositório.

Obrigado.

---
