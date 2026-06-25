import tkinter as tk
from tkinter import messagebox, ttk

from core.composicoes_proprias import (
    TIPO_COMPONENTE_MERCADO,
    TIPO_COMPONENTE_SINAPI,
    calcular_custo_unitario,
    novo_componente_mercado,
    novo_componente_sinapi,
    verificar_componentes_depreciados,
)
from core.composicoes_proprias_storage import (
    atualizar,
    carregar,
    criar,
    excluir,
    listar,
    obter_por_id,
)
from ui.orcamento_customizado import DialogoBuscaSinapi
from ui.widgets import (
    PLACEHOLDER_ESTADO,
    aplicar_icone_janela,
    centralizar_janela,
    confirmar_exclusao_com_espera,
    criar_barra_modulo,
    estado_do_combo,
    perguntar_texto,
    valores_combo_estado,
)

COR_DEPRECIADO = "#fff8e1"


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


class DialogoComponenteMercado(tk.Toplevel):
    def __init__(self, parent, on_confirmar):
        super().__init__(parent)
        self.on_confirmar = on_confirmar
        self.title("Componente de mercado")
        aplicar_icone_janela(self)
        self.configure(bg="#ececec")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        painel = tk.Frame(self, bg="#ececec", padx=16, pady=14)
        painel.pack(fill="both", expand=True)

        campos = [
            ("Código:", "codigo"),
            ("Descrição:", "descricao"),
            ("Unidade:", "unidade"),
            ("Custo unitário (R$):", "custo"),
            ("Coeficiente:", "coeficiente"),
        ]
        self.vars = {}
        for rotulo, chave in campos:
            linha = tk.Frame(painel, bg="#ececec")
            linha.pack(fill="x", pady=3)
            tk.Label(linha, text=rotulo, width=22, anchor="w", bg="#ececec").pack(side="left")
            var = tk.StringVar(value="1" if chave == "coeficiente" else "")
            self.vars[chave] = var
            ttk.Entry(linha, textvariable=var, width=36).pack(side="left", fill="x", expand=True)

        botoes = ttk.Frame(painel)
        botoes.pack(fill="x", pady=(12, 0))
        ttk.Button(botoes, text="Cancelar", command=self.destroy, style="Delete.TButton").pack(
            side="right", padx=(6, 0)
        )
        ttk.Button(botoes, text="Adicionar", command=self._confirmar, style="Add.TButton").pack(
            side="right"
        )

        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        centralizar_janela(self, parent)

    def _parse_float(self, texto):
        return float(str(texto).strip().replace(",", "."))

    def _confirmar(self):
        try:
            custo = self._parse_float(self.vars["custo"].get())
            coeficiente = self._parse_float(self.vars["coeficiente"].get())
            if coeficiente <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "Componente de mercado",
                "Informe custo e coeficiente numéricos válidos (coeficiente > 0).",
                parent=self,
            )
            return

        codigo = self.vars["codigo"].get().strip()
        descricao = self.vars["descricao"].get().strip()
        unidade = self.vars["unidade"].get().strip()
        if not descricao or not unidade:
            messagebox.showwarning(
                "Componente de mercado",
                "Informe descrição e unidade.",
                parent=self,
            )
            return

        componente = novo_componente_mercado(codigo, descricao, unidade, custo, coeficiente)
        self.on_confirmar(componente)
        self.destroy()


class ComposicoesPropriasFrame(tk.Frame):
    def __init__(self, parent, ctx, on_voltar):
        super().__init__(parent, bg="#ececec")
        self.ctx = ctx
        self.on_voltar = on_voltar
        self._dados = carregar()
        self._composicao_editando_id = None
        self._montar()
        ctx.registrar_callback_sinapi(self._ao_atualizar_sinapi)

    def _texto_referencia(self):
        ref = self.ctx.sinapi_referencia_rotulo
        if ref == "BASE AUSENTE":
            return "Base não carregada"
        return f"Referência SINAPI: {ref}"

    def _montar(self):
        self.label_referencia = criar_barra_modulo(
            self,
            "Configurar Composições Próprias",
            self.on_voltar,
            texto_referencia=self._texto_referencia(),
        )

        conteudo = tk.Frame(self, bg="#ececec")
        conteudo.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        linha_topo = tk.Frame(conteudo, bg="#ececec")
        linha_topo.pack(fill="x", pady=(0, 8))

        tk.Label(linha_topo, text="Estado (prévia de custos):", bg="#ececec").pack(side="left")
        estados = self.ctx.obter_estados()
        self.combo_estado = ttk.Combobox(
            linha_topo, values=valores_combo_estado(estados), width=14, state="readonly"
        )
        self.combo_estado.pack(side="left", padx=(4, 12))
        self.combo_estado.set(PLACEHOLDER_ESTADO)
        self.combo_estado.bind("<<ComboboxSelected>>", self._atualizar_listas)

        painel = tk.PanedWindow(conteudo, orient=tk.HORIZONTAL, sashwidth=6, bg="#cccccc")
        painel.pack(fill="both", expand=True)

        esquerda = tk.LabelFrame(
            painel, text="Composições cadastradas", bg="#ececec", padx=6, pady=6
        )
        painel.add(esquerda, minsize=320)

        self.var_busca = tk.StringVar()
        self.var_busca.trace_add("write", lambda *_a: self._atualizar_lista_composicoes())
        linha_busca = tk.Frame(esquerda, bg="#ececec")
        linha_busca.pack(fill="x", pady=(0, 6))
        tk.Label(linha_busca, text="Filtrar:", bg="#ececec").pack(side="left")
        ttk.Entry(linha_busca, textvariable=self.var_busca, width=28).pack(
            side="left", padx=(4, 0), fill="x", expand=True
        )

        container_tree = tk.Frame(esquerda, bg="#ececec")
        container_tree.pack(fill="both", expand=True)

        colunas_comp = ("codigo", "nome", "unidade", "custo")
        self.tree_composicoes = ttk.Treeview(
            container_tree, columns=colunas_comp, show="headings", height=14
        )
        self.tree_composicoes.heading("codigo", text="Código")
        self.tree_composicoes.heading("nome", text="Nome")
        self.tree_composicoes.heading("unidade", text="Unid.")
        self.tree_composicoes.heading("custo", text="Custo est.")
        self.tree_composicoes.column("codigo", width=56, anchor="center", stretch=False)
        self.tree_composicoes.column("nome", width=220, stretch=True)
        self.tree_composicoes.column("unidade", width=48, anchor="center", stretch=False)
        self.tree_composicoes.column("custo", width=90, anchor="e", stretch=False)
        scroll_comp = ttk.Scrollbar(
            container_tree, orient="vertical", command=self.tree_composicoes.yview
        )
        self.tree_composicoes.configure(yscrollcommand=scroll_comp.set)
        self.tree_composicoes.pack(side="left", fill="both", expand=True)
        scroll_comp.pack(side="right", fill="y")
        self.tree_composicoes.bind("<<TreeviewSelect>>", self._ao_selecionar_composicao)

        linha_bt_comp = tk.Frame(esquerda, bg="#ececec")
        linha_bt_comp.pack(fill="x", pady=(6, 0))
        ttk.Button(
            linha_bt_comp, text="Nova composição", command=self._nova_composicao, style="Add.Compact.TButton"
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            linha_bt_comp, text="Excluir", command=self._excluir_composicao, style="Delete.Compact.TButton"
        ).pack(side="left")

        direita = tk.LabelFrame(painel, text="Edição da composição", bg="#ececec", padx=8, pady=8)
        painel.add(direita, minsize=420)

        form = tk.Frame(direita, bg="#ececec")
        form.pack(fill="x", pady=(0, 8))

        self.var_codigo = tk.StringVar()
        self.var_nome = tk.StringVar()
        self.var_unidade = tk.StringVar()

        for rotulo, var in (
            ("Código:", self.var_codigo),
            ("Nome:", self.var_nome),
            ("Unidade:", self.var_unidade),
        ):
            linha = tk.Frame(form, bg="#ececec")
            linha.pack(fill="x", pady=2)
            tk.Label(linha, text=rotulo, width=10, anchor="w", bg="#ececec").pack(side="left")
            ttk.Entry(linha, textvariable=var, width=48).pack(side="left", fill="x", expand=True)

        ttk.Button(
            form, text="Salvar alterações", command=self._salvar_composicao, style="Save.TButton"
        ).pack(anchor="e", pady=(6, 0))

        painel_comp = tk.LabelFrame(
            direita, text="Componentes", bg="#ececec", padx=6, pady=6
        )
        painel_comp.pack(fill="both", expand=True)

        colunas = ("codigo", "descricao", "unidade", "coeficiente", "tipo")
        self.tree_componentes = ttk.Treeview(
            painel_comp, columns=colunas, show="headings", height=10
        )
        self.tree_componentes.heading("codigo", text="Código")
        self.tree_componentes.heading("descricao", text="Descrição")
        self.tree_componentes.heading("unidade", text="Unid.")
        self.tree_componentes.heading("coeficiente", text="Coef.")
        self.tree_componentes.heading("tipo", text="Tipo")
        self.tree_componentes.column("codigo", width=56, anchor="center", stretch=False)
        self.tree_componentes.column("descricao", width=220, stretch=True)
        self.tree_componentes.column("unidade", width=48, anchor="center", stretch=False)
        self.tree_componentes.column("coeficiente", width=64, anchor="e", stretch=False)
        self.tree_componentes.column("tipo", width=72, anchor="center", stretch=False)
        self.tree_componentes.tag_configure("depreciado", background=COR_DEPRECIADO)
        scroll_cmp = ttk.Scrollbar(painel_comp, orient="vertical", command=self.tree_componentes.yview)
        self.tree_componentes.configure(yscrollcommand=scroll_cmp.set)
        self.tree_componentes.pack(side="left", fill="both", expand=True)
        scroll_cmp.pack(side="right", fill="y")

        linha_bt_cmp = tk.Frame(direita, bg="#ececec")
        linha_bt_cmp.pack(fill="x", pady=(8, 0))
        ttk.Button(
            linha_bt_cmp,
            text="Adicionar componente SINAPI",
            command=self._adicionar_sinapi,
            style="Compact.TButton",
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            linha_bt_cmp,
            text="Adicionar componente mercado",
            command=self._adicionar_mercado,
            style="Compact.TButton",
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            linha_bt_cmp,
            text="Remover componente",
            command=self._remover_componente,
            style="Delete.Compact.TButton",
        ).pack(side="left")

        self._atualizar_lista_composicoes()

    def _estado_selecionado(self):
        return estado_do_combo(self.combo_estado.get())

    def _ao_atualizar_sinapi(self):
        if self.label_referencia is not None:
            self.label_referencia.config(text=self._texto_referencia())
        estados = self.ctx.obter_estados()
        self.combo_estado["values"] = valores_combo_estado(estados)
        if self.combo_estado.get() not in self.combo_estado["values"]:
            self.combo_estado.set(PLACEHOLDER_ESTADO)
        self._atualizar_listas()

    def _atualizar_listas(self, _event=None):
        self._atualizar_lista_composicoes()
        self._atualizar_componentes()

    def _filtrar_composicoes(self):
        texto = self.var_busca.get().strip().lower()
        composicoes = listar(self._dados)
        if not texto:
            return composicoes
        filtradas = []
        for comp in composicoes:
            codigo = str(comp.get("codigo", "")).lower()
            nome = str(comp.get("nome", "")).lower()
            if texto in codigo or texto in nome:
                filtradas.append(comp)
        return filtradas

    def _atualizar_lista_composicoes(self):
        selecionado = self._composicao_editando_id
        self.tree_composicoes.delete(*self.tree_composicoes.get_children())
        estado = self._estado_selecionado()
        primeiro_id = None
        for comp in self._filtrar_composicoes():
            custo, _ = calcular_custo_unitario(comp, self.ctx.sinapi, estado)
            iid = comp["id"]
            if primeiro_id is None:
                primeiro_id = iid
            self.tree_composicoes.insert(
                "",
                "end",
                iid=iid,
                values=(
                    comp.get("codigo", ""),
                    comp.get("nome", ""),
                    comp.get("unidade", ""),
                    _formatar_moeda(custo) if estado else "—",
                ),
            )
        if selecionado and self.tree_composicoes.exists(selecionado):
            self.tree_composicoes.selection_set(selecionado)
            self.tree_composicoes.focus(selecionado)
        elif primeiro_id:
            self.tree_composicoes.selection_set(primeiro_id)
            self._carregar_composicao_na_edicao(primeiro_id)

    def _ao_selecionar_composicao(self, _event=None):
        selecionado = self.tree_composicoes.selection()
        if not selecionado:
            return
        self._carregar_composicao_na_edicao(selecionado[0])

    def _carregar_composicao_na_edicao(self, composicao_id):
        comp = obter_por_id(composicao_id, self._dados)
        if comp is None:
            return
        self._composicao_editando_id = composicao_id
        self.var_codigo.set(comp.get("codigo", ""))
        self.var_nome.set(comp.get("nome", ""))
        self.var_unidade.set(comp.get("unidade", ""))
        self._atualizar_componentes()

    def _composicao_em_edicao(self):
        if not self._composicao_editando_id:
            return None
        return obter_por_id(self._composicao_editando_id, self._dados)

    def _atualizar_componentes(self):
        self.tree_componentes.delete(*self.tree_componentes.get_children())
        comp = self._composicao_em_edicao()
        if comp is None:
            return
        estado = self._estado_selecionado()
        depreciados = set(verificar_componentes_depreciados(comp, self.ctx.sinapi, estado))
        for componente in comp.get("componentes", []):
            tipo = componente.get("tipo", "")
            rotulo_tipo = "SINAPI" if tipo == TIPO_COMPONENTE_SINAPI else "Mercado"
            tags = ("depreciado",) if componente.get("id") in depreciados else ()
            self.tree_componentes.insert(
                "",
                "end",
                iid=componente["id"],
                values=(
                    componente.get("codigo", ""),
                    componente.get("descricao", ""),
                    componente.get("unidade", ""),
                    _formatar_quantidade(componente.get("coeficiente", 0)),
                    rotulo_tipo,
                ),
                tags=tags,
            )

    def _nova_composicao(self):
        codigo = perguntar_texto(
            self.winfo_toplevel(), "Nova composição", "Código da composição:"
        )
        if not codigo or not codigo.strip():
            return
        nome = perguntar_texto(
            self.winfo_toplevel(), "Nova composição", "Nome da composição:"
        )
        if not nome or not nome.strip():
            return
        unidade = perguntar_texto(
            self.winfo_toplevel(),
            "Nova composição",
            "Unidade de medida:",
            valor_inicial="un",
        )
        if not unidade or not unidade.strip():
            return
        try:
            novo_id = criar(codigo, nome, unidade, dados=self._dados)
        except ValueError as exc:
            messagebox.showwarning("Nova composição", str(exc), parent=self.winfo_toplevel())
            return
        self._dados = carregar()
        self._composicao_editando_id = novo_id
        self._atualizar_listas()
        if self.tree_composicoes.exists(novo_id):
            self.tree_composicoes.selection_set(novo_id)
            self.tree_composicoes.focus(novo_id)

    def _salvar_composicao(self):
        comp = self._composicao_em_edicao()
        if comp is None:
            messagebox.showinfo(
                "Salvar",
                "Selecione uma composição para editar.",
                parent=self.winfo_toplevel(),
            )
            return
        comp["codigo"] = self.var_codigo.get().strip()
        comp["nome"] = self.var_nome.get().strip()
        comp["unidade"] = self.var_unidade.get().strip()
        try:
            atualizar(comp, self._dados)
        except ValueError as exc:
            messagebox.showwarning("Salvar", str(exc), parent=self.winfo_toplevel())
            return
        self._dados = carregar()
        self._atualizar_listas()

    def _excluir_composicao(self):
        comp = self._composicao_em_edicao()
        if comp is None:
            messagebox.showinfo(
                "Excluir",
                "Selecione uma composição.",
                parent=self.winfo_toplevel(),
            )
            return
        if not confirmar_exclusao_com_espera(
            self.winfo_toplevel(),
            "Excluir composição",
            f"Excluir a composição \"{comp.get('codigo')} — {comp.get('nome')}\"?",
            "Excluir composição",
        ):
            return
        try:
            excluir(comp["id"], self._dados)
        except ValueError as exc:
            messagebox.showwarning("Excluir", str(exc), parent=self.winfo_toplevel())
            return
        self._dados = carregar()
        self._composicao_editando_id = None
        self.var_codigo.set("")
        self.var_nome.set("")
        self.var_unidade.set("")
        self._atualizar_listas()

    def _adicionar_sinapi(self):
        comp = self._composicao_em_edicao()
        if comp is None:
            messagebox.showinfo(
                "Componente SINAPI",
                "Selecione ou crie uma composição primeiro.",
                parent=self.winfo_toplevel(),
            )
            return

        def ao_escolher(codigo, descricao, unidade, _custo, _quantidade, _estado, _tipo_sinapi=""):
            coef_texto = perguntar_texto(
                self.winfo_toplevel(),
                "Coeficiente",
                f"Coeficiente para {codigo}:",
                valor_inicial="1",
            )
            if coef_texto is None:
                return
            try:
                coeficiente = float(str(coef_texto).strip().replace(",", "."))
                if coeficiente <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showwarning(
                    "Coeficiente",
                    "Informe um coeficiente numérico maior que zero.",
                    parent=self.winfo_toplevel(),
                )
                return
            componente = novo_componente_sinapi(codigo, descricao, unidade, coeficiente)
            comp.setdefault("componentes", []).append(componente)
            try:
                atualizar(comp, self._dados)
            except ValueError as exc:
                messagebox.showwarning("Componente", str(exc), parent=self.winfo_toplevel())
                return
            self._dados = carregar()
            self._atualizar_listas()

        DialogoBuscaSinapi(
            self.winfo_toplevel(),
            self.ctx,
            self._estado_selecionado(),
            ao_escolher,
            titulo="Adicionar componente SINAPI",
            mostrar_quantidade=False,
            texto_confirmar="Selecionar",
            fechar_unico=True,
        )

    def _adicionar_mercado(self):
        comp = self._composicao_em_edicao()
        if comp is None:
            messagebox.showinfo(
                "Componente mercado",
                "Selecione ou crie uma composição primeiro.",
                parent=self.winfo_toplevel(),
            )
            return

        def ao_confirmar(componente):
            comp.setdefault("componentes", []).append(componente)
            try:
                atualizar(comp, self._dados)
            except ValueError as exc:
                messagebox.showwarning("Componente", str(exc), parent=self.winfo_toplevel())
                return
            self._dados = carregar()
            self._atualizar_listas()

        DialogoComponenteMercado(self.winfo_toplevel(), ao_confirmar)

    def _remover_componente(self):
        comp = self._composicao_em_edicao()
        if comp is None:
            return
        selecionado = self.tree_componentes.selection()
        if not selecionado:
            messagebox.showinfo(
                "Remover componente",
                "Selecione um componente na lista.",
                parent=self.winfo_toplevel(),
            )
            return
        comp_id = selecionado[0]
        comp["componentes"] = [
            c for c in comp.get("componentes", []) if c.get("id") != comp_id
        ]
        try:
            atualizar(comp, self._dados)
        except ValueError as exc:
            messagebox.showwarning("Remover", str(exc), parent=self.winfo_toplevel())
            return
        self._dados = carregar()
        self._atualizar_listas()

    def focar(self):
        pass
