import tkinter as tk
from tkinter import ttk
from typing import Literal

from core.orcamento_customizado import TIPO_GRUPO

TkAnchor = Literal["nw", "n", "ne", "w", "center", "e", "sw", "s", "se"]
Coluna = tuple[str, str, int, TkAnchor, int]

COLUNAS: tuple[Coluna, ...] = (
    ("item", "Item", 52, "center", 0),
    ("codigo", "Código", 72, "center", 0),
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
COR_TEXTO = "#333333"


class GradeOrcamento(tk.Frame):
    """Grade orçamentária com Canvas — uma linha (Frame) por item, altura variável."""

    def __init__(self, parent, on_duplo_clique_qtd=None):
        super().__init__(parent, bg="#ececec")
        self.on_duplo_clique_qtd = on_duplo_clique_qtd
        self._linhas = []
        self._selecao_meta = None
        self._largura_descricao = 280
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

        self.canvas = tk.Canvas(container, highlightthickness=0, bg=COR_FUNDO)
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
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

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
        self._selecao_meta = None

    def posicao_scroll(self):
        return self.canvas.yview()[0]

    def restaurar_scroll(self, fracao):
        if fracao is not None:
            self.canvas.yview_moveto(fracao)

    def adicionar_linha(self, meta, valores, estilo="item"):
        idx = len(self._linhas)
        cor_fundo = COR_GRUPO if estilo == "grupo" else COR_FUNDO
        if estilo != "grupo" and idx % 2 == 1:
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

        if self._selecao_meta and self._meta_coincide(meta, self._selecao_meta):
            self._aplicar_destaque(registro)

        self._vincular_selecao(frame, meta)
        for filho in frame.winfo_children():
            self._vincular_selecao(filho, meta)
            filho.bind("<MouseWheel>", self._on_mousewheel)

        self.after_idle(self._atualizar_scrollregion)

    def _vincular_selecao(self, widget, meta):
        widget.bind("<Button-1>", lambda _e, m=meta: self.selecionar_meta(m))

    def _duplo_clique_qtd(self, meta):
        if self.on_duplo_clique_qtd and meta.get("tipo") != TIPO_GRUPO:
            self.on_duplo_clique_qtd(meta.get("id"))

    def _meta_coincide(self, a, b):
        return a.get("tipo") == b.get("tipo") and a.get("id") == b.get("id")

    def selecionar_meta(self, meta):
        self._selecao_meta = dict(meta)
        for linha in self._linhas:
            if self._meta_coincide(linha["meta"], meta):
                self._aplicar_destaque(linha)
            else:
                self._remover_destaque(linha)

    def selecionar_por_id(self, tipo, item_id):
        for linha in self._linhas:
            if linha["meta"].get("tipo") == tipo and linha["meta"].get("id") == item_id:
                self.selecionar_meta(linha["meta"])
                self._rolar_para_linha(linha["frame"])
                return

    def selecionar_item(self, item_id):
        for linha in self._linhas:
            meta = linha["meta"]
            if meta.get("id") == item_id and meta.get("tipo") != TIPO_GRUPO:
                self.selecionar_meta(meta)
                self._rolar_para_linha(linha["frame"])
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
        if not self._selecao_meta:
            return None
        return dict(self._selecao_meta)

    def obter_grupo_id_selecionado(self):
        meta = self.obter_meta_selecionada()
        if not meta:
            return None
        if meta.get("tipo") == TIPO_GRUPO:
            return meta.get("id")
        return meta.get("grupo_id")
