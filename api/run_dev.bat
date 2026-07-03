@echo off
REM Inicia a API ORC em modo desenvolvimento.
cd /d "%~dp0\.."
if not exist "api\.env" (
  copy ".env.example" "api\.env"
  echo Arquivo api\.env criado a partir de .env.example
)
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
