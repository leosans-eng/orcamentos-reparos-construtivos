"""Prévia dos itens cadastrados em uma composição própria do orçamento."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui.temas import aplicar_chrome_dialogo
from ui.widgets import (
    aplicar_icone_janela,
    centralizar_janela,
    criar_botao_fechar,
    formatar_decimal_br,
    formatar_moeda_br,
    preparar_toplevel,
)


class DialogoPreviaComposicao(tk.Toplevel):
    def __init__(
        self,
        parent,
        *,
        item: dict,
        composicao: dict | None,
        estado: str,
        linhas: list[dict],
        custo_unitario: float,
        total: float,
        on_alterar_discriminar=None,
    ):
        super().__init__(parent)
        preparar_toplevel(self)
        aplicar_chrome_dialogo(self)
        cores = self._cores
        self.title("Prévia da composição")
        aplicar_icone_janela(self)
        self.configure(bg=cores.fundo)
        self.transient(parent)
        self.grab_set()
        self.geometry("960x540")
        self.minsize(760, 400)

        self._item_id = item.get("id")
        self.on_alterar_discriminar = on_alterar_discriminar

        painel = tk.Frame(self, bg=cores.fundo, padx=16, pady=14)
        painel.pack(fill="both", expand=True)
        painel.columnconfigure(0, weight=1)
        painel.rowconfigure(3, weight=1)

        tk.Label(
            painel,
            text="Itens da composição própria",
            font=("Arial", 12, "bold"),
            fg=cores.titulo,
            bg=cores.fundo,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        nome = str(item.get("nome") or (composicao or {}).get("nome") or "—").strip()
        tk.Label(
            painel,
            text=nome,
            font=("Arial", 11),
            fg=cores.texto,
            bg=cores.fundo,
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        codigo = str(item.get("codigo") or "").strip() or "—"
        unidade = str(item.get("unidade") or "").strip() or "—"
        try:
            quantidade = float(item.get("quantidade") or 0)
        except (TypeError, ValueError):
            quantidade = 0.0
        estado_txt = estado or "não selecionado"
        resumo = (
            f"Código: {codigo}  ·  Unid.: {unidade}"
            f"  ·  Qtd.: {formatar_decimal_br(quantidade)}"
            f"  ·  Estado: {estado_txt}"
            f"  ·  Custo unit. s/ BDI: {formatar_moeda_br(custo_unitario)}"
            f"  ·  Total s/ BDI: {formatar_moeda_br(total)}"
        )
        tk.Label(
            painel,
            text=resumo,
            font=("Arial", 9),
            fg=cores.texto_suave,
            bg=cores.fundo,
            anchor="w",
            wraplength=920,
            justify="left",
        ).grid(row=2, column=0, sticky="ew", pady=(4, 8))

        colunas = (
            "codigo",
            "tipo",
            "descricao",
            "unid",
            "coef",
            "qtd",
            "valor",
            "total",
        )
        tree = ttk.Treeview(painel, columns=colunas, show="headings", height=14)
        tree.heading("codigo", text="Código")
        tree.heading("tipo", text="Tipo")
        tree.heading("descricao", text="Descrição")
        tree.heading("unid", text="Unid.")
        tree.heading("coef", text="Coef.")
        tree.heading("qtd", text="Qtd.")
        tree.heading("valor", text="Valor unit.")
        tree.heading("total", text="Total s/ BDI")
        tree.column("codigo", width=80, anchor="center")
        tree.column("tipo", width=70, anchor="center")
        tree.column("descricao", width=320, anchor="w")
        tree.column("unid", width=50, anchor="center")
        tree.column("coef", width=64, anchor="e")
        tree.column("qtd", width=70, anchor="e")
        tree.column("valor", width=88, anchor="e")
        tree.column("total", width=90, anchor="e")
        tree.tag_configure("nao_encontrado", foreground=cores.perigo)
        tree.tag_configure("total", font=("Arial", 9, "bold"), foreground=cores.texto)

        scroll = ttk.Scrollbar(painel, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.grid(row=3, column=0, sticky="nsew")
        scroll.grid(row=3, column=1, sticky="ns")

        if composicao is None:
            tree.insert(
                "",
                "end",
                values=(
                    "",
                    "",
                    "Composição não encontrada no catálogo",
                    "",
                    "",
                    "",
                    "",
                    "",
                ),
                tags=("nao_encontrado",),
            )
        elif not linhas:
            tree.insert(
                "",
                "end",
                values=("", "", "Nenhum item cadastrado nesta composição", "", "", "", "", ""),
            )
        else:
            for linha in linhas:
                tags = ()
                if not linha.get("encontrado", True):
                    tags = ("nao_encontrado",)
                tree.insert(
                    "",
                    "end",
                    values=(
                        linha.get("codigo", ""),
                        linha.get("tipo", ""),
                        linha.get("descricao", ""),
                        linha.get("unidade", ""),
                        formatar_decimal_br(linha.get("coeficiente", 0)),
                        formatar_decimal_br(linha.get("quantidade", 0)),
                        formatar_moeda_br(linha.get("valor_unit", 0)),
                        formatar_moeda_br(linha.get("total", 0)),
                    ),
                    tags=tags,
                )

        total_linhas = sum(float(linha.get("total") or 0) for linha in linhas)
        tree.insert(
            "",
            "end",
            values=(
                "",
                "",
                "Subtotal da composição (s/ BDI)",
                "",
                "",
                "",
                "",
                formatar_moeda_br(total_linhas if linhas else total),
            ),
            tags=("total",),
        )

        avisos = tk.Frame(painel, bg=cores.fundo)
        avisos.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        if composicao is None:
            tk.Label(
                avisos,
                text="Esta composição não está mais no catálogo. Recadastre-a ou substitua o item.",
                font=("Arial", 9),
                fg=cores.perigo,
                bg=cores.fundo,
                anchor="w",
                wraplength=900,
                justify="left",
            ).pack(fill="x")
        elif not estado:
            tk.Label(
                avisos,
                text="Selecione um Estado para carregar os valores unitários da SINAPI.",
                font=("Arial", 9),
                fg="#ffe082" if cores.escuro else "#a67c00",
                bg=cores.fundo,
                anchor="w",
            ).pack(fill="x")

        opcoes = tk.Frame(painel, bg=cores.fundo)
        opcoes.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.var_discriminar = tk.BooleanVar(
            value=bool(item.get("discriminar_componentes"))
        )
        style = ttk.Style(self)
        try:
            style.layout("Fundo.TCheckbutton", style.layout("Cartao.TCheckbutton"))
        except tk.TclError:
            pass
        style.configure(
            "Fundo.TCheckbutton",
            background=cores.fundo,
            foreground=cores.texto,
            focuscolor=cores.fundo,
        )
        style.map(
            "Fundo.TCheckbutton",
            background=[
                ("active", cores.fundo),
                ("selected", cores.fundo),
                ("pressed", cores.fundo),
                ("!disabled", cores.fundo),
            ],
            foreground=[
                ("active", cores.texto),
                ("selected", cores.texto),
                ("disabled", cores.texto_suave),
            ],
        )
        chk = ttk.Checkbutton(
            opcoes,
            text="Discriminar itens no orçamento final (Excel/Word)",
            variable=self.var_discriminar,
            command=self._ao_alternar_discriminar,
            style="Fundo.TCheckbutton",
        )
        chk.pack(anchor="w")
        tk.Label(
            opcoes,
            text="Opcional. Apenas para composições próprias. Se marcada, a planilha (Excel/Word) lista os componentes cadastrados no lugar da linha única de composição própria.",
            font=("Arial", 8),
            fg=cores.texto_suave,
            bg=cores.fundo,
            anchor="w",
            wraplength=900,
            justify="left",
        ).pack(anchor="w", pady=(2, 0))
        if on_alterar_discriminar is None:
            chk.configure(state="disabled")

        botoes = tk.Frame(painel, bg=cores.fundo)
        botoes.grid(row=6, column=0, columnspan=2, sticky="e", pady=(12, 0))
        criar_botao_fechar(botoes, command=self.destroy).pack(side="right")

        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        centralizar_janela(self, parent)

    def _ao_alternar_discriminar(self):
        if self.on_alterar_discriminar is None or not self._item_id:
            return
        self.on_alterar_discriminar(
            self._item_id, bool(self.var_discriminar.get())
        )
