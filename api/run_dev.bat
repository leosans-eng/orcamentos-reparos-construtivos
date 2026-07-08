@echo off
REM Inicia a API ORC em modo desenvolvimento (PostgreSQL via Docker Compose).
cd /d "%~dp0\.."

if not exist "api\.env" (
  copy ".env.example" "api\.env"
  echo Arquivo api\.env criado a partir de .env.example
)

REM Sobe o Postgres se o Docker estiver disponivel.
where docker >nul 2>&1
if %ERRORLEVEL%==0 (
  echo Verificando container PostgreSQL...
  docker compose up -d
  if errorlevel 1 (
    echo.
    echo AVISO: nao foi possivel subir o Postgres com Docker Compose.
    echo Instale o Docker Desktop ou aponte DATABASE_URL em api\.env para um Postgres ja existente.
    echo.
  ) else (
    echo Aguardando Postgres ficar pronto...
    timeout /t 3 /nobreak >nul
  )
) else (
  echo.
  echo AVISO: Docker nao encontrado no PATH.
  echo A API espera PostgreSQL em DATABASE_URL ^(api\.env^).
  echo Instale Docker Desktop e rode: docker compose up -d
  echo Ou use um Postgres local com a mesma URL do .env.example.
  echo.
)

set "PYTHON=%~dp0..\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

REM --reload-dir api evita reiniciar ao salvar JSON em dados_usuario/
REM --host 0.0.0.0 permite acesso pela rede (colegas usam http://SEU_IPV4:8000)
"%PYTHON%" -m uvicorn api.main:app --reload --reload-dir api --host 0.0.0.0 --port 8000
