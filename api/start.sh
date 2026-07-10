#!/usr/bin/env bash
# Opcional: WSL ou shell bash no Windows.
# No servidor Windows o caminho padrão é run_dev.bat
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Arquivo .env criado a partir de .env.example — edite SECRET_KEY e ADMIN_PASSWORD."
fi

docker compose up -d --build
echo
echo "API:      http://localhost:8000/docs"
echo "Health:   http://localhost:8000/api/health"
echo "Logs:     docker compose logs -f api"
echo "Parar:    docker compose down"
