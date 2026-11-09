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
    quase_iguais,
    resolver_snap,
    resultado_desenho,
    retangulo_eixos,
    segmento_mais_proximo,
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
        self._ferramenta = "polilinha"
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
            self._ferramenta = "polilinha"

    def limpar(self):
        self.pontos.clear()
        self.fechado = False
        self._canto_ret = None
        self._buffer = ""
        self._ultimo_snap = None
        self._limpar_estado_offset(restaurar_hall=False)
        self._redesenhar_estatico()
        self._atualizar_volante()
        self._avisar_resultado()
        self._set_status(self._msg_inicio())

    def limpar_tudo(self):
        for chave in self._camadas:
            self._camadas[chave] = {"pontos": [], "fechado": False}
        self._canto_ret = None
        self._buffer = ""
        self._ultimo_snap = None
        self._limpar_estado_offset(restaurar_hall=False)
        self._ferramenta = "polilinha"
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
        self._canto_ret = None
        self._buffer = ""
        self._ultimo_snap = None
        self._limpar_estado_offset(restaurar_hall=False)
        self._ferramenta = "polilinha"
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
        nome = "Externa" if self.camada_ativa == "externa" else "Hall"
        return (
            f"Camada {nome}: clique o primeiro ponto. "
            "Polar (F10) sugere 45°/90°. Offset: distância vazia e depois o comprimento."
        )

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
            ("<Control-Z>", self._ao_desfazer_tecla),
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
            (4, 12),
            "Offset (retângulo)",
            "Hall retangular a partir de uma parede.\n"
            "1) Clique a parede da Externa\n"
            "2) Digite a distância vazia / profundidade (m) e Enter\n"
            "3) Estique o comprimento (digite ou arraste) e Enter/clique.",
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
            self._desfazer,
            (4, 4),
            "Desfazer",
            "Remove o último vértice da camada ativa.\nAtalho: Backspace ou Ctrl+Z.",
        )
        _btn(
            "trash-outline",
            self.limpar,
            (0, 0),
            "Limpar",
            "Apaga só a camada ativa (Externa ou Hall).",
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
            "Offset: 1º distância vazia · 2º comprimento (digite ou arraste)\n"
            "Hall também pode ser desenhado do zero na camada HALL\n"
            "Shift: trava H/V · F11: guias · digite medida + Enter\n"
            "Botão direito: completa · roda: zoom · espaço+arraste: pan",
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

        self._status = ttk.Label(rodape, text="Clique para começar.")
        self._status.pack(side="right")

        self._atualizar_chips()
        self._ligar_canvas()

    def _ligar_canvas(self):
        c = self.canvas
        c.bind("<Button-1>", self._ao_clique)
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
        self._desfazer()
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
        if self.pontos and not self.fechado:
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
            pode_fechar=len(self.pontos) >= 3 and not self.fechado,
            ponto_fechamento=self.pontos[0] if self.pontos else None,
        )

    def _ativar_camada(self, camada: str):
        if camada not in self._camadas or camada == self.camada_ativa:
            self._atualizar_chips_camada()
            return
        self._canto_ret = None
        self._buffer = ""
        if self._ferramenta.startswith("offset"):
            self._limpar_estado_offset(restaurar_hall=True)
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
        self._limpar_estado_offset(restaurar_hall=True)
        self._offset_hall_backup = {
            "pontos": list(self._camadas["hall"]["pontos"]),
            "fechado": bool(self._camadas["hall"]["fechado"]),
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
        self._limpar_estado_offset(restaurar_hall=False)
        self._ferramenta = "polilinha"
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
        self.pontos = list(retangulo_eixos(self._canto_ret, ponto))
        self._canto_ret = None
        self.fechado = True
        self._buffer = ""
        self._redesenhar_estatico()
        self._atualizar_volante()
        self._avisar_resultado()
        self._set_status("Retângulo completo. Aplique a metragem ou limpe para outro desenho.")

    def _ao_mover(self, event):
        self._cursor_tela = (event.x, event.y)
        if self._pan is not None:
            self._ao_pan_move(event)
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

    def _ao_arraste(self, event):
        if self._pan is not None or self._espaco:
            self._ao_pan_move(event)

    def _ao_soltar(self, _event):
        if self._pan is not None:
            self._ao_pan_fim()

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
            if not digitando_offset and (not self.pontos or self.fechado):
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
        if (event.keysym or "").lower() == "c" and not self._buffer:
            self.fechar_poligono()
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
        if self._buffer:
            self._buffer = ""
            self._atualizar_volante()
            self._set_status("Medida digitada cancelada.")
            return "break"
        if self._canto_ret is not None:
            self._canto_ret = None
            self.pontos.clear()
            self._redesenhar_estatico()
            self._atualizar_volante()
            return "break"
        if self.pontos and not self.fechado:
            self._desfazer()
        return "break"

    def _ao_backspace(self, _event=None):
        if self._buffer:
            self._buffer = self._buffer[:-1]
            self._atualizar_volante()
            return "break"
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
        if origem is None or self.fechado:
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
        ponto = ponto_na_direcao(origem, destino, metros)
        self._buffer = ""
        if self._ferramenta == "retangulo":
            self._clique_retangulo(ponto)
            return
        snap_falso = ResultadoSnap(ponto, "orto")
        self._clique_polilinha(snap_falso)

    def _desfazer(self):
        if self.fechado:
            self.fechado = False
            self._redesenhar_estatico()
            self._atualizar_volante()
            self._avisar_resultado()
            self._set_status("Polígono reaberto. Continue ou complete de novo.")
            return
        if self._ferramenta == "retangulo" and self._canto_ret is not None:
            self._canto_ret = None
            self.pontos.clear()
        elif self.pontos:
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
        self.fechado = True
        self._buffer = ""
        self._redesenhar_estatico()
        self._atualizar_volante()
        self._avisar_resultado()
        self._set_status("Polígono completo. Aplique a metragem ou limpe para outro desenho.")

    def _usar(self, ferramenta: str):
        if self._ferramenta.startswith("offset"):
            self._limpar_estado_offset(restaurar_hall=True)
        else:
            self._limpar_estado_offset(restaurar_hall=False)
        if ferramenta == self._ferramenta and not self.pontos:
            return
        self._ferramenta = ferramenta
        # Não apaga a outra camada; só reinicia a ativa se já houver traço.
        if self.pontos or self.fechado:
            self.limpar()
        else:
            self._canto_ret = None
            self._buffer = ""
            self._redesenhar_estatico()
            self._atualizar_volante()
            self._avisar_resultado()
        if ferramenta == "retangulo":
            self._set_status("Retângulo na camada ativa: clique dois cantos opostos.")
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

        if origem is not None and snap is not None and not self.fechado:
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

    def _texto_live(self, snap: ResultadoSnap | None) -> str:
        partes = ["Externa" if self.camada_ativa == "externa" else "Hall"]
        if self._ferramenta.startswith("offset"):
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
