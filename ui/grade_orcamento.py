import tkinter as tk
from tkinter import ttk
from typing import Literal

from core.orcamento_customizado import TIPO_GRUPO

TkAnchor = Literal["nw", "n", "ne", "w", "center", "e", "sw", "s", "se"]
Coluna = tuple[str, str, int, TkAnchor, int]

COLUNAS: tuple[Coluna, ...] = (
    ("item", "Item", 52, "center", 0),
    ("codigo", "Código", 72, "center", 0),
    ("tipo_ic", "I/C", 36, "center", 0),
    ("descricao", "Descrição", 180, "w", 1),
    ("quantidade", "Qtd.", 64, "w", 0),
    ("unidade", "Unid.", 48, "w", 0),
    ("custo_unit", "Custo unit.", 92, "w", 0),
    ("custo_bdi", "Custo c/ BDI", 92, "w", 0),
    ("total", "Total", 96, "center", 0),
)

COR_FUNDO = "#ffffff"
COR_CABECALHO = "#e0e8ec"
COR_SELECAO = "#cce4f0"
COR_GRUPO = "#e8f4f8"
COR_BORDA = "#cccccc"
COR_COMPOSICAO = "#7b5e00"
COR_ALERTA_DEPRECIADO = "#fff8e1"
COR_TEXTO = "#333333"


class GradeOrcamento(tk.Frame):
    """Grade orçamentária com Canvas — uma linha (Frame) por item, altura variável."""

    def __init__(self, parent, on_duplo_clique_qtd=None, on_tecla_delete=None):
        super().__init__(parent, bg="#ececec")
        self.on_duplo_clique_qtd = on_duplo_clique_qtd
        self.on_tecla_delete = on_tecla_delete
        self._linhas = []
        self._selecao_metas: list[dict] = []
        self._ancora_indice: int | None = None
        self._tem_itens_depreciados = False
        self._largura_descricao = 280
        self._reconstruindo = False
        self._fracao_scroll_salva = 0.0
        self._montar()

    def _montar(self):
        self.cabecalho = tk.Frame(self, bg=COR_CABECALHO, highlightbackground=COR_BORDA, highlightthickness=1)
        self.cabecalho.pack(fill="x")

        for col, (_chave, titulo, largura_min, anchor, peso) in enumerate(COLUNAS):
            tk.Label(
                self.cabecalho,
                text=titulo,
                font=("Arial", 9, "bold"),
                bg=COR_CABECALHO,
                fg="#444444",
                anchor=anchor,
                padx=4,
                pady=6,
            ).grid(row=0, column=col, sticky="nsew", padx=(0, 1))
            self.cabecalho.columnconfigure(col, minsize=largura_min, weight=peso)

        container = tk.Frame(self, bg="#ececec")
        container.pack(fill="both", expand=True, pady=(2, 0))

        self.canvas = tk.Canvas(
            container, highlightthickness=0, bg=COR_FUNDO, takefocus=1
        )
        self.scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.frame_linhas = tk.Frame(self.canvas, bg=COR_FUNDO)

        self.frame_linhas.bind("<Configure>", self._atualizar_scrollregion)
        self._janela_canvas = self.canvas.create_window((0, 0), window=self.frame_linhas, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind("<Configure>", self._ao_redimensionar_canvas)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.frame_linhas.bind("<MouseWheel>", self._on_mousewheel)
        for alvo in (self, container, self.canvas, self.frame_linhas, self.cabecalho):
            self._vincular_tecla_delete(alvo)

    def _vincular_tecla_delete(self, widget):
        for tecla in ("<Delete>", "<KP_Delete>"):
            widget.bind(tecla, self._ao_tecla_delete, add="+")

    def _ao_tecla_delete(self, event):
        if self.on_tecla_delete is not None:
            self.on_tecla_delete(event)
            return "break"


    def _conteudo_cabe_no_canvas(self):
        self.update_idletasks()
        bbox = self.canvas.bbox("all")
        if not bbox:
            return True
        return (bbox[3] - bbox[1]) <= self.canvas.winfo_height()

    def _on_mousewheel(self, event):
        if not event.delta:
            return
        if self._conteudo_cabe_no_canvas():
            return
        pos = self.canvas.yview()
        if event.delta > 0 and pos[0] <= 0:
            return
        if event.delta < 0 and pos[1] >= 1:
            return
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def _atualizar_scrollregion(self, _event=None):
        if self._reconstruindo:
            return
        bbox = self.canvas.bbox("all")
        if bbox:
            self.canvas.configure(scrollregion=bbox)

    def iniciar_reconstrucao(self):
        self.update_idletasks()
        self._reconstruindo = True
        try:
            self._fracao_scroll_salva = float(self.canvas.yview()[0])
        except tk.TclError:
            self._fracao_scroll_salva = 0.0

    def salvar_fracao_scroll(self):
        return self._fracao_scroll_salva

    def _ao_redimensionar_canvas(self, event):
        largura = max(event.width, 400)
        self.canvas.itemconfig(self._janela_canvas, width=largura)
        peso_desc = next(p for _k, _t, _m, _a, p in COLUNAS if _k == "descricao")
        fixo = sum(m for _k, _t, m, _a, p in COLUNAS if p == 0) + len(COLUNAS)
        self._largura_descricao = max(120, largura - fixo - 24)
        for linha in self._linhas:
            if linha.get("lbl_descricao"):
                linha["lbl_descricao"].config(wraplength=self._largura_descricao)
        self._atualizar_scrollregion()

    def limpar(self):
        for linha in self._linhas:
            linha["frame"].destroy()
        self._linhas.clear()
        self._selecao_metas.clear()
        self._ancora_indice = None
        self._tem_itens_depreciados = False

    def tem_itens_depreciados(self) -> bool:
        return self._tem_itens_depreciados

    def salvar_posicao_scroll(self):
        self.update_idletasks()
        try:
            return float(self.canvas.yview()[0])
        except tk.TclError:
            return 0.0

    def restaurar_fracao_scroll(self, fracao_top):
        self.update_idletasks()
        bbox = self.canvas.bbox("all")
        if not bbox:
            return
        self.canvas.configure(scrollregion=bbox)
        self.update_idletasks()
        self.canvas.yview_moveto(max(0.0, min(1.0, fracao_top)))

    def finalizar_reconstrucao(self, fracao_top=None, metas_selecionadas=None):
        if fracao_top is None:
            fracao_top = self._fracao_scroll_salva
        self._reconstruindo = False
        self.restaurar_fracao_scroll(fracao_top)
        if metas_selecionadas is not None:
            existentes = [
                meta
                for meta in metas_selecionadas
                if self._indice_por_meta(meta) is not None
            ]
            if existentes:
                self.selecionar_metas(existentes)
            else:
                self._selecao_metas.clear()
                self._ancora_indice = None
                self._atualizar_destaques()

    def adicionar_linha(self, meta, valores, estilo="item", alerta_depreciado=False):
        idx = len(self._linhas)
        cor_fundo = COR_GRUPO if estilo == "grupo" else COR_FUNDO
        if alerta_depreciado and estilo != "grupo":
            cor_fundo = COR_ALERTA_DEPRECIADO
            self._tem_itens_depreciados = True
        elif estilo != "grupo" and idx % 2 == 1:
            cor_fundo = "#f7f9fa"

        frame = tk.Frame(
            self.frame_linhas,
            bg=cor_fundo,
            highlightbackground=COR_BORDA,
            highlightthickness=0,
        )
        frame.pack(fill="x", pady=(0, 1))
        frame.bind("<MouseWheel>", self._on_mousewheel)

        fonte = ("Arial", 9, "bold") if estilo == "grupo" else ("Arial", 9)
        cor_texto = COR_COMPOSICAO if estilo == "composicao" else COR_TEXTO

        widgets = {}
        for col, (chave, _titulo, largura_min, anchor, peso) in enumerate(COLUNAS):
            texto = valores.get(chave, "")
            if chave == "descricao":
                lbl = tk.Label(
                    frame,
                    text=texto,
                    font=fonte,
                    fg=cor_texto,
                    bg=cor_fundo,
                    anchor="w",
                    justify="left",
                    wraplength=self._largura_descricao,
                    padx=4,
                    pady=5,
                )
                lbl.grid(row=0, column=col, sticky="nsew", padx=(0, 1))
                widgets["lbl_descricao"] = lbl
            elif chave == "item" and estilo != "grupo":
                lbl = tk.Label(
                    frame,
                    text=texto,
                    font=fonte,
                    fg=cor_texto,
                    bg=cor_fundo,
                    anchor=anchor,
                    padx=4,
                    pady=5,
                )
                lbl.grid(row=0, column=col, sticky="nsew", padx=(10, 1))
            elif chave == "quantidade" and estilo != "grupo" and texto:
                lbl = tk.Label(
                    frame,
                    text=texto,
                    font=fonte,
                    fg=cor_texto,
                    bg=cor_fundo,
                    anchor=anchor,
                    padx=4,
                    pady=5,
                    cursor="hand2",
                )
                lbl.grid(row=0, column=col, sticky="nsew", padx=(0, 1))
                lbl.bind("<Double-1>", lambda _e, m=meta: self._duplo_clique_qtd(m))
                widgets["lbl_quantidade"] = lbl
            else:
                lbl = tk.Label(
                    frame,
                    text=texto,
                    font=fonte,
                    fg=cor_texto,
                    bg=cor_fundo,
                    anchor=anchor,
                    padx=4,
                    pady=5,
                )
                lbl.grid(row=0, column=col, sticky="nsew", padx=(0, 1))

            frame.columnconfigure(col, minsize=largura_min, weight=peso)

        registro = {
            "frame": frame,
            "meta": meta,
            "estilo": estilo,
            "cor_base": cor_fundo,
            "lbl_descricao": widgets.get("lbl_descricao"),
        }
        self._linhas.append(registro)

        if any(self._meta_coincide(meta, sel) for sel in self._selecao_metas):
            self._aplicar_destaque(registro)

        self._vincular_selecao(frame, idx)
        self._vincular_tecla_delete(frame)
        for filho in frame.winfo_children():
            self._vincular_selecao(filho, idx)
            self._vincular_tecla_delete(filho)
            filho.bind("<MouseWheel>", self._on_mousewheel)

    def _vincular_selecao(self, widget, indice_linha):
        widget.bind(
            "<Button-1>",
            lambda event, i=indice_linha: self._ao_clicar_linha(i, event),
        )

    def _duplo_clique_qtd(self, meta):
        if self.on_duplo_clique_qtd and meta.get("tipo") != TIPO_GRUPO:
            self.on_duplo_clique_qtd(meta.get("id"))

    def _meta_coincide(self, a, b):
        return a.get("tipo") == b.get("tipo") and a.get("id") == b.get("id")

    def _indice_por_meta(self, meta):
        for indice, linha in enumerate(self._linhas):
            if self._meta_coincide(linha["meta"], meta):
                return indice
        return None

    def _ao_clicar_linha(self, indice_linha, event):
        if indice_linha < 0 or indice_linha >= len(self._linhas):
            return
        meta = dict(self._linhas[indice_linha]["meta"])
        ctrl = bool(event.state & 0x4)
        shift = bool(event.state & 0x1)

        if shift and self._ancora_indice is not None:
            inicio = min(self._ancora_indice, indice_linha)
            fim = max(self._ancora_indice, indice_linha)
            self._selecao_metas = [
                dict(self._linhas[i]["meta"]) for i in range(inicio, fim + 1)
            ]
        elif ctrl:
            if any(self._meta_coincide(meta, sel) for sel in self._selecao_metas):
                self._selecao_metas = [
                    sel
                    for sel in self._selecao_metas
                    if not self._meta_coincide(meta, sel)
                ]
            else:
                self._selecao_metas.append(meta)
            self._ancora_indice = indice_linha
        else:
            self._selecao_metas = [meta]
            self._ancora_indice = indice_linha

        self.focus_set()
        self.canvas.focus_set()
        self._atualizar_destaques()

    def _atualizar_destaques(self):
        for linha in self._linhas:
            if any(self._meta_coincide(linha["meta"], sel) for sel in self._selecao_metas):
                self._aplicar_destaque(linha)
            else:
                self._remover_destaque(linha)

    def selecionar_meta(self, meta, rolar=False):
        self._selecao_metas = [dict(meta)]
        self._ancora_indice = self._indice_por_meta(meta)
        self._atualizar_destaques()
        if rolar:
            indice = self._ancora_indice
            if indice is not None:
                self._rolar_para_linha(self._linhas[indice]["frame"])

    def selecionar_metas(self, metas):
        self._selecao_metas = [dict(meta) for meta in metas]
        if self._selecao_metas:
            self._ancora_indice = self._indice_por_meta(self._selecao_metas[0])
        else:
            self._ancora_indice = None
        self._atualizar_destaques()

    def selecionar_por_id(self, tipo, item_id, rolar=True):
        for linha in self._linhas:
            if linha["meta"].get("tipo") == tipo and linha["meta"].get("id") == item_id:
                self.selecionar_meta(linha["meta"], rolar=rolar)
                return

    def selecionar_item(self, item_id, rolar=True):
        for linha in self._linhas:
            meta = linha["meta"]
            if meta.get("id") == item_id and meta.get("tipo") != TIPO_GRUPO:
                self.selecionar_meta(meta, rolar=rolar)
                return

    def _rolar_para_linha(self, frame):
        self.update_idletasks()
        y = frame.winfo_y()
        altura_visivel = self.canvas.winfo_height()
        altura_total = self.frame_linhas.winfo_height()
        if altura_total <= altura_visivel:
            return
        fracao = max(0.0, min(1.0, (y - altura_visivel * 0.2) / (altura_total - altura_visivel)))
        self.canvas.yview_moveto(fracao)

    def _aplicar_destaque(self, linha):
        for widget in linha["frame"].winfo_children():
            try:
                widget.configure(bg=COR_SELECAO)
            except tk.TclError:
                pass

    def _remover_destaque(self, linha):
        cor = linha["cor_base"]
        for widget in linha["frame"].winfo_children():
            try:
                widget.configure(bg=cor)
            except tk.TclError:
                pass

    def obter_meta_selecionada(self):
        if not self._selecao_metas:
            return None
        return dict(self._selecao_metas[0])

    def obter_metas_selecionadas(self):
        return [dict(meta) for meta in self._selecao_metas]

    def obter_grupo_id_selecionado(self):
        meta = self.obter_meta_selecionada()
        if not meta:
            return None
        if meta.get("tipo") == TIPO_GRUPO:
            return meta.get("id")
        return meta.get("grupo_id")
