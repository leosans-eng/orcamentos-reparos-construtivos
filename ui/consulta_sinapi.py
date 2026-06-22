import tkinter as tk
from tkinter import ttk

from core.sinapi_busca import buscar_sinapi, obter_unidades_sinapi
from ui.widgets import COR_TITULO_PADRAO, criar_botao_voltar

# Debounce proposital (ms): evita rebuscar a cada tecla enquanto o usuário digita.
DEBOUNCE_BUSCA_MS = 300
UNIDADE_TODAS = "Todas"


class ConsultaSinapiFrame(tk.Frame):
    def __init__(self, parent, ctx, on_voltar):
        super().__init__(parent, bg="#ececec")
        self.ctx = ctx
        self.on_voltar = on_voltar
        self._job_busca = None
        self._montar()
        ctx.registrar_callback_sinapi(self._ao_atualizar_sinapi)

    def _montar(self):
        barra = tk.Frame(self, bg="#ececec")
        barra.pack(fill="x", padx=10, pady=(8, 0))
        criar_botao_voltar(barra, self.on_voltar, bg_parent="#ececec").pack(side="left")

        cabecalho = tk.Frame(self, bg="#ececec")
        cabecalho.pack(fill="x", padx=16, pady=(12, 8))

        tk.Label(
            cabecalho,
            text="Consulta SINAPI",
            font=("Arial", 14, "bold"),
            fg=COR_TITULO_PADRAO,
            bg="#ececec",
        ).pack(side="left")

        self.label_referencia = tk.Label(
            cabecalho,
            text=self._texto_referencia(),
            font=("Arial", 9),
            fg="#666666",
            bg="#ececec",
        )
        self.label_referencia.pack(side="right")

        painel_busca = tk.LabelFrame(
            self,
            text="Pesquisar insumo ou composição",
            bg="#ececec",
            padx=10,
            pady=8,
        )
        painel_busca.pack(fill="x", padx=16, pady=(0, 8))

        linha_filtros = tk.Frame(painel_busca, bg="#ececec")
        linha_filtros.pack(fill="x")

        tk.Label(linha_filtros, text="Estado:", bg="#ececec").grid(
            row=0, column=0, padx=(4, 6), pady=4, sticky="w"
        )

        estados = self.ctx.obter_estados()
        self.combo_estado = ttk.Combobox(
            linha_filtros,
            values=estados,
            width=8,
            state="readonly",
        )
        self.combo_estado.grid(row=0, column=1, padx=4, pady=4, sticky="w")
        if estados:
            self.combo_estado.set("SP" if "SP" in estados else estados[0])

        tk.Label(linha_filtros, text="Unidade:", bg="#ececec").grid(
            row=0, column=2, padx=(16, 6), pady=4, sticky="w"
        )

        self.combo_unidade = ttk.Combobox(
            linha_filtros,
            values=[UNIDADE_TODAS],
            width=10,
            state="readonly",
        )
        self.combo_unidade.grid(row=0, column=3, padx=4, pady=4, sticky="w")
        self.combo_unidade.set(UNIDADE_TODAS)
        self._atualizar_unidades()

        tk.Label(linha_filtros, text="Buscar:", bg="#ececec").grid(
            row=0, column=4, padx=(16, 6), pady=4, sticky="w"
        )

        self.var_busca = tk.StringVar()
        self.entrada_busca = ttk.Entry(linha_filtros, textvariable=self.var_busca, width=40)
        self.entrada_busca.grid(row=0, column=5, padx=4, pady=4, sticky="ew")
        linha_filtros.columnconfigure(5, weight=1)

        tk.Label(
            painel_busca,
            text=(
                "Digite palavras do insumo/composição ou o código SINAPI. "
                "Acentos são opcionais e não é preciso digitar todas as palavras — "
                "ex.: “ceramica piso” ou “reboco parede”."
            ),
            font=("Arial", 8),
            fg="#666666",
            bg="#ececec",
            wraplength=900,
            justify="left",
        ).pack(anchor="w", padx=4, pady=(4, 0))

        self.label_status = tk.Label(
            self,
            text="Selecione o estado e digite para pesquisar.",
            font=("Arial", 9),
            fg="#555555",
            bg="#ececec",
            anchor="w",
        )
        self.label_status.pack(fill="x", padx=18, pady=(0, 4))

        painel_resultados = tk.LabelFrame(
            self,
            text="Resultados",
            bg="#ececec",
            padx=8,
            pady=6,
        )
        painel_resultados.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        colunas = ("codigo", "descricao", "unidade", "custo")
        self.tree = ttk.Treeview(
            painel_resultados,
            columns=colunas,
            show="headings",
            height=14,
        )
        self.tree.heading("codigo", text="Código")
        self.tree.heading("descricao", text="Descrição")
        self.tree.heading("unidade", text="Unid.")
        self.tree.heading("custo", text="Custo unit. (R$)")

        self.tree.column("codigo", width=90, minwidth=70, stretch=False)
        self.tree.column("descricao", width=520, minwidth=200, stretch=True)
        self.tree.column("unidade", width=60, minwidth=50, stretch=False, anchor="center")
        self.tree.column("custo", width=110, minwidth=90, stretch=False, anchor="e")

        scroll_y = ttk.Scrollbar(painel_resultados, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scroll_y.pack(side="right", fill="y")

        painel_detalhe = tk.Frame(self, bg="#f5fafc", highlightbackground="#cccccc", highlightthickness=1)
        painel_detalhe.pack(fill="x", padx=16, pady=(0, 10))

        self.label_detalhe = tk.Label(
            painel_detalhe,
            text="Selecione um item na lista para ver os detalhes.",
            font=("Arial", 9),
            fg="#444444",
            bg="#f5fafc",
            wraplength=920,
            justify="left",
            anchor="w",
            padx=10,
            pady=8,
        )
        self.label_detalhe.pack(fill="x")

        self.var_busca.trace_add("write", self._ao_digitar)
        self.combo_estado.bind("<<ComboboxSelected>>", self._ao_mudar_estado)
        self.combo_unidade.bind("<<ComboboxSelected>>", lambda _e: self._executar_busca())
        self.tree.bind("<<TreeviewSelect>>", self._ao_selecionar_item)

        if self.ctx.sinapi.empty:
            self.label_status.config(
                text="Base SINAPI indisponível. Aguarde a atualização ou verifique sinapi/sinapi_processado.",
                fg="#C62828",
            )

    def _texto_referencia(self):
        ref = self.ctx.sinapi_referencia_rotulo
        if ref == "BASE AUSENTE":
            return "Base não carregada"
        return f"Referência SINAPI: {ref}"

    def _unidade_selecionada(self):
        valor = self.combo_unidade.get().strip()
        return None if not valor or valor == UNIDADE_TODAS else valor

    def _atualizar_unidades(self):
        estado = self.combo_estado.get().strip()
        unidades = obter_unidades_sinapi(self.ctx.sinapi, estado or None)
        valores = [UNIDADE_TODAS] + unidades
        atual = self.combo_unidade.get().strip()
        self.combo_unidade["values"] = valores
        if atual in valores:
            self.combo_unidade.set(atual)
        else:
            self.combo_unidade.set(UNIDADE_TODAS)

    def _ao_mudar_estado(self, _event=None):
        self._atualizar_unidades()
        self._executar_busca()

    def _ao_atualizar_sinapi(self):
        estados = self.ctx.obter_estados()
        self.combo_estado["values"] = estados
        if estados and self.combo_estado.get() not in estados:
            self.combo_estado.set("SP" if "SP" in estados else estados[0])
        self._atualizar_unidades()
        self.label_referencia.config(text=self._texto_referencia())
        if self.var_busca.get().strip():
            self._executar_busca()

    def _ao_digitar(self, *_args):
        if self._job_busca is not None:
            self.after_cancel(self._job_busca)
        self._job_busca = self.after(DEBOUNCE_BUSCA_MS, self._executar_busca)

    def _executar_busca(self):
        if self._job_busca is not None:
            self.after_cancel(self._job_busca)
            self._job_busca = None

        estado = self.combo_estado.get().strip()
        consulta = self.var_busca.get()
        unidade = self._unidade_selecionada()

        if not estado:
            self.label_status.config(
                text="Selecione um estado antes de pesquisar.",
                fg="#C62828",
            )
            return

        resultados, mensagem = buscar_sinapi(
            self.ctx.sinapi,
            estado,
            consulta,
            unidade=unidade,
        )
        self._preencher_resultados(resultados)
        cor = "#555555" if not resultados.empty else "#a67c00"
        if "indisponível" in mensagem.lower() or "nenhum item" in mensagem.lower():
            cor = "#C62828"
        self.label_status.config(text=mensagem, fg=cor)

    def _preencher_resultados(self, df):
        self.tree.delete(*self.tree.get_children())
        for _, linha in df.iterrows():
            custo = linha.get("custo", 0)
            try:
                custo_fmt = f"R$ {float(custo):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            except (TypeError, ValueError):
                custo_fmt = str(custo)

            self.tree.insert(
                "",
                "end",
                values=(
                    str(linha.get("codigo", "")),
                    str(linha.get("descricao", "")),
                    str(linha.get("unidade", "")),
                    custo_fmt,
                ),
            )
        self.label_detalhe.config(text="Selecione um item na lista para ver os detalhes.")

    def _ao_selecionar_item(self, _event=None):
        selecionado = self.tree.selection()
        if not selecionado:
            return
        valores = self.tree.item(selecionado[0], "values")
        if len(valores) < 4:
            return
        codigo, descricao, unidade, custo = valores
        estado = self.combo_estado.get().strip()
        self.label_detalhe.config(
            text=(
                f"Código: {codigo}  ·  Estado: {estado}  ·  Unidade: {unidade}  ·  "
                f"Custo: {custo}\n{descricao}"
            ),
        )

    def focar(self):
        self.entrada_busca.focus_set()
