@echo off
REM Producao — servidor Windows (Docker Desktop): sobe Postgres + API.
REM Equivalente: docker compose up -d --build
cd /d "%~dp0"

if not exist ".env" (
  copy ".env.example" ".env"
  echo Arquivo .env criado a partir de .env.example
  echo Edite SECRET_KEY e ADMIN_PASSWORD em .env antes de usar em producao.
  echo.
)

where docker >nul 2>&1
if errorlevel 1 (
  echo Docker nao encontrado no PATH.
  echo Instale e abra o Docker Desktop, depois execute este arquivo de novo.
  pause
  exit /b 1
)

docker compose up -d --build
if errorlevel 1 (
  echo.
  echo Falha ao subir os containers. Verifique se o Docker Desktop esta em execucao.
  pause
  exit /b 1
)

echo.
echo API:      http://localhost:8000/docs
echo Health:   http://localhost:8000/api/health
echo Rede:     http://IP_DO_SERVIDOR:8000
echo Logs:     docker compose logs -f api
echo Parar:    docker compose down
echo.
pause
