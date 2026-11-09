"""Caminhos do app em desenvolvimento e no executável PyInstaller."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def app_dir() -> Path:
    """Pasta do programa — dados graváveis (SINAPI, status) ficam aqui."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def bundle_dir() -> Path:
    """Recursos empacotados (JSON de vícios, ícone)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", app_dir()))
    return Path(__file__).resolve().parent


def icon_path() -> Path | None:
    for candidate in (
        bundle_dir() / "icone.ico",
        app_dir() / "icone.ico",
    ):
        if candidate.is_file():
            return candidate
    return None


def asset_path(*parts: str) -> Path | None:
    for base in (bundle_dir(), app_dir()):
        candidate = base.joinpath("assets", *parts)
        if candidate.is_file():
            return candidate
    return None


def sinapi_referencia_dir() -> Path:
    pasta = app_dir() / "sinapi" / "sinapi_referencia"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def env_path() -> Path:
    """Caminho preferencial do .env (instalação, ao lado do executável)."""
    for candidato in env_paths():
        if candidato.is_file():
            return candidato
    return app_dir() / ".env"


def env_paths() -> tuple[Path, ...]:
    """Locais onde o .env pode estar no desenvolvimento e no executável instalado."""
    vistos: list[Path] = []
    for candidato in (
        dados_usuario_dir() / ".env",
        app_dir() / ".env",
        bundle_dir() / ".env",
    ):
        if candidato not in vistos:
            vistos.append(candidato)
    return tuple(vistos)


_NOME_ANOMALIAS_AREA_PRIVATIVA = "anomalias_area_privativa.json"
_NOME_ANOMALIAS_AREA_PRIVATIVA_LEGADO = "vicios_construtivos.json"


def _migrar_anomalias_area_privativa_legado(destino: Path) -> None:
    """Renomeia o JSON antigo se a instalação ainda só tiver o nome legado."""
    if destino.is_file():
        return
    for base in (destino.parent, app_dir(), bundle_dir()):
        antigo = base / _NOME_ANOMALIAS_AREA_PRIVATIVA_LEGADO
        if not antigo.is_file() or antigo.resolve() == destino.resolve():
            continue
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            antigo.replace(destino)
            return
        except OSError:
            try:
                destino.write_bytes(antigo.read_bytes())
                return
            except OSError:
                continue


def anomalias_area_privativa_path_gravacao() -> Path:
    """
    Caminho gravável do catálogo de anomalias da área privativa.

    No executável usa a pasta empacotada (_internal), o mesmo arquivo que o
    instalador sobrescreve a cada atualização (ignoreversion). Em desenvolvimento
    usa a raiz do projeto.
    """
    if is_frozen():
        return bundle_dir() / _NOME_ANOMALIAS_AREA_PRIVATIVA
    return app_dir() / _NOME_ANOMALIAS_AREA_PRIVATIVA


def anomalias_area_privativa_path() -> Path:
    """Localiza o catálogo empacotado/atualizado; migra o nome legado se preciso."""
    destino = anomalias_area_privativa_path_gravacao()
    _migrar_anomalias_area_privativa_legado(destino)
    candidatos: list[Path] = [destino]
    if is_frozen():
        # Pacote primeiro (substituído na atualização); pasta do .exe só como legado.
        candidatos.extend(
            [
                bundle_dir() / _NOME_ANOMALIAS_AREA_PRIVATIVA,
                app_dir() / _NOME_ANOMALIAS_AREA_PRIVATIVA,
                bundle_dir() / _NOME_ANOMALIAS_AREA_PRIVATIVA_LEGADO,
                app_dir() / _NOME_ANOMALIAS_AREA_PRIVATIVA_LEGADO,
            ]
        )
    else:
        candidatos.extend(
            [
                app_dir() / _NOME_ANOMALIAS_AREA_PRIVATIVA,
                app_dir() / _NOME_ANOMALIAS_AREA_PRIVATIVA_LEGADO,
            ]
        )
    vistos: set[Path] = set()
    for candidate in candidatos:
        try:
            chave = candidate.resolve()
        except OSError:
            chave = candidate
        if chave in vistos:
            continue
        vistos.add(chave)
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"{_NOME_ANOMALIAS_AREA_PRIVATIVA} não encontrado. "
        f"Procurado em {bundle_dir()} e {app_dir()}."
    )


def vicios_construtivos_path() -> Path:
    """Compatibilidade: nome antigo do catálogo de área privativa."""
    return anomalias_area_privativa_path()


def vicios_construtivos_path_gravacao() -> Path:
    """Compatibilidade: gravação do catálogo de área privativa."""
    return anomalias_area_privativa_path_gravacao()


def anomalias_area_comum_path() -> Path:
    gravacao = app_dir() / "anomalias_area_comum.json"
    bundle = bundle_dir() / "anomalias_area_comum.json"
    for candidate in (gravacao, bundle):
        if candidate.is_file():
            return candidate
    return gravacao


def anomalias_area_comum_path_gravacao() -> Path:
    return app_dir() / "anomalias_area_comum.json"


def municipios_uf_path() -> Path | None:
    """JSON compacto município → UF (IBGE), empacotado com o aplicativo."""
    for candidate in (
        bundle_dir() / "dados" / "municipios_uf.json",
        app_dir() / "dados" / "municipios_uf.json",
    ):
        if candidate.is_file():
            return candidate
    return None


def dados_usuario_dir() -> Path:
    """
    Pasta de dados graváveis pelo usuário, fora do pacote de instalação.
    No executável usa %LOCALAPPDATA%\\ORC; em desenvolvimento usa dados_usuario/.
    """
    if is_frozen():
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        pasta = base / "ORC"
    else:
        pasta = app_dir() / "dados_usuario"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def orcamentos_customizados_path() -> Path:
    return dados_usuario_dir() / "orcamentos_customizados.json"


def composicoes_proprias_path() -> Path:
    return dados_usuario_dir() / "composicoes_proprias.json"


def etapas_predefinidas_path() -> Path:
    return dados_usuario_dir() / "etapas_predefinidas.json"


def area_comum_rascunhos_dir() -> Path:
    pasta = dados_usuario_dir() / "area_comum_rascunhos"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def area_comum_autosave_path() -> Path:
    return area_comum_rascunhos_dir() / "_autosave.json"
