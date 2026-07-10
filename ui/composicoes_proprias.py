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
    ESTADO_PREVIA_PADRAO,
    atualizar,
    carregar,
    criar,
    excluir,
    listar,
    obter_cache_catalogo,
    obter_estado_previa_custos,
    obter_por_id,
    salvar_estado_previa_custos,
)
from ui.icones import (
    criar_botao_inserir_prominente,
    criar_botao_ttk_com_icone,
)
from ui.orcamento_customizado import DialogoBuscaSinapi
from ui.recarga_catalogo import RecarregadorCatalogo
from ui.widgets import (
    PLACEHOLDER_ESTADO,
    ControleAtualizacaoPagina,
    aplicar_icone_janela,
    centralizar_janela,
    confirmar_exclusao_com_espera,
    criar_barra_modulo,
    estado_do_combo,
    formatar_decimal_br,
    formatar_moeda_br,
    perguntar_texto,
    preparar_toplevel,
    valores_combo_estado,
    focar_entrada_apos_exibir,
)

COR_DEPRECIADO = "#fff8e1"


def _formatar_moeda(valor):
    return formatar_moeda_br(valor)


def _formatar_quantidade(valor):
    return formatar_decimal_br(valor, casas=4)


class DialogoComponenteMercado(tk.Toplevel):
    def __init__(self, parent, on_confirmar):
        super().__init__(parent)
        preparar_toplevel(self)
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
        self._entrada_inicial = None
        for rotulo, chave in campos:
            linha = tk.Frame(painel, bg="#ececec")
            linha.pack(fill="x", pady=3)
            tk.Label(linha, text=rotulo, width=22, anchor="w", bg="#ececec").pack(side="left")
            var = tk.StringVar(value="1" if chave == "coeficiente" else "")
            self.vars[chave] = var
            entrada = ttk.Entry(linha, textvariable=var, width=36)
            entrada.pack(side="left", fill="x", expand=True)
            if self._entrada_inicial is None:
                self._entrada_inicial = entrada

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
        if self._entrada_inicial is not None:
            focar_entrada_apos_exibir(self._entrada_inicial)

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


class DialogoNovaComposicao(tk.Toplevel):
    def __init__(self, parent, on_confirmar):
        super().__init__(parent)
        preparar_toplevel(self)
        self.on_confirmar = on_confirmar
        self.title("Nova composição")
        aplicar_icone_janela(self)
        self.configure(bg="#ececec")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        painel = tk.Frame(self, bg="#ececec", padx=16, pady=14)
        painel.pack(fill="both", expand=True)

        campos = [
            ("Código da composição:", "codigo", ""),
            ("Nome da composição:", "nome", ""),
            ("Unidade de medida:", "unidade", "un"),
        ]
        self.vars = {}
        self._entradas = {}
        for indice, (rotulo, chave, valor_inicial) in enumerate(campos):
            linha = tk.Frame(painel, bg="#ececec")
            linha.pack(fill="x", pady=3)
            tk.Label(linha, text=rotulo, width=22, anchor="w", bg="#ececec").pack(side="left")
            var = tk.StringVar(value=valor_inicial)
            self.vars[chave] = var
            entrada = ttk.Entry(linha, textvariable=var, width=36)
            entrada.pack(side="left", fill="x", expand=True)
            self._entradas[chave] = entrada
            if indice == 0:
                self._entrada_inicial = entrada

        botoes = ttk.Frame(painel)
        botoes.pack(fill="x", pady=(12, 0))
        ttk.Button(botoes, text="Cancelar", command=self.destroy, style="Delete.TButton").pack(
            side="right", padx=(6, 0)
        )
        ttk.Button(botoes, text="Criar", command=self._confirmar, style="Add.TButton").pack(
            side="right"
        )

        self.bind("<Escape>", lambda _e: self.destroy())
        self.bind("<Return>", lambda _e: self._confirmar())
        self.update_idletasks()
        centralizar_janela(self, parent)
        focar_entrada_apos_exibir(self._entrada_inicial)

    def _confirmar(self):
        codigo = self.vars["codigo"].get().strip()
        nome = self.vars["nome"].get().strip()
        unidade = self.vars["unidade"].get().strip()
        if not codigo:
            messagebox.showwarning(
                "Nova composição",
                "Informe o código da composição.",
                parent=self,
            )
            self._entradas["codigo"].focus_set()
            return
        if not nome:
            messagebox.showwarning(
                "Nova composição",
                "Informe o nome da composição.",
                parent=self,
            )
            self._entradas["nome"].focus_set()
            return
        if not unidade:
            messagebox.showwarning(
                "Nova composição",
                "Informe a unidade de medida.",
                parent=self,
            )
            self._entradas["unidade"].focus_set()
            return
        if self.on_confirmar(codigo, nome, unidade):
            self.destroy()


class ComposicoesPropriasFrame(tk.Frame):
    def __init__(self, parent, ctx, on_voltar):
        super().__init__(parent, bg="#ececec")
        self.ctx = ctx
        self.on_voltar = on_voltar
        self._dados = {
            "versao": 1,
            "composicoes": [],
            "estado_previa_custos": ESTADO_PREVIA_PADRAO,
        }
        self._composicao_editando_id = None
        self._icones_botoes = []
        self._atualizando_lista = False
        self._suprimir_selecao = False
        self._recarregador = RecarregadorCatalogo(
            self,
            obter_cache=obter_cache_catalogo,
            carregar_rede=carregar,
            ao_aplicar=self._aplicar_dados_catalogo,
            ao_erro=self._ao_erro_recarga_catalogo,
            ao_inicio=self._ao_inicio_carregamento,
            ao_fim=self._ao_fim_carregamento,
        )
        self._montar()
        ctx.registrar_callback_sinapi(self._ao_atualizar_sinapi)

    def _texto_referencia(self):
        ref = self.ctx.sinapi_referencia_rotulo
        if ref == "BASE AUSENTE":
            return "Base não carregada"
        return f"Referência SINAPI: {ref}"

    def _montar_botao_recarregar_cabecalho(self, parent):
        self._controle_atualizacao = ControleAtualizacaoPagina(
            parent,
            command=self.recarregar_catalogo,
            refs=self._icones_botoes,
        )

    def _ao_erro_recarga_catalogo(self, mensagem: str, avisar_erro: bool):
        if avisar_erro:
            messagebox.showwarning(
                "Recarregar",
                mensagem,
                parent=self.winfo_toplevel(),
            )

    def _ao_inicio_carregamento(self):
        if getattr(self, "_controle_atualizacao", None) is not None:
            self._controle_atualizacao.definir_ativo(True)

    def _ao_fim_carregamento(self):
        if getattr(self, "_controle_atualizacao", None) is not None:
            self._controle_atualizacao.definir_ativo(False)

    def _aplicar_dados_catalogo(self, dados: dict):
        self._dados = dados
        self._atualizar_listas(calcular_custos_lista=False)

    def recarregar_catalogo(self, *, forcar_rede: bool = True):
        self._recarregador.solicitar(forcar_rede=forcar_rede, avisar_erro=True)

    def _liberar_supressao_selecao(self):
        self._suprimir_selecao = False

    def _montar(self):
        self.label_referencia = criar_barra_modulo(
            self,
            "Configurar Composições Próprias",
            self.on_voltar,
            texto_referencia=self._texto_referencia(),
            montar_acoes_apos_titulo=self._montar_botao_recarregar_cabecalho,
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
        self._aplicar_estado_previa_inicial(estados)
        self.combo_estado.bind("<<ComboboxSelected>>", self._ao_mudar_estado_previa)

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
        criar_botao_ttk_com_icone(
            linha_bt_comp,
            texto="Nova composição",
            nome_icone="add-circle-outline",
            command=self._nova_composicao,
            estilo="Add.Compact.TButton",
            refs=self._icones_botoes,
        ).pack(side="left", padx=(0, 4))
        criar_botao_ttk_com_icone(
            linha_bt_comp,
            texto="Excluir",
            nome_icone="trash-outline",
            command=self._excluir_composicao,
            estilo="Delete.Compact.TButton",
            refs=self._icones_botoes,
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

        criar_botao_ttk_com_icone(
            form,
            texto="Salvar alterações",
            nome_icone="save-outline",
            command=self._salvar_composicao,
            estilo="Save.TButton",
            refs=self._icones_botoes,
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
        criar_botao_inserir_prominente(
            linha_bt_cmp,
            texto="Adicionar componente SINAPI",
            command=self._adicionar_sinapi,
            refs=self._icones_botoes,
        ).pack(side="left", padx=(0, 4))
        criar_botao_inserir_prominente(
            linha_bt_cmp,
            texto="Adicionar componente mercado",
            command=self._adicionar_mercado,
            refs=self._icones_botoes,
        ).pack(side="left", padx=(0, 4))
        criar_botao_ttk_com_icone(
            linha_bt_cmp,
            texto="Remover componente",
            nome_icone="remove-circle-outline",
            command=self._remover_componente,
            estilo="Delete.Compact.TButton",
            refs=self._icones_botoes,
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            linha_bt_cmp,
            text="Item ↑",
            command=lambda: self._mover_componente(-1),
            style="Compact.TButton",
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            linha_bt_cmp,
            text="Item ↓",
            command=lambda: self._mover_componente(1),
            style="Compact.TButton",
        ).pack(side="left")

    def _atualizar_lista_composicoes(self, *, calcular_custos=True):
        self._suprimir_selecao = True
        self._atualizando_lista = True
        try:
            selecionado = self._composicao_editando_id
            self.tree_composicoes.delete(*self.tree_composicoes.get_children())
            estado = self._estado_selecionado()
            primeiro_id = None
            for comp in self._filtrar_composicoes():
                iid = comp["id"]
                if primeiro_id is None:
                    primeiro_id = iid
                if calcular_custos and estado:
                    custo, _ = calcular_custo_unitario(comp, self.ctx.sinapi, estado)
                    custo_txt = _formatar_moeda(custo)
                elif calcular_custos:
                    custo_txt = "—"
                else:
                    custo_txt = "…"
                self.tree_composicoes.insert(
                    "",
                    "end",
                    iid=iid,
                    values=(
                        comp.get("codigo", ""),
                        comp.get("nome", ""),
                        comp.get("unidade", ""),
                        custo_txt,
                    ),
                )
            if selecionado and self.tree_composicoes.exists(selecionado):
                self.tree_composicoes.selection_set(selecionado)
                self.tree_composicoes.focus(selecionado)
                self._carregar_composicao_na_edicao(selecionado)
            elif primeiro_id:
                self.tree_composicoes.selection_set(primeiro_id)
                self._carregar_composicao_na_edicao(primeiro_id)
        finally:
            self._atualizando_lista = False
            self.after_idle(self._liberar_supressao_selecao)
        if not calcular_custos:
            self.after_idle(self._completar_custos_lista_composicoes)

    def _completar_custos_lista_composicoes(self):
        estado = self._estado_selecionado()
        for iid in self.tree_composicoes.get_children():
            comp = obter_por_id(iid, self._dados)
            if comp is None:
                continue
            if estado:
                custo, _ = calcular_custo_unitario(comp, self.ctx.sinapi, estado)
                custo_txt = _formatar_moeda(custo)
            else:
                custo_txt = "—"
            valores = list(self.tree_composicoes.item(iid, "values"))
            if len(valores) >= 4:
                valores[3] = custo_txt
                self.tree_composicoes.item(iid, values=valores)

    def _ao_selecionar_composicao(self, _event=None):
        if self._atualizando_lista or self._suprimir_selecao:
            return
        selecionado = self.tree_composicoes.selection()
        if not selecionado:
            return
        self._carregar_composicao_na_edicao(selecionado[0])

    def _estado_selecionado(self):
        return estado_do_combo(self.combo_estado.get())

    def _aplicar_estado_previa_inicial(self, estados):
        preferido = obter_estado_previa_custos(self._dados)
        for candidato in (preferido, ESTADO_PREVIA_PADRAO):
            if candidato in estados:
                self.combo_estado.set(candidato)
                return
        self.combo_estado.set(PLACEHOLDER_ESTADO)

    def _ao_mudar_estado_previa(self, _event=None):
        estado = self._estado_selecionado()
        if estado:
            salvar_estado_previa_custos(estado, self._dados)
            self._dados = carregar()
        self._atualizar_listas()

    def _ao_atualizar_sinapi(self):
        if self.label_referencia is not None:
            self.label_referencia.config(text=self._texto_referencia())
        estados = self.ctx.obter_estados()
        self.combo_estado["values"] = valores_combo_estado(estados)
        if self.combo_estado.get() not in self.combo_estado["values"]:
            self._aplicar_estado_previa_inicial(estados)
        self._atualizar_listas()

    def _atualizar_listas(self, _event=None, *, calcular_custos_lista=True):
        self._atualizar_lista_composicoes(calcular_custos=calcular_custos_lista)
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
        def ao_confirmar(codigo, nome, unidade):
            try:
                novo_id = criar(codigo, nome, unidade, dados=self._dados)
            except ValueError as exc:
                messagebox.showwarning("Nova composição", str(exc), parent=dialogo)
                dialogo._entradas["codigo"].focus_set()
                return False
            self._dados = carregar()
            self._composicao_editando_id = novo_id
            self._atualizar_listas()
            if self.tree_composicoes.exists(novo_id):
                self.tree_composicoes.selection_set(novo_id)
                self.tree_composicoes.focus(novo_id)
            return True

        dialogo = DialogoNovaComposicao(self.winfo_toplevel(), ao_confirmar)

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
            if "Recarregue" in str(exc):
                self.recarregar_catalogo()
            return
        self._dados = carregar()
        self._atualizar_listas()

    def _mover_componente(self, delta):
        comp = self._composicao_em_edicao()
        if comp is None:
            return
        selecionado = self.tree_componentes.selection()
        if not selecionado:
            messagebox.showinfo(
                "Mover componente",
                "Selecione um componente na lista.",
                parent=self.winfo_toplevel(),
            )
            return
        comp_id = selecionado[0]
        componentes = comp.get("componentes", [])
        indice = next(
            (i for i, item in enumerate(componentes) if item.get("id") == comp_id),
            -1,
        )
        if indice < 0:
            return
        novo_indice = indice + delta
        if novo_indice < 0 or novo_indice >= len(componentes):
            return
        componentes[indice], componentes[novo_indice] = (
            componentes[novo_indice],
            componentes[indice],
        )
        try:
            atualizar(comp, self._dados)
        except ValueError as exc:
            messagebox.showwarning("Mover componente", str(exc), parent=self.winfo_toplevel())
            return
        self._dados = carregar()
        self._atualizar_componentes()
        if self.tree_componentes.exists(comp_id):
            self.tree_componentes.selection_set(comp_id)
            self.tree_componentes.focus(comp_id)

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
        self.recarregar_catalogo(forcar_rede=False)
