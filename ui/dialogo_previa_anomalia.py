"""Prévia das composições, quantitativos e valores de uma anomalia."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui.widgets import (
    aplicar_icone_janela,
    centralizar_janela,
    criar_botao_fechar,
    formatar_decimal_br,
    formatar_moeda_br,
    preparar_toplevel,
)


def _agrupar_linhas(linhas: list[dict]) -> list[dict]:
    grupos: dict[tuple, dict] = {}
    ordem: list[tuple] = []
    for linha in linhas:
        chave = (
            str(linha.get("codigo", "")),
            str(linha.get("descricao", "")),
            str(linha.get("unidade", "")),
            round(float(linha.get("valor_unit") or 0), 4),
            str(linha.get("grupo") or ""),
        )
        if chave not in grupos:
            grupos[chave] = {
                "codigo": chave[0],
                "descricao": chave[1],
                "unidade": chave[2],
                "valor_unit": float(linha.get("valor_unit") or 0),
                "grupo": chave[4],
                "quantidade": 0.0,
                "total": 0.0,
                "detalhes": [],
            }
            ordem.append(chave)
        grupo = grupos[chave]
        quantidade = float(linha.get("quantidade") or 0)
        total = float(linha.get("total") or 0)
        grupo["quantidade"] += quantidade
        grupo["total"] += total
        grupo["detalhes"].append(linha)
    return [grupos[chave] for chave in ordem]


class DialogoPreviaAnomalia(tk.Toplevel):
    def __init__(
        self,
        parent,
        *,
        nome_anomalia: str,
        comodos: list[str],
        estado: str,
        linhas: list[dict],
        subtotal: float,
    ):
        super().__init__(parent)
        preparar_toplevel(self)
        self.title("Prévia da anomalia")
        aplicar_icone_janela(self)
        self.configure(bg="#ececec")
        self.transient(parent)
        self.grab_set()
        self.geometry("920x500")
        self.minsize(720, 380)

        painel = tk.Frame(self, bg="#ececec", padx=16, pady=14)
        painel.pack(fill="both", expand=True)
        painel.columnconfigure(0, weight=1)
        painel.rowconfigure(3, weight=1)

        tk.Label(
            painel,
            text="Prévia da planilha",
            font=("Arial", 12, "bold"),
            fg="#006699",
            bg="#ececec",
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        tk.Label(
            painel,
            text=nome_anomalia,
            font=("Arial", 11),
            fg="#222222",
            bg="#ececec",
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        comodos_txt = ", ".join(comodos) if comodos else "—"
        estado_txt = estado or "não selecionado"
        resumo = (
            f"Cômodos: {comodos_txt}  ·  Estado: {estado_txt}"
            f"  ·  Subtotal s/ BDI: {formatar_moeda_br(subtotal)}"
        )
        tk.Label(
            painel,
            text=resumo,
            font=("Arial", 9),
            fg="#555555",
            bg="#ececec",
            anchor="w",
            wraplength=920,
            justify="left",
        ).grid(row=2, column=0, sticky="ew", pady=(4, 8))

        colunas = ("codigo", "descricao", "unid", "qtd", "valor", "total", "grupo")
        tree = ttk.Treeview(painel, columns=colunas, show="headings", height=14)
        tree.heading("codigo", text="Código")
        tree.heading("descricao", text="Composição / item")
        tree.heading("unid", text="Unid.")
        tree.heading("qtd", text="Qtd.")
        tree.heading("valor", text="Valor unit.")
        tree.heading("total", text="Total s/ BDI")
        tree.heading("grupo", text="Grupo")
        tree.column("codigo", width=80, anchor="center")
        tree.column("descricao", width=340, anchor="w")
        tree.column("unid", width=55, anchor="center")
        tree.column("qtd", width=70, anchor="e")
        tree.column("valor", width=78, anchor="e")
        tree.column("total", width=88, anchor="e")
        tree.column("grupo", width=110, anchor="w")
        tree.tag_configure("nao_encontrado", foreground="#c62828")
        tree.tag_configure("total", font=("Arial", 9, "bold"))

        scroll = ttk.Scrollbar(painel, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.grid(row=3, column=0, sticky="nsew")
        scroll.grid(row=3, column=1, sticky="ns")

        grupos = _agrupar_linhas(linhas)
        for grupo in grupos:
            tags = ()
            if "não encontrado" in grupo["descricao"].casefold() or grupo["descricao"] == "Selecione um Estado":
                tags = ("nao_encontrado",)
            tree.insert(
                "",
                "end",
                values=(
                    grupo["codigo"],
                    grupo["descricao"],
                    grupo["unidade"],
                    formatar_decimal_br(grupo["quantidade"], 2),
                    formatar_moeda_br(grupo["valor_unit"]),
                    formatar_moeda_br(grupo["total"]),
                    "Repintura" if grupo["grupo"] == "repintura" else grupo["grupo"],
                ),
                tags=tags,
            )

        total_linhas = sum(float(linha.get("total") or 0) for linha in linhas)
        tree.insert(
            "",
            "end",
            values=("", "Subtotal da anomalia (s/ BDI)", "", "", "", formatar_moeda_br(total_linhas), ""),
            tags=("total",),
        )

        if not estado:
            tk.Label(
                painel,
                text="Selecione um Estado para carregar os valores unitários da SINAPI.",
                font=("Arial", 9),
                fg="#a67c00",
                bg="#ececec",
                anchor="w",
            ).grid(row=4, column=0, sticky="w", pady=(8, 0))

        botoes = tk.Frame(painel, bg="#ececec")
        botoes.grid(row=5, column=0, columnspan=2, sticky="e", pady=(12, 0))
        criar_botao_fechar(botoes, command=self.destroy).pack(side="right")

        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        centralizar_janela(self, parent)
