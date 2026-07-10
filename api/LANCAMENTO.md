# Checklist de entrega — API ORC (servidor Windows)

## Subida padrão

1. Instalar/abrir **Docker Desktop**
2. `copy .env.example .env` — definir `SECRET_KEY` e `ADMIN_PASSWORD`
3. Executar **`run_dev.bat`**

## Segurança

- [ ] `SECRET_KEY` de produção (não o valor de exemplo)
- [ ] `ADMIN_PASSWORD` forte
- [ ] `.env` fora do Git
- [ ] Firewall Windows: porta **TCP 8000** (rede privada)

## Banco / seed

- [ ] Pasta `dados_usuario/` com os JSON no servidor (seed na 1ª subida)
- [ ] Backup `pg_dump` (Agendador de Tarefas) + teste de restore
- [ ] Após o seed, dados vivem no Postgres

## Rede

- [ ] Clientes usam o IPv4 da LAN do servidor (não localhost)
- [ ] Teste de outro PC: `http://IP:8000/api/health`
- [ ] Se falhar só na LAN: Firewall + checar se a porta 8000 está publicada no Docker Desktop

## Testes rápidos

- [ ] `/api/health` → ok
- [ ] Login admin; criar usuário
- [ ] Desktop ORC conecta em `http://IP:8000`
- [ ] Dois PCs editando: conflito 409 funciona
- [ ] `docker compose restart api` — dados permanecem

## Comandos úteis (Prompt / PowerShell)

| Ação | Comando |
|------|---------|
| Subir | `run_dev.bat` |
| Parar | `docker compose down` |
| Logs | `docker compose logs -f api` |
| Só API | `docker compose up -d api` |

### Backup

```bat
mkdir backups 2>nul
docker exec orc-postgres pg_dump -U orc -d orc -F c -f /tmp/orc.dump
docker cp orc-postgres:/tmp/orc.dump backups\orc_AAAAMMDD.dump
```
