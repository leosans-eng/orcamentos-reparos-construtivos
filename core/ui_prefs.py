"""Preferências de interface do ORC (persistidas no perfil do usuário)."""

from __future__ import annotations

import json
from pathlib import Path

from app_paths import dados_usuario_dir

ORDENACAO_CRIADO = "criado_em"
ORDENACAO_ATUALIZADO = "atualizado_em"
ORDENACOES_LISTA_ORCAMENTOS = (ORDENACAO_CRIADO, ORDENACAO_ATUALIZADO)
COLUNAS_AREA_PRIVATIVA_PADRAO = (0.20, 0.20, 0.60)


def _normalizar_colunas_area_privativa(valor) -> list[float]:
    try:
        vals = [float(x) for x in valor]
    except (TypeError, ValueError):
        return list(COLUNAS_AREA_PRIVATIVA_PADRAO)
    if len(vals) != 3 or any(v <= 0 for v in vals):
        return list(COLUNAS_AREA_PRIVATIVA_PADRAO)
    total = sum(vals)
    if total <= 0:
        return list(COLUNAS_AREA_PRIVATIVA_PADRAO)
    return [round(v / total, 4) for v in vals]


def _prefs_padrao() -> dict:
    return {
        "legenda_grade_orcamento": True,
        "ordenacao_lista_orcamentos": ORDENACAO_CRIADO,
        "area_privativa_colunas": list(COLUNAS_AREA_PRIVATIVA_PADRAO),
        "tema_ui": "orc",
    }


def ui_prefs_path() -> Path:
    return dados_usuario_dir() / "orc_ui_prefs.json"


def carregar_ui_prefs() -> dict:
    caminho = ui_prefs_path()
    dados = _prefs_padrao()
    if not caminho.is_file():
        return dados
    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            bruto = json.load(arquivo)
    except (OSError, json.JSONDecodeError, TypeError):
        return dados
    if not isinstance(bruto, dict):
        return dados
    if "legenda_grade_orcamento" in bruto:
        dados["legenda_grade_orcamento"] = bool(bruto["legenda_grade_orcamento"])
    ordenacao = str(bruto.get("ordenacao_lista_orcamentos", ORDENACAO_CRIADO)).strip()
    if ordenacao in ORDENACOES_LISTA_ORCAMENTOS:
        dados["ordenacao_lista_orcamentos"] = ordenacao
    if "area_privativa_colunas" in bruto:
        dados["area_privativa_colunas"] = _normalizar_colunas_area_privativa(
            bruto["area_privativa_colunas"]
        )
    if "tema_ui" in bruto:
        tema = str(bruto.get("tema_ui") or "orc").strip()
        dados["tema_ui"] = tema or "orc"
    return dados


def salvar_ui_prefs(prefs: dict) -> None:
    atual = carregar_ui_prefs()
    if "legenda_grade_orcamento" in prefs:
        atual["legenda_grade_orcamento"] = bool(prefs["legenda_grade_orcamento"])
    if "ordenacao_lista_orcamentos" in prefs:
        ordenacao = str(prefs["ordenacao_lista_orcamentos"]).strip()
        if ordenacao in ORDENACOES_LISTA_ORCAMENTOS:
            atual["ordenacao_lista_orcamentos"] = ordenacao
    if "area_privativa_colunas" in prefs:
        atual["area_privativa_colunas"] = _normalizar_colunas_area_privativa(
            prefs["area_privativa_colunas"]
        )
    if "tema_ui" in prefs:
        tema = str(prefs.get("tema_ui") or "orc").strip()
        atual["tema_ui"] = tema or "orc"
    caminho = ui_prefs_path()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(atual, arquivo, ensure_ascii=False, indent=2)


def obter_pref(chave: str, padrao=None):
    prefs = carregar_ui_prefs()
    if chave in prefs:
        return prefs[chave]
    return _prefs_padrao().get(chave, padrao)


def definir_pref(chave: str, valor) -> None:
    salvar_ui_prefs({chave: valor})
