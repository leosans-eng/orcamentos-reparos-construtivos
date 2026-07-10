@echo off
REM Desenvolvimento (PC do Léo, sem Docker Desktop no Windows, com WSL):
REM   1) No WSL: docker compose up -d db   (e docker compose stop api, se a porta 8000 estiver ocupada)
REM   2) Aqui: sobe a API no Windows com --reload
REM Producao no servidor: run_dev.bat
cd /d "%~dp0"

if not exist ".env" (
  copy ".env.example" ".env"
  echo Arquivo .env criado a partir de .env.example
)

echo API Windows ^(uvicorn --reload^) + Postgres em localhost:5432 ^(WSL^)
echo Se falhar a conexao com o banco, no WSL rode: docker compose up -d db
echo.

set "PYTHON=%~dp0..\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

set PYTHONPATH=%~dp0..
REM %~dp0 termina com \ — nao usar como "--reload-dir \"%dp0%\"" (quebra as aspas).
"%PYTHON%" -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
