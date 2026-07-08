"""Atualiza DATABASE_URL em api/.env para PostgreSQL (mantém as demais chaves)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / "api" / ".env"
PG_LINE = "DATABASE_URL=postgresql+psycopg2://orc:orc_dev@localhost:5432/orc"


def main() -> int:
    example = ROOT / ".env.example"
    if not ENV_PATH.is_file():
        ENV_PATH.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        print("api/.env criado a partir de .env.example")
        return 0

    texto = ENV_PATH.read_text(encoding="utf-8")
    linhas_out: list[str] = []
    tem_url = False
    mudou = False

    for linha in texto.splitlines(keepends=True):
        if linha.startswith("DATABASE_URL="):
            tem_url = True
            atual = linha.strip()
            if atual == PG_LINE:
                linhas_out.append(linha)
            else:
                nl = "\n" if linha.endswith("\n") else ""
                linhas_out.append(PG_LINE + nl)
                mudou = True
        else:
            linhas_out.append(linha)

    if not tem_url:
        linhas_out.insert(0, PG_LINE + "\n")
        mudou = True

    if mudou:
        ENV_PATH.write_text("".join(linhas_out), encoding="utf-8")
        print("DATABASE_URL atualizado para PostgreSQL em api/.env")
    else:
        print("api/.env já aponta para o PostgreSQL padrão — nenhuma alteração.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
