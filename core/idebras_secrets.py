"""Criptografia das credenciais do Idebras para o executável.

Isso impede leitura casual da pasta do programa (bloco de notas em um .env).
A chave viaja junto com o aplicativo; não impede engenharia reversa do .exe.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

from app_paths import app_dir, bundle_dir, is_frozen

_NOME_ARQUIVO = "idebras.dat"
_ITERACOES = 210_000
_SALT = b"ORC\x1didebras\x1fv1\x00"


def caminho_credenciais_empacotadas() -> Path | None:
    for base in (bundle_dir(), app_dir()):
        candidato = base / "dados" / _NOME_ARQUIVO
        if candidato.is_file():
            return candidato
    return None


def _fernet() -> Fernet:
    material = (
        os.environ.get("ORC_IDEBRAS_WRAP")
        or "orc|area-privativa|idebras|nao-usar-em-texto-puro"
    ).encode("utf-8")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=_ITERACOES,
    )
    chave = base64.urlsafe_b64encode(kdf.derive(material))
    return Fernet(chave)


def cifrar_credenciais(dados: dict[str, str]) -> bytes:
    payload = json.dumps(
        {
            "url": str(dados.get("url") or "").strip(),
            "usuario": str(dados.get("usuario") or "").strip(),
            "senha": str(dados.get("senha") or ""),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return _fernet().encrypt(payload)


def decifrar_credenciais(bloco: bytes) -> dict[str, str]:
    try:
        bruto = _fernet().decrypt(bloco)
        dados = json.loads(bruto.decode("utf-8"))
    except (InvalidToken, ValueError, UnicodeError, json.JSONDecodeError):
        return {"url": "", "usuario": "", "senha": ""}
    if not isinstance(dados, dict):
        return {"url": "", "usuario": "", "senha": ""}
    return {
        "url": str(dados.get("url") or "").strip(),
        "usuario": str(dados.get("usuario") or "").strip(),
        "senha": str(dados.get("senha") or ""),
    }


def carregar_credenciais_empacotadas() -> dict[str, str] | None:
    caminho = caminho_credenciais_empacotadas()
    if caminho is None:
        return None
    try:
        bloco = caminho.read_bytes()
    except OSError:
        return None
    if not bloco:
        return None
    dados = decifrar_credenciais(bloco)
    if not dados.get("usuario") and not dados.get("senha"):
        return None
    return dados


def usar_apenas_credenciais_empacotadas() -> bool:
    """No .exe instalado não se lê .env em texto puro na pasta do programa."""
    return is_frozen()
