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
REM --host 0.0.0.0 permite acesso pela rede (colegas usam http://SEU_IPV4:8000)
REM Se a porta 8000 travar, encerre processos uvicorn antigos antes de subir de novo.
"%PYTHON%" -m uvicorn api.main:app --reload --reload-dir api --host 0.0.0.0 --port 8000
