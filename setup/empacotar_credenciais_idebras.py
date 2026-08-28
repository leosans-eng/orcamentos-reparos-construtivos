"""Gera dados/idebras.dat a partir do .env local (não vai para o git)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.idebras_client import URL_IDEBRAS_PADRAO, carregar_credenciais_idebras  # noqa: E402
from core.idebras_secrets import _NOME_ARQUIVO, cifrar_credenciais  # noqa: E402


def main() -> int:
    origem = ROOT / ".env"
    if not origem.is_file():
        print("ERRO: .env nao encontrado na raiz do projeto.")
        print("Crie o arquivo com user_idebras e password_idebras para gerar o instalador.")
        return 1

    credenciais = carregar_credenciais_idebras(origem)
    if not credenciais.get("usuario") or not credenciais.get("senha"):
        print("ERRO: user_idebras ou password_idebras ausentes no .env.")
        return 1

    destino = ROOT / "dados" / _NOME_ARQUIVO
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(cifrar_credenciais(credenciais))

    url = credenciais.get("url") or URL_IDEBRAS_PADRAO
    print(f"Credenciais do Idebras criptografadas ({url}).")
    print(f"Arquivo gerado: {destino.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
