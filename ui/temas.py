"""Temas visuais da interface do ORC (Padrão ORC, Sun Valley, Azure e Forest)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import tkinter as tk
from tkinter import ttk

from core.ui_prefs import definir_pref, obter_pref

TEMA_ORC = "orc"
TEMA_SV_CLARO = "sun-valley-light"
TEMA_SV_ESCURO = "sun-valley-dark"
TEMA_AZURE_CLARO = "azure-light"
TEMA_AZURE_ESCURO = "azure-dark"
TEMA_FOREST_CLARO = "forest-light"
TEMA_FOREST_ESCURO = "forest-dark"
PREF_TEMA = "tema_ui"

TEMAS_EXTERNOS = (
    TEMA_SV_CLARO,
    TEMA_SV_ESCURO,
    TEMA_AZURE_CLARO,
    TEMA_AZURE_ESCURO,
    TEMA_FOREST_CLARO,
    TEMA_FOREST_ESCURO,
)

ROTULOS_TEMA = {
    TEMA_ORC: "Padrão ORC",
    TEMA_SV_CLARO: "Sun Valley (claro)",
    TEMA_SV_ESCURO: "Sun Valley (escuro)",
    TEMA_AZURE_CLARO: "Azure (claro)",
    TEMA_AZURE_ESCURO: "Azure (escuro)",
    TEMA_FOREST_CLARO: "Forest (claro)",
    TEMA_FOREST_ESCURO: "Forest (escuro)",
}

_LISTENERS_TEMA: list = []


@dataclass(frozen=True)
class CoresTema:
    fundo: str
    fundo_destaque: str
    fundo_barra: str
    fundo_cartao: str
    fundo_cartao_off: str
    fundo_hover: str
    texto: str
    texto_suave: str
    titulo: str
    titulo_hover: str
    borda: str
    borda_hover: str
    borda_suave: str
    faixa: str
    perigo: str
    escuro: bool


CORES_ORC = CoresTema(
    fundo="#ececec",
    fundo_destaque="#e2eef3",
    fundo_barra="#ffffff",
    fundo_cartao="#ffffff",
    fundo_cartao_off="#f0f0f0",
    fundo_hover="#f5fafc",
    texto="#444444",
    texto_suave="#555555",
    titulo="#006699",
    titulo_hover="#004466",
    borda="#006699",
    borda_hover="#004466",
    borda_suave="#c5d6de",
    faixa="#006699",
    perigo="#c62828",
    escuro=False,
)


def rotulo_tema(tema_id: str) -> str:
    chave = str(tema_id or TEMA_ORC)
    return ROTULOS_TEMA.get(chave, chave)


def _tema_conhecido(tema_id: str) -> bool:
    chave = str(tema_id or "").strip()
    return chave == TEMA_ORC or chave in TEMAS_EXTERNOS


def tema_usa_imagens(tema_id: str | None = None) -> bool:
    """True quando o tema desenha botões com imagem e ignora as cores ttk do ORC."""
    chave = str(tema_id or tema_salvo() or TEMA_ORC).strip()
    return chave in TEMAS_EXTERNOS


def tema_salvo() -> str:
    valor = str(obter_pref(PREF_TEMA, TEMA_ORC) or TEMA_ORC).strip()
    if not valor:
        return TEMA_ORC
    if not _tema_conhecido(valor):
        salvar_tema(TEMA_ORC)
        return TEMA_ORC
    return valor


def salvar_tema(tema_id: str) -> None:
    definir_pref(PREF_TEMA, str(tema_id or TEMA_ORC).strip() or TEMA_ORC)


def registrar_listener_tema(callback) -> None:
    if callback not in _LISTENERS_TEMA:
        _LISTENERS_TEMA.append(callback)


def limpar_listeners_tema() -> None:
    _LISTENERS_TEMA.clear()


def _obter_style(root):
    estilo = getattr(root, "_orc_style", None)
    if estilo is not None:
        return estilo
    estilo = ttk.Style(root)
    root._orc_style = estilo
    return estilo


def _sv_disponivel() -> bool:
    try:
        import sv_ttk  # noqa: F401

        return True
    except ImportError:
        return False


def _arquivo_tema(*parts: str) -> Path | None:
    from app_paths import app_dir, bundle_dir

    for base in (bundle_dir(), app_dir()):
        candidato = base.joinpath("assets", "temas", *parts)
        if candidato.is_file():
            return candidato
    return None


def _azure_disponivel() -> bool:
    return _arquivo_tema("azure", "azure.tcl") is not None


def _forest_disponivel() -> bool:
    return (
        _arquivo_tema("forest", "forest-light.tcl") is not None
        and _arquivo_tema("forest", "forest-dark.tcl") is not None
    )


def _externo_disponivel(tema_id: str) -> bool:
    if tema_id in (TEMA_SV_CLARO, TEMA_SV_ESCURO):
        return _sv_disponivel()
    if tema_id in (TEMA_AZURE_CLARO, TEMA_AZURE_ESCURO):
        return _azure_disponivel()
    if tema_id in (TEMA_FOREST_CLARO, TEMA_FOREST_ESCURO):
        return _forest_disponivel()
    return False


def ids_temas_disponiveis(root) -> list[str]:
    """Padrão ORC + temas MIT (Sun Valley, Azure, Forest) quando os arquivos existem."""
    ids = [TEMA_ORC]
    for extra in TEMAS_EXTERNOS:
        if _externo_disponivel(extra):
            ids.append(extra)
    return ids


def opcoes_tema(root) -> list[tuple[str, str]]:
    """Lista (id, rótulo) para o combobox de Configurações."""
    return [(tema_id, rotulo_tema(tema_id)) for tema_id in ids_temas_disponiveis(root)]


def _usar_tema_nativo(estilo) -> None:
    for nome in ("vista", "xpnative", "winnative", "clam", "default"):
        try:
            estilo.theme_use(nome)
            return
        except tk.TclError:
            continue


def _carregar_azure(root) -> None:
    if getattr(root, "_orc_azure_carregado", False):
        return
    caminho = _arquivo_tema("azure", "azure.tcl")
    if caminho is None:
        raise FileNotFoundError("Tema Azure não encontrado em assets/temas/azure.")
    root.tk.call("source", str(caminho.resolve()).replace("\\", "/"))
    root._orc_azure_carregado = True


def _carregar_forest(root) -> None:
    if getattr(root, "_orc_forest_carregado", False):
        return
    claro = _arquivo_tema("forest", "forest-light.tcl")
    escuro = _arquivo_tema("forest", "forest-dark.tcl")
    if claro is None or escuro is None:
        raise FileNotFoundError("Tema Forest não encontrado em assets/temas/forest.")
    root.tk.call("source", str(claro.resolve()).replace("\\", "/"))
    root.tk.call("source", str(escuro.resolve()).replace("\\", "/"))
    root._orc_forest_carregado = True


def _aplicar_engine(root, escolhido: str) -> str:
    if escolhido in (TEMA_SV_CLARO, TEMA_SV_ESCURO):
        import sv_ttk

        sv_ttk.set_theme(
            "dark" if escolhido == TEMA_SV_ESCURO else "light",
            root,
        )
        try:
            root.tk.call("configure_colors")
        except tk.TclError:
            pass
        return escolhido
    if escolhido in (TEMA_AZURE_CLARO, TEMA_AZURE_ESCURO):
        _carregar_azure(root)
        root.tk.call(
            "set_theme", "dark" if escolhido == TEMA_AZURE_ESCURO else "light"
        )
        return escolhido
    if escolhido in (TEMA_FOREST_CLARO, TEMA_FOREST_ESCURO):
        _carregar_forest(root)
        ttk.Style(root).theme_use(escolhido)
        return escolhido
    estilo = _obter_style(root)
    _usar_tema_nativo(estilo)
    return TEMA_ORC


def _hex_para_rgb(cor: str) -> tuple[int, int, int]:
    texto = str(cor or "").strip().lstrip("#")
    if len(texto) == 3:
        texto = "".join(ch * 2 for ch in texto)
    if len(texto) != 6:
        raise ValueError(cor)
    return int(texto[0:2], 16), int(texto[2:4], 16), int(texto[4:6], 16)


def _rgb_para_hex(rgb: tuple[int, int, int]) -> str:
    r, g, b = (max(0, min(255, int(c))) for c in rgb)
    return f"#{r:02x}{g:02x}{b:02x}"


def _misturar(cor_a: str, cor_b: str, fator: float) -> str:
    ra, ga, ba = _hex_para_rgb(cor_a)
    rb, gb, bb = _hex_para_rgb(cor_b)
    return _rgb_para_hex(
        (
            ra + (rb - ra) * fator,
            ga + (gb - ga) * fator,
            ba + (bb - ba) * fator,
        )
    )


def _luminancia(cor: str) -> float:
    r, g, b = (c / 255.0 for c in _hex_para_rgb(cor))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def texto_contraste(fundo: str) -> str:
    """Texto legível sobre `fundo` (escuro em fundo claro, claro em fundo escuro)."""
    return "#1c1c1c" if _luminancia(fundo) > 0.62 else "#ffffff"


def _normalizar_cor(root, valor, padrao: str) -> str:
    if not valor:
        return padrao
    texto = str(valor).strip()
    if texto.startswith("#"):
        try:
            _hex_para_rgb(texto)
            return texto.lower()
        except ValueError:
            return padrao
    try:
        r, g, b = root.winfo_rgb(texto)
        return _rgb_para_hex((r >> 8, g >> 8, b >> 8))
    except tk.TclError:
        return padrao


def _lookup_cor(root, style, specs, padrao: str) -> str:
    for widget, opcao in specs:
        try:
            valor = style.lookup(widget, opcao)
        except tk.TclError:
            continue
        cor = _normalizar_cor(root, valor, "")
        if cor:
            return cor
    return padrao


def _paleta_conhecida(tema_id: str) -> CoresTema | None:
    if tema_id == TEMA_ORC:
        return CORES_ORC
    if tema_id == TEMA_SV_CLARO:
        return _paleta_de_base(
            fundo="#fafafa",
            texto="#1c1c1c",
            accent="#005fb8",
            escuro=False,
        )
    if tema_id == TEMA_SV_ESCURO:
        return _paleta_de_base(
            fundo="#1c1c1c",
            texto="#fafafa",
            accent="#57c8ff",
            escuro=True,
        )
    if tema_id == TEMA_AZURE_CLARO:
        return _paleta_de_base(
            fundo="#ffffff",
            texto="#000000",
            accent="#007fff",
            escuro=False,
        )
    if tema_id == TEMA_AZURE_ESCURO:
        return _paleta_de_base(
            fundo="#333333",
            texto="#ffffff",
            accent="#007fff",
            escuro=True,
        )
    if tema_id == TEMA_FOREST_CLARO:
        return _paleta_de_base(
            fundo="#ffffff",
            texto="#313131",
            accent="#217346",
            escuro=False,
        )
    if tema_id == TEMA_FOREST_ESCURO:
        return _paleta_de_base(
            fundo="#313131",
            texto="#eeeeee",
            accent="#217346",
            escuro=True,
        )
    return None


def _paleta_de_base(*, fundo: str, texto: str, accent: str, escuro: bool) -> CoresTema:
    if escuro:
        titulo = (
            _misturar(accent, "#ffffff", 0.35)
            if _luminancia(accent) < 0.55
            else accent
        )
        titulo_hover = _misturar(titulo, "#ffffff", 0.2)
        fundo_cartao = _misturar(fundo, "#ffffff", 0.08)
        fundo_cartao_off = _misturar(fundo, "#000000", 0.12)
        fundo_hover = _misturar(fundo, "#ffffff", 0.14)
        fundo_destaque = _misturar(fundo, titulo, 0.18)
        fundo_barra = fundo_destaque
        texto_suave = _misturar(texto, fundo, 0.35)
        borda_suave = _misturar(fundo, "#ffffff", 0.18)
        perigo = "#ef9a9a"
    else:
        titulo = accent
        titulo_hover = _misturar(titulo, "#000000", 0.2)
        fundo_cartao = (
            "#ffffff" if _luminancia(fundo) > 0.85 else _misturar(fundo, "#ffffff", 0.7)
        )
        fundo_cartao_off = _misturar(fundo, "#000000", 0.06)
        fundo_hover = _misturar(fundo_cartao, titulo, 0.08)
        fundo_destaque = _misturar(fundo, titulo, 0.12)
        fundo_barra = fundo_cartao
        texto_suave = _misturar(texto, fundo, 0.35)
        borda_suave = _misturar(fundo, titulo, 0.25)
        perigo = CORES_ORC.perigo
    return CoresTema(
        fundo=fundo,
        fundo_destaque=fundo_destaque,
        fundo_barra=fundo_barra,
        fundo_cartao=fundo_cartao,
        fundo_cartao_off=fundo_cartao_off,
        fundo_hover=fundo_hover,
        texto=texto,
        texto_suave=texto_suave,
        titulo=titulo,
        titulo_hover=titulo_hover,
        borda=titulo,
        borda_hover=titulo_hover,
        borda_suave=borda_suave,
        faixa=titulo,
        perigo=perigo,
        escuro=escuro,
    )


def cores_tema(widget, tema_id: str | None = None) -> CoresTema:
    """Paleta para widgets clássicos (Hub, rodapé) conforme o tema ttk atual."""
    root = widget.nametowidget(".") if hasattr(widget, "nametowidget") else widget
    escolhido = str(
        tema_id
        or getattr(root, "_orc_tema_atual", None)
        or tema_salvo()
        or TEMA_ORC
    ).strip()
    conhecida = _paleta_conhecida(escolhido)
    if conhecida is not None:
        return conhecida

    style = ttk.Style(root)
    fundo = _lookup_cor(
        root,
        style,
        (("TFrame", "background"), (".", "background"), ("TLabel", "background")),
        CORES_ORC.fundo,
    )
    texto = _lookup_cor(
        root,
        style,
        (("TLabel", "foreground"), (".", "foreground")),
        CORES_ORC.texto,
    )
    accent = _lookup_cor(
        root,
        style,
        (
            (".", "selectbackground"),
            (".", "focuscolor"),
            ("TButton", "background"),
        ),
        CORES_ORC.titulo,
    )
    escuro = _luminancia(fundo) < 0.45
    return _paleta_de_base(fundo=fundo, texto=texto, accent=accent, escuro=escuro)


@dataclass(frozen=True)
class EstilosBotao:
    adicionar: str
    excluir: str
    editar: str
    salvar: str
    compacto: str
    compacto_adicionar: str
    compacto_excluir: str
    compacto_editar: str
    icone: str
    icone_adicionar: str
    icone_excluir: str
    icone_editar: str
    icone_salvar: str


def estilos_botao(widget, tema_id: str | None = None) -> EstilosBotao:
    """Estilos ttk + cor do ícone conforme o tema (pixmap usa a cor no SVG)."""
    root = widget.nametowidget(".") if hasattr(widget, "nametowidget") else widget
    escolhido = str(
        tema_id
        or getattr(root, "_orc_tema_atual", None)
        or tema_salvo()
        or TEMA_ORC
    ).strip()
    cores = cores_tema(root, escolhido)
    if tema_usa_imagens(escolhido):
        verde = "#81c784" if cores.escuro else "#2e7d32"
        return EstilosBotao(
            adicionar="Add.TButton",
            excluir="Delete.TButton",
            editar="Edit.TButton",
            salvar="Save.TButton",
            compacto="Compact.TButton",
            compacto_adicionar="Add.Compact.TButton",
            compacto_excluir="Delete.Compact.TButton",
            compacto_editar="Edit.Compact.TButton",
            icone=cores.titulo,
            icone_adicionar=verde,
            icone_excluir=cores.perigo,
            icone_editar=cores.titulo,
            icone_salvar=verde,
        )
    preto = "#000000"
    return EstilosBotao(
        adicionar="Add.TButton",
        excluir="Delete.TButton",
        editar="Edit.TButton",
        salvar="Save.TButton",
        compacto="Compact.TButton",
        compacto_adicionar="Add.Compact.TButton",
        compacto_excluir="Delete.Compact.TButton",
        compacto_editar="Edit.Compact.TButton",
        icone=preto,
        icone_adicionar=preto,
        icone_excluir=preto,
        icone_editar=preto,
        icone_salvar=preto,
    )


@dataclass(frozen=True)
class CoresGrade:
    fundo: str
    cabecalho: str
    grupo: str
    grupo_selecao: str
    texto_grupo_selecao: str
    item_selecao: str
    borda: str
    composicao: str
    alerta_depreciado: str
    estado_alternativo: str
    discriminar: str
    texto: str
    texto_cabecalho: str
    marcador: str
    zebra: str
    vazio: str
    banner: str
    banner_texto: str
    banner_borda: str


def cores_grade(widget, tema_id: str | None = None) -> CoresGrade:
    """Cores da grade orçamentária; no claro mantém a paleta semântica do ORC."""
    cores = cores_tema(widget, tema_id)
    if cores.escuro:
        grupo_sel = _misturar(cores.titulo, "#ffffff", 0.12)
        return CoresGrade(
            fundo=cores.fundo_cartao,
            cabecalho=_misturar(cores.fundo, cores.titulo, 0.22),
            grupo=_misturar(cores.titulo, cores.fundo, 0.4),
            grupo_selecao=grupo_sel,
            texto_grupo_selecao=texto_contraste(grupo_sel),
            item_selecao=_misturar(cores.fundo_cartao, "#ffffff", 0.16),
            borda=cores.borda_suave,
            composicao="#f0c14a",
            alerta_depreciado=_misturar(cores.fundo_cartao, "#c9a227", 0.42),
            estado_alternativo=_misturar(cores.fundo_cartao, cores.titulo, 0.32),
            discriminar=_misturar(cores.fundo_cartao, "#66bb6a", 0.28),
            texto=cores.texto,
            texto_cabecalho=cores.texto,
            marcador=cores.titulo,
            zebra=_misturar(cores.fundo_cartao, "#ffffff", 0.05),
            vazio=cores.texto_suave,
            banner=_misturar(cores.fundo_cartao, "#c9a227", 0.38),
            banner_texto="#ffe082",
            banner_borda="#c9a227",
        )
    return CoresGrade(
        fundo="#ffffff",
        cabecalho="#e0e8ec",
        grupo="#8eccef",
        grupo_selecao="#3d8ec4",
        texto_grupo_selecao="#ffffff",
        item_selecao="#d2d6da",
        borda=cores.borda_suave or "#cccccc",
        composicao="#7b5e00",
        alerta_depreciado="#fff8e1",
        estado_alternativo="#e8f4fc",
        discriminar="#e4f0e6",
        texto=cores.texto,
        texto_cabecalho=cores.texto,
        marcador=cores.titulo,
        zebra="#f7f9fa",
        vazio=cores.texto_suave,
        banner="#fff3cd",
        banner_texto="#7a5b00",
        banner_borda="#e0c36a",
    )


def aplicar_paleta_tk(root, cores: CoresTema) -> None:
    """Restaura cores clássicas do Tk (Label, LabelFrame, tooltip).

    Temas escuros (Sun Valley, Azure…) alteram a paleta global; sem isto, ao
    voltar para um tema claro os textos de widgets tk ficam brancos.
    """
    try:
        root.tk_setPalette(
            background=cores.fundo,
            foreground=cores.texto,
            activeBackground=cores.fundo_hover,
            activeForeground=cores.texto,
            highlightBackground=cores.fundo,
            highlightColor=cores.titulo,
            selectBackground=cores.titulo,
            selectForeground=texto_contraste(cores.titulo),
            insertBackground=cores.texto,
        )
    except tk.TclError:
        pass


def aplicar_chrome_dialogo(janela) -> tuple[CoresTema, EstilosBotao]:
    """Fundo do Toplevel + estilos de botão do tema atual."""
    cores = cores_tema(janela)
    estilos = estilos_botao(janela)
    try:
        janela.configure(bg=cores.fundo)
    except tk.TclError:
        pass
    janela._cores = cores
    janela._estilos = estilos
    return cores, estilos


def aplicar_tema(root, tema_id: str | None = None) -> str:
    """Aplica o tema ttk na janela raiz e reconfigura os estilos do ORC."""
    from ui.widgets import configurar_estilos_ttk

    escolhido = str(tema_id if tema_id is not None else tema_salvo() or TEMA_ORC).strip()
    if not escolhido or not _tema_conhecido(escolhido):
        escolhido = TEMA_ORC

    aplicado = TEMA_ORC
    try:
        aplicado = _aplicar_engine(root, escolhido)
    except (tk.TclError, RuntimeError, ValueError, FileNotFoundError, ImportError):
        estilo = _obter_style(root)
        _usar_tema_nativo(estilo)
        aplicado = TEMA_ORC

    configurar_estilos_ttk(root, forcar=True, tema_id=aplicado)
    root._orc_tema_atual = aplicado
    try:
        cores = cores_tema(root, aplicado)
        root.configure(bg=cores.fundo)
        aplicar_paleta_tk(root, cores)
    except tk.TclError:
        pass
    for callback in list(_LISTENERS_TEMA):
        try:
            callback(aplicado)
        except Exception:
            pass
    return aplicado
