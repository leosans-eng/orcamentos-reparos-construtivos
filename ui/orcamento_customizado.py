import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from core.orcamento_customizado import (
    TIPO_COMPOSICAO_PROPRIA,
    TIPO_GRUPO,
    TIPO_SINAPI,
    OrcamentoCustomizado,
    rotulo_item,
    subtotal_grupo,
    subtotal_item,
)
from core.sinapi_busca import obter_item_sinapi, obter_unidades_sinapi, pesquisar_sinapi
from ui.widgets import COR_TITULO_PADRAO, criar_botao_voltar

DEBOUNCE_BUSCA_MS = 250
UNIDADE_TODAS = "Todas"


def _formatar_moeda(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return str(valor)


def _formatar_quantidade(valor):
    try:
        v = float(valor)
        if v == int(v):
            return str(int(v))
        return f"{v:,.4f}".rstrip("0").rstrip(".").replace(".", ",")
    except (TypeError, ValueError):
        return str(valor)


class OrcamentoCustomizadoFrame(tk.Frame):
    def __init__(self, parent, ctx, on_voltar):
        super().__init__(parent, bg="#ececec")
        self.ctx = ctx
        self.on_voltar = on_voltar
        self.orcamento = OrcamentoCustomizado()
        self._job_busca = None
        self._mapa_tree = {}
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
            text="Orçamento Customizado",
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

        painel_principal = tk.PanedWindow(
            self, orient="horizontal", sashwidth=6, bg="#cccccc", sashrelief="raised"
        )
        painel_principal.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self._montar_painel_orcamento(painel_principal)
        self._montar_painel_busca(painel_principal)

        painel_principal.paneconfigure(self.frame_orcamento, minsize=360)
        painel_principal.paneconfigure(self.frame_busca, minsize=320)

    def _montar_painel_orcamento(self, painel_principal):
        self.frame_orcamento = tk.Frame(painel_principal, bg="#ececec")
        painel_principal.add(self.frame_orcamento, stretch="always")

        topo = tk.Frame(self.frame_orcamento, bg="#ececec")
        topo.pack(fill="x", padx=4, pady=(0, 6))

        tk.Label(topo, text="Nome do orçamento:", bg="#ececec").pack(side="left")
        self.var_nome_orcamento = tk.StringVar()
        self.var_nome_orcamento.trace_add("write", self._ao_alterar_nome)
        ttk.Entry(topo, textvariable=self.var_nome_orcamento, width=36).pack(
            side="left", padx=(6, 0)
        )

        painel_tree = tk.LabelFrame(
            self.frame_orcamento,
            text="Estrutura do orçamento",
            bg="#ececec",
            padx=6,
            pady=6,
        )
        painel_tree.pack(fill="both", expand=True, padx=4, pady=(0, 6))

        colunas = ("quantidade", "unidade", "custo_unit", "total")
        self.tree_orcamento = ttk.Treeview(
            painel_tree,
            columns=colunas,
            show="tree headings",
            height=16,
            selectmode="browse",
        )
        self.tree_orcamento.heading("#0", text="Item / Grupo")
        self.tree_orcamento.heading("quantidade", text="Qtd.")
        self.tree_orcamento.heading("unidade", text="Unid.")
        self.tree_orcamento.heading("custo_unit", text="Custo unit.")
        self.tree_orcamento.heading("total", text="Total")

        self.tree_orcamento.column("#0", width=280, minwidth=160, stretch=True)
        self.tree_orcamento.column("quantidade", width=70, minwidth=55, stretch=False, anchor="e")
        self.tree_orcamento.column("unidade", width=50, minwidth=40, stretch=False, anchor="center")
        self.tree_orcamento.column("custo_unit", width=95, minwidth=80, stretch=False, anchor="e")
        self.tree_orcamento.column("total", width=95, minwidth=80, stretch=False, anchor="e")

        scroll_orc = ttk.Scrollbar(painel_tree, orient="vertical", command=self.tree_orcamento.yview)
        self.tree_orcamento.configure(yscrollcommand=scroll_orc.set)
        self.tree_orcamento.pack(side="left", fill="both", expand=True)
        scroll_orc.pack(side="right", fill="y")

        self.tree_orcamento.tag_configure("grupo", font=("Arial", 9, "bold"))
        self.tree_orcamento.tag_configure("composicao", foreground="#7b5e00")

        botoes_grupo = tk.Frame(self.frame_orcamento, bg="#ececec")
        botoes_grupo.pack(fill="x", padx=4, pady=(0, 4))

        ttk.Button(botoes_grupo, text="Novo grupo", command=self._novo_grupo).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(
            botoes_grupo, text="Remover selecionado", command=self._remover_selecionado
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            botoes_grupo,
            text="Editar quantidade",
            command=self._editar_quantidade_selecionada,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            botoes_grupo,
            text="Composição própria…",
            command=self._adicionar_composicao_propria,
        ).pack(side="left")

        rodape_orc = tk.Frame(self.frame_orcamento, bg="#f5fafc", highlightbackground="#cccccc", highlightthickness=1)
        rodape_orc.pack(fill="x", padx=4, pady=(4, 0))

        self.label_total = tk.Label(
            rodape_orc,
            text="Total geral: R$ 0,00",
            font=("Arial", 11, "bold"),
            fg="#006699",
            bg="#f5fafc",
            anchor="e",
            padx=10,
            pady=8,
        )
        self.label_total.pack(fill="x")

        self.label_dica_orc = tk.Label(
            self.frame_orcamento,
            text=(
                "Crie grupos (ex.: Serviços preliminares), selecione um grupo e adicione "
                "itens SINAPI pela busca ao lado. Duplo clique na quantidade para editar."
            ),
            font=("Arial", 8),
            fg="#666666",
            bg="#ececec",
            justify="left",
            wraplength=400,
        )
        self.label_dica_orc.pack(fill="x", padx=6, pady=(6, 0))

        self.tree_orcamento.bind("<Double-1>", self._ao_duplo_clique_orcamento)

    def _montar_painel_busca(self, painel_principal):
        self.frame_busca = tk.Frame(painel_principal, bg="#ececec")
        painel_principal.add(self.frame_busca, stretch="always")

        painel_busca = tk.LabelFrame(
            self.frame_busca,
            text="Buscar na SINAPI",
            bg="#ececec",
            padx=8,
            pady=6,
        )
        painel_busca.pack(fill="x", padx=4, pady=(0, 6))

        linha_filtros = tk.Frame(painel_busca, bg="#ececec")
        linha_filtros.pack(fill="x")

        tk.Label(linha_filtros, text="Estado:", bg="#ececec").grid(
            row=0, column=0, padx=(2, 4), pady=3, sticky="w"
        )
        estados = self.ctx.obter_estados()
        self.combo_estado = ttk.Combobox(
            linha_filtros, values=estados, width=7, state="readonly"
        )
        self.combo_estado.grid(row=0, column=1, padx=2, pady=3, sticky="w")
        if estados:
            self.combo_estado.set("SP" if "SP" in estados else estados[0])

        tk.Label(linha_filtros, text="Unid.:", bg="#ececec").grid(
            row=0, column=2, padx=(10, 4), pady=3, sticky="w"
        )
        self.combo_unidade = ttk.Combobox(
            linha_filtros, values=[UNIDADE_TODAS], width=8, state="readonly"
        )
        self.combo_unidade.grid(row=0, column=3, padx=2, pady=3, sticky="w")
        self.combo_unidade.set(UNIDADE_TODAS)

        tk.Label(linha_filtros, text="Buscar:", bg="#ececec").grid(
            row=1, column=0, padx=(2, 4), pady=3, sticky="w"
        )
        self.var_busca = tk.StringVar()
        self.entrada_busca = ttk.Entry(linha_filtros, textvariable=self.var_busca, width=28)
        self.entrada_busca.grid(row=1, column=1, columnspan=3, padx=2, pady=3, sticky="ew")
        linha_filtros.columnconfigure(1, weight=1)

        self._atualizar_unidades()

        self.label_status_busca = tk.Label(
            painel_busca,
            text="Digite para pesquisar insumos e composições.",
            font=("Arial", 8),
            fg="#555555",
            bg="#ececec",
            anchor="w",
        )
        self.label_status_busca.pack(fill="x", pady=(4, 0))

        painel_resultados = tk.LabelFrame(
            self.frame_busca,
            text="Resultados",
            bg="#ececec",
            padx=6,
            pady=4,
        )
        painel_resultados.pack(fill="both", expand=True, padx=4, pady=(0, 6))

        colunas = ("codigo", "descricao", "unidade", "custo")
        self.tree_busca = ttk.Treeview(
            painel_resultados,
            columns=colunas,
            show="headings",
            height=12,
        )
        self.tree_busca.heading("codigo", text="Código")
        self.tree_busca.heading("descricao", text="Descrição")
        self.tree_busca.heading("unidade", text="Unid.")
        self.tree_busca.heading("custo", text="Custo unit.")

        self.tree_busca.column("codigo", width=72, minwidth=60, stretch=False)
        self.tree_busca.column("descricao", width=200, minwidth=120, stretch=True)
        self.tree_busca.column("unidade", width=45, minwidth=40, stretch=False, anchor="center")
        self.tree_busca.column("custo", width=85, minwidth=70, stretch=False, anchor="e")

        scroll_busca = ttk.Scrollbar(
            painel_resultados, orient="vertical", command=self.tree_busca.yview
        )
        self.tree_busca.configure(yscrollcommand=scroll_busca.set)
        self.tree_busca.pack(side="left", fill="both", expand=True)
        scroll_busca.pack(side="right", fill="y")

        linha_add = tk.Frame(self.frame_busca, bg="#ececec")
        linha_add.pack(fill="x", padx=4, pady=(0, 6))

        tk.Label(linha_add, text="Quantidade:", bg="#ececec").pack(side="left")
        self.var_quantidade_add = tk.StringVar(value="1")
        ttk.Entry(linha_add, textvariable=self.var_quantidade_add, width=10).pack(
            side="left", padx=(6, 12)
        )
        ttk.Button(
            linha_add,
            text="Adicionar ao grupo selecionado",
            command=self._adicionar_sinapi_ao_grupo,
        ).pack(side="left")

        self.var_busca.trace_add("write", self._ao_digitar)
        self.combo_estado.bind("<<ComboboxSelected>>", self._ao_mudar_estado)
        self.combo_unidade.bind("<<ComboboxSelected>>", lambda _e: self._executar_busca())

        if self.ctx.sinapi.empty:
            self.label_status_busca.config(
                text="Base SINAPI indisponível.",
                fg="#C62828",
            )

        self._atualizar_tree_orcamento()

    def _texto_referencia(self):
        ref = self.ctx.sinapi_referencia_rotulo
        if ref == "BASE AUSENTE":
            return "Base não carregada"
        return f"Referência SINAPI: {ref}"

    def _ao_alterar_nome(self, *_args):
        self.orcamento.definir_nome(self.var_nome_orcamento.get())

    def _unidade_selecionada(self):
        valor = self.combo_unidade.get().strip()
        return None if not valor or valor == UNIDADE_TODAS else valor

    def _aplicar_unidades(self, unidades):
        valores = [UNIDADE_TODAS] + list(unidades)
        atual = self.combo_unidade.get().strip()
        self.combo_unidade["values"] = valores
        if atual in valores:
            self.combo_unidade.set(atual)
        else:
            self.combo_unidade.set(UNIDADE_TODAS)

    def _atualizar_unidades(self, consulta=None):
        estado = self.combo_estado.get().strip()
        if consulta is None:
            consulta = self.var_busca.get() if hasattr(self, "var_busca") else ""
        if consulta and consulta.strip():
            unidades = obter_unidades_sinapi(self.ctx.sinapi, estado or None, consulta)
        else:
            unidades = obter_unidades_sinapi(self.ctx.sinapi, estado or None)
        self._aplicar_unidades(unidades)

    def _ao_mudar_estado(self, _event=None):
        self._atualizar_unidades()
        self._executar_busca()
        self._atualizar_tree_orcamento()

    def _ao_atualizar_sinapi(self):
        estados = self.ctx.obter_estados()
        self.combo_estado["values"] = estados
        if estados and self.combo_estado.get() not in estados:
            self.combo_estado.set("SP" if "SP" in estados else estados[0])
        self._atualizar_unidades()
        self.label_referencia.config(text=self._texto_referencia())
        if self.var_busca.get().strip():
            self._executar_busca()
        self._atualizar_tree_orcamento()

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
            self.label_status_busca.config(
                text="Selecione um estado.",
                fg="#C62828",
            )
            return

        resultados, mensagem, unidades = pesquisar_sinapi(
            self.ctx.sinapi,
            estado,
            consulta,
            unidade=unidade,
        )
        self._aplicar_unidades(unidades)
        self._preencher_resultados_busca(resultados)
        cor = "#555555" if not resultados.empty else "#a67c00"
        if "indisponível" in mensagem.lower() or "nenhum item" in mensagem.lower():
            cor = "#C62828"
        self.label_status_busca.config(text=mensagem, fg=cor)

    def _preencher_resultados_busca(self, df):
        self.tree_busca.delete(*self.tree_busca.get_children())
        for _, linha in df.iterrows():
            custo = linha.get("custo", 0)
            self.tree_busca.insert(
                "",
                "end",
                values=(
                    str(linha.get("codigo", "")),
                    str(linha.get("descricao", "")),
                    str(linha.get("unidade", "")),
                    _formatar_moeda(custo),
                ),
            )

    def _grupo_id_selecionado(self):
        selecionado = self.tree_orcamento.selection()
        if not selecionado:
            return None
        iid = selecionado[0]
        meta = self._mapa_tree.get(iid)
        if not meta:
            return None
        if meta["tipo"] == TIPO_GRUPO:
            return meta["id"]
        return meta.get("grupo_id")

    def _novo_grupo(self):
        nome = simpledialog.askstring(
            "Novo grupo",
            "Nome do grupo (ex.: Serviços preliminares):",
            parent=self.winfo_toplevel(),
        )
        if not nome or not nome.strip():
            return
        try:
            grupo_id = self.orcamento.adicionar_grupo(nome)
        except ValueError as exc:
            messagebox.showwarning("Grupo", str(exc), parent=self.winfo_toplevel())
            return
        self._atualizar_tree_orcamento()
        self._selecionar_grupo_na_tree(grupo_id)

    def _selecionar_grupo_na_tree(self, grupo_id):
        for iid, meta in self._mapa_tree.items():
            if meta.get("tipo") == TIPO_GRUPO and meta.get("id") == grupo_id:
                self.tree_orcamento.selection_set(iid)
                self.tree_orcamento.focus(iid)
                self.tree_orcamento.see(iid)
                break

    def _parse_quantidade(self, texto):
        limpo = str(texto).strip().replace(",", ".")
        return float(limpo)

    def _adicionar_sinapi_ao_grupo(self):
        grupo_id = self._grupo_id_selecionado()
        if not grupo_id:
            messagebox.showinfo(
                "Adicionar item",
                "Selecione um grupo na árvore do orçamento antes de adicionar itens.",
                parent=self.winfo_toplevel(),
            )
            return

        selecionado = self.tree_busca.selection()
        if not selecionado:
            messagebox.showinfo(
                "Adicionar item",
                "Selecione um item nos resultados da busca SINAPI.",
                parent=self.winfo_toplevel(),
            )
            return

        valores = self.tree_busca.item(selecionado[0], "values")
        if len(valores) < 4:
            return

        codigo, descricao, unidade, custo_fmt = valores
        estado = self.combo_estado.get().strip()

        try:
            quantidade = self._parse_quantidade(self.var_quantidade_add.get())
        except ValueError:
            messagebox.showwarning(
                "Quantidade",
                "Informe um valor numérico válido para a quantidade.",
                parent=self.winfo_toplevel(),
            )
            return

        custo_str = custo_fmt.replace("R$", "").strip().replace(".", "").replace(",", ".")
        try:
            custo = float(custo_str)
        except ValueError:
            custo = 0.0

        try:
            item_id = self.orcamento.adicionar_item_sinapi(
                grupo_id,
                codigo,
                descricao,
                unidade,
                custo,
                quantidade,
                estado,
            )
        except ValueError as exc:
            messagebox.showwarning("Adicionar item", str(exc), parent=self.winfo_toplevel())
            return

        self._atualizar_tree_orcamento()
        self._selecionar_item_na_tree(item_id)

    def _selecionar_item_na_tree(self, item_id):
        for iid, meta in self._mapa_tree.items():
            if meta.get("tipo") in (TIPO_SINAPI, TIPO_COMPOSICAO_PROPRIA) and meta.get("id") == item_id:
                self.tree_orcamento.selection_set(iid)
                self.tree_orcamento.focus(iid)
                self.tree_orcamento.see(iid)
                break

    def _adicionar_composicao_propria(self):
        grupo_id = self._grupo_id_selecionado()
        if not grupo_id:
            messagebox.showinfo(
                "Composição própria",
                "Selecione um grupo na árvore do orçamento.",
                parent=self.winfo_toplevel(),
            )
            return

        nome = simpledialog.askstring(
            "Composição própria",
            "Nome do item (ex.: Reparo de trincas e fissuras com PU):",
            parent=self.winfo_toplevel(),
        )
        if not nome or not nome.strip():
            return

        unidade = simpledialog.askstring(
            "Composição própria",
            "Unidade de medida (ex.: m, m², un):",
            initialvalue="m",
            parent=self.winfo_toplevel(),
        )
        if not unidade or not unidade.strip():
            return

        try:
            item_id = self.orcamento.adicionar_composicao_propria(
                grupo_id, nome, unidade, quantidade=1.0
            )
        except ValueError as exc:
            messagebox.showwarning(
                "Composição própria", str(exc), parent=self.winfo_toplevel()
            )
            return

        messagebox.showinfo(
            "Composição própria",
            (
                "Item registrado como composição própria (em desenvolvimento).\n\n"
                "No futuro você poderá vincular insumos e composições SINAPI "
                "com coeficientes definidos por você."
            ),
            parent=self.winfo_toplevel(),
        )
        self._atualizar_tree_orcamento()
        self._selecionar_item_na_tree(item_id)

    def _meta_selecionada(self):
        selecionado = self.tree_orcamento.selection()
        if not selecionado:
            return None, None
        iid = selecionado[0]
        return iid, self._mapa_tree.get(iid)

    def _remover_selecionado(self):
        iid, meta = self._meta_selecionada()
        if not meta:
            messagebox.showinfo(
                "Remover",
                "Selecione um grupo ou item para remover.",
                parent=self.winfo_toplevel(),
            )
            return

        if meta["tipo"] == TIPO_GRUPO:
            if not messagebox.askyesno(
                "Remover grupo",
                f"Remover o grupo e todos os seus itens?",
                parent=self.winfo_toplevel(),
            ):
                return
            self.orcamento.remover_grupo(meta["id"])
        else:
            self.orcamento.remover_item(meta["id"])

        self._atualizar_tree_orcamento()

    def _editar_quantidade_selecionada(self):
        _iid, meta = self._meta_selecionada()
        if not meta or meta["tipo"] == TIPO_GRUPO:
            messagebox.showinfo(
                "Quantidade",
                "Selecione um item (SINAPI ou composição própria) para editar a quantidade.",
                parent=self.winfo_toplevel(),
            )
            return
        self._dialogo_editar_quantidade(meta["id"])

    def _ao_duplo_clique_orcamento(self, event):
        iid = self.tree_orcamento.identify_row(event.y)
        coluna = self.tree_orcamento.identify_column(event.x)
        if not iid or coluna != "#1":
            return
        meta = self._mapa_tree.get(iid)
        if not meta or meta["tipo"] == TIPO_GRUPO:
            return
        self._dialogo_editar_quantidade(meta["id"])

    def _dialogo_editar_quantidade(self, item_id):
        _grupo, item = self.orcamento.obter_item(item_id)
        if item is None:
            return

        nova = simpledialog.askstring(
            "Editar quantidade",
            f"Nova quantidade para:\n{rotulo_item(item)}",
            initialvalue=_formatar_quantidade(item["quantidade"]),
            parent=self.winfo_toplevel(),
        )
        if nova is None:
            return
        try:
            quantidade = self._parse_quantidade(nova)
            self.orcamento.atualizar_quantidade(item_id, quantidade)
        except ValueError as exc:
            messagebox.showwarning("Quantidade", str(exc), parent=self.winfo_toplevel())
            return

        self._atualizar_tree_orcamento()
        self._selecionar_item_na_tree(item_id)

    def _atualizar_tree_orcamento(self):
        self.tree_orcamento.delete(*self.tree_orcamento.get_children())
        self._mapa_tree.clear()

        estado_atual = self.combo_estado.get().strip()

        for grupo in self.orcamento.grupos:
            sub = subtotal_grupo(grupo)
            iid_grupo = self.tree_orcamento.insert(
                "",
                "end",
                text=grupo["nome"],
                values=("", "", "", _formatar_moeda(sub)),
                open=True,
                tags=("grupo",),
            )
            self._mapa_tree[iid_grupo] = {"tipo": TIPO_GRUPO, "id": grupo["id"]}

            for item in grupo["itens"]:
                if item["tipo"] == TIPO_SINAPI:
                    custo = item["custo_unitario"]
                    if estado_atual and item.get("estado") != estado_atual:
                        linha = obter_item_sinapi(
                            self.ctx.sinapi, item["codigo"], estado_atual
                        )
                        if linha is not None:
                            try:
                                custo = float(linha.get("custo", custo))
                            except (TypeError, ValueError):
                                pass
                            item["custo_unitario"] = custo
                            item["estado"] = estado_atual

                    total = subtotal_item(item)
                    tag = ()
                    iid_item = self.tree_orcamento.insert(
                        iid_grupo,
                        "end",
                        text=rotulo_item(item),
                        values=(
                            _formatar_quantidade(item["quantidade"]),
                            item["unidade"],
                            _formatar_moeda(custo),
                            _formatar_moeda(total),
                        ),
                        tags=tag,
                    )
                else:
                    iid_item = self.tree_orcamento.insert(
                        iid_grupo,
                        "end",
                        text=rotulo_item(item),
                        values=(
                            _formatar_quantidade(item["quantidade"]),
                            item["unidade"],
                            "—",
                            _formatar_moeda(0),
                        ),
                        tags=("composicao",),
                    )

                self._mapa_tree[iid_item] = {
                    "tipo": item["tipo"],
                    "id": item["id"],
                    "grupo_id": grupo["id"],
                }

            sub_atualizado = subtotal_grupo(grupo)
            self.tree_orcamento.item(
                iid_grupo, values=("", "", "", _formatar_moeda(sub_atualizado))
            )

        self.label_total.config(text=f"Total geral: {_formatar_moeda(self.orcamento.total())}")

    def focar(self):
        self.entrada_busca.focus_set()
