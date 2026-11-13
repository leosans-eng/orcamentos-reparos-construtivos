"""Configuração e sessão da API ORC (URL, token, credenciais salvas)."""

from __future__ import annotations

import base64
import ctypes
import json
import sys
from pathlib import Path

from app_paths import dados_usuario_dir

URL_PADRAO = "https://api-orc.indenizacaomcmv.com.br"


def api_config_path() -> Path:
    return dados_usuario_dir() / "orc_api.json"


def sessao_path() -> Path:
    return dados_usuario_dir() / "orc_sessao.json"


# A senha salva é protegida com o DPAPI do Windows: só o mesmo usuário do
# Windows, neste computador, consegue abrir. Arquivos antigos guardavam a
# senha só em base64 ("senha"); eles continuam sendo lidos e são convertidos
# no próximo login.
_PREFIXO_DPAPI = "dpapi:"


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(dados: bytes, *, proteger: bool) -> bytes:
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    buffer = ctypes.create_string_buffer(dados, len(dados))
    entrada = _DataBlob(len(dados), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    saida = _DataBlob()
    funcao = crypt32.CryptProtectData if proteger else crypt32.CryptUnprotectData
    # 0x1 = CRYPTPROTECT_UI_FORBIDDEN (nunca abrir janela do sistema).
    if not funcao(ctypes.byref(entrada), None, None, None, None, 0x1, ctypes.byref(saida)):
        raise OSError("DPAPI recusou os dados")
    try:
        return ctypes.string_at(saida.pbData, saida.cbData)
    finally:
        kernel32.LocalFree(saida.pbData)


def _codificar_senha(senha: str) -> str:
    dados = senha.encode("utf-8")
    if sys.platform == "win32":
        try:
            protegido = _dpapi(dados, proteger=True)
            return _PREFIXO_DPAPI + base64.b64encode(protegido).decode("ascii")
        except (OSError, AttributeError):
            pass
    return base64.b64encode(dados).decode("ascii")


def _decodificar_senha(valor: str) -> str:
    try:
        if valor.startswith(_PREFIXO_DPAPI):
            if sys.platform != "win32":
                return ""
            protegido = base64.b64decode(valor[len(_PREFIXO_DPAPI):].encode("ascii"))
            return _dpapi(protegido, proteger=False).decode("utf-8")
        return base64.b64decode(valor.encode("ascii")).decode("utf-8")
    except (ValueError, UnicodeError, OSError, AttributeError):
        return ""


def _ler_json(caminho: Path) -> dict | None:
    """Lê um JSON de configuração; arquivo ausente ou estragado vira None."""
    if not caminho.is_file():
        return None
    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (OSError, ValueError) as exc:
        print(f"[ORC] Ignorando {caminho.name} ilegível: {exc}")
        return None
    return dados if isinstance(dados, dict) else None


def carregar_config() -> dict:
    caminho = api_config_path()
    padrao = {
        "base_url": URL_PADRAO,
        "salvar_usuario": True,
        "salvar_senha": False,
        "usuario": "",
        "senha": "",
    }
    dados = _ler_json(caminho)
    if dados is None:
        return padrao
    base_url = str(dados.get("base_url", URL_PADRAO)).strip().rstrip("/")
    salvar_usuario = bool(dados.get("salvar_usuario", True))
    salvar_senha = bool(dados.get("salvar_senha", False))
    usuario = str(dados.get("usuario", "")).strip() if salvar_usuario else ""
    senha = ""
    if salvar_senha:
        senha = _decodificar_senha(str(dados.get("senha", "")))
    return {
        "base_url": base_url or URL_PADRAO,
        "salvar_usuario": salvar_usuario,
        "salvar_senha": salvar_senha and salvar_usuario,
        "usuario": usuario,
        "senha": senha,
    }


def salvar_config(
    base_url: str,
    *,
    salvar_usuario: bool = False,
    salvar_senha: bool = False,
    usuario: str = "",
    senha: str = "",
) -> None:
    caminho = api_config_path()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    base_url = str(base_url or "").strip().rstrip("/") or URL_PADRAO
    salvar_usuario = bool(salvar_usuario)
    salvar_senha = bool(salvar_senha) and salvar_usuario
    payload = {
        "base_url": base_url,
        "salvar_usuario": salvar_usuario,
        "salvar_senha": salvar_senha,
        "usuario": str(usuario or "").strip() if salvar_usuario else "",
        "senha": _codificar_senha(senha) if salvar_senha else "",
    }
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(payload, arquivo, ensure_ascii=False, indent=2)


def carregar_sessao() -> dict | None:
    dados = _ler_json(sessao_path())
    if dados is None:
        return None
    token = str(dados.get("access_token", "")).strip()
    username = str(dados.get("username", "")).strip()
    if not token:
        return None
    return {"access_token": token, "username": username}


def salvar_sessao(access_token: str, username: str) -> None:
    caminho = sessao_path()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(
            {"access_token": access_token, "username": username},
            arquivo,
            ensure_ascii=False,
            indent=2,
        )


def limpar_sessao() -> None:
    caminho = sessao_path()
    if caminho.is_file():
        caminho.unlink()
