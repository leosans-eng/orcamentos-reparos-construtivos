"""Canvas de desenho 2D (polilinha/retângulo) com snap no estilo CAD.

Destinado a preencher metragens da Área Comum: o usuário desenha em metros
(Orto, Polar, osnap e guias) e o painel devolve área e perímetro.
"""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk

from core.desenho_geometria import (
    ConfigSnap,
    Ponto,
    ResultadoDesenho,
    ResultadoSnap,
    angulo_graus,
    area_poligono,
    comprimento_ao_longo,
    dict_para_camadas,
    desenho_camadas_para_dict,
    distancia,
    lado_do_ponto,
    offset_retangulo,
    offset_retangulo_comprimento,
    offset_segmento,
    offset_segmento_comprimento,
    passo_grade_visivel,
    perimetro,
    ponto_na_direcao,
    ponto_no_segmento,
    quase_iguais,
    resolver_snap,
    resultado_desenho,
    retangulo_eixos,
    segmento_mais_proximo,
)
from core.desenho_edicao import (
    HistoricoDesenho,
    ajustar_comprimento,
    apagar_segmentos,
    copiar_camadas,
    extremos_segmento,
    indices_segmentos,
    mover_vertices,
    selecionar_por_retangulo,
    vertices_da_selecao,
)
from ui.icones import criar_botao_ttk_so_icone
from ui.temas import cores_tema, estilos_botao
from ui.widgets import (
    formatar_decimal_br,
    formatar_quantidade_edicao,
    parse_decimal_br,
    vincular_tooltip,
)

# (chave, rótulo, tipo_medida, camada)
CAMPOS_DESENHO_AREA_COMUM = (
    ("area_construida_m2", "Área construída / cobertura", "area", "externa"),
    ("perimetro_beiral_m", "Perímetro de beiral (calha)", "perimetro", "externa"),
    ("perimetro_paredes_externas_bloco_m", "Perímetro de paredes externas (bloco)", "perimetro", "externa"),
    ("perimetro_platibanda_bloco_m", "Perímetro de platibanda (bloco)", "perimetro", "externa"),
    ("perimetro_hall_parede_pav_m", "Perímetro de parede do hall (pavimento)", "perimetro", "hall"),
    ("perimetro_hall_rodape_pav_m", "Perímetro de rodapé do hall (pavimento)", "perimetro", "hall"),
    ("area_laje_hall_pav_m2", "Área da laje do hall (pavimento)", "area", "hall"),
    ("area_piso_hall_pav_m2", "Área de piso do hall (pavimento)", "area", "hall"),
)

CHAVES_MEDIDA_ORCCAD = frozenset(
    chave for chave, _rotulo, _tipo, _camada in CAMPOS_DESENHO_AREA_COMUM
)

COR_EXTERNA = "#006699"
COR_HALL = "#2e7d32"
COR_SELECAO = "#1e88e5"
COR_GRIP = "#1565c0"
COR_GRIP_QUENTE = "#e53935"
COR_JANELA = "#1e88e5"
COR_CRUZAMENTO = "#2e7d32"

_TOL_LINHA_PX = 8.0
_TOL_GRIP_PX = 7.0
_ARRASTE_MIN_PX = 4.0

_ZOOM_MIN = 8.0
_ZOOM_MAX = 400.0
_ABERTURA_PX = 16.0
_ABERTURA_GUIA_PX = 36.0
_PASSO_GRADE_SNAP = 0.1


class PainelDesenho2D(tk.Frame):
    """Widget reutilizável: desenho em metros com Orto, Polar e snap."""

    def __init__(self, parent, *, on_resultado=None):
        cores = cores_tema(parent)
        super().__init__(parent, bg=cores.fundo)
        self._cores = cores
        self.on_resultado = on_resultado
        self._camadas = {
            "externa": {"pontos": [], "fechado": False},
            "hall": {"pontos": [], "fechado": False},
        }
        self.camada_ativa = "externa"
        # "selecao" é o estado sem comando: clique seleciona, como no AutoCAD.
        self._ferramenta = "selecao"
        self._canto_ret = None
        self._buffer = ""
        self._shift = False
        self._espaco = False
        self._zoom = 40.0
        self._ox = 72.0
        self._oy = 520.0
        self._vista_ok = False
        self._enquadrar_pendente = False
        self._job_enquadrar = None
        self._pan = None
        self._ultimo_snap: ResultadoSnap | None = None
        self._cursor_tela = (0.0, 0.0)
        self._binds_janela: list[tuple] = []
        self._seqs_bind_all: list[str] = []
        self._refs_icones: list = []
        self._offset_modo = None  # None | "segmento" | "retangulo"
        self._offset_fase = None  # None | "distancia" | "comprimento"
        self._offset_seg = None  # (Ponto, Ponto) selecionado na externa
        self._offset_dist = None  # distância vazia confirmada (m)
        self._offset_lado = None  # +1 / -1
        self._offset_comp = None  # comprimento editável (m)
        self._offset_hall_backup = None
        self._chips_camada: dict = {}

        self._selecao: set[tuple[str, int]] = set()
        self._hover_linha: tuple[str, int] | None = None
        self._janela_sel: list[float] | None = None  # [sx0, sy0, sx1, sy1]
        self._janela_por_arraste = False
        self._press_xy: tuple[float, float] | None = None
        self._mover_base: Ponto | None = None
        self._grip: tuple[str, int, Ponto] | None = None
        self._grip_por_arraste = False
        self._editor_cota = None
        self._historico = HistoricoDesenho()
        self.revisao = 0

        self.var_ortho = tk.BooleanVar(value=False)
        self.var_polar = tk.BooleanVar(value=True)
        self.var_osnap = tk.BooleanVar(value=True)
        self.var_grade = tk.BooleanVar(value=True)
        self.var_guias = tk.BooleanVar(value=True)

        self._montar()
        self.canvas.bind("<Configure>", self._ao_configurar)

    @property
    def pontos(self) -> list[Ponto]:
        return self._camadas[self.camada_ativa]["pontos"]

    @pontos.setter
    def pontos(self, valor: list[Ponto]):
        self._camadas[self.camada_ativa]["pontos"] = list(valor)

    @property
    def fechado(self) -> bool:
        return bool(self._camadas[self.camada_ativa]["fechado"])

    @fechado.setter
    def fechado(self, valor: bool):
        self._camadas[self.camada_ativa]["fechado"] = bool(valor)

    def resultado_camada(self, camada: str) -> ResultadoDesenho | None:
        dados = self._camadas.get(camada) or {}
        pts = dados.get("pontos") or []
        if len(pts) < 2:
            return None
        return resultado_desenho(pts, fechado=bool(dados.get("fechado")))

    def resultado(self) -> ResultadoDesenho | None:
        return self.resultado_camada(self.camada_ativa)

    def resultados(self) -> dict[str, ResultadoDesenho | None]:
        return {
            "externa": self.resultado_camada("externa"),
            "hall": self.resultado_camada("hall"),
        }

    def _limpar_estado_offset(self, *, restaurar_hall: bool = False):
        if restaurar_hall and self._offset_hall_backup is not None:
            self._camadas["hall"] = {
                "pontos": list(self._offset_hall_backup["pontos"]),
                "fechado": bool(self._offset_hall_backup["fechado"]),
            }
        self._offset_seg = None
        self._offset_modo = None
        self._offset_fase = None
        self._offset_dist = None
        self._offset_lado = None
        self._offset_comp = None
        self._offset_hall_backup = None
        if self._ferramenta.startswith("offset"):
            self._ferramenta = "selecao"

    # ------------------------------------------------------------------
    # Estado, histórico e API pública
    # ------------------------------------------------------------------

    def _estado(self) -> dict:
        return {"camadas": copiar_camadas(self._camadas), "ativa": self.camada_ativa}

    def _restaurar(self, estado: dict):
        self._camadas = copiar_camadas(estado["camadas"])
        self.camada_ativa = estado.get("ativa") or "externa"

    def _registrar(self, estado: dict | None = None):
        """Guarda o estado anterior a uma alteração (para Ctrl+Z)."""
        self._historico.registrar(estado if estado is not None else self._estado())
        self.revisao += 1

    def _cancelar_comandos(self):
        if self._canto_ret is not None and len(self.pontos) == 1 and not self.fechado:
            self.pontos.clear()
        self._canto_ret = None
        self._buffer = ""
        self._janela_sel = None
        self._janela_por_arraste = False
        self._mover_base = None
        self._grip = None
        self._grip_por_arraste = False
        self._fechar_editor_cota()
        if self._ferramenta.startswith("offset"):
            self._limpar_estado_offset(restaurar_hall=True)

    def _apos_mudanca_historico(self, mensagem: str):
        self._selecao.clear()
        self._hover_linha = None
        if self._ferramenta not in ("polilinha",):
            self._ferramenta = "selecao"
        self.revisao += 1
        self._atualizar_chips_camada()
        self._redesenhar_estatico()
        self._atualizar_volante()
        self._avisar_resultado()
        self._set_status(mensagem)

    def desfazer(self):
        if self._ferramenta == "retangulo" and self._canto_ret is not None:
            self._canto_ret = None
            self.pontos.clear()
            self._redesenhar_estatico()
            self._atualizar_volante()
            self._set_status("Retângulo cancelado.")
            return
        self._cancelar_comandos()
        anterior = self._historico.desfazer(self._estado())
        if anterior is None:
            self._set_status("Nada para desfazer.")
            return
        self._restaurar(anterior)
        self._apos_mudanca_historico("Desfeito. Ctrl+Y refaz.")

    def refazer(self):
        self._cancelar_comandos()
        proximo = self._historico.refazer(self._estado())
        if proximo is None:
            self._set_status("Nada para refazer.")
            return
        self._restaurar(proximo)
        self._apos_mudanca_historico("Refeito.")

    def tem_pontos(self, camada: str) -> int:
        return len(self._camadas.get(camada, {}).get("pontos") or [])

    def limpar(self):
        self._cancelar_comandos()
        if self.pontos or self.fechado:
            self._registrar()
        self.pontos.clear()
        self.fechado = False
        self._ultimo_snap = None
        self._selecao = {s for s in self._selecao if s[0] != self.camada_ativa}
        self._ferramenta = "selecao"
        self._redesenhar_estatico()
        self._atualizar_volante()
        self._avisar_resultado()
        self._set_status(self._msg_inicio())

    def limpar_tudo(self):
        self._cancelar_comandos()
        if any(d["pontos"] for d in self._camadas.values()):
            self._registrar()
        for chave in self._camadas:
            self._camadas[chave] = {"pontos": [], "fechado": False}
        self._ultimo_snap = None
        self._selecao.clear()
        self._ferramenta = "selecao"
        self._redesenhar_estatico()
        self._atualizar_volante()
        self._avisar_resultado()
        self._set_status(self._msg_inicio())

    def exportar(self) -> dict:
        return desenho_camadas_para_dict(
            externa_pontos=self._camadas["externa"]["pontos"],
            externa_fechado=self._camadas["externa"]["fechado"],
            hall_pontos=self._camadas["hall"]["pontos"],
            hall_fechado=self._camadas["hall"]["fechado"],
        )

    def carregar(self, dados):
        camadas = dict_para_camadas(dados)
        for chave, (pts, fechado) in camadas.items():
            self._camadas[chave] = {"pontos": list(pts), "fechado": fechado}
        self.camada_ativa = "externa"
        self._limpar_estado_offset(restaurar_hall=False)
        self._cancelar_comandos()
        self._ultimo_snap = None
        self._selecao.clear()
        self._historico.limpar()
        self.revisao = 0
        self._ferramenta = "selecao"
        self._atualizar_chips_camada()
        self._redesenhar_estatico()
        self._atualizar_volante()
        self._avisar_resultado()
        if self._camadas["externa"]["pontos"] or self._camadas["hall"]["pontos"]:
            self.enquadrar_quando_visivel()
            self._set_status("Planta carregada. Edite Externa/Hall ou salve no orçamento.")
        else:
            self._set_status(self._msg_inicio())

    def _msg_inicio(self) -> str:
        return ""

    def vincular_atalhos(self, janela):
        """F3/F7/F8/F10/F11 em qualquer foco da janela (bind_all)."""
        self._desvincular_atalhos()

        def desta_janela(handler):
            def inner(event):
                try:
                    widget = event.widget
                    if isinstance(widget, str):
                        widget = janela.nametowidget(widget)
                    if widget.winfo_toplevel() is not janela:
                        return None
                except tk.TclError:
                    return None
                return handler(event)

            return inner

        pares = (
            ("<F3>", lambda e: self._alternar(self.var_osnap)),
            ("<F7>", lambda e: self._alternar(self.var_grade)),
            ("<F8>", lambda e: self._alternar(self.var_ortho)),
            ("<F10>", lambda e: self._alternar(self.var_polar)),
            ("<F11>", lambda e: self._alternar(self.var_guias)),
            ("<Shift_L>", lambda e: self._set_shift(True)),
            ("<KeyRelease-Shift_L>", lambda e: self._set_shift(False)),
            ("<Shift_R>", lambda e: self._set_shift(True)),
            ("<KeyRelease-Shift_R>", lambda e: self._set_shift(False)),
            ("<space>", self._ao_espaco),
            ("<KeyRelease-space>", lambda e: self._set_espaco(False)),
            ("<Home>", self._ao_home),
            ("<Control-z>", self._ao_desfazer_tecla),
            ("<Control-Z>", self._ao_refazer_tecla),
            ("<Control-y>", self._ao_refazer_tecla),
            ("<Control-Y>", self._ao_refazer_tecla),
            ("<Delete>", self._ao_delete),
        )
        for seq, handler in pares:
            wrapped = desta_janela(handler)
            if seq.startswith("<F"):
                if seq == "<F10>":
                    janela.bind_all(seq, wrapped)
                else:
                    janela.bind_all(seq, wrapped, add="+")
                self._seqs_bind_all.append(seq)
            else:
                janela.bind(seq, wrapped)
                self.canvas.bind(seq, wrapped)
                self._binds_janela.append((janela, seq))
                self._binds_janela.append((self.canvas, seq))
        janela.bind("<Destroy>", self._ao_destruir_janela, add="+")

    def desvincular_atalhos(self):
        self._desvincular_atalhos()

    def _desvincular_atalhos(self):
        for janela, seq in self._binds_janela:
            try:
                janela.unbind(seq)
            except tk.TclError:
                pass
        self._binds_janela.clear()
        for seq in self._seqs_bind_all:
            try:
                self.unbind_all(seq)
            except tk.TclError:
                pass
        self._seqs_bind_all.clear()

    def _ao_destruir_janela(self, event):
        if event.widget is event.widget.winfo_toplevel():
            self._desvincular_atalhos()

    def _montar(self):
        cores = self._cores
        estilos = estilos_botao(self)
        barra = ttk.Frame(self, padding=(8, 6))
        barra.pack(fill="x")

        for chave, rotulo, cor in (
            ("externa", "EXTERNA", COR_EXTERNA),
            ("hall", "HALL", COR_HALL),
        ):
            chip = tk.Label(
                barra,
                text=rotulo,
                padx=8,
                pady=2,
                font=("Segoe UI", 8, "bold"),
                cursor="hand2",
            )
            chip.pack(side="left", padx=(0, 4))
            chip.bind("<Button-1>", lambda _e, c=chave: self._ativar_camada(c))
            vincular_tooltip(
                chip,
                "Parte externa do edifício (fachada, beiral, cobertura)."
                if chave == "externa"
                else "Hall interno: desenhe do zero ou use Offset a partir de uma parede externa.",
            )
            self._chips_camada[chave] = (chip, cor)
        self._atualizar_chips_camada()

        ttk.Separator(barra, orient="vertical").pack(side="left", fill="y", padx=8)

        def _btn(nome_icone, comando, padx, titulo, detalhe):
            botao = criar_botao_ttk_so_icone(
                barra,
                nome_icone=nome_icone,
                command=comando,
                estilo=estilos.compacto,
                cor_icone=estilos.icone,
                refs=self._refs_icones,
            )
            botao.pack(side="left", padx=padx)
            vincular_tooltip(botao, f"{titulo}\n{detalhe}" if detalhe else titulo)
            return botao

        _btn(
            "analytics-outline",
            lambda: self._usar("polilinha"),
            (0, 0),
            "Polilinha",
            "Desenhe de ponto a ponto na camada ativa.\n"
            "Clique nos vértices ou digite a medida em metros e Enter.",
        )
        _btn(
            "square-outline",
            lambda: self._usar("retangulo"),
            (4, 4),
            "Retângulo",
            "Retângulo alinhado aos eixos na camada ativa:\n"
            "clique em dois cantos opostos.",
        )
        _btn(
            "cad-offset",
            lambda: self._usar_offset("segmento"),
            (4, 0),
            "Offset (lado)",
            "Parede paralela no estilo AutoCAD OFFSET.\n"
            "1) Clique a parede da Externa\n"
            "2) Digite a distância vazia (m) e Enter\n"
            "3) Digite ou arraste o comprimento da nova parede e Enter/clique.",
        )
        _btn(
            "cad-offset-rect",
            lambda: self._usar_offset("retangulo"),
            (4, 4),
            "Offset (retângulo)",
            "Hall retangular a partir de uma parede.\n"
            "1) Clique a parede da Externa\n"
            "2) Digite a distância vazia / profundidade (m) e Enter\n"
            "3) Estique o comprimento (digite ou arraste) e Enter/clique.",
        )
        _btn(
            "cad-move",
            self.iniciar_mover,
            (0, 12),
            "Mover",
            "Move as linhas selecionadas; as paredes vizinhas esticam.\n"
            "1) Selecione (clique ou janela)  2) Ponto base  3) Destino\n"
            "No destino, digite a distância (m) e Enter. Atalho: M.",
        )
        _btn(
            "checkmark-circle-outline",
            self.fechar_poligono,
            (0, 0),
            "Completar",
            "Fecha o polígono da camada ativa e calcula área/perímetro.\n"
            "Atalho: C, Enter ou botão direito.",
        )
        _btn(
            "arrow-undo-sharp",
            self.desfazer,
            (4, 0),
            "Desfazer",
            "Desfaz a última alteração (vértice, offset, mover, apagar…).\n"
            "Atalho: Ctrl+Z. Backspace remove só o último vértice ao desenhar.",
        )
        _btn(
            "arrow-redo-sharp",
            self.refazer,
            (4, 4),
            "Refazer",
            "Refaz o que foi desfeito.\nAtalho: Ctrl+Y.",
        )
        _btn(
            "trash-outline",
            self.limpar,
            (0, 0),
            "Limpar camada",
            "Apaga só a camada ativa (Externa ou Hall).\n"
            "Para apagar linhas selecionadas, use Delete.",
        )
        _btn(
            "expand",
            self._enquadrar,
            (12, 0),
            "Enquadrar",
            "Ajusta o zoom para ver o desenho inteiro.\nAtalho: Home.",
        )

        btn_ajuda = tk.Label(
            barra,
            text="?",
            bg=cores.fundo_destaque,
            fg=cores.titulo,
            font=("Arial", 9, "bold"),
            width=2,
            cursor="hand2",
            relief="solid",
            bd=1,
        )
        btn_ajuda.pack(side="left", padx=(10, 0))
        vincular_tooltip(
            btn_ajuda,
            "EXTERNA e HALL são dois polígonos no mesmo desenho\n"
            "Sem comando ativo (Esc), o clique seleciona linhas:\n"
            "  arrastar → direita: janela azul (só o que estiver inteiro dentro)\n"
            "  arrastar ← esquerda: cruzamento verde (tudo o que tocar)\n"
            "  Clique substitui · Shift+clique adiciona/remove · clique no vazio limpa\n"
            "  Shift+janela acrescenta à seleção · Esc limpa\n"
            "Seleção: M move · Delete apaga · quadrados azuis (grips) arrastam vértices\n"
            "Duplo clique numa linha: digitar o novo comprimento\n"
            "Offset: 1º distância vazia · 2º comprimento (digite ou arraste)\n"
            "Shift: trava H/V · F11: guias · digite medida + Enter\n"
            "Ctrl+Z / Ctrl+Y · roda: zoom · espaço+arraste: pan",
        )

        moldura = ttk.Frame(self)
        moldura.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self.canvas = tk.Canvas(
            moldura,
            bg="#fbfcfd",
            highlightthickness=1,
            highlightbackground=cores.borda_suave,
            cursor="crosshair",
            takefocus=True,
        )
        self.canvas.pack(fill="both", expand=True)

        rodape = ttk.Frame(self, padding=(8, 4))
        rodape.pack(fill="x")
        self._chips = {}
        dicas_chip = {
            "ortho": (
                "ORTO (F8): sugere horizontal e vertical quando o cursor\n"
                "se aproxima desses eixos. Não impede outros ângulos.\n"
                "Segure Shift para travar em 90°."
            ),
            "polar": (
                "POLAR (F10): sugere 0°, 45°, 90°… quando o cursor\n"
                "se aproxima desses ângulos. Fora disso o traço é livre."
            ),
            "osnap": (
                "SNAP (F3): o cursor gruda em extremidades, meios,\n"
                "interseções e o primeiro ponto (completar polígono)."
            ),
            "grade": "GRADE (F7): o ponto clicado alinha à malha de 10 cm.",
            "guias": (
                "GUIAS (F11): alinha com X/Y de pontos já desenhados\n"
                "(mesmo de longe) e sugere o mesmo comprimento de um lado anterior."
            ),
        }
        for chave, var, rotulo, tecla in (
            ("ortho", self.var_ortho, "ORTO", "F8"),
            ("polar", self.var_polar, "POLAR", "F10"),
            ("osnap", self.var_osnap, "SNAP", "F3"),
            ("grade", self.var_grade, "GRADE", "F7"),
            ("guias", self.var_guias, "GUIAS", "F11"),
        ):
            chip = tk.Label(
                rodape,
                text=f"{rotulo} {tecla}",
                padx=8,
                pady=2,
                font=("Segoe UI", 8, "bold"),
                cursor="hand2",
            )
            chip.pack(side="left", padx=(0, 4))
            chip.bind("<Button-1>", lambda _e, v=var, k=chave: self._clique_chip(v, k))
            var.trace_add("write", lambda *_a: self._atualizar_chips())
            vincular_tooltip(chip, dicas_chip[chave])
            self._chips[chave] = chip

        self._status = ttk.Label(rodape, text="")
        self._status.pack(side="right")

        self._atualizar_chips()
        self._ligar_canvas()

    def _ligar_canvas(self):
        c = self.canvas
        c.bind("<Button-1>", self._ao_clique)
        c.bind("<Double-Button-1>", self._ao_duplo_clique)
        c.bind("<B1-Motion>", self._ao_arraste)
        c.bind("<ButtonRelease-1>", self._ao_soltar)
        c.bind("<Button-2>", self._ao_pan_inicio)
        c.bind("<B2-Motion>", self._ao_pan_move)
        c.bind("<ButtonRelease-2>", self._ao_pan_fim)
        c.bind("<Button-3>", self._ao_direito)
        c.bind("<Motion>", self._ao_mover)
        c.bind("<Enter>", lambda e: c.focus_set())
        c.bind("<MouseWheel>", self._ao_roda)
        c.bind("<Button-4>", lambda e: self._zoom_em(e.x, e.y, 1.12))
        c.bind("<Button-5>", lambda e: self._zoom_em(e.x, e.y, 1 / 1.12))
        c.bind("<Key>", self._ao_tecla)
        c.bind("<Return>", self._ao_enter)
        c.bind("<KP_Enter>", self._ao_enter)
        c.bind("<Escape>", self._ao_escape)
        c.bind("<BackSpace>", self._ao_backspace)

    def _foco_em_campo(self) -> bool:
        w = self.winfo_toplevel().focus_get()
        if w is None:
            return False
        return w.winfo_class() in {"TEntry", "Entry", "TCombobox", "Text", "TSpinbox"}

    def _alternar(self, var: tk.BooleanVar, irmao: tk.BooleanVar | None = None):
        var.set(not var.get())
        if var.get() and irmao is not None:
            irmao.set(False)
        self._atualizar_chips()
        self._atualizar_volante()
        return "break"

    def _clique_chip(self, var: tk.BooleanVar, chave: str):
        self._alternar(var)

    def _set_shift(self, ativo: bool):
        self._shift = bool(ativo)
        self._atualizar_chips()
        self._atualizar_volante()
        return "break"

    def _ao_espaco(self, event):
        if self._foco_em_campo():
            return None
        self._set_espaco(True)
        return "break"

    def _set_espaco(self, ativo: bool):
        self._espaco = bool(ativo)
        try:
            self.canvas.config(cursor="fleur" if self._espaco or self._pan else "crosshair")
        except tk.TclError:
            pass
        return "break"

    def _ao_desfazer_tecla(self, event):
        if self._foco_em_campo():
            return None
        self.desfazer()
        return "break"

    def _ao_refazer_tecla(self, event):
        if self._foco_em_campo():
            return None
        self.refazer()
        return "break"

    def _ao_delete(self, event):
        if self._foco_em_campo():
            return None
        self.apagar_selecao()
        return "break"

    def _ao_home(self, event):
        if self._foco_em_campo():
            return None
        self._enquadrar()
        return "break"

    def _config_snap(self) -> ConfigSnap:
        return ConfigSnap(
            ortho=bool(self.var_ortho.get()),
            polar=bool(self.var_polar.get()),
            trava_orto=bool(self._shift),
            osnap=bool(self.var_osnap.get()),
            grade=bool(self.var_grade.get()),
            passo_grade=_PASSO_GRADE_SNAP,
            guias=bool(self.var_guias.get()),
        )

    def _mundo_para_tela(self, x: float, y: float) -> tuple[float, float]:
        return self._ox + x * self._zoom, self._oy - y * self._zoom

    def _tela_para_mundo(self, sx: float, sy: float) -> Ponto:
        return Ponto((sx - self._ox) / self._zoom, (self._oy - sy) / self._zoom)

    def _abertura_m(self) -> float:
        return _ABERTURA_PX / max(self._zoom, EPSILON_ZOOM)

    def _abertura_guia_m(self) -> float:
        return min(2.5, max(0.3, _ABERTURA_GUIA_PX / max(self._zoom, EPSILON_ZOOM)))

    def _origem_atual(self) -> Ponto | None:
        if self._ferramenta == "retangulo":
            return self._canto_ret
        if self._ferramenta == "mover":
            return self._mover_base
        if self._grip is not None:
            return self._grip[2]
        if self._ferramenta == "polilinha" and self.pontos and not self.fechado:
            return self.pontos[-1]
        return None

    def _vertices_snap(self) -> list[Ponto]:
        verts = list(self.pontos)
        outra = "hall" if self.camada_ativa == "externa" else "externa"
        verts.extend(self._camadas[outra]["pontos"])
        return verts

    def _segmentos_snap(self) -> list[tuple[Ponto, Ponto]]:
        segs = list(_pares(self.pontos, fechado=self.fechado))
        outra = "hall" if self.camada_ativa == "externa" else "externa"
        dados = self._camadas[outra]
        segs.extend(_pares(dados["pontos"], fechado=bool(dados["fechado"])))
        return segs

    def _resolver(self, sx: float, sy: float) -> ResultadoSnap:
        cursor = self._tela_para_mundo(sx, sy)
        return resolver_snap(
            cursor,
            origem=self._origem_atual(),
            vertices=self._vertices_snap(),
            segmentos=self._segmentos_snap(),
            config=self._config_snap(),
            abertura=self._abertura_m(),
            abertura_guia=self._abertura_guia_m(),
            pode_fechar=(
                self._ferramenta == "polilinha"
                and len(self.pontos) >= 3
                and not self.fechado
            ),
            ponto_fechamento=self.pontos[0] if self.pontos else None,
        )

    def _ativar_camada(self, camada: str):
        if camada not in self._camadas or camada == self.camada_ativa:
            self._atualizar_chips_camada()
            return
        self._cancelar_comandos()
        if self._ferramenta in ("mover", "retangulo"):
            self._ferramenta = "selecao"
        self.camada_ativa = camada
        self._atualizar_chips_camada()
        self._redesenhar_estatico()
        self._atualizar_volante()
        self._avisar_resultado()
        self._set_status(self._msg_inicio())

    def _atualizar_chips_camada(self):
        for chave, (chip, cor) in self._chips_camada.items():
            ativo = chave == self.camada_ativa
            chip.config(
                bg=cor if ativo else self._cores.fundo_cartao_off,
                fg="#ffffff" if ativo else self._cores.texto_suave,
            )

    def _usar_offset(self, modo: str):
        externa = self._camadas["externa"]["pontos"]
        if len(externa) < 2:
            self._set_status("Desenhe e complete a Externa antes de usar Offset.")
            return
        self._cancelar_comandos()
        self._selecao.clear()
        self._offset_hall_backup = {
            "pontos": list(self._camadas["hall"]["pontos"]),
            "fechado": bool(self._camadas["hall"]["fechado"]),
            "estado": self._estado(),
        }
        self._ferramenta = f"offset_{modo}"
        self._offset_modo = modo
        self._offset_fase = "parede"
        self._buffer = ""
        self._canto_ret = None
        self._redesenhar_estatico()
        self._atualizar_volante()
        self._set_status(
            f"Offset ({'retângulo' if modo == 'retangulo' else 'lado'}): "
            "clique uma parede da EXTERNA."
        )

    def _segmentos_externa(self) -> list[tuple[Ponto, Ponto]]:
        dados = self._camadas["externa"]
        return _pares(dados["pontos"], fechado=bool(dados["fechado"]))

    def _geometria_offset_atual(
        self, *, distancia: float | None = None, comprimento: float | None = None
    ):
        if self._offset_seg is None:
            return None
        a, b = self._offset_seg
        dist = self._offset_dist if distancia is None else distancia
        comp = self._offset_comp if comprimento is None else comprimento
        lado = self._offset_lado
        if dist is None or dist <= 0 or comp is None or comp <= 0 or lado is None:
            return None
        if self._offset_modo == "retangulo":
            return list(offset_retangulo_comprimento(a, b, dist, lado, comp))
        a2, b2 = offset_segmento_comprimento(a, b, dist, lado, comp)
        return [a2, b2]

    def _atualizar_rascunho_offset(self):
        pts = self._geometria_offset_atual()
        if pts is None:
            return
        self.camada_ativa = "hall"
        self.pontos = pts
        self.fechado = self._offset_modo == "retangulo" and len(pts) >= 3
        self._atualizar_chips_camada()
        self._redesenhar_estatico()
        self._atualizar_volante()
        self._avisar_resultado()

    def _confirmar_distancia_offset(self, metros: float, cursor: Ponto | None = None):
        if self._offset_seg is None or metros <= 0:
            return
        a, b = self._offset_seg
        ref = cursor or self._tela_para_mundo(*self._cursor_tela)
        self._offset_lado = lado_do_ponto(ref, a, b)
        self._offset_dist = metros
        self._offset_comp = max(0.1, distancia(a, b))
        self._offset_fase = "comprimento"
        self._buffer = ""
        self._atualizar_rascunho_offset()
        self._set_status(
            "Distância ok. Agora o COMPRIMENTO da parede: digite (m) e Enter, "
            "arraste o mouse ou clique para confirmar."
        )

    def _confirmar_comprimento_offset(self, comprimento: float | None = None):
        if self._offset_fase != "comprimento":
            return
        if comprimento is not None:
            if comprimento <= 0:
                self._set_status("Informe um comprimento maior que zero.")
                return
            self._offset_comp = comprimento
        if self._offset_comp is None or self._offset_comp <= 0:
            self._set_status("Defina o comprimento (digite ou arraste).")
            return
        self._atualizar_rascunho_offset()
        modo = self._offset_modo
        if self._offset_hall_backup is not None:
            self._registrar(self._offset_hall_backup["estado"])
        self._limpar_estado_offset(restaurar_hall=False)
        self._ferramenta = "selecao" if modo == "retangulo" else "polilinha"
        self._buffer = ""
        self._atualizar_chips_camada()
        self._redesenhar_estatico()
        self._atualizar_volante()
        self._avisar_resultado()
        if modo == "retangulo":
            self._set_status(
                "Hall retangular criado. Limpe o Hall para refazer ou continue editando."
            )
        else:
            self._set_status(
                "Parede do hall criada com o comprimento definido. "
                "Continue a polilinha ou Complete."
            )

    def _ao_configurar(self, event):
        if event.widget is not self.canvas or event.width < 20:
            return
        if self._enquadrar_pendente and event.width >= 80 and event.height >= 80:
            self._concluir_enquadramento()
            return
        if not self._vista_ok:
            self._ox = 72.0
            self._oy = event.height - 48.0
            self._vista_ok = True
        self._redesenhar_estatico()
        self._atualizar_volante()

    def _ao_clique(self, event):
        self.canvas.focus_set()
        if self._espaco:
            self._ao_pan_inicio(event)
            return
        if self._ferramenta.startswith("offset"):
            cursor = self._tela_para_mundo(event.x, event.y)
            if self._offset_fase == "comprimento":
                if self._buffer:
                    try:
                        self._confirmar_comprimento_offset(
                            parse_decimal_br(self._buffer)
                        )
                    except ValueError:
                        self._set_status("Comprimento inválido.")
                    return
                self._offset_comp = comprimento_ao_longo(
                    self._offset_seg[0], self._offset_seg[1], cursor
                )
                self._confirmar_comprimento_offset()
                return
            achado = segmento_mais_proximo(
                cursor,
                self._segmentos_externa(),
                max_dist=max(0.8, self._abertura_m() * 3),
            )
            if achado is None:
                self._set_status("Clique mais perto de uma parede da Externa.")
                return
            _i, a, b, _d = achado
            self._offset_seg = (a, b)
            self._offset_fase = "distancia"
            self._ultimo_snap = ResultadoSnap(cursor, "livre")
            self._atualizar_volante()
            self._set_status(
                "Parede selecionada. Digite a DISTÂNCIA VAZIA (m) e Enter "
                "(o lado segue o cursor)."
            )
            return
        if self._ferramenta == "selecao":
            self._clique_selecao(event)
            return
        if self._ferramenta == "mover":
            self._clique_mover(event)
            return
        if self.fechado:
            self._set_status(
                "Polígono desta camada completo. Limpar, Desfazer ou troque de camada."
            )
            return
        snap = self._resolver(event.x, event.y)
        self._ultimo_snap = snap
        if self._ferramenta == "retangulo":
            self._clique_retangulo(snap.ponto)
            return
        self._clique_polilinha(snap)

    # ------------------------------------------------------------------
    # Seleção (estado sem comando), grips, mover, apagar e cotas
    # ------------------------------------------------------------------

    def _linha_em(self, sx: float, sy: float, tol_px: float = _TOL_LINHA_PX):
        """Linha (camada, índice) mais próxima do ponto de tela, ou None."""
        cursor = self._tela_para_mundo(sx, sy)
        melhor = None
        for nome, dados in self._camadas.items():
            pts = dados["pontos"]
            n = len(pts)
            for i in indices_segmentos(n, bool(dados["fechado"])):
                ia, ib = extremos_segmento(n, i)
                pe = ponto_no_segmento(cursor, pts[ia], pts[ib])
                d = distancia(cursor, pe) * self._zoom
                if d <= tol_px and (melhor is None or d < melhor[0]):
                    melhor = (d, (nome, i))
        return melhor[1] if melhor else None

    def _grips(self) -> set[tuple[str, int]]:
        return vertices_da_selecao(self._camadas, self._selecao)

    def _grip_em(self, sx: float, sy: float):
        for nome, idx in self._grips():
            p = self._camadas[nome]["pontos"][idx]
            gx, gy = self._mundo_para_tela(p.x, p.y)
            if abs(gx - sx) <= _TOL_GRIP_PX and abs(gy - sy) <= _TOL_GRIP_PX:
                return nome, idx
        return None

    def _clique_selecao(self, event):
        self._press_xy = (event.x, event.y)
        shift = bool(event.state & 0x0001)
        if self._grip is not None:
            self._soltar_grip(self._resolver(event.x, event.y).ponto)
            return
        if self._janela_sel is not None:
            self._janela_sel[2], self._janela_sel[3] = event.x, event.y
            self._concluir_janela(shift)
            return
        grip = self._grip_em(event.x, event.y)
        if grip is not None:
            nome, idx = grip
            self._grip = (nome, idx, self._camadas[nome]["pontos"][idx])
            self._grip_por_arraste = False
            self._ultimo_snap = self._resolver(event.x, event.y)
            self._redesenhar_estatico()
            self._atualizar_volante()
            self._set_status(
                "Grip ativo: clique o novo lugar do vértice ou digite a distância (m) e Enter. "
                "Esc cancela."
            )
            return
        linha = self._linha_em(event.x, event.y)
        if linha is not None:
            if shift:
                if linha in self._selecao:
                    self._selecao.discard(linha)
                else:
                    self._selecao.add(linha)
            else:
                self._selecao = {linha}
            self._redesenhar_estatico()
            self._atualizar_volante()
            self._status_selecao()
            return
        self._janela_sel = [event.x, event.y, event.x, event.y]
        self._janela_por_arraste = False
        self._atualizar_volante()

    def _concluir_janela(self, com_shift: bool):
        sx0, sy0, sx1, sy1 = self._janela_sel
        self._janela_sel = None
        self._janela_por_arraste = False
        if abs(sx1 - sx0) < 2 and abs(sy1 - sy0) < 2:
            if not com_shift:
                self._selecao.clear()
            self._redesenhar_estatico()
            self._atualizar_volante()
            self._status_selecao()
            return
        achadas = selecionar_por_retangulo(
            self._camadas,
            self._tela_para_mundo(sx0, sy0),
            self._tela_para_mundo(sx1, sy1),
            cruzamento=sx1 < sx0,
        )
        if com_shift:
            self._selecao |= achadas
        else:
            self._selecao = set(achadas)
        self._redesenhar_estatico()
        self._atualizar_volante()
        self._status_selecao()

    def _status_selecao(self):
        n = len(self._selecao)
        if not n:
            self._set_status(self._msg_inicio())
            return
        total = sum(
            distancia(*self._extremos(nome, i)) for nome, i in self._selecao
        )
        self._set_status(
            f"{n} linha(s) · {formatar_decimal_br(total, 2)} m"
        )

    def _extremos(self, nome: str, i: int) -> tuple[Ponto, Ponto]:
        pts = self._camadas[nome]["pontos"]
        ia, ib = extremos_segmento(len(pts), i)
        return pts[ia], pts[ib]

    def _soltar_grip(self, destino: Ponto):
        if self._grip is None:
            return
        nome, idx, original = self._grip
        self._grip = None
        self._grip_por_arraste = False
        self._buffer = ""
        if quase_iguais(destino, original):
            self._redesenhar_estatico()
            self._atualizar_volante()
            self._status_selecao()
            return
        self._registrar()
        self._camadas = mover_vertices(
            self._camadas, [(nome, idx)], destino.x - original.x, destino.y - original.y
        )
        self._redesenhar_estatico()
        self._atualizar_volante()
        self._avisar_resultado()
        self._set_status("Vértice movido. Ctrl+Z desfaz.")

    def iniciar_mover(self):
        if self._ferramenta.startswith("offset") or self._ferramenta in (
            "polilinha",
            "retangulo",
        ):
            self._cancelar_comandos()
            self._ferramenta = "selecao"
        if not self._selecao:
            self._redesenhar_estatico()
            self._atualizar_volante()
            self._set_status(
                "Mover: primeiro selecione linhas (clique ou janela) e pressione M."
            )
            return
        self._grip = None
        self._janela_sel = None
        self._ferramenta = "mover"
        self._mover_base = None
        self._buffer = ""
        self.canvas.focus_set()
        self._atualizar_volante()
        self._set_status("Mover: clique o PONTO BASE (use o snap).")

    def _clique_mover(self, event):
        snap = self._resolver(event.x, event.y)
        self._ultimo_snap = snap
        if self._mover_base is None:
            self._mover_base = snap.ponto
            self._atualizar_volante()
            self._set_status(
                "Mover: clique o DESTINO ou digite a distância (m) e Enter "
                "(a direção segue o cursor)."
            )
            return
        self._aplicar_mover(snap.ponto)

    def _camadas_movidas(self, destino: Ponto):
        base = self._mover_base
        vertices = vertices_da_selecao(self._camadas, self._selecao)
        return mover_vertices(
            self._camadas, vertices, destino.x - base.x, destino.y - base.y
        )

    def _aplicar_mover(self, destino: Ponto):
        if self._mover_base is None:
            return
        if not quase_iguais(destino, self._mover_base):
            self._registrar()
            self._camadas = self._camadas_movidas(destino)
            msg = "Linhas movidas. Ctrl+Z desfaz."
        else:
            msg = "Destino igual à base: nada foi movido."
        self._mover_base = None
        self._buffer = ""
        self._ferramenta = "selecao"
        self._selecao.clear()
        self._redesenhar_estatico()
        self._atualizar_volante()
        self._avisar_resultado()
        self._set_status(msg)

    def apagar_selecao(self):
        if self._ferramenta not in ("selecao",) or not self._selecao:
            self._set_status("Selecione linhas para apagar (clique ou janela).")
            return
        novas = copiar_camadas(self._camadas)
        for nome, dados in novas.items():
            indices = [i for camada, i in self._selecao if camada == nome]
            if not indices:
                continue
            resultado = apagar_segmentos(dados["pontos"], bool(dados["fechado"]), indices)
            if resultado is None:
                rotulo = "Externa" if nome == "externa" else "Hall"
                self._set_status(
                    f"{rotulo}: apagar essas linhas dividiria o desenho em partes. "
                    "Apague linhas vizinhas ou a camada inteira."
                )
                return
            dados["pontos"], dados["fechado"] = resultado
        self._registrar()
        self._camadas = novas
        n = len(self._selecao)
        self._selecao.clear()
        self._hover_linha = None
        self._redesenhar_estatico()
        self._atualizar_volante()
        self._avisar_resultado()
        self._set_status(f"{n} linha(s) apagada(s). Ctrl+Z desfaz.")

    def _ao_duplo_clique(self, event):
        if self._ferramenta != "selecao" or self._espaco:
            return None
        self._janela_sel = None
        linha = self._linha_em(event.x, event.y, tol_px=_TOL_LINHA_PX + 6)
        if linha is None:
            return "break"
        self._abrir_editor_cota(*linha)
        return "break"

    def _abrir_editor_cota(self, nome: str, indice: int):
        self._fechar_editor_cota()
        a, b = self._extremos(nome, indice)
        atual = distancia(a, b)
        xm, ym = self._mundo_para_tela((a.x + b.x) / 2, (a.y + b.y) / 2)
        var = tk.StringVar(value=formatar_decimal_br(atual, 2))
        entrada = tk.Entry(
            self.canvas,
            textvariable=var,
            width=9,
            justify="center",
            font=("Segoe UI", 9, "bold"),
            relief="solid",
            bd=1,
        )
        item = self.canvas.create_window(xm, ym - 14, window=entrada)
        self._editor_cota = (entrada, item, nome, indice)

        def aplicar(_e=None):
            texto = var.get()
            self._fechar_editor_cota()
            try:
                metros = parse_decimal_br(texto)
            except ValueError:
                self._set_status("Comprimento inválido.")
                return "break"
            self._aplicar_cota(nome, indice, metros)
            return "break"

        def cancelar(_e=None):
            self._fechar_editor_cota()
            self._set_status("Edição de cota cancelada.")
            return "break"

        entrada.bind("<Return>", aplicar)
        entrada.bind("<KP_Enter>", aplicar)
        entrada.bind("<Escape>", cancelar)
        entrada.bind("<FocusOut>", lambda _e: self._fechar_editor_cota())
        entrada.focus_set()
        entrada.select_range(0, "end")
        self._set_status(
            "Digite o novo comprimento (m) e Enter. A linha seguinte acompanha; Esc cancela."
        )

    def _fechar_editor_cota(self):
        editor = self._editor_cota
        self._editor_cota = None
        if editor is None:
            return
        entrada, item, _nome, _indice = editor
        try:
            self.canvas.delete(item)
            entrada.destroy()
            self.canvas.focus_set()
        except tk.TclError:
            pass

    def _aplicar_cota(self, nome: str, indice: int, metros: float):
        if metros <= 0:
            self._set_status("Informe um comprimento maior que zero.")
            return
        dados = self._camadas[nome]
        n = len(dados["pontos"])
        if indice not in indices_segmentos(n, bool(dados["fechado"])):
            return
        self._registrar()
        dados["pontos"] = ajustar_comprimento(
            dados["pontos"], bool(dados["fechado"]), indice, metros
        )
        self._redesenhar_estatico()
        self._atualizar_volante()
        self._avisar_resultado()
        self._set_status(
            f"Linha ajustada para {formatar_decimal_br(metros, 2)} m. Ctrl+Z desfaz."
        )

    def _clique_polilinha(self, snap: ResultadoSnap):
        if (
            snap.tipo == "primeiro"
            and len(self.pontos) >= 3
            and quase_iguais(snap.ponto, self.pontos[0])
        ):
            self.fechar_poligono()
            return
        if self.pontos and quase_iguais(snap.ponto, self.pontos[-1]):
            return
        self._registrar()
        self.pontos.append(snap.ponto)
        self._buffer = ""
        self._redesenhar_estatico()
        self._atualizar_volante()
        self._avisar_resultado()
        n = len(self.pontos)
        if n == 1:
            self._set_status("Próximo ponto. Digite a medida (m) e Enter, ou clique.")
        else:
            self._set_status("Continue, clique no primeiro ponto ou Completar.")

    def _clique_retangulo(self, ponto: Ponto):
        if self._canto_ret is None:
            self._canto_ret = ponto
            self.pontos = [ponto]
            self._set_status("Clique o canto oposto do retângulo.")
            self._redesenhar_estatico()
            self._atualizar_volante()
            return
        if quase_iguais(ponto, self._canto_ret):
            return
        anterior = self._estado()
        anterior["camadas"][self.camada_ativa] = {"pontos": [], "fechado": False}
        self._registrar(anterior)
        self.pontos = list(retangulo_eixos(self._canto_ret, ponto))
        self._canto_ret = None
        self.fechado = True
        self._buffer = ""
        self._ferramenta = "selecao"
        self._redesenhar_estatico()
        self._atualizar_volante()
        self._avisar_resultado()
        self._set_status("Retângulo completo. Aplique a metragem ou limpe para outro desenho.")

    def _ao_mover(self, event):
        self._cursor_tela = (event.x, event.y)
        if self._pan is not None:
            self._ao_pan_move(event)
            return
        if self._ferramenta == "selecao" and self._grip is None:
            if self._janela_sel is not None:
                self._janela_sel[2], self._janela_sel[3] = event.x, event.y
            self._hover_linha = (
                None if self._janela_sel is not None else self._linha_em(event.x, event.y)
            )
            self._ultimo_snap = None
            self._atualizar_volante()
            return
        if (
            self._ferramenta.startswith("offset")
            and self._offset_fase == "comprimento"
            and self._offset_seg is not None
            and not self._buffer
        ):
            cursor = self._tela_para_mundo(event.x, event.y)
            self._offset_comp = comprimento_ao_longo(
                self._offset_seg[0], self._offset_seg[1], cursor
            )
            self._atualizar_rascunho_offset()
            return
        self._ultimo_snap = self._resolver(event.x, event.y)
        self._atualizar_volante()

    def _arrastou(self, event) -> bool:
        if self._press_xy is None:
            return False
        x0, y0 = self._press_xy
        return math.hypot(event.x - x0, event.y - y0) >= _ARRASTE_MIN_PX

    def _ao_arraste(self, event):
        if self._pan is not None or self._espaco:
            self._ao_pan_move(event)
            return
        if self._ferramenta != "selecao":
            self._ao_mover(event)
            return
        if self._grip is not None:
            if self._arrastou(event):
                self._grip_por_arraste = True
            self._cursor_tela = (event.x, event.y)
            self._ultimo_snap = self._resolver(event.x, event.y)
            self._atualizar_volante()
            return
        if self._janela_sel is not None:
            if self._arrastou(event):
                self._janela_por_arraste = True
            self._janela_sel[2], self._janela_sel[3] = event.x, event.y
            self._atualizar_volante()

    def _ao_soltar(self, event):
        if self._pan is not None:
            self._ao_pan_fim()
            return
        if self._ferramenta != "selecao":
            return
        if self._grip is not None and self._grip_por_arraste:
            self._soltar_grip(self._resolver(event.x, event.y).ponto)
        elif self._janela_sel is not None and self._janela_por_arraste:
            self._janela_sel[2], self._janela_sel[3] = event.x, event.y
            self._concluir_janela(bool(event.state & 0x0001))
        elif self._janela_sel is not None:
            self._janela_sel = None
            self._janela_por_arraste = False
            if not (event.state & 0x0001) and self._selecao:
                self._selecao.clear()
                self._redesenhar_estatico()
            self._atualizar_volante()
            self._status_selecao()
        self._press_xy = None

    def _ao_pan_inicio(self, event):
        self._pan = (event.x, event.y, self._ox, self._oy)
        self.canvas.config(cursor="fleur")
        return "break"

    def _ao_pan_move(self, event):
        if self._pan is None:
            return
        x0, y0, ox, oy = self._pan
        self._ox = ox + (event.x - x0)
        self._oy = oy + (event.y - y0)
        self._redesenhar_estatico()
        self._atualizar_volante()

    def _ao_pan_fim(self, _event=None):
        self._pan = None
        self.canvas.config(cursor="fleur" if self._espaco else "crosshair")

    def _ao_direito(self, _event):
        self.canvas.focus_set()
        if self._ferramenta.startswith("offset"):
            self._cancelar_offset()
            return "break"
        if self._ferramenta in ("selecao", "mover"):
            return self._ao_escape()
        if self._ferramenta == "retangulo" and self._canto_ret is not None:
            self._canto_ret = None
            self.pontos.clear()
            self._redesenhar_estatico()
            self._atualizar_volante()
            self._set_status("Retângulo cancelado.")
            return "break"
        if len(self.pontos) >= 3 and not self.fechado:
            self.fechar_poligono()
        elif self.pontos and not self.fechado:
            self._desfazer()
        return "break"

    def _ao_roda(self, event):
        fator = 1.12 if event.delta > 0 else 1 / 1.12
        self._zoom_em(event.x, event.y, fator)
        return "break"

    def _zoom_em(self, sx, sy, fator):
        mundo = self._tela_para_mundo(sx, sy)
        novo = min(_ZOOM_MAX, max(_ZOOM_MIN, self._zoom * fator))
        self._zoom = novo
        self._ox = sx - mundo.x * self._zoom
        self._oy = sy + mundo.y * self._zoom
        self._redesenhar_estatico()
        self._atualizar_volante()

    def _ao_tecla(self, event):
        ch = event.char or ""
        if ch and ch in "0123456789,.":
            digitando_offset = (
                self._ferramenta.startswith("offset")
                and self._offset_fase in ("distancia", "comprimento")
            )
            digitando_edicao = (
                self._ferramenta == "mover" and self._mover_base is not None
            ) or self._grip is not None
            desenhando = (
                self._ferramenta in ("polilinha", "retangulo")
                and self.pontos
                and not self.fechado
            )
            if not (digitando_offset or digitando_edicao or desenhando):
                return "break"
            if ch in ",." and ("," in self._buffer or "." in self._buffer):
                return "break"
            self._buffer += "," if ch == "." else ch
            if digitando_offset and self._offset_fase == "comprimento":
                try:
                    self._offset_comp = parse_decimal_br(self._buffer)
                    if self._offset_comp > 0:
                        self._atualizar_rascunho_offset()
                        return "break"
                except ValueError:
                    pass
            self._atualizar_volante()
            return "break"
        tecla = (event.keysym or "").lower()
        if tecla == "c" and not self._buffer and self._ferramenta == "polilinha":
            self.fechar_poligono()
            return "break"
        if tecla == "m" and not self._buffer and self._ferramenta == "selecao":
            self.iniciar_mover()
            return "break"
        return None

    def _ao_enter(self, _event=None):
        if self._ferramenta.startswith("offset"):
            if self._offset_fase == "comprimento":
                if self._buffer:
                    try:
                        metros = parse_decimal_br(self._buffer)
                    except ValueError:
                        self._set_status("Comprimento inválido.")
                        return "break"
                    self._confirmar_comprimento_offset(metros)
                else:
                    self._confirmar_comprimento_offset()
                return "break"
            if self._buffer:
                self._confirmar_distancia()
                return "break"
            self._set_status("Digite a distância vazia (m) e Enter.")
            return "break"
        if self._buffer:
            self._confirmar_distancia()
            return "break"
        if self._ferramenta == "polilinha":
            self.fechar_poligono()
        return "break"

    def _cancelar_offset(self):
        self._buffer = ""
        self._limpar_estado_offset(restaurar_hall=True)
        self._atualizar_chips_camada()
        self._redesenhar_estatico()
        self._atualizar_volante()
        self._avisar_resultado()
        self._set_status("Offset cancelado.")

    def _ao_escape(self, _event=None):
        if self._ferramenta.startswith("offset"):
            if self._buffer:
                self._buffer = ""
                self._atualizar_volante()
                if self._offset_fase == "comprimento":
                    self._set_status(
                        "Valor digitado cancelado. Arraste, digite outro ou Esc."
                    )
                else:
                    self._set_status(
                        "Distância cancelada. Digite outra ou Esc de novo."
                    )
                return "break"
            if self._offset_fase == "comprimento":
                # Volta para redigitar a distância vazia.
                if self._offset_hall_backup is not None:
                    self._camadas["hall"] = {
                        "pontos": list(self._offset_hall_backup["pontos"]),
                        "fechado": bool(self._offset_hall_backup["fechado"]),
                    }
                self._offset_fase = "distancia"
                self._offset_dist = None
                self._offset_lado = None
                self._offset_comp = None
                self._redesenhar_estatico()
                self._atualizar_volante()
                self._avisar_resultado()
                self._set_status(
                    "Comprimento cancelado. Digite de novo a distância vazia (m)."
                )
                return "break"
            self._cancelar_offset()
            return "break"
        if self._editor_cota is not None:
            self._fechar_editor_cota()
            return "break"
        if self._buffer:
            self._buffer = ""
            self._atualizar_volante()
            self._set_status("Medida digitada cancelada.")
            return "break"
        if self._ferramenta == "mover":
            self._mover_base = None
            self._ferramenta = "selecao"
            self._atualizar_volante()
            self._set_status("Mover cancelado. A seleção foi mantida.")
            return "break"
        if self._grip is not None:
            self._grip = None
            self._grip_por_arraste = False
            self._redesenhar_estatico()
            self._atualizar_volante()
            self._status_selecao()
            return "break"
        if self._janela_sel is not None:
            self._janela_sel = None
            self._atualizar_volante()
            self._status_selecao()
            return "break"
        if self._canto_ret is not None:
            self._canto_ret = None
            self.pontos.clear()
        if self._ferramenta in ("polilinha", "retangulo"):
            # Como no AutoCAD: Esc encerra o comando e mantém o que foi desenhado.
            self._ferramenta = "selecao"
            self._redesenhar_estatico()
            self._atualizar_volante()
            self._set_status("")
            return "break"
        if self._selecao:
            self._selecao.clear()
            self._redesenhar_estatico()
            self._atualizar_volante()
            self._set_status(self._msg_inicio())
        return "break"

    def _ao_backspace(self, _event=None):
        if self._buffer:
            self._buffer = self._buffer[:-1]
            self._atualizar_volante()
            return "break"
        if self._ferramenta in ("polilinha", "retangulo"):
            self._desfazer()
        return "break"

    def _confirmar_distancia(self):
        if self._ferramenta.startswith("offset"):
            if self._offset_seg is None or self._offset_fase not in (
                "distancia",
                "parede",
            ):
                self._set_status("Selecione antes uma parede da Externa.")
                return
            try:
                metros = parse_decimal_br(self._buffer)
            except ValueError:
                self._set_status("Distância inválida.")
                return
            if metros <= 0:
                self._set_status("Informe uma distância maior que zero.")
                return
            self._confirmar_distancia_offset(metros)
            return
        origem = self._origem_atual()
        editando = self._ferramenta == "mover" or self._grip is not None
        if origem is None or (self.fechado and not editando):
            self._buffer = ""
            return
        try:
            metros = parse_decimal_br(self._buffer)
        except ValueError:
            self._set_status("Medida inválida.")
            return
        if metros <= 0:
            self._set_status("Informe um comprimento maior que zero.")
            return
        destino = self._ultimo_snap.ponto if self._ultimo_snap else origem
        if quase_iguais(destino, origem):
            self._set_status("Aponte o cursor na direção desejada antes do Enter.")
            return
        ponto = ponto_na_direcao(origem, destino, metros)
        self._buffer = ""
        if self._ferramenta == "mover":
            self._aplicar_mover(ponto)
            return
        if self._grip is not None:
            self._soltar_grip(ponto)
            return
        if self._ferramenta == "retangulo":
            self._clique_retangulo(ponto)
            return
        snap_falso = ResultadoSnap(ponto, "orto")
        self._clique_polilinha(snap_falso)

    def _desfazer(self):
        """Backspace ao desenhar: tira o último vértice (ou reabre o polígono)."""
        if self._ferramenta == "retangulo" and self._canto_ret is not None:
            self._canto_ret = None
            self.pontos.clear()
        elif self.fechado:
            self._registrar()
            self.fechado = False
            self._ferramenta = "polilinha"
            self._redesenhar_estatico()
            self._atualizar_volante()
            self._avisar_resultado()
            self._set_status("Polígono reaberto. Continue ou complete de novo.")
            return
        elif self.pontos:
            self._registrar()
            self.pontos.pop()
        self._buffer = ""
        self._redesenhar_estatico()
        self._atualizar_volante()
        self._avisar_resultado()

    def fechar_poligono(self):
        if self.fechado:
            return
        if len(self.pontos) < 3:
            self._set_status("São necessários pelo menos 3 pontos para completar.")
            return
        self._registrar()
        self.fechado = True
        self._buffer = ""
        self._ferramenta = "selecao"
        self._redesenhar_estatico()
        self._atualizar_volante()
        self._avisar_resultado()
        self._set_status("Polígono completo. Aplique a metragem ou limpe para outro desenho.")

    def _usar(self, ferramenta: str):
        self._cancelar_comandos()
        self._selecao.clear()
        nome = "Externa" if self.camada_ativa == "externa" else "Hall"
        if self.fechado:
            self._ferramenta = "selecao"
            self._redesenhar_estatico()
            self._atualizar_volante()
            self._set_status(
                f"A camada {nome} já tem um polígono completo. "
                "Use Limpar camada, edite as linhas ou troque de camada."
            )
            return
        if ferramenta == "retangulo" and self.pontos:
            self._ferramenta = "selecao"
            self._redesenhar_estatico()
            self._atualizar_volante()
            self._set_status(
                f"A camada {nome} já tem linhas. Limpe-a para desenhar um retângulo."
            )
            return
        self._ferramenta = ferramenta
        self._redesenhar_estatico()
        self._atualizar_volante()
        self._avisar_resultado()
        if ferramenta == "retangulo":
            self._set_status("Retângulo na camada ativa: clique dois cantos opostos.")
        elif self.pontos:
            self._set_status("Polilinha: continuando do último ponto da camada.")
        else:
            self._set_status(
                "Polilinha na camada ativa. Polar sugere 45°/90° sem bloquear."
            )

    def enquadrar_quando_visivel(self):
        """Enquadra o desenho assim que o canvas tiver tamanho real."""
        self._enquadrar_pendente = True
        if self._aplicar_enquadramento():
            self._enquadrar_pendente = False
            return
        self._agendar_enquadramento(0)

    def _agendar_enquadramento(self, tentativas: int):
        if self._job_enquadrar is not None:
            try:
                self.after_cancel(self._job_enquadrar)
            except (tk.TclError, ValueError):
                pass
            self._job_enquadrar = None
        if tentativas > 30 or not self._enquadrar_pendente:
            return
        self._job_enquadrar = self.after(
            40, lambda: self._tentar_enquadrar(tentativas)
        )

    def _tentar_enquadrar(self, tentativas: int):
        self._job_enquadrar = None
        if not self._enquadrar_pendente:
            return
        if self._aplicar_enquadramento():
            self._enquadrar_pendente = False
            return
        self._agendar_enquadramento(tentativas + 1)

    def _concluir_enquadramento(self):
        if self._aplicar_enquadramento():
            self._enquadrar_pendente = False

    def _enquadrar(self):
        self._enquadrar_pendente = False
        self._aplicar_enquadramento()

    def _aplicar_enquadramento(self) -> bool:
        try:
            w = int(self.canvas.winfo_width())
            h = int(self.canvas.winfo_height())
        except tk.TclError:
            return False
        if w < 80 or h < 80:
            return False
        todos: list[Ponto] = []
        for dados in self._camadas.values():
            todos.extend(dados["pontos"])
        if len(todos) < 1:
            self._ox, self._oy, self._zoom = 72.0, h - 48.0, 40.0
            self._vista_ok = True
            self._redesenhar_estatico()
            return True
        xs = [p.x for p in todos]
        ys = [p.y for p in todos]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        dx = max(maxx - minx, 1.0)
        dy = max(maxy - miny, 1.0)
        margem = 56
        zoom = min((w - 2 * margem) / dx, (h - 2 * margem) / dy)
        self._zoom = min(_ZOOM_MAX, max(_ZOOM_MIN, zoom))
        cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
        self._ox = w / 2.0 - cx * self._zoom
        self._oy = h / 2.0 + cy * self._zoom
        self._vista_ok = True
        self._redesenhar_estatico()
        self._atualizar_volante()
        return True

    def _avisar_resultado(self):
        if self.on_resultado:
            self.on_resultado(self.resultados())

    def _set_status(self, texto: str):
        self._status.config(text=texto)

    def _atualizar_chips(self):
        cores = self._cores
        estados = {
            "ortho": bool(self.var_ortho.get()) or bool(self._shift),
            "polar": self.var_polar.get(),
            "osnap": self.var_osnap.get(),
            "grade": self.var_grade.get(),
            "guias": self.var_guias.get(),
        }
        for chave, chip in self._chips.items():
            ligado = estados[chave]
            chip.config(
                bg=cores.titulo if ligado else cores.fundo_cartao_off,
                fg="#ffffff" if ligado else cores.texto_suave,
            )

    def _redesenhar_estatico(self):
        c = self.canvas
        w, h = c.winfo_width(), c.winfo_height()
        if w < 4 or h < 4:
            return
        c.delete("estatico")
        cores = self._cores
        c.create_rectangle(0, 0, w, h, fill="#fbfcfd", outline="", tags="estatico")
        passo = passo_grade_visivel(self._zoom)
        x0, y0 = self._tela_para_mundo(0, h).x, self._tela_para_mundo(0, h).y
        x1, y1 = self._tela_para_mundo(w, 0).x, self._tela_para_mundo(w, 0).y
        minx, maxx = min(x0, x1), max(x0, x1)
        miny, maxy = min(y0, y1), max(y0, y1)
        gx = _alinha_grade(minx, passo)
        while gx <= maxx:
            sx, _ = self._mundo_para_tela(gx, 0)
            major = _eh_major(gx, passo)
            cor = "#c5d6de" if major else "#e8eef1"
            c.create_line(sx, 0, sx, h, fill=cor, tags="estatico")
            if major:
                c.create_text(
                    sx + 4, h - 12, text=_fmt_eixo(gx), anchor="w", fill="#7a8a94",
                    font=("Segoe UI", 7), tags="estatico",
                )
            gx += passo
        gy = _alinha_grade(miny, passo)
        while gy <= maxy:
            _, sy = self._mundo_para_tela(0, gy)
            major = _eh_major(gy, passo)
            cor = "#c5d6de" if major else "#e8eef1"
            c.create_line(0, sy, w, sy, fill=cor, tags="estatico")
            if major:
                c.create_text(
                    6, sy - 4, text=_fmt_eixo(gy), anchor="sw", fill="#7a8a94",
                    font=("Segoe UI", 7), tags="estatico",
                )
            gy += passo
        ox, oy = self._mundo_para_tela(0, 0)
        c.create_line(0, oy, w, oy, fill=cores.titulo, width=1, tags="estatico")
        c.create_line(ox, 0, ox, h, fill=cores.titulo, width=1, tags="estatico")

        for nome, cor_linha, fill_poly in (
            ("externa", COR_EXTERNA, "#d7e8f2"),
            ("hall", COR_HALL, "#c8e6c9"),
        ):
            dados = self._camadas[nome]
            pts = dados["pontos"]
            fechado = bool(dados["fechado"])
            ativa = nome == self.camada_ativa
            if fechado and len(pts) >= 3:
                coords = []
                for p in pts:
                    sx, sy = self._mundo_para_tela(p.x, p.y)
                    coords.extend((sx, sy))
                c.create_polygon(
                    *coords,
                    fill=fill_poly,
                    outline="",
                    stipple="gray25",
                    tags="estatico",
                )
            pares = _pares(pts, fechado=fechado)
            if (
                ativa
                and self._ferramenta == "retangulo"
                and self._canto_ret is not None
                and len(pts) == 1
            ):
                pares = []
            espessura = 3 if ativa else 2
            for a, b in pares:
                x1, y1 = self._mundo_para_tela(a.x, a.y)
                x2, y2 = self._mundo_para_tela(b.x, b.y)
                c.create_line(
                    x1, y1, x2, y2, fill=cor_linha, width=espessura, tags="estatico"
                )
                if ativa:
                    self._cota_segmento(a, b)
            for i, p in enumerate(pts):
                sx, sy = self._mundo_para_tela(p.x, p.y)
                if i == 0:
                    cor_pt = cor_linha
                else:
                    cor_pt = cores.perigo if ativa else cor_linha
                r = 5 if (ativa and i == 0) else 4
                c.create_rectangle(
                    sx - r, sy - r, sx + r, sy + r,
                    fill=cor_pt, outline=cor_pt, tags="estatico",
                )

        if self._offset_seg is not None:
            a, b = self._offset_seg
            x1, y1 = self._mundo_para_tela(a.x, a.y)
            x2, y2 = self._mundo_para_tela(b.x, b.y)
            c.create_line(
                x1, y1, x2, y2, fill="#f9a825", width=4, tags="estatico"
            )

    def _cota_segmento(self, a: Ponto, b: Ponto):
        metros = distancia(a, b)
        if metros < 1e-6:
            return
        x1, y1 = self._mundo_para_tela(a.x, a.y)
        x2, y2 = self._mundo_para_tela(b.x, b.y)
        if hypot_tela(x1, y1, x2, y2) < 36:
            return
        dx, dy = x2 - x1, y2 - y1
        comp = hypot_tela(x1, y1, x2, y2)
        nx, ny = -dy / comp, dx / comp
        mx, my = (x1 + x2) / 2 + nx * 12, (y1 + y2) / 2 + ny * 12
        self.canvas.create_text(
            mx, my,
            text=f"{formatar_decimal_br(metros, 2)} m",
            fill="#c62828",
            font=("Segoe UI", 8, "bold"),
            tags="estatico",
        )

    def _atualizar_volante(self):
        c = self.canvas
        c.delete("volante")
        snap = self._ultimo_snap
        origem = self._origem_atual()
        cores = self._cores

        if self._ferramenta.startswith("offset"):
            cursor = self._tela_para_mundo(*self._cursor_tela)
            if self._offset_seg is None:
                achado = segmento_mais_proximo(
                    cursor,
                    self._segmentos_externa(),
                    max_dist=max(0.8, self._abertura_m() * 3),
                )
                if achado is not None:
                    _i, a, b, _d = achado
                    x1, y1 = self._mundo_para_tela(a.x, a.y)
                    x2, y2 = self._mundo_para_tela(b.x, b.y)
                    c.create_line(
                        x1, y1, x2, y2, fill="#f9a825", width=3, dash=(4, 3), tags="volante"
                    )
            elif self._offset_fase == "comprimento":
                a, b = self._offset_seg
                comp = self._offset_comp or max(0.1, distancia(a, b))
                if self._buffer:
                    try:
                        comp = parse_decimal_br(self._buffer)
                    except ValueError:
                        pass
                if comp <= 0:
                    comp = 0.1
                pts = self._geometria_offset_atual(comprimento=comp)
                if pts and self._offset_modo == "retangulo":
                    coords = []
                    for p in pts:
                        sx, sy = self._mundo_para_tela(p.x, p.y)
                        coords.extend((sx, sy))
                    c.create_polygon(
                        *coords,
                        outline=COR_HALL,
                        fill="#c8e6c9",
                        dash=(4, 3),
                        tags="volante",
                    )
                elif pts and len(pts) >= 2:
                    x1, y1 = self._mundo_para_tela(pts[0].x, pts[0].y)
                    x2, y2 = self._mundo_para_tela(pts[1].x, pts[1].y)
                    c.create_line(
                        x1, y1, x2, y2, fill=COR_HALL, width=3, dash=(6, 4), tags="volante"
                    )
                texto = (
                    f"Comp. {self._buffer} m  (Enter)"
                    if self._buffer
                    else f"Comp. {formatar_decimal_br(comp, 2)} m  (Enter ou clique)"
                )
                xm, ym = self._mundo_para_tela((a.x + b.x) / 2, (a.y + b.y) / 2)
                c.create_text(
                    xm, ym - 18, text=texto, fill="#333333",
                    font=("Segoe UI", 9, "bold"), tags="volante",
                )
            else:
                a, b = self._offset_seg
                lado = lado_do_ponto(cursor, a, b)
                dist = 1.0
                if self._buffer:
                    try:
                        dist = parse_decimal_br(self._buffer)
                    except ValueError:
                        dist = 1.0
                if dist <= 0:
                    dist = 1.0
                if self._offset_modo == "retangulo":
                    pts = offset_retangulo(a, b, dist, lado)
                    coords = []
                    for p in pts:
                        sx, sy = self._mundo_para_tela(p.x, p.y)
                        coords.extend((sx, sy))
                    c.create_polygon(
                        *coords,
                        outline=COR_HALL,
                        fill="#c8e6c9",
                        dash=(4, 3),
                        tags="volante",
                    )
                else:
                    a2, b2 = offset_segmento(a, b, dist, lado)
                    x1, y1 = self._mundo_para_tela(a2.x, a2.y)
                    x2, y2 = self._mundo_para_tela(b2.x, b2.y)
                    c.create_line(
                        x1, y1, x2, y2, fill=COR_HALL, width=3, dash=(6, 4), tags="volante"
                    )
                texto = (
                    f"Dist. {self._buffer} m  (Enter)"
                    if self._buffer
                    else "Digite a distância vazia (m) e Enter"
                )
                xm, ym = self._mundo_para_tela((a.x + b.x) / 2, (a.y + b.y) / 2)
                c.create_text(
                    xm, ym - 18, text=texto, fill="#333333",
                    font=("Segoe UI", 9, "bold"), tags="volante",
                )
            live = self._texto_live(snap)
            if live:
                self._status.config(text=live)
            return

        self._desenhar_edicao_volante()

        editando = self._ferramenta == "mover" or self._grip is not None
        if origem is not None and snap is not None and (not self.fechado or editando):
            x1, y1 = self._mundo_para_tela(origem.x, origem.y)
            x2, y2 = self._mundo_para_tela(snap.ponto.x, snap.ponto.y)
            c.create_line(
                x1, y1, x2, y2, fill="#5b6b75", width=2, dash=(6, 4), tags="volante"
            )
            metros = distancia(origem, snap.ponto)
            ang = angulo_graus(origem, snap.ponto)
            texto = f"{formatar_decimal_br(metros, 2)} m  {ang:.0f}°"
            if self._buffer:
                texto = f"{self._buffer} m  (Enter confirma)"
            c.create_text(
                (x1 + x2) / 2,
                (y1 + y2) / 2 - 16,
                text=texto,
                fill="#333333",
                font=("Segoe UI", 9, "bold"),
                tags="volante",
            )
            if self._ferramenta == "retangulo" and self._canto_ret is not None:
                pts = retangulo_eixos(self._canto_ret, snap.ponto)
                coords = []
                for p in pts:
                    sx, sy = self._mundo_para_tela(p.x, p.y)
                    coords.extend((sx, sy))
                cor_ativa = COR_EXTERNA if self.camada_ativa == "externa" else COR_HALL
                c.create_polygon(
                    *coords, outline=cor_ativa, fill="#d7e8f2", dash=(4, 3), tags="volante"
                )
            elif len(self.pontos) >= 2 and not self.fechado:
                fx, fy = self._mundo_para_tela(self.pontos[0].x, self.pontos[0].y)
                c.create_line(x2, y2, fx, fy, fill="#9aaa73", dash=(3, 4), tags="volante")

        if snap is not None:
            self._desenhar_guias(snap)
            self._marcador_snap(snap)

        live = self._texto_live(snap)
        if live:
            self._status.config(text=live)

    def _linha_volante(self, a: Ponto, b: Ponto, cor: str, largura: int, **kwargs):
        x1, y1 = self._mundo_para_tela(a.x, a.y)
        x2, y2 = self._mundo_para_tela(b.x, b.y)
        self.canvas.create_line(
            x1, y1, x2, y2, fill=cor, width=largura, tags="volante", **kwargs
        )

    def _desenhar_edicao_volante(self):
        """Destaque de seleção, janela/cruzamento, grips e fantasma do mover."""
        c = self.canvas
        if (
            self._ferramenta not in ("selecao", "mover")
            and self._grip is None
            and not self._selecao
            and self._janela_sel is None
        ):
            return

        hover = self._hover_linha
        if hover and hover not in self._selecao:
            try:
                self._linha_volante(*self._extremos(*hover), "#90caf9", 5)
            except (IndexError, KeyError):
                pass

        for chave in list(self._selecao):
            try:
                self._linha_volante(*self._extremos(*chave), COR_SELECAO, 4)
            except (IndexError, KeyError):
                continue

        snap = self._ultimo_snap
        if (
            self._ferramenta == "mover"
            and self._mover_base is not None
            and snap is not None
        ):
            ghost = self._camadas_movidas(snap.ponto)
            for nome, i in list(self._selecao):
                pts = ghost[nome]["pontos"]
                n = len(pts)
                if i not in indices_segmentos(n, bool(ghost[nome]["fechado"])):
                    continue
                ia, ib = extremos_segmento(n, i)
                self._linha_volante(pts[ia], pts[ib], COR_SELECAO, 3, dash=(6, 4))

        if self._grip is not None and snap is not None:
            nome, idx, _orig = self._grip
            dest = snap.ponto
            pts = self._camadas[nome]["pontos"]
            n = len(pts)
            if 0 <= idx < n:
                fechado = bool(self._camadas[nome]["fechado"]) and n >= 3
                vizinhos = []
                if idx > 0 or fechado:
                    vizinhos.append((idx - 1) % n)
                if idx < n - 1 or fechado:
                    vizinhos.append((idx + 1) % n)
                for j in vizinhos:
                    self._linha_volante(pts[j], dest, COR_GRIP_QUENTE, 2, dash=(4, 3))

        for nome, idx in self._grips():
            p = self._camadas[nome]["pontos"][idx]
            quente = (
                self._grip is not None
                and self._grip[0] == nome
                and self._grip[1] == idx
            )
            if quente and snap is not None:
                p = snap.ponto
            sx, sy = self._mundo_para_tela(p.x, p.y)
            r = 5
            c.create_rectangle(
                sx - r,
                sy - r,
                sx + r,
                sy + r,
                fill=COR_GRIP_QUENTE if quente else COR_GRIP,
                outline="#ffffff",
                width=1,
                tags="volante",
            )

        if self._janela_sel is not None:
            sx0, sy0, sx1, sy1 = self._janela_sel
            cruzamento = sx1 < sx0
            cor = COR_CRUZAMENTO if cruzamento else COR_JANELA
            fill = "#c8e6c9" if cruzamento else "#bbdefb"
            kwargs = dict(
                outline=cor,
                fill=fill,
                stipple="gray25",
                width=2,
                tags="volante",
            )
            if cruzamento:
                kwargs["dash"] = (4, 3)
            c.create_rectangle(sx0, sy0, sx1, sy1, **kwargs)

    def _texto_live(self, snap: ResultadoSnap | None) -> str:
        if self._ferramenta.startswith("offset"):
            partes = ["Externa" if self.camada_ativa == "externa" else "Hall"]
            partes.append(f"Offset {self._offset_modo or ''}".strip())
            if self._offset_fase == "comprimento":
                partes.append("esticar comprimento")
                if self._offset_comp:
                    partes.append(f"{formatar_decimal_br(self._offset_comp, 2)} m")
            elif self._offset_fase == "distancia":
                partes.append("distância vazia")
            if self._buffer:
                partes.append(f"digitando {self._buffer} m")
            return "  ·  ".join(partes)

        if self._grip is not None:
            partes = ["Grip"]
            orig = self._grip[2]
            if snap is not None:
                partes.append(f"{formatar_decimal_br(distancia(orig, snap.ponto), 2)} m")
                if snap.rotulo:
                    partes.append(snap.rotulo)
            if self._buffer:
                partes.append(f"digitando {self._buffer} m")
            else:
                partes.append("clique o destino ou Enter")
            return "  ·  ".join(partes)

        if self._ferramenta == "mover":
            partes = [f"Mover · {len(self._selecao)} linha(s)"]
            if self._mover_base is None:
                partes.append("clique o ponto base")
            elif snap is not None:
                metros = distancia(self._mover_base, snap.ponto)
                partes.append(f"{formatar_decimal_br(metros, 2)} m")
                partes.append(f"{angulo_graus(self._mover_base, snap.ponto):.0f}°")
                if snap.rotulo:
                    partes.append(snap.rotulo)
            if self._buffer:
                partes.append(f"digitando {self._buffer} m")
            elif self._mover_base is not None:
                partes.append("clique o destino ou Enter")
            return "  ·  ".join(partes)

        if self._ferramenta == "selecao":
            if self._janela_sel is not None:
                return ""
            n = len(self._selecao)
            if not n:
                return ""
            total = sum(
                distancia(*self._extremos(nome, i)) for nome, i in self._selecao
            )
            return f"{n} linha(s) · {formatar_decimal_br(total, 2)} m"

        partes = ["Externa" if self.camada_ativa == "externa" else "Hall"]
        if snap and snap.rotulo:
            partes.append(snap.rotulo)
        if self.pontos:
            if self.fechado:
                res = resultado_desenho(self.pontos, fechado=True)
                partes.append(f"Área {formatar_decimal_br(res.area_m2, 2)} m²")
                partes.append(f"Perím. {formatar_decimal_br(res.perimetro_m, 2)} m")
            else:
                compr = perimetro(self.pontos, fechado=False)
                if snap and self._origem_atual():
                    compr += distancia(self._origem_atual(), snap.ponto)
                partes.append(f"Perím. {formatar_decimal_br(compr, 2)} m")
                if len(self.pontos) >= 2:
                    pts = list(self.pontos)
                    if snap:
                        pts.append(snap.ponto)
                    if len(pts) >= 3:
                        area = area_poligono(pts)
                        partes.append(f"Se completar: {formatar_decimal_br(area, 2)} m²")
        if self._buffer:
            partes.append(f"digitando {self._buffer} m")
        return "  ·  ".join(partes) if partes else self._status.cget("text")

    def _desenhar_guias(self, snap: ResultadoSnap):
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        ancoras = list(snap.ancoras_guia)
        origem = self._origem_atual()
        if origem is not None and snap.tipo in {"orto", "guia", "grade", "polar", "igual"}:
            ancoras.append(origem)
        vistos = set()
        for a in ancoras:
            chave = (round(a.x, 6), round(a.y, 6))
            if chave in vistos:
                continue
            vistos.add(chave)
            sx, sy = self._mundo_para_tela(a.x, a.y)
            if abs(a.y - snap.ponto.y) <= 1e-6:
                self.canvas.create_line(0, sy, w, sy, fill="#43a047", dash=(5, 4), tags="volante")
            if abs(a.x - snap.ponto.x) <= 1e-6:
                self.canvas.create_line(sx, 0, sx, h, fill="#43a047", dash=(5, 4), tags="volante")

    def _marcador_snap(self, snap: ResultadoSnap):
        sx, sy = self._mundo_para_tela(snap.ponto.x, snap.ponto.y)
        cor = "#f9a825" if snap.tipo != "guia" else "#43a047"
        r = 7 if snap.tipo == "primeiro" else 6
        if snap.tipo in {"fim", "primeiro", "orto", "polar", "grade", "livre"}:
            self.canvas.create_rectangle(
                sx - r, sy - r, sx + r, sy + r, outline=cor, width=2, fill="", tags="volante"
            )
        elif snap.tipo == "meio":
            self.canvas.create_polygon(
                sx, sy - r, sx + r, sy + r, sx - r, sy + r,
                outline=cor, fill="", width=2, tags="volante",
            )
        elif snap.tipo == "int":
            self.canvas.create_line(sx - r, sy - r, sx + r, sy + r, fill=cor, width=2, tags="volante")
            self.canvas.create_line(sx - r, sy + r, sx + r, sy - r, fill=cor, width=2, tags="volante")
        elif snap.tipo == "igual":
            self.canvas.create_line(sx - r, sy, sx + r, sy, fill=cor, width=2, tags="volante")
            self.canvas.create_line(sx, sy - r, sx, sy + r, fill=cor, width=2, tags="volante")
            self.canvas.create_oval(sx - 4, sy - 4, sx + 4, sy + 4, outline=cor, width=2, tags="volante")
        elif snap.tipo == "perp":
            self.canvas.create_line(sx - r, sy + r, sx + r, sy + r, fill=cor, width=2, tags="volante")
            self.canvas.create_line(sx - r, sy + r, sx - r, sy - r, fill=cor, width=2, tags="volante")
        else:
            self.canvas.create_oval(sx - 5, sy - 5, sx + 5, sy + 5, outline=cor, width=2, tags="volante")
        if snap.rotulo:
            self.canvas.create_text(
                sx + 12, sy - 12, text=snap.rotulo, anchor="w",
                fill=cor, font=("Segoe UI", 8, "bold"), tags="volante",
            )


EPSILON_ZOOM = 1e-6


def _pares(pontos, *, fechado: bool):
    n = len(pontos)
    if n < 2:
        return []
    saida = [(pontos[i], pontos[i + 1]) for i in range(n - 1)]
    if fechado and n >= 3:
        saida.append((pontos[-1], pontos[0]))
    return saida


def _alinha_grade(valor: float, passo: float) -> float:
    return math.floor(valor / passo) * passo


def _eh_major(valor: float, passo: float) -> bool:
    base = passo * 5
    return abs(round(valor / base) * base - valor) < max(passo * 1e-6, 1e-9)


def _fmt_eixo(valor: float) -> str:
    if abs(valor) < 1e-9:
        return "0"
    return formatar_decimal_br(valor, 2)


def hypot_tela(x1, y1, x2, y2) -> float:
    return math.hypot(x2 - x1, y2 - y1)


def valor_para_campo(resultado: ResultadoDesenho | None, tipo_campo: str) -> str:
    if resultado is None:
        return ""
    valor = resultado.valor_para(tipo_campo)
    if tipo_campo == "area" and not resultado.fechado:
        return ""
    if valor <= 0:
        return ""
    return formatar_quantidade_edicao(valor, 2)


class PreviaDesenho2D(tk.Frame):
    """Canvas só de leitura da planta salva no orçamento."""

    def __init__(self, parent, *, largura=340, altura=260):
        cores = cores_tema(parent)
        super().__init__(parent, bg=cores.fundo)
        self._cores = cores
        self._camadas = {
            "externa": ([], False),
            "hall": ([], False),
        }
        self.canvas = tk.Canvas(
            self,
            width=largura,
            height=altura,
            bg="#fbfcfd",
            highlightthickness=1,
            highlightbackground=cores.borda_suave,
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._ao_configurar)
        self._texto_vazio = (
            "Desenhe a planta (externa + hall) no ORCCAD\n"
            "para ver aqui a prévia salva."
        )

    def definir(self, dados):
        self._camadas = dict_para_camadas(dados)
        self._redesenhar()

    def _ao_configurar(self, _event=None):
        self._redesenhar()

    def _redesenhar(self):
        c = self.canvas
        w, h = c.winfo_width(), c.winfo_height()
        if w < 8 or h < 8:
            return
        c.delete("all")
        cores = self._cores
        c.create_rectangle(0, 0, w, h, fill="#fbfcfd", outline="")
        todos: list[Ponto] = []
        for pts, _fechado in self._camadas.values():
            todos.extend(pts)
        if len(todos) < 2:
            c.create_text(
                w / 2,
                h / 2,
                text=self._texto_vazio,
                fill=cores.texto_suave,
                font=("Segoe UI", 9),
                justify="center",
                width=max(120, w - 24),
            )
            return
        xs = [p.x for p in todos]
        ys = [p.y for p in todos]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)
        dx = max(maxx - minx, 0.5)
        dy = max(maxy - miny, 0.5)
        margem = 28
        zoom = min((w - 2 * margem) / dx, (h - 2 * margem) / dy)
        zoom = max(zoom, 1e-6)
        cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
        ox = w / 2.0 - cx * zoom
        oy = h / 2.0 + cy * zoom

        def tela(p: Ponto) -> tuple[float, float]:
            return ox + p.x * zoom, oy - p.y * zoom

        for nome, cor, fill in (
            ("externa", COR_EXTERNA, "#d7e8f2"),
            ("hall", COR_HALL, "#c8e6c9"),
        ):
            pts, fechado = self._camadas.get(nome, ([], False))
            if fechado and len(pts) >= 3:
                coords = []
                for p in pts:
                    coords.extend(tela(p))
                c.create_polygon(*coords, fill=fill, outline="", stipple="gray25")
            for a, b in _pares(pts, fechado=fechado):
                x1, y1 = tela(a)
                x2, y2 = tela(b)
                c.create_line(x1, y1, x2, y2, fill=cor, width=2)
        c.create_text(
            8,
            h - 6,
            text="Planta baixa",
            anchor="sw",
            fill=cores.texto_suave,
            font=("Segoe UI", 8),
        )


def _area_assinada_xy(pts: list[tuple[float, float]]) -> float:
    soma = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        soma += x1 * y2 - x2 * y1
    return soma / 2.0


def _ponto_no_triangulo(p, a, b, c) -> bool:
    def cruz(u, v, w):
        return (v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0])

    return cruz(a, b, p) > 1e-8 and cruz(b, c, p) > 1e-8 and cruz(c, a, p) > 1e-8


def _triangular_poligono(pts: list[tuple[float, float]]) -> list[tuple]:
    """Divide um polígono CCW, mesmo côncavo, em triângulos."""
    n = len(pts)
    if n < 3:
        return []
    if n == 3:
        return [(pts[0], pts[1], pts[2])]
    idx = list(range(n))
    saida = []
    guarda = n * n
    while len(idx) > 3 and guarda > 0:
        guarda -= 1
        achou = False
        m = len(idx)
        for i in range(m):
            i0, i1, i2 = idx[(i - 1) % m], idx[i], idx[(i + 1) % m]
            a, b, c = pts[i0], pts[i1], pts[i2]
            if (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]) <= 1e-8:
                continue
            if any(
                _ponto_no_triangulo(pts[j], a, b, c)
                for j in idx
                if j not in (i0, i1, i2)
            ):
                continue
            saida.append((a, b, c))
            del idx[i]
            achou = True
            break
        if not achou:
            break
    if len(idx) == 3:
        saida.append((pts[idx[0]], pts[idx[1]], pts[idx[2]]))
    return saida


_COR_BLOCO = (
    (251, 252, 253),
    (212, 232, 243),
    (158, 195, 214),
    (231, 243, 248),
    (0, 102, 153),
)


def _raster_triangulo(depth, buf, largura, altura, p0, p1, p2, cor, folga):
    """Preenche um triângulo. Aresta de topo ou de base plana também entra."""
    verts = sorted(
        (
            (p0[0], p0[1], p0[2] + folga),
            (p1[0], p1[1], p1[2] + folga),
            (p2[0], p2[1], p2[2] + folga),
        ),
        key=lambda p: (p[1], p[0]),
    )
    (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = verts
    if y2 <= y0:
        return
    r, g, b = _COR_BLOCO[cor]

    def borda(y, ya, xa, za, yb, xb, zb):
        dy = yb - ya
        if abs(dy) < 1e-12:
            return xa, za
        t = (y - ya) / dy
        return xa + (xb - xa) * t, za + (zb - za) * t

    y_ini = max(0, math.floor(y0))
    y_fim = min(altura - 1, math.ceil(y2))
    for y in range(y_ini, y_fim + 1):
        ys = y + 0.5
        if ys < y0 or ys > y2:
            continue
        xl, zl = borda(ys, y0, x0, z0, y2, x2, z2)
        if y1 <= y0:
            xs, zs = borda(ys, y1, x1, z1, y2, x2, z2)
        elif y1 >= y2:
            xs, zs = borda(ys, y0, x0, z0, y1, x1, z1)
        elif ys <= y1:
            xs, zs = borda(ys, y0, x0, z0, y1, x1, z1)
        else:
            xs, zs = borda(ys, y1, x1, z1, y2, x2, z2)
        if xl > xs:
            xl, xs, zl, zs = xs, xl, zs, zl
        # Meio pixel a mais fecha a fresta entre triângulos vizinhos.
        i0 = max(0, math.floor(xl - 0.5))
        i1 = min(largura - 1, math.ceil(xs + 0.5))
        if i1 < i0:
            continue
        span = xs - xl
        base = y * largura
        for x in range(i0, i1 + 1):
            t = 0.0 if span < 1e-9 else ((x + 0.5) - xl) / span
            if t < 0.0:
                t = 0.0
            elif t > 1.0:
                t = 1.0
            z = zl + (zs - zl) * t
            i = base + x
            if z < depth[i]:
                depth[i] = z
                o = i * 3
                buf[o] = r
                buf[o + 1] = g
                buf[o + 2] = b


def _foto_rgb(buf: bytearray, largura: int, altura: int, escala: int) -> tk.PhotoImage:
    import os
    import tempfile

    fd, path = tempfile.mkstemp(suffix=".ppm")
    try:
        with os.fdopen(fd, "wb") as arquivo:
            arquivo.write(f"P6\n{largura} {altura}\n255\n".encode("ascii"))
            arquivo.write(buf)
        imagem = tk.PhotoImage(file=path)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    if escala > 1:
        return imagem.zoom(escala, escala)
    return imagem


def _raster_linha(depth, buf, largura, altura, p0, p1, cor, folga):
    x0, y0, z0 = p0[0], p0[1], p0[2] + folga
    x1, y1, z1 = p1[0], p1[1], p1[2] + folga
    r, g, b = _COR_BLOCO[cor]
    passos = max(abs(int(round(x1)) - int(round(x0))), abs(int(round(y1)) - int(round(y0))), 1)
    for passo in range(passos + 1):
        t = passo / passos
        x = int(round(x0 + (x1 - x0) * t))
        y = int(round(y0 + (y1 - y0) * t))
        if x < 0 or y < 0 or x >= largura or y >= altura:
            continue
        z = z0 + (z1 - z0) * t
        i = y * largura + x
        if z < depth[i]:
            depth[i] = z
            o = i * 3
            buf[o] = r
            buf[o + 1] = g
            buf[o + 2] = b


class VistaIsometricaBloco(tk.Frame):
    """Extrusão isométrica de um bloco a partir da planta externa."""

    def __init__(self, parent, *, largura=340, altura=168):
        cores = cores_tema(parent)
        super().__init__(parent, bg=cores.fundo)
        self._cores = cores
        self._pontos: list[Ponto] = []
        self._fechado = False
        self._pe_direito = 0.0
        self._pavimentos = 0
        self._angulo = math.radians(-38)
        self._arrastando = False
        self._ultimo_x = 0
        self._foto = None
        self._job_giro = None
        self._escala = 1
        self.canvas = tk.Canvas(
            self,
            width=largura,
            height=altura,
            bg="#fbfcfd",
            highlightthickness=1,
            highlightbackground=cores.borda_suave,
            cursor="fleur",
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _e: self._redesenhar())
        self.canvas.bind("<ButtonPress-1>", self._iniciar_giro)
        self.canvas.bind("<B1-Motion>", self._girar)
        self.canvas.bind("<ButtonRelease-1>", self._soltar_giro)

    def definir(self, pontos, fechado, pe_direito: float, pavimentos: float) -> None:
        self._pontos = list(pontos or [])
        self._fechado = bool(fechado) and len(self._pontos) >= 3
        try:
            self._pe_direito = max(0.0, float(pe_direito or 0))
        except (TypeError, ValueError):
            self._pe_direito = 0.0
        try:
            self._pavimentos = max(0, int(round(float(pavimentos or 0))))
        except (TypeError, ValueError):
            self._pavimentos = 0
        self._redesenhar()

    def _iniciar_giro(self, event):
        self._arrastando = True
        self._ultimo_x = event.x

    def _girar(self, event):
        if not self._arrastando:
            return
        self._angulo += (event.x - self._ultimo_x) * 0.012
        self._ultimo_x = event.x
        self._escala = 2
        self._pedir_redesenho()

    def _soltar_giro(self, _event):
        self._arrastando = False
        self._escala = 1
        self._pedir_redesenho()

    def _pedir_redesenho(self):
        if self._job_giro is not None:
            return
        self._job_giro = self.after(16, self._executar_redesenho)

    def _executar_redesenho(self):
        self._job_giro = None
        self._redesenhar()

    def _redesenhar(self):
        c = self.canvas
        try:
            w, h = c.winfo_width(), c.winfo_height()
        except tk.TclError:
            return
        if w < 8 or h < 8:
            return
        escala = self._escala if w // max(self._escala, 1) >= 8 and h // max(self._escala, 1) >= 8 else 1
        rw, rh = w // escala, h // escala
        c.delete("all")
        c.create_rectangle(0, 0, w, h, fill="#fbfcfd", outline="")
        if not self._fechado:
            self._mensagem(c, w, h, "A vista do bloco usa a planta externa fechada.")
            return
        if self._pe_direito <= 0 or self._pavimentos <= 0:
            self._mensagem(
                c,
                w,
                h,
                "Informe o pé-direito e a quantidade de pavimentos\npara ver o bloco.",
            )
            return

        pe = self._pe_direito
        pav = self._pavimentos
        altura = pe * pav
        ang = self._angulo
        cos_a = math.cos(ang)
        sin_a = math.sin(ang)
        pts = self._pontos

        def mundo(x, y, z):
            rx = x * cos_a - y * sin_a
            ry = x * sin_a + y * cos_a
            return rx, ry * 0.5 + z, ry

        amostras = []
        for p in pts:
            amostras.append(mundo(p.x, p.y, 0.0))
            amostras.append(mundo(p.x, p.y, altura))
        sxs = [a[0] for a in amostras]
        sys_ = [a[1] for a in amostras]
        minx, maxx = min(sxs), max(sxs)
        miny, maxy = min(sys_), max(sys_)
        margem = 16
        largura_m = max(maxx - minx, 0.5)
        altura_m = max(maxy - miny, 0.5)
        zoom = min((rw - 2 * margem) / largura_m, (rh - 2 * margem) / altura_m)
        zoom = max(zoom, 1e-6)
        ox = rw / 2.0 - (minx + maxx) / 2.0 * zoom
        oy = rh / 2.0 + (miny + maxy) / 2.0 * zoom

        def tela(x, y, z):
            sx, sy, profundidade = mundo(x, y, z)
            return ox + sx * zoom, oy - sy * zoom, profundidade

        contorno = [(p.x, p.y) for p in pts]
        if _area_assinada_xy(contorno) < 0:
            contorno.reverse()
        n = len(contorno)
        olhar_x, olhar_y = sin_a, cos_a
        depth = [1e30] * (rw * rh)
        buf = bytearray(bytes((251, 252, 253)) * (rw * rh))
        for a, b, c3 in _triangular_poligono(contorno):
            _raster_triangulo(
                depth,
                buf,
                rw,
                rh,
                tela(a[0], a[1], altura),
                tela(b[0], b[1], altura),
                tela(c3[0], c3[1], altura),
                3,
                -0.04,
            )
        for i in range(n):
            ax, ay = contorno[i]
            bx, by = contorno[(i + 1) % n]
            dx, dy = bx - ax, by - ay
            comp = math.hypot(dx, dy) or 1.0
            fora_x, fora_y = dy / comp, -dx / comp
            voltada = fora_x * olhar_x + fora_y * olhar_y
            nrx = fora_x * cos_a - fora_y * sin_a
            cor_parede = 1 if nrx >= 0 else 2
            p00 = tela(ax, ay, 0.0)
            p10 = tela(bx, by, 0.0)
            p11 = tela(bx, by, altura)
            p01 = tela(ax, ay, altura)
            _raster_triangulo(depth, buf, rw, rh, p00, p10, p11, cor_parede, 0.0)
            _raster_triangulo(depth, buf, rw, rh, p00, p11, p01, cor_parede, 0.0)
            topo_a = tela(ax, ay, altura)
            topo_b = tela(bx, by, altura)
            _raster_linha(depth, buf, rw, rh, topo_a, topo_b, 4, -0.08)
            if voltada < -1e-4:
                _raster_linha(depth, buf, rw, rh, tela(ax, ay, 0.0), topo_a, 4, -0.08)
                _raster_linha(depth, buf, rw, rh, tela(bx, by, 0.0), topo_b, 4, -0.08)
                for andar in range(1, pav):
                    _raster_linha(
                        depth,
                        buf,
                        rw,
                        rh,
                        tela(ax, ay, andar * pe),
                        tela(bx, by, andar * pe),
                        4,
                        -0.08,
                    )
        self._foto = _foto_rgb(buf, rw, rh, escala)
        c.create_image(0, 0, image=self._foto, anchor="nw")
        c.create_text(
            8,
            h - 6,
            text="Visão isométrica",
            anchor="sw",
            fill=self._cores.texto_suave,
            font=("Segoe UI", 8),
        )

    def _mensagem(self, canvas, largura, altura, texto):
        canvas.create_text(
            largura / 2,
            altura / 2,
            text=texto,
            fill=self._cores.texto_suave,
            font=("Segoe UI", 9),
            justify="center",
            width=max(120, largura - 24),
        )
