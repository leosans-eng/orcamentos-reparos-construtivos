"""Janela para visualizar ambientes da planta Idebras e aplicar metragens."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from core.idebras_client import AmbienteIdebras, PlantaIdebras, medidas_para_orcamento
from ui.icones import criar_botao_ttk_com_icone
from ui.temas import aplicar_chrome_dialogo
from ui.widgets import aplicar_icone_janela, centralizar_janela, criar_botao_fechar, preparar_toplevel


class DialogoAmbientesPlanta(tk.Toplevel):
    def __init__(
        self,
        parent,
        *,
        conjunto_nome: str,
        planta: PlantaIdebras,
        ambientes: list[AmbienteIdebras],
        on_aplicar,
    ):
        super().__init__(parent)
        preparar_toplevel(self)
        cores, estilos = aplicar_chrome_dialogo(self)
        fundo = cores.fundo
        self.on_aplicar = on_aplicar
        self.ambientes = list(ambientes)
        self._refs_icones: list = []
        self.title("Ambientes da planta")
        aplicar_icone_janela(self)
        self.transient(parent)
        self.grab_set()
        self.geometry("980x460")
        self.minsize(760, 360)

        painel = tk.Frame(self, bg=fundo, padx=16, pady=14)
        painel.pack(fill="both", expand=True)
        painel.rowconfigure(2, weight=1)
        painel.columnconfigure(0, weight=1)

        tk.Label(
            painel,
            text="Ambientes da planta",
            font=("Arial", 12, "bold"),
            fg=cores.titulo,
            bg=fundo,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        resumo = (
            f"{conjunto_nome}  ·  {planta.nome}"
            f"  ·  Área total {planta.area_total} m²"
        )
        if planta.metodo_construtivo:
            resumo += f"  ·  {planta.metodo_construtivo}"
        tk.Label(
            painel,
            text=resumo,
            font=("Arial", 9),
            fg=cores.texto_suave,
            bg=fundo,
            anchor="w",
            wraplength=900,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(2, 8))

        colunas = (
            "ambiente",
            "mapeamento",
            "piso",
            "parede",
            "ceramica",
            "perimetro",
            "tipo_piso",
            "teto",
        )
        tree = ttk.Treeview(painel, columns=colunas, show="headings", height=12)
        tree.heading("ambiente", text="Ambiente")
        tree.heading("mapeamento", text="Preenche")
        tree.heading("piso", text="Piso (m²)")
        tree.heading("parede", text="Rev. Arg. (m²)")
        tree.heading("ceramica", text="Rev. Cer. (m²)")
        tree.heading("perimetro", text="Perímetro")
        tree.heading("tipo_piso", text="Tipo de piso")
        tree.heading("teto", text="Teto")
        tree.column("ambiente", width=160, anchor="w")
        tree.column("mapeamento", width=130, anchor="w")
        tree.column("piso", width=90, anchor="e")
        tree.column("parede", width=110, anchor="e")
        tree.column("ceramica", width=110, anchor="e")
        tree.column("perimetro", width=90, anchor="e")
        tree.column("tipo_piso", width=150, anchor="w")
        tree.column("teto", width=110, anchor="w")

        scroll = ttk.Scrollbar(painel, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.grid(row=2, column=0, sticky="nsew")
        scroll.grid(row=2, column=1, sticky="ns")

        mapeados = 0
        for amb in self.ambientes:
            destino = amb.comodo_orc or "— (não usado)"
            if amb.comodo_orc:
                mapeados += 1
            tree.insert(
                "",
                "end",
                values=(
                    amb.ambiente,
                    destino,
                    amb.area_piso,
                    amb.area_parede,
                    amb.area_parede_ceramica,
                    amb.perimetro_piso,
                    amb.tipo_piso,
                    amb.tipo_teto,
                ),
            )

        nota = (
            f"{mapeados} ambiente(s) correspondem aos cômodos do orçamento. "
            "Clique em Preencher para aplicar as metragens."
        )
        tk.Label(
            painel,
            text=nota,
            font=("Arial", 9),
            fg=cores.texto,
            bg=fundo,
            anchor="w",
        ).grid(row=3, column=0, sticky="w", pady=(8, 0))

        botoes = tk.Frame(painel, bg=fundo)
        botoes.grid(row=4, column=0, columnspan=2, sticky="e", pady=(12, 0))
        criar_botao_fechar(botoes, command=self.destroy).pack(side="right", padx=(6, 0))
        criar_botao_ttk_com_icone(
            botoes,
            texto="Preencher",
            nome_icone="color-wand-outline",
            command=self._aplicar,
            estilo=estilos.adicionar,
            cor_icone=estilos.icone_adicionar,
            refs=self._refs_icones,
        ).pack(side="right")

        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        centralizar_janela(self, parent)

    def _medidas(self):
        return medidas_para_orcamento(self.ambientes)

    def _aplicar(self):
        self.on_aplicar(self._medidas())
        self.destroy()
