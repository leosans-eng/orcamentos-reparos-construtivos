@echo off
REM Inicia a API ORC em modo desenvolvimento.
cd /d "%~dp0\.."

if not exist "api\.env" (
  copy ".env.example" "api\.env"
  echo Arquivo api\.env criado a partir de .env.example
)

set "PYTHON=%~dp0..\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

REM --reload-dir api evita reiniciar ao salvar JSON em dados_usuario/
REM Use 127.0.0.1 para dev local; pare instancias antigas se a porta 8000 travar.
"%PYTHON%" -m uvicorn api.main:app --reload --reload-dir api --host 127.0.0.1 --port 8000
