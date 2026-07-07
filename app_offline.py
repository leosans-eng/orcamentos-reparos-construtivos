"""
ORC em modo offline — dados em JSON local, sem login nem API.

Uso: python app_offline.py

Lê e grava em dados_usuario/:
  - orcamentos_customizados.json
  - composicoes_proprias.json
  - etapas_predefinidas.json
"""

from core.offline_bootstrap import ativar_modo_offline

ativar_modo_offline()

from core.precarga_catalogos import iniciar_precarga_catalogos  # noqa: E402
from app import OrcApp  # noqa: E402


if __name__ == "__main__":
    iniciar_precarga_catalogos()
    app = OrcApp(offline=True)
    app.janela.title("ORC — modo offline (testes)")
    app.executar()
