@echo off
REM Atualiza DATABASE_URL em api\.env para PostgreSQL (mantem o restante do arquivo).
cd /d "%~dp0\.."

if not exist "api\.env" (
  copy ".env.example" "api\.env"
  echo api\.env criado a partir de .env.example
  goto :prox
)

set "PYTHON=%~dp0..\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

"%PYTHON%" -m api.switch_env_postgres
if errorlevel 1 (
  echo Falha ao atualizar api\.env
  pause
  exit /b 1
)

:prox
echo.
echo Proximo passo:
echo   1. Instale Docker Desktop se ainda nao tiver
echo   2. docker compose up -d
echo   3. ^(opcional^) migrar dados do SQLite:
echo        .venv\Scripts\python.exe -m api.migrate_sqlite_to_postgres
echo   4. api\run_dev.bat
pause
