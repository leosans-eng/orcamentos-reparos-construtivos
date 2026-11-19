"""Aba 1 da Área Comum: estruturas do condomínio e dados de todo o condomínio.

Cada estrutura (ex.: "Bloco padrão × 15", "Salão de festas × 1") tem as
próprias medidas, percentuais, esquadrias e planta, organizadas em partes
recolhíveis (Prédio, Cobertura, Fachada, Hall). Caixas, calçadas e
observações valem para o condomínio inteiro. À direita ficam o ORCCAD, a
planta e a visão isométrica da estrutura que está na tela.

A aba não calcula nem salva sozinha: o módulo (AreaComumFrame) pede os dados
com coletar_em() e devolve com aplicar(); os campos avisam o módulo a cada
alteração (_ao_alterar_campo), como os demais campos da tela.
"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk

from core.area_comum import (
    CHAVES_MEDIDA_CONDOMINIO,
    CHAVES_MEDIDA_ESTRUTURA,
    CHAVES_MEDIDA_SO_RESIDENCIAL,
    CHAVES_PCT_CONDOMINIO,
    CHAVES_PCT_ESTRUTURA,
    ESQUADRIAS_MODELO,
    LOCAL_CONDOMINIO,
    LOCAL_RESIDENCIAL,
    PERCENTUAIS_MODELO,
    TIPO_OUTRA,
    TIPO_RESIDENCIAL,
    TIPOS_COBERTURA,
    TIPOS_ESTRUTURA,
    blocos_residenciais,
    esquadrias_da_estrutura,
    nova_estrutura,
    normalizar_estrutura,
    quantitativos_da_estrutura,
    quantitativos_do_condominio,
)
from core.area_comum_calculos import numero
from core.desenho_geometria import dict_para_camadas, resultado_desenho
from ui.desenho_2d import CHAVES_MEDIDA_ORCCAD, PreviaDesenho2D, VistaIsometricaBloco
from ui.icones import criar_botao_ttk_com_icone, criar_icone_svg
from ui.temas import _misturar, aplicar_chrome_dialogo
from ui.widgets import (
    PLACEHOLDER_ESTADO,
    aplicar_icone_janela,
    centralizar_janela,
    criar_botao_cancelar,
    estado_do_combo,
    focar_entrada_apos_exibir,
    formatar_decimal_br,
    preparar_toplevel,
    vincular_tooltip,
)

DICA_ORCCAD = "Quantitativo carregado a partir do desenho no ORCCAD"

FONTE = ("Segoe UI", 9)
FONTE_NEGRITO = ("Segoe UI", 9, "bold")
FONTE_PEQUENA = ("Segoe UI", 8)
FONTE_TITULO = ("Arial", 10, "bold")
FONTE_ESTRUTURA = ("Arial", 12, "bold")

# Espaços fixos (px): unidade e total ficam colados ao campo.
ESPACO_ROTULO = 14
ESPACO_UNIDADE = 4
LARGURA_UNIDADE = 24
ESPACO_TOTAL = 12
ESPACO_COLUNAS = 36
PAD_CARTAO = 14
LARGURA_DESENHO = 360


def _n(valor, casas=2) -> str:
    try:
        v = float(valor or 0)
    except (TypeError, ValueError):
        return "—"
    return "—" if v == 0 else formatar_decimal_br(v, casas)


def _total(q, chave, unidade="") -> str:
    texto = _n(q.get(chave), 2 if unidade else 0)
    if texto == "—":
        return ""
    return f"{texto} {unidade} no total" if unidade else f"{texto} no total"


def _parcial_e_total(q, chave_parcial, por, chave_total, unidade) -> str:
    parcial, total = _n(q.get(chave_parcial)), _n(q.get(chave_total))
    if total == "—":
        return ""
    return f"{parcial} {unidade} {por} · {total} {unidade} no total"


def _aptos(q) -> str:
    if not q.get("qtd_aptos_total"):
        return ""
    return (
        f"{_n(q.get('qtd_aptos_por_bloco'), 0)} por bloco · "
        f"{_n(q.get('qtd_aptos_total'), 0)} no total"
    )


# Partes de cada estrutura.  medida: (chave, rótulo, unidade, total)
PARTES_ESTRUTURA = (
    {
        "id": "predio",
        "titulo": "Prédio",
        "iso": "pavimentos",
        "combo": ("tipo_estrutura", "Tipo de estrutura", TIPOS_ESTRUTURA),
        "medidas": (
            ("qtd_pavimentos", "Pavimentos", "", None),
            ("qtd_aptos_por_pavimento", "Apartamentos por pavimento", "", _aptos),
            ("pe_direito_m", "Pé-direito", "m", None),
        ),
    },
    {
        "id": "cobertura",
        "titulo": "Cobertura",
        "iso": "cobertura",
        "combo": ("tipo_cobertura", "Tipo de cobertura", TIPOS_COBERTURA),
        "medidas": (
            ("qtd_aguas_telhado", "Águas do telhado", "", None),
            ("area_construida_m2", "Área da cobertura", "m²",
             lambda q: _total(q, "area_cobertura_total_m2", "m²")),
            ("perimetro_beiral_m", "Perímetro de beiral / calha", "m", None),
            ("perimetro_platibanda_bloco_m", "Perímetro da platibanda", "m",
             lambda q: _total(q, "perimetro_platibanda_total_m", "m")),
            ("altura_platibanda_m", "Altura da platibanda", "m", None),
        ),
        "percentuais": ("troca_estrutura_cobertura", "troca_telhas_cobertura",
                        "instalacao_tabeira_beiral", "troca_rufos_pingadeira"),
    },
    {
        "id": "fachada",
        "titulo": "Fachada",
        "iso": "paredes",
        "medidas": (
            ("perimetro_paredes_externas_bloco_m", "Perímetro de paredes externas", "m",
             lambda q: _total(q, "perimetro_paredes_externas_total_m", "m")),
        ),
        "esquadrias": True,
        "resultados": (
            ("Fachada sem esquadrias",
             lambda q: _parcial_e_total(q, "area_fachada_bloco_m2", "por bloco",
                                        "area_fachada_total_m2", "m²")),
            ("Esquadrias",
             lambda q: _parcial_e_total(q, "esquadria_area_pav_m2", "por pavimento",
                                        "esquadria_area_total_m2", "m²")),
            ("Pingadeira", lambda q: _total(q, "pingadeira_total_m", "m")),
            ("Janelas", lambda q: _total(q, "esquadria_qtd_janelas_total")),
        ),
        "percentuais": ("troca_revestimento_fachada", "pintura_fachada"),
        "selador": True,
    },
    {
        "id": "hall",
        "titulo": "Hall",
        "iso": None,
        "so_residencial": True,
        "medidas": (
            ("perimetro_hall_parede_pav_m", "Perímetro de parede (um pavimento)", "m",
             lambda q: _total(q, "perimetro_hall_parede_total_m", "m")),
            ("perimetro_hall_rodape_pav_m", "Perímetro de rodapé (um pavimento)", "m",
             lambda q: _total(q, "perimetro_hall_rodape_total_m", "m")),
            ("area_laje_hall_pav_m2", "Área da laje (um pavimento)", "m²",
             lambda q: _total(q, "area_laje_hall_total_m2", "m²")),
            ("area_piso_hall_pav_m2", "Área de piso (um pavimento)", "m²",
             lambda q: _total(q, "area_piso_hall_total_m2", "m²")),
        ),
        "resultados": (
            ("Paredes internas", lambda q: _total(q, "area_alvenaria_hall_total_m2", "m²")),
        ),
        "percentuais": ("troca_revestimento_paredes_hall", "troca_revestimento_tetos_hall",
                        "troca_pisos_hall", "troca_rodape_hall",
                        "pintura_paredes_hall", "pintura_teto_hall"),
    },
)

PARTE_EXTERNAS = {
    "id": "externas",
    "titulo": "Áreas externas",
    "iso": None,
    "medidas": (
        ("caixas_inspecao_bloco", "Caixas de inspeção (um bloco)", "",
         lambda q: _total(q, "caixas_inspecao_total")),
        ("caixas_gordura_bloco", "Caixas de gordura (um bloco)", "",
         lambda q: _total(q, "caixas_gordura_total")),
    ),
    "percentuais": ("troca_tampas_inspecao", "troca_tampas_gordura", "troca_calcadas"),
}

# Dentro de cada parte o nome curto basta (a parte já diz onde é).
ROTULOS_PCT = {
    "troca_estrutura_cobertura": "Troca da estrutura",
    "troca_telhas_cobertura": "Troca de telhas",
    "instalacao_tabeira_beiral": "Instalação de tabeira / beiral",
    "troca_rufos_pingadeira": "Troca de rufos e pingadeiras",
    "troca_revestimento_fachada": "Troca de revestimento",
    "pintura_fachada": "Pintura",
    "troca_revestimento_paredes_hall": "Troca de revestimento das paredes",
    "troca_revestimento_tetos_hall": "Troca de revestimento dos tetos",
    "troca_pisos_hall": "Troca de pisos",
    "troca_rodape_hall": "Troca de rodapé",
    "pintura_paredes_hall": "Pintura das paredes",
    "pintura_teto_hall": "Pintura do teto",
    "troca_tampas_inspecao": "Troca de tampas das caixas de inspeção",
    "troca_tampas_gordura": "Troca de tampas das caixas de gordura",
    "troca_calcadas": "Troca de calçadas e caminhos",
}
QTD_PCT = {chave: (qtd, unidade) for chave, _r, _p, qtd, unidade in PERCENTUAIS_MODELO}
CAMPOS_ESQUADRIA = ("dim_x", "dim_y", "h_peitoril", "qtd_por_pav")


def _formatar_esquadria(valor) -> str:
    # Import aqui: ui.area_comum importa este módulo.
    from ui.area_comum import _texto_campo_numerico

    return _texto_campo_numerico(valor, casas=2)


# ---------------------------------------------------------------------------
class EstruturaTela:
    """Campos de uma estrutura na tela (variáveis do Tk + rótulos calculados)."""

    def __init__(self, dados: dict):
        dados = normalizar_estrutura(dados)
        self.id = dados["id"]
        self.nome = dados["nome"]
        self.tipo = dados["tipo"]
        self.desenho = dados["desenho"]
        self.var_qtd = tk.StringVar()
        self.var_tipo_estrutura = tk.StringVar()
        self.var_tipo_cobertura = tk.StringVar()
        self.vars_medida = {chave: tk.StringVar() for chave in CHAVES_MEDIDA_ESTRUTURA}
        self.vars_pct = {chave: tk.StringVar() for chave in CHAVES_PCT_ESTRUTURA}
        self.vars_esq = {
            modelo["id"]: {campo: tk.StringVar() for campo in CAMPOS_ESQUADRIA}
            for modelo in ESQUADRIAS_MODELO
        }
        self.definir(dados)
        # Preenchidos ao montar a tela.
        self.grupo = None
        self.lbl_nome = None
        self.totais: list = []
        self.qtd_pct: dict = {}
        self.esq_calc: dict = {}
        self.esq_total: dict = {}
        self.resumos: dict = {}

    @property
    def residencial(self) -> bool:
        return self.tipo != TIPO_OUTRA

    def definir(self, dados: dict) -> None:
        self.nome = dados["nome"]
        self.desenho = dados["desenho"]
        self.var_qtd.set(dados["quantidade"])
        self.var_tipo_estrutura.set(dados["tipo_estrutura"] or PLACEHOLDER_ESTADO)
        self.var_tipo_cobertura.set(dados["tipo_cobertura"] or PLACEHOLDER_ESTADO)
        for chave, var in self.vars_medida.items():
            var.set(dados["medidas"].get(chave, ""))
        for chave, var in self.vars_pct.items():
            var.set(dados["percentuais"].get(chave, ""))
        por_id = {e["id"]: e for e in dados["esquadrias"]}
        for ident, campos in self.vars_esq.items():
            salvo = por_id.get(ident) or {}
            for campo, var in campos.items():
                var.set(_formatar_esquadria(salvo.get(campo)))

    def coletar(self) -> dict:
        dados = nova_estrutura(self.nome, self.tipo, self.var_qtd.get())
        dados["id"] = self.id
        dados["tipo_estrutura"] = estado_do_combo(self.var_tipo_estrutura.get())
        dados["tipo_cobertura"] = estado_do_combo(self.var_tipo_cobertura.get())
        dados["medidas"] = {k: v.get().strip() for k, v in self.vars_medida.items()}
        dados["percentuais"] = {k: v.get().strip() for k, v in self.vars_pct.items()}
        for linha in dados["esquadrias"]:
            for campo, var in self.vars_esq[linha["id"]].items():
                linha[campo] = var.get().strip()
        dados["desenho"] = self.desenho
        return normalizar_estrutura(dados)

    def variaveis(self) -> list:
        saida = [self.var_qtd, self.var_tipo_estrutura, self.var_tipo_cobertura]
        saida += list(self.vars_medida.values()) + list(self.vars_pct.values())
        for campos in self.vars_esq.values():
            saida += list(campos.values())
        return saida


class _PercentualDoLocal:
    """Um percentual das estruturas de um local da aba 2.

    Ex.: "Troca de telhas" de "Blocos residenciais" lê o primeiro bloco
    residencial e, ao gravar, vale para todos os blocos residenciais.
    """

    def __init__(self, estruturas, chave):
        self._estruturas = estruturas
        self._chave = chave

    def get(self) -> str:
        for estrutura in self._estruturas:
            return estrutura.vars_pct[self._chave].get()
        return ""

    def set(self, valor) -> None:
        for estrutura in self._estruturas:
            estrutura.vars_pct[self._chave].set(valor)


# ---------------------------------------------------------------------------
class AbaDadosIniciais:
    def __init__(self, modulo, notebook):
        self.f = modulo
        self.c = modulo._cores
        self.fonte = tkfont.Font(family=FONTE[0], size=FONTE[1])
        self.refs: list = []
        self.estruturas: list[EstruturaTela] = []
        self.atual: EstruturaTela | None = None
        self.vars_medida_cond = {chave: tk.StringVar() for chave in CHAVES_MEDIDA_CONDOMINIO}
        self.vars_pct_cond = {chave: tk.StringVar() for chave in CHAVES_PCT_CONDOMINIO}
        self.cond_totais: list = []
        self.cond_qtd_pct: dict = {}
        self.var_blocos_residenciais = tk.StringVar()
        self.var_legenda = tk.StringVar()
        self.var_orccad = tk.StringVar()
        self._recolhidos: set = set()  # (id da estrutura, id da parte)
        self._job_rolagem = None
        for var in [*self.vars_medida_cond.values(), *self.vars_pct_cond.values()]:
            var.trace_add("write", self.f._ao_alterar_campo)

        self.aba = ttk.Frame(notebook)
        notebook.add(self.aba, text="1. Dados iniciais")
        self._montar()
        self.aplicar_estruturas([nova_estrutura()])

    # ============================================================ API do módulo
    def coletar_em(self, dados: dict) -> None:
        """Grava estruturas e dados do condomínio no rascunho `dados`."""
        dados["estruturas"] = [e.coletar() for e in self.estruturas]
        iniciais = dados.setdefault("dados_iniciais", {})
        iniciais["medidas"] = {k: v.get().strip() for k, v in self.vars_medida_cond.items()}
        iniciais["percentuais"] = {k: v.get().strip() for k, v in self.vars_pct_cond.items()}

    def dados_para_calculo(self) -> dict:
        dados: dict = {}
        self.coletar_em(dados)
        return dados

    def aplicar(self, dados: dict) -> None:
        """Mostra as estruturas e os dados do condomínio de um rascunho normalizado."""
        iniciais = dados.get("dados_iniciais") or {}
        for chave, var in self.vars_medida_cond.items():
            var.set((iniciais.get("medidas") or {}).get(chave, ""))
        for chave, var in self.vars_pct_cond.items():
            var.set((iniciais.get("percentuais") or {}).get(chave, ""))
        self.aplicar_estruturas(dados.get("estruturas") or [nova_estrutura()])

    def aplicar_estruturas(self, lista: list[dict]) -> None:
        lista = [normalizar_estrutura(e) for e in lista] or [nova_estrutura()]
        mesma_forma = len(self.estruturas) == len(lista) and all(
            e.tipo == d["tipo"] for e, d in zip(self.estruturas, lista)
        )
        if mesma_forma:
            # Mesmas estruturas na mesma ordem (abrir rascunho, desfazer): só
            # troca valores e nomes. Recriar ~400 campos custava ~0,3 s.
            for estrutura, dados in zip(self.estruturas, lista):
                estrutura.id = dados["id"]
                if estrutura.lbl_nome is not None and estrutura.nome != dados["nome"]:
                    estrutura.lbl_nome.configure(text=dados["nome"])
                estrutura.definir(dados)
        else:
            atual_id = self.atual.id if self.atual else None
            self.estruturas = [EstruturaTela(d) for d in lista]
            for estrutura in self.estruturas:
                for var in estrutura.variaveis():
                    var.trace_add("write", self.f._ao_alterar_campo)
            self.atual = next(
                (e for e in self.estruturas if e.id == atual_id), self.estruturas[0]
            )
            self._remontar_lista()
        self.mostrar_desenho()

    def estruturas_do_local(self, local) -> list[EstruturaTela]:
        if local == LOCAL_CONDOMINIO:
            return list(self.estruturas)
        if local == LOCAL_RESIDENCIAL:
            return [e for e in self.estruturas if e.residencial]
        return [e for e in self.estruturas if e.id == local]

    def percentuais_do_local(self, local) -> dict:
        """Percentuais que uma anomalia do `local` lê e grava na aba 1.

        Os de cobertura, fachada e hall valem para as estruturas do local; os
        de caixas e calçadas são sempre os do condomínio.
        """
        estruturas = self.estruturas_do_local(local)
        saida = {chave: _PercentualDoLocal(estruturas, chave) for chave in CHAVES_PCT_ESTRUTURA}
        saida.update(self.vars_pct_cond)
        return saida

    def percentuais_aba2(self) -> dict:
        return self.percentuais_do_local(LOCAL_RESIDENCIAL)

    def primeira_residencial(self) -> EstruturaTela | None:
        return next((e for e in self.estruturas if e.residencial), None)

    def atualizar_exibicao(self) -> None:
        """Totais, percentuais, esquadrias e resumos de cada estrutura."""
        dados = self.dados_para_calculo()
        for estrutura, coletada in zip(self.estruturas, dados["estruturas"]):
            q = quantitativos_da_estrutura(coletada)
            self._mostrar_quantitativos(estrutura.totais, estrutura.qtd_pct, q)
            self._mostrar_esquadrias(estrutura, q)
            self._mostrar_resumos(estrutura, q)
        q_cond = quantitativos_do_condominio(dados)
        self._mostrar_quantitativos(self.cond_totais, self.cond_qtd_pct, q_cond)
        total = blocos_residenciais(dados)
        texto = f"{_n(total, 0)} {'bloco residencial' if total == 1 else 'blocos residenciais'}"
        self.var_blocos_residenciais.set(texto if total else "")
        self.mostrar_desenho()

    def mostrar_desenho(self) -> None:
        estrutura = self.atual
        if estrutura is None:
            return
        self.planta.definir(estrutura.desenho)
        camadas = dict_para_camadas(estrutura.desenho)
        pontos, fechado = camadas["externa"]
        linhas = []
        for rotulo, (pts, fech) in (("Externa", camadas["externa"]), ("Hall", camadas["hall"])):
            if len(pts) < 2:
                continue
            res = resultado_desenho(pts, fechado=fech)
            if res.fechado:
                linhas.append(f"{rotulo} — Área: {formatar_decimal_br(res.area_m2, 2)} m² · "
                              f"Perímetro: {formatar_decimal_br(res.perimetro_m, 2)} m")
            else:
                linhas.append(f"{rotulo} (aberta) — Perímetro: "
                              f"{formatar_decimal_br(res.perimetro_m, 2)} m")
        self.var_legenda.set("\n".join(linhas))
        self.var_orccad.set(f"Planta: {estrutura.nome}")
        m = estrutura.vars_medida
        self.iso.definir(
            pontos,
            bool(fechado),
            numero(m["pe_direito_m"].get()),
            numero(m["qtd_pavimentos"].get()),
            platibanda=numero(m["altura_platibanda_m"].get()),
            blocos=numero(estrutura.var_qtd.get()),
        )

    def estrutura_por_id(self, ident) -> EstruturaTela | None:
        return next((e for e in self.estruturas if e.id == ident), None)

    # ============================================================ montagem
    def _montar(self):
        c = self.c
        self.f._montar_condominio_dados(self.aba)
        corpo = tk.Frame(self.aba, bg=c.fundo)
        corpo.pack(fill="both", expand=True, padx=(12, 8), pady=(0, 8))
        self._montar_desenho(corpo).pack(side="right", fill="y", padx=(14, 0))
        esquerda = tk.Frame(corpo, bg=c.fundo)
        esquerda.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(esquerda, bg=c.fundo, highlightthickness=0)
        barra = ttk.Scrollbar(esquerda, orient="vertical", command=self.canvas.yview)
        self.interior = tk.Frame(self.canvas, bg=c.fundo)
        janela = self.canvas.create_window((0, 0), window=self.interior, anchor="nw")

        def ao_rolar(inicio, fim):
            barra.set(inicio, fim)
            self._agendar_estrutura_visivel()

        self.canvas.configure(yscrollcommand=ao_rolar)
        self.interior.bind(
            "<Configure>",
            lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind(
            "<Configure>", lambda e: self.canvas.itemconfigure(janela, width=e.width - 4)
        )
        barra.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.f._vincular_scroll(self.canvas, self.interior)

    def _montar_desenho(self, pai):
        c = self.c
        col = tk.Frame(pai, bg=c.fundo)
        self._botao_orccad(col).pack(fill="x", pady=(0, 8))
        self.planta = PreviaDesenho2D(col, largura=LARGURA_DESENHO, altura=240)
        self.planta.pack(fill="x")
        tk.Label(col, textvariable=self.var_legenda, font=FONTE_PEQUENA, fg=c.titulo,
                 bg=c.fundo, anchor="w", justify="left").pack(fill="x", pady=(4, 8))
        self.iso = VistaIsometricaBloco(col, largura=LARGURA_DESENHO, altura=260)
        self.iso.pack(fill="x")
        return col

    def _botao_orccad(self, pai):
        """Quadrado do ícone num tom um pouco mais escuro, texto ao lado num tom
        mais claro, separados por um traço; no hover os dois escurecem."""
        c = self.c
        tons = {"icone": _misturar(c.fundo_destaque, c.titulo, 0.16), "texto": c.fundo_destaque}
        tons_hover = {k: _misturar(v, c.titulo, 0.14) for k, v in tons.items()}
        borda = _misturar(c.fundo_destaque, c.titulo, 0.38)
        lado = 40

        botao = tk.Frame(pai, bg=borda, padx=1, pady=1, cursor="hand2")
        quadrado = tk.Frame(botao, bg=tons["icone"], width=lado, height=lado, cursor="hand2")
        quadrado.pack(side="left")
        quadrado.pack_propagate(False)
        icone = criar_icone_svg(botao, "cube-outline", altura=20, cor=c.titulo)
        self.refs.append(icone)
        lbl_icone = tk.Label(quadrado, image=icone, bg=tons["icone"], cursor="hand2")
        lbl_icone.place(relx=0.5, rely=0.5, anchor="center")
        tk.Frame(botao, bg=borda, width=1).pack(side="left", fill="y")
        textos = tk.Frame(botao, bg=tons["texto"], padx=10, height=lado, cursor="hand2")
        textos.pack(side="left", fill="both", expand=True)
        miolo = tk.Frame(textos, bg=tons["texto"], cursor="hand2")
        miolo.place(relx=0, rely=0.5, anchor="w")
        titulo = tk.Label(miolo, text="Abrir ORCCAD", font=FONTE_TITULO, fg=c.titulo,
                          bg=tons["texto"], anchor="w", cursor="hand2")
        titulo.pack(anchor="w")
        sub = tk.Label(miolo, textvariable=self.var_orccad, font=FONTE_PEQUENA,
                       fg=c.texto_suave, bg=tons["texto"], anchor="w", cursor="hand2")
        sub.pack(anchor="w")
        lado_icone = (quadrado, lbl_icone)
        lado_texto = (textos, miolo, titulo, sub)

        def pintar(paleta):
            for w in lado_icone:
                w.configure(bg=paleta["icone"])
            for w in lado_texto:
                w.configure(bg=paleta["texto"])

        for w in (botao, *lado_icone, *lado_texto):
            w.bind("<Enter>", lambda _e: pintar(tons_hover), add="+")
            w.bind("<Leave>", lambda _e: pintar(tons), add="+")
            w.bind("<Button-1>", lambda _e: self.f._abrir_orccad(), add="+")
        return botao

    def _remontar_lista(self):
        for w in self.interior.winfo_children():
            w.destroy()
        self.f._entradas_caracteristicas.difference_update(
            {e for e in self.f._entradas_caracteristicas if not _existe(e)}
        )
        self.cond_totais.clear()
        self.cond_qtd_pct.clear()
        for estrutura in self.estruturas:
            self._montar_estrutura(estrutura)
        self._botao_adicionar().pack(fill="x", pady=(0, 18))
        cab = self._cabecalho_grupo(self.interior, "Todo o condomínio")
        cab.pack(fill="x", pady=(0, 8))
        tk.Label(cab.linha, textvariable=self.var_blocos_residenciais, font=FONTE,
                 fg=self.c.texto_suave, bg=self.c.fundo).pack(side="right")
        self._montar_parte(self.interior, PARTE_EXTERNAS, None).pack(fill="x", pady=(0, 10))
        self._montar_observacoes().pack(fill="x", pady=(0, 10))

    # ---------------------------------------------------------------- estruturas
    def _cabecalho_grupo(self, pai, titulo, estrutura=None):
        c = self.c
        quadro = tk.Frame(pai, bg=c.fundo)
        linha = tk.Frame(quadro, bg=c.fundo)
        linha.pack(fill="x")
        quadro.linha = linha
        lbl_titulo = tk.Label(linha, text=titulo, font=FONTE_ESTRUTURA, fg=c.texto, bg=c.fundo)
        lbl_titulo.pack(side="left")
        if estrutura is not None:
            estrutura.lbl_nome = lbl_titulo
            tk.Label(linha, text="Unidades iguais:", font=FONTE, fg=c.texto_suave,
                     bg=c.fundo).pack(side="left", padx=(18, 6))
            qtd = self._entrada(linha, 5, var=estrutura.var_qtd)
            qtd.pack(side="left")
            self.f._vincular_campo_numerico(qtd)
            self._botao_remover(linha, estrutura).pack(side="right", padx=(16, 0))
            tipo = "Bloco residencial" if estrutura.residencial else "Outra edificação"
            tk.Label(linha, text=tipo, font=FONTE, fg=c.texto_suave, bg=c.fundo).pack(side="right")
        tk.Frame(quadro, bg=c.titulo, height=2).pack(fill="x", pady=(4, 0))
        return quadro

    def _montar_estrutura(self, estrutura: EstruturaTela):
        estrutura.totais.clear()
        estrutura.qtd_pct.clear()
        estrutura.esq_calc.clear()
        estrutura.esq_total.clear()
        estrutura.resumos.clear()
        grupo = tk.Frame(self.interior, bg=self.c.fundo)
        grupo.pack(fill="x")
        estrutura.grupo = grupo
        self._cabecalho_grupo(grupo, estrutura.nome, estrutura).pack(fill="x", pady=(0, 8))
        for parte in PARTES_ESTRUTURA:
            if parte.get("so_residencial") and not estrutura.residencial:
                continue
            self._montar_parte(grupo, parte, estrutura).pack(fill="x", pady=(0, 10))
        # Clicar ou entrar num campo da estrutura mostra a planta dela.
        for w in _descendentes(grupo):
            w.bind("<Button-1>", lambda _e, e=estrutura: self._escolher(e), add="+")
            w.bind("<FocusIn>", lambda _e, e=estrutura: self._escolher(e), add="+")

    def _botao_remover(self, pai, estrutura):
        c = self.c
        unica = len(self.estruturas) == 1
        cor = _misturar(c.texto_suave, c.fundo, 0.45) if unica else c.texto_suave
        icone = criar_icone_svg(pai, "trash-outline", altura=13, cor=cor)
        self.refs.append(icone)
        botao = tk.Label(pai, text=" Remover", image=icone, compound="left", font=FONTE,
                         fg=cor, bg=c.fundo, cursor="arrow" if unica else "hand2")
        if unica:
            vincular_tooltip(botao, "O condomínio precisa de pelo menos uma estrutura")
            return botao
        icone_hover = criar_icone_svg(pai, "trash-outline", altura=13, cor=c.perigo)
        self.refs.append(icone_hover)
        botao.bind("<Enter>", lambda _e: botao.configure(fg=c.perigo, image=icone_hover))
        botao.bind("<Leave>", lambda _e: botao.configure(fg=cor, image=icone))
        botao.bind("<Button-1>", lambda _e: self._remover(estrutura))
        return botao

    def _botao_adicionar(self):
        c = self.c
        botao = tk.Label(self.interior, text="+  Adicionar estrutura", font=FONTE_NEGRITO,
                         fg=c.titulo, bg=c.fundo_cartao, highlightthickness=1,
                         highlightbackground=c.titulo, pady=8, cursor="hand2")
        botao.bind("<Button-1>", lambda _e: self._dialogo_nova_estrutura())
        botao.bind("<Enter>", lambda _e: botao.configure(bg=c.fundo_destaque))
        botao.bind("<Leave>", lambda _e: botao.configure(bg=c.fundo_cartao))
        return botao

    # ---------------------------------------------------------------- partes
    def _montar_parte(self, pai, parte, estrutura: EstruturaTela | None):
        c = self.c
        cartao = tk.Frame(pai, bg=c.fundo_cartao, highlightthickness=1,
                          highlightbackground=c.borda_suave)
        corpo = tk.Frame(cartao, bg=c.fundo_cartao, padx=PAD_CARTAO, pady=10)
        resumo = self._cabecalho_parte(cartao, corpo, parte, estrutura)
        if estrutura is not None:
            estrutura.resumos[parte["id"]] = resumo
            residencial_ = estrutura.residencial
        else:
            residencial_ = True
        vars_medida = estrutura.vars_medida if estrutura else self.vars_medida_cond
        vars_pct = estrutura.vars_pct if estrutura else self.vars_pct_cond
        totais = estrutura.totais if estrutura else self.cond_totais
        qtd_pct = estrutura.qtd_pct if estrutura else self.cond_qtd_pct

        medidas = [
            m for m in parte.get("medidas", ())
            if residencial_ or m[0] not in CHAVES_MEDIDA_SO_RESIDENCIAL
        ]
        modelos = esquadrias_da_estrutura(estrutura.tipo) if parte.get("esquadrias") else []
        pct = parte.get("percentuais", ())
        # Largura do rótulo: o maior rótulo DESTE cartão (não da página inteira).
        rotulos = [m[1] for m in medidas] + [r[0] for r in parte.get("resultados", ())]
        rotulos += [rotulo for _m, rotulo in modelos] + [ROTULOS_PCT[k] for k in pct[0::2]]
        if parte.get("combo"):
            rotulos.append(parte["combo"][1])
        largura = max(self.fonte.measure(t) for t in rotulos) + ESPACO_ROTULO

        g = self._grade(corpo, largura)
        linha = 0
        if parte.get("combo"):
            chave, rotulo, opcoes = parte["combo"]
            self._rotulo(g, rotulo, linha)
            var = getattr(estrutura, f"var_{chave}")
            combo = ttk.Combobox(g, textvariable=var, values=(PLACEHOLDER_ESTADO, *opcoes),
                                 state="readonly", width=24)
            combo.grid(row=linha, column=1, columnspan=3, sticky="w", pady=3)
            _fechar_combo_ao_rolar(combo)
            linha += 1
        for chave, rotulo, unidade, total in medidas:
            self._linha_medida(g, linha, vars_medida[chave], chave, rotulo, unidade, total, totais)
            linha += 1
        coluna_resultado, recuo = 3, (ESPACO_TOTAL, 0)
        if parte.get("esquadrias"):
            self._subtitulo(corpo, "Esquadrias por pavimento")
            self._montar_esquadrias(corpo, estrutura, modelos, largura)
            # Os resultados da fachada vêm das esquadrias: ficam depois delas.
            self._subtitulo(corpo, "Resultados")
            g, linha = self._grade(corpo, largura), 0
            coluna_resultado, recuo = 1, (0, 0)
        for rotulo, func in parte.get("resultados", ()):
            self._rotulo(g, rotulo, linha)
            lbl = tk.Label(g, text="", font=FONTE_NEGRITO, fg=c.titulo, bg=c.fundo_cartao,
                           anchor="w")
            lbl.grid(row=linha, column=coluna_resultado, columnspan=4, sticky="w", pady=3,
                     padx=recuo)
            totais.append((lbl, func))
            linha += 1
        if pct:
            self._subtitulo(corpo, "Percentuais de reparos")
            origem = estrutura.id if estrutura else LOCAL_CONDOMINIO
            self._montar_percentuais(corpo, vars_pct, qtd_pct, pct, largura,
                                     parte.get("selador"), origem)
        if (estrutura.id if estrutura else "cond", parte["id"]) in self._recolhidos:
            corpo.pack_forget()
        return cartao

    def _cabecalho_parte(self, cartao, corpo, parte, estrutura):
        """Faixa clara clicável: recolhe e abre o cartão (fechado = uma linha só)."""
        c = self.c
        cab = tk.Frame(cartao, bg=c.fundo_destaque, cursor="hand2")
        cab.pack(fill="x")
        corpo.pack(fill="x")
        fechada = criar_icone_svg(cab, "caret-forward-outline", altura=11, cor=c.titulo)
        aberta = criar_icone_svg(cab, "caret-forward-outline", altura=11, cor=c.titulo, angulo=90)
        self.refs += [fechada, aberta]
        chave = (estrutura.id if estrutura else "cond", parte["id"])
        seta = tk.Label(cab, image=fechada if chave in self._recolhidos else aberta,
                        bg=c.fundo_destaque, cursor="hand2", width=14)
        seta.pack(side="left", padx=(PAD_CARTAO - 4, 4), pady=6)
        titulo = tk.Label(cab, text=parte["titulo"], font=FONTE_TITULO, fg=c.titulo,
                          bg=c.fundo_destaque, cursor="hand2")
        titulo.pack(side="left")
        resumo = tk.Label(cab, text="", font=FONTE, fg=c.texto_suave, bg=c.fundo_destaque,
                          cursor="hand2")
        resumo.pack(side="right", padx=PAD_CARTAO)

        def alternar(_e=None):
            if chave in self._recolhidos:
                self._recolhidos.discard(chave)
                corpo.pack(fill="x")
                seta.configure(image=aberta)
            else:
                self._recolhidos.add(chave)
                corpo.pack_forget()
                seta.configure(image=fechada)

        for w in (cab, seta, titulo, resumo):
            w.bind("<Button-1>", alternar)
        if parte.get("iso"):
            self.f._ligar_destaque_isometrico([cab], parte["iso"])
        cartao.cabecalho = cab
        return resumo

    def _grade(self, corpo, largura_rotulo):
        g = tk.Frame(corpo, bg=self.c.fundo_cartao)
        g.pack(fill="x", anchor="w")
        g.columnconfigure(0, minsize=largura_rotulo)
        g.columnconfigure(2, minsize=ESPACO_UNIDADE + LARGURA_UNIDADE)
        return g

    def _linha_medida(self, g, linha, var, chave, rotulo, unidade, total, totais):
        c = self.c
        desenho = chave in CHAVES_MEDIDA_ORCCAD
        lbl = self._rotulo(g, rotulo, linha)
        entrada = self._entrada(g, 10, var=var, desenho=desenho)
        entrada.grid(row=linha, column=1, sticky="w", pady=3)
        self.f._vincular_campo_numerico(entrada)
        if desenho:
            vincular_tooltip(entrada, DICA_ORCCAD)
        tk.Label(g, text=unidade, font=FONTE, fg=c.texto_suave, bg=c.fundo_cartao,
                 anchor="w").grid(row=linha, column=2, sticky="w", padx=(ESPACO_UNIDADE, 0))
        if total:
            t = tk.Label(g, text="", font=FONTE_NEGRITO, fg=c.titulo, bg=c.fundo_cartao,
                         anchor="w")
            t.grid(row=linha, column=3, sticky="w", padx=(ESPACO_TOTAL, 0))
            totais.append((t, total))
        from ui.area_comum import PARTES_ISOMETRICA

        parte = PARTES_ISOMETRICA.get(chave)
        if parte:
            self.f._ligar_destaque_isometrico([lbl, entrada], parte, campo=entrada)

    def _montar_esquadrias(self, corpo, estrutura, modelos, largura_rotulo):
        c = self.c
        t = tk.Frame(corpo, bg=c.fundo_cartao)
        t.pack(fill="x", anchor="w")
        t.columnconfigure(0, minsize=largura_rotulo)
        titulos = ("Esquadria", "Largura", "Altura", "Peitoril", "Qtd./pav.",
                   "Perímetro", "Pingadeira", "Área")
        for col, texto in enumerate(titulos):
            tk.Label(t, text=texto, font=FONTE_NEGRITO, fg=c.texto, bg=c.fundo_cartao,
                     anchor="w").grid(row=0, column=col, sticky="w", pady=(0, 2),
                                      padx=(0, 10 if col else 0))
        for i, (modelo, rotulo) in enumerate(modelos, start=1):
            ident = modelo["id"]
            tk.Label(t, text=rotulo, font=FONTE, fg=c.texto, bg=c.fundo_cartao,
                     anchor="w").grid(row=i, column=0, sticky="w")
            for col, campo in enumerate(CAMPOS_ESQUADRIA, start=1):
                entrada = self._entrada(t, 7, var=estrutura.vars_esq[ident][campo])
                entrada.grid(row=i, column=col, sticky="w", padx=(0, 10), pady=2)
                self.f._vincular_campo_numerico(entrada, casas=2)
            calc = {}
            for col, campo in enumerate(("perimetro", "pingadeira", "area"), start=5):
                lbl = tk.Label(t, text="—", font=FONTE, fg=c.titulo, bg=c.fundo_cartao,
                               anchor="w")
                lbl.grid(row=i, column=col, sticky="w", padx=(0, 10))
                calc[campo] = lbl
            estrutura.esq_calc[ident] = calc
        fim = len(modelos) + 1
        tk.Frame(t, bg=c.borda_suave, height=1).grid(row=fim, column=0, columnspan=8,
                                                       sticky="ew", pady=(4, 2))
        tk.Label(t, text="Total por pavimento", font=FONTE_NEGRITO, fg=c.titulo,
                 bg=c.fundo_cartao, anchor="w").grid(row=fim + 1, column=0, sticky="w")
        for col, campo in ((4, "qtd"), (5, "perimetro"), (6, "pingadeira"), (7, "area")):
            lbl = tk.Label(t, text="—", font=FONTE_NEGRITO, fg=c.titulo, bg=c.fundo_cartao,
                           anchor="w")
            lbl.grid(row=fim + 1, column=col, sticky="w")
            estrutura.esq_total[campo] = lbl

    def _montar_percentuais(self, corpo, vars_pct, qtd_pct, chaves, largura_rotulo, selador,
                            origem):
        """Duas colunas compactas; a da esquerda alinha com os campos de cima."""
        c = self.c
        g = tk.Frame(corpo, bg=c.fundo_cartao)
        g.pack(fill="x", anchor="w")
        g.columnconfigure(0, minsize=largura_rotulo)
        direita = [ROTULOS_PCT[k] for k in chaves[1::2]]
        if direita:
            g.columnconfigure(
                3,
                minsize=max(self.fonte.measure(t) for t in direita) + ESPACO_ROTULO + ESPACO_COLUNAS,
            )
        for i, chave in enumerate(chaves):
            linha, lado = divmod(i, 2)
            base = lado * 3
            lbl = self._rotulo(g, ROTULOS_PCT[chave], linha, coluna=base)
            if lado:
                lbl.grid_configure(padx=(ESPACO_COLUNAS, 0))
            var = vars_pct[chave]
            campo = tk.Frame(g, bg=c.fundo_cartao)
            campo.grid(row=linha, column=base + 1, sticky="w", pady=3)
            entrada = self._entrada(campo, 5, var=var)
            entrada.pack(side="left")
            self.f._vincular_campo_numerico(entrada, percentual=True)
            entrada.bind("<FocusIn>",
                         lambda _e, k=chave, v=var: self.f._ao_focar_percentual(k, v), add="+")
            entrada.bind("<FocusOut>",
                         lambda _e, k=chave, w=entrada, v=var: self.f._ao_sair_percentual(
                             k, w, v, origem),
                         add="+")
            tk.Label(campo, text="%", font=FONTE, fg=c.texto_suave,
                     bg=c.fundo_cartao).pack(side="left", padx=(ESPACO_UNIDADE, 0))
            qtd = tk.Label(g, text="", font=FONTE_NEGRITO, fg=c.titulo, bg=c.fundo_cartao,
                           anchor="w", width=13)
            qtd.grid(row=linha, column=base + 2, sticky="w", padx=(ESPACO_TOTAL, 0))
            qtd_pct[chave] = qtd
        if selador:
            linha = (len(chaves) + 1) // 2
            ttk.Checkbutton(
                g,
                text="2 demãos de fundo selador",
                variable=self.f.var_duas_demaos_selador,
                command=self.f._ao_trocar_demaos_selador,
            ).grid(row=linha, column=0, columnspan=3, sticky="w", pady=(4, 0))

    def _montar_observacoes(self):
        c = self.c
        cartao = tk.Frame(self.interior, bg=c.fundo_cartao, highlightthickness=1,
                          highlightbackground=c.borda_suave)
        corpo = tk.Frame(cartao, bg=c.fundo_cartao, padx=PAD_CARTAO, pady=10)
        self._cabecalho_parte(cartao, corpo, {"id": "obs", "titulo": "Observações"}, None)
        texto = tk.Text(corpo, height=4, font=FONTE, relief="solid", bd=1,
                        highlightthickness=0, wrap="word", fg=c.texto, bg=c.fundo_cartao,
                        insertbackground=c.texto)
        texto.pack(fill="x")
        observacoes = getattr(self.f, "_observacoes", "")
        if observacoes:
            texto.insert("1.0", observacoes)
        texto.edit_modified(False)
        texto.bind("<KeyRelease>", lambda _e: self.f._ao_alterar_campo())
        texto.bind("<<Modified>>", self.f._ao_modificar_observacoes)
        self.f.texto_obs = texto
        return cartao

    # ---------------------------------------------------------------- peças
    def _rotulo(self, g, texto, linha, coluna=0):
        lbl = tk.Label(g, text=texto, font=FONTE, fg=self.c.texto, bg=self.c.fundo_cartao,
                       anchor="w")
        lbl.grid(row=linha, column=coluna, sticky="w", pady=3)
        return lbl

    def _entrada(self, pai, largura, var=None, desenho=False):
        # tk.Entry em todos: no Windows o ttk ignora o fundo e desalinha a coluna.
        c = self.c
        entrada = tk.Entry(
            pai, width=largura, textvariable=var, font=FONTE, relief="solid", bd=1,
            highlightthickness=0, fg=c.texto, insertbackground=c.texto,
            bg=c.fundo_cartao_off if desenho else c.fundo_cartao,
        )
        self.f._entradas_caracteristicas.add(entrada)
        entrada.bind("<Escape>", lambda _e: self.f._tirar_foco_campo(), add="+")
        return entrada

    def _subtitulo(self, corpo, texto):
        tk.Label(corpo, text=texto, font=FONTE_NEGRITO, fg=self.c.texto,
                 bg=self.c.fundo_cartao, anchor="w").pack(fill="x", pady=(12, 4))

    # ============================================================ exibição
    @staticmethod
    def _mostrar_quantitativos(totais, qtd_pct, q):
        for lbl, func in totais:
            lbl.configure(text=func(q))
        for chave, lbl in qtd_pct.items():
            qtd_chave, unidade = QTD_PCT[chave]
            texto = _n(q.get(qtd_chave))
            lbl.configure(text="" if texto == "—" else f"{texto} {unidade}")

    @staticmethod
    def _medida(valor, unidade):
        texto = _n(valor)
        return texto if texto == "—" else f"{texto} {unidade}"

    def _mostrar_esquadrias(self, estrutura, q):
        linhas = q.get("esquadrias") or {}
        for ident, calc in estrutura.esq_calc.items():
            d = linhas.get(ident) or {}
            calc["perimetro"].configure(text=self._medida(d.get("perimetro_pav_m"), "m"))
            calc["pingadeira"].configure(text=self._medida(d.get("pingadeira_pav_m"), "m"))
            calc["area"].configure(text=self._medida(d.get("area_pav_m2"), "m²"))
        total = estrutura.esq_total
        if total:
            total["qtd"].configure(text=_n(q.get("esquadria_qtd_pav")))
            total["perimetro"].configure(text=self._medida(q.get("esquadria_perimetro_pav_m"), "m"))
            total["pingadeira"].configure(
                text=self._medida(q.get("esquadria_pingadeira_pav_m"), "m"))
            total["area"].configure(text=self._medida(q.get("esquadria_area_pav_m2"), "m²"))

    @staticmethod
    def _mostrar_resumos(estrutura, q):
        r = estrutura.resumos
        if "predio" in r:
            partes = []
            if q.get("qtd_pavimentos"):
                partes.append(f"{_n(q['qtd_pavimentos'], 0)} pavimentos")
            if q.get("pe_direito_m"):
                partes.append(f"pé-direito {_n(q['pe_direito_m'])} m")
            if q.get("qtd_aptos_total"):
                partes.append(f"{_n(q['qtd_aptos_total'], 0)} apartamentos")
            r["predio"].configure(text=" · ".join(partes))
        if "cobertura" in r:
            r["cobertura"].configure(text=_total(q, "area_cobertura_total_m2", "m²"))
        if "fachada" in r:
            r["fachada"].configure(text=_total(q, "area_fachada_total_m2", "m²"))
        if "hall" in r:
            texto = _total(q, "area_piso_hall_total_m2", "m²")
            r["hall"].configure(text=texto.replace("no total", "de piso no total"))

    # ============================================================ estrutura na tela
    def _escolher(self, estrutura):
        if self.atual is not estrutura:
            self.atual = estrutura
            self.mostrar_desenho()

    def _agendar_estrutura_visivel(self):
        if self._job_rolagem is None:
            self._job_rolagem = self.aba.after_idle(self._estrutura_visivel)

    def _estrutura_visivel(self):
        """O desenho acompanha a rolagem: mostra a estrutura no topo da área visível."""
        self._job_rolagem = None
        try:
            topo = self.canvas.canvasy(0) + 40
        except tk.TclError:
            return
        escolhida = None
        for estrutura in self.estruturas:
            grupo = estrutura.grupo
            if grupo is None or not _existe(grupo):
                continue
            if grupo.winfo_y() <= topo:
                escolhida = estrutura
        if escolhida is not None:
            self._escolher(escolhida)

    def ir_para(self, estrutura):
        self.canvas.update_idletasks()
        altura = max(self.interior.winfo_height(), 1)
        self.canvas.yview_moveto(estrutura.grupo.winfo_y() / altura)

    # ============================================================ adicionar / remover
    def _dialogo_nova_estrutura(self):
        topo = self.f.winfo_toplevel()
        dialog = tk.Toplevel(topo)
        preparar_toplevel(dialog)
        cores, estilos = aplicar_chrome_dialogo(dialog)
        dialog.title("Adicionar estrutura")
        aplicar_icone_janela(dialog)
        dialog.transient(topo)
        dialog.grab_set()
        dialog.resizable(False, False)
        refs: list = []

        painel = tk.Frame(dialog, bg=cores.fundo, padx=18, pady=14)
        painel.pack(fill="x")
        var_nome = tk.StringVar(value=self._nome_livre("Salão de festas"))
        var_tipo = tk.StringVar(value=TIPO_OUTRA)
        var_qtd = tk.StringVar(value="1")
        g = tk.Frame(painel, bg=cores.fundo)
        g.pack(fill="x")
        tk.Label(g, text="Nome:", bg=cores.fundo, fg=cores.texto).grid(
            row=0, column=0, sticky="w", pady=4)
        nome = ttk.Entry(g, textvariable=var_nome, width=32)
        nome.grid(row=0, column=1, sticky="w", padx=(10, 0), pady=4)
        tk.Label(g, text="Tipo:", bg=cores.fundo, fg=cores.texto).grid(
            row=1, column=0, sticky="nw", pady=4)
        tipos = tk.Frame(g, bg=cores.fundo)
        tipos.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=4)
        ttk.Radiobutton(tipos, text="Bloco residencial", value=TIPO_RESIDENCIAL,
                        variable=var_tipo).pack(anchor="w")
        ttk.Radiobutton(tipos, text="Outra edificação (salão, guarita, portaria…)",
                        value=TIPO_OUTRA, variable=var_tipo).pack(anchor="w", pady=(2, 0))
        tk.Label(g, text="Unidades iguais:", bg=cores.fundo, fg=cores.texto).grid(
            row=2, column=0, sticky="w", pady=4)
        qtd = ttk.Entry(g, textvariable=var_qtd, width=8)
        qtd.grid(row=2, column=1, sticky="w", padx=(10, 0), pady=4)
        aviso = tk.Label(painel, text="", bg=cores.fundo, fg=cores.perigo, anchor="w")
        aviso.pack(fill="x", pady=(6, 0))

        def confirmar(_e=None):
            texto_nome = " ".join(var_nome.get().split())
            if not texto_nome:
                aviso.configure(text="Informe o nome.")
                return
            if any(e.nome.casefold() == texto_nome.casefold() for e in self.estruturas):
                aviso.configure(text="Já existe uma estrutura com esse nome.")
                return
            unidades = numero(var_qtd.get())
            if unidades <= 0 or unidades != int(unidades):
                aviso.configure(text="Informe quantas unidades iguais existem (número inteiro).")
                return
            dialog.destroy()
            self._adicionar(texto_nome, var_tipo.get(), formatar_decimal_br(unidades, 0))

        botoes = tk.Frame(painel, bg=cores.fundo)
        botoes.pack(fill="x", pady=(8, 0))
        criar_botao_cancelar(botoes, dialog.destroy).pack(side="right")
        criar_botao_ttk_com_icone(
            botoes,
            texto="Adicionar",
            nome_icone="add-circle-outline",
            command=confirmar,
            estilo=estilos.adicionar,
            cor_icone=estilos.icone_adicionar,
            refs=refs,
        ).pack(side="right", padx=(0, 8))
        dialog._refs_icones = refs
        dialog.bind("<Return>", confirmar)
        dialog.bind("<Escape>", lambda _e: dialog.destroy())
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.update_idletasks()
        centralizar_janela(dialog, topo)
        focar_entrada_apos_exibir(nome, selecionar=True)

    def _nome_livre(self, base):
        nomes = {e.nome.casefold() for e in self.estruturas}
        if base.casefold() not in nomes:
            return base
        n = 2
        while f"{base} {n}".casefold() in nomes:
            n += 1
        return f"{base} {n}"

    def _adicionar(self, nome, tipo, quantidade):
        dados = [e.coletar() for e in self.estruturas]
        nova = nova_estrutura(nome, tipo, quantidade)
        self.aplicar_estruturas([*dados, nova])
        estrutura = self.estruturas[-1]
        self._escolher(estrutura)
        self.f._estruturas_mudaram(f"Adicionar estrutura «{nome}»")
        self.aba.after_idle(lambda: self.ir_para(estrutura))

    def _remover(self, estrutura):
        mensagem = f"Remover «{estrutura.nome}»?\nAs medidas e a planta dela serão apagadas."
        anomalias = self.f._anomalias_no_local(estrutura.id)
        if anomalias:
            qtd = len(anomalias)
            mensagem += (
                f"\n\n{'A anomalia' if qtd == 1 else f'As {qtd} anomalias'} dela na aba 2 "
                f"{'também será removida' if qtd == 1 else 'também serão removidas'}."
            )
        if not messagebox.askyesno("Remover estrutura", mensagem, parent=self.f.winfo_toplevel()):
            return
        restantes = [e.coletar() for e in self.estruturas if e is not estrutura]
        if self.atual is estrutura:
            self.atual = None
        self.f._remover_anomalias_do_local(estrutura.id)
        self.aplicar_estruturas(restantes)
        self.f._estruturas_mudaram(f"Remover estrutura «{estrutura.nome}»")


# ---------------------------------------------------------------------------
def _descendentes(widget):
    pendentes = [widget]
    while pendentes:
        atual = pendentes.pop()
        yield atual
        pendentes.extend(atual.winfo_children())


def _existe(widget) -> bool:
    try:
        return bool(widget.winfo_exists())
    except tk.TclError:
        return False


def _fechar_combo_ao_rolar(combo):
    from ui.area_comum import _vincular_combo_fecha_ao_rolar

    _vincular_combo_fecha_ao_rolar(combo)
