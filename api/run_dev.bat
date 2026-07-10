@echo off
REM Desenvolvimento Windows: Postgres no Docker + API no host com --reload.
REM No Linux/WSL/servidor prefira a stack completa:
REM   docker compose up -d --build
cd /d "%~dp0\.."

if not exist "api\.env" (
  copy ".env.example" "api\.env"
  echo Arquivo api\.env criado a partir de .env.example
)

where docker >nul 2>&1
if %ERRORLEVEL%==0 (
  echo Subindo apenas o Postgres ^(docker compose up -d db^)...
  docker compose up -d db
  if errorlevel 1 (
    echo AVISO: nao foi possivel subir o Postgres. Verifique o Docker.
  ) else (
    timeout /t 3 /nobreak >nul
  )
) else (
  echo AVISO: Docker nao encontrado no PATH do Windows.
  echo No WSL use: docker compose up -d --build
  echo Ou: docker compose up -d db   e depois este .bat com Postgres acessivel em localhost:5432
)

set "PYTHON=%~dp0..\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

REM --reload so para desenvolvimento no host Windows.
"%PYTHON%" -m uvicorn api.main:app --reload --reload-dir api --host 0.0.0.0 --port 8000
