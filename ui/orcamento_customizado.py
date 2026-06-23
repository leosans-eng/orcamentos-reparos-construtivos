import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from core.orcamento_customizado import (
    BDI_PADRAO,
    TIPO_COMPOSICAO_PROPRIA,
    TIPO_GRUPO,
    TIPO_SINAPI,
    OrcamentoCustomizado,
    custo_unitario_com_bdi,
    rotulo_item,
    subtotal_grupo,
    subtotal_item,
)
from core.orcamento_storage import (
    atualizar_orcamento_na_lista,
    carregar_arquivo,
    criar_orcamento,
    dict_para_orcamento,
    excluir_orcamento,
    listar_nomes,
    obter_orcamento_dict,
    renomear_orcamento,
    salvar_arquivo,
)
from core.sinapi_busca import obter_item_sinapi, obter_unidades_sinapi, pesquisar_sinapi
from ui.grade_orcamento import GradeOrcamento
from ui.widgets import (
    PLACEHOLDER_ESTADO,
    centralizar_janela,
    confirmar_exclusao_com_espera,
    criar_barra_modulo,
    estado_do_combo,
    valores_combo_estado,
)

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


def _formatar_bdi(valor):
    try:
        v = float(valor)
        texto = f"{v:.2f}".replace(".", ",")
        return texto
    except (TypeError, ValueError):
        return str(valor)


class DialogoEditarQuantidade(tk.Toplevel):
    def __init__(self, parent, descricao_item, quantidade_atual, on_confirmar):
        super().__init__(parent)
        self.on_confirmar = on_confirmar
        self.title("Editar quantidade")
        self.configure(bg="#ececec")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        largura_wrap = min(560, max(280, parent.winfo_screenwidth() - 120))

        painel = tk.Frame(self, bg="#ececec", padx=16, pady=14)
        painel.pack(fill="both", expand=True)

        tk.Label(
            painel,
            text="Item:",
            font=("Arial", 9, "bold"),
            fg="#444444",
            bg="#ececec",
            anchor="w",
        ).pack(fill="x")

        tk.Label(
            painel,
            text=descricao_item,
            font=("Arial", 9),
            fg="#333333",
            bg="#f5fafc",
            justify="left",
            anchor="w",
            wraplength=largura_wrap,
            padx=8,
            pady=8,
        ).pack(fill="x", pady=(4, 12))

        linha_qtd = tk.Frame(painel, bg="#ececec")
        linha_qtd.pack(fill="x", pady=(0, 12))
        tk.Label(linha_qtd, text="Nova quantidade:", bg="#ececec").pack(side="left")
        self.var_quantidade = tk.StringVar(value=_formatar_quantidade(quantidade_atual))
        entrada = ttk.Entry(linha_qtd, textvariable=self.var_quantidade, width=14)
        entrada.pack(side="left", padx=(8, 0))
        entrada.focus_set()
        entrada.select_range(0, "end")
        entrada.bind("<Return>", lambda _e: self._confirmar())
        entrada.bind("<Escape>", lambda _e: self.destroy())

        botoes = ttk.Frame(painel)
        botoes.pack(fill="x")
        ttk.Button(botoes, text="Cancelar", command=self.destroy, style="Delete.TButton").pack(
            side="left"
        )
        ttk.Button(botoes, text="Confirmar", command=self._confirmar, style="Add.TButton").pack(
            side="right"
        )

        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        centralizar_janela(self, parent)

    def _confirmar(self):
        self.on_confirmar(self.var_quantidade.get())
        self.destroy()


class DialogoBuscaSinapi(tk.Toplevel):
    def __init__(
        self,
        parent,
        ctx,
        estado_inicial,
        on_confirmar,
        *,
        titulo="Buscar na SINAPI",
        mostrar_quantidade=True,
        texto_confirmar="Inserir no grupo",
        texto_confirmar_fechar="Inserir e fechar",
        fechar_unico=False,
    ):
        super().__init__(parent)
        self.ctx = ctx
        self.on_confirmar = on_confirmar
        self._job_busca = None
        self.mostrar_quantidade = mostrar_quantidade
        self.texto_confirmar = texto_confirmar
        self.texto_confirmar_fechar = texto_confirmar_fechar
        self.fechar_unico = fechar_unico

        self.title(titulo)
        self.geometry("820x520")
        self.minsize(640, 400)
        self.configure(bg="#ececec")
        self.transient(parent)
        self.grab_set()

        self._montar(estado_inicial)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        centralizar_janela(self, parent)

    def _montar(self, estado_inicial):
        painel = tk.Frame(self, bg="#ececec", padx=12, pady=10)
        painel.pack(fill="both", expand=True)

        linha_filtros = tk.Frame(painel, bg="#ececec")
        linha_filtros.pack(fill="x", pady=(0, 6))

        tk.Label(linha_filtros, text="Estado:", bg="#ececec").grid(
            row=0, column=0, padx=(0, 4), pady=3, sticky="w"
        )
        estados = self.ctx.obter_estados()
        self.combo_estado = ttk.Combobox(
            linha_filtros,
            values=valores_combo_estado(estados),
            width=14,
            state="readonly",
        )
        self.combo_estado.grid(row=0, column=1, padx=4, pady=3, sticky="w")
        estado_valido = estado_do_combo(estado_inicial)
        if estado_valido and estado_valido in estados:
            self.combo_estado.set(estado_valido)
        else:
            self.combo_estado.set(PLACEHOLDER_ESTADO)

        tk.Label(linha_filtros, text="Unidade:", bg="#ececec").grid(
            row=0, column=2, padx=(14, 4), pady=3, sticky="w"
        )
        self.combo_unidade = ttk.Combobox(
            linha_filtros, values=[UNIDADE_TODAS], width=10, state="readonly"
        )
        self.combo_unidade.grid(row=0, column=3, padx=4, pady=3, sticky="w")
        self.combo_unidade.set(UNIDADE_TODAS)

        tk.Label(linha_filtros, text="Buscar:", bg="#ececec").grid(
            row=1, column=0, padx=(0, 4), pady=3, sticky="w"
        )
        self.var_busca = tk.StringVar()
        self.entrada_busca = ttk.Entry(linha_filtros, textvariable=self.var_busca, width=36)
        self.entrada_busca.grid(row=1, column=1, padx=4, pady=3, sticky="ew")

        if self.mostrar_quantidade:
            tk.Label(linha_filtros, text="Quantidade:", bg="#ececec").grid(
                row=1, column=2, padx=(14, 4), pady=3, sticky="w"
            )
            self.var_quantidade = tk.StringVar(value="1")
            ttk.Entry(linha_filtros, textvariable=self.var_quantidade, width=10).grid(
                row=1, column=3, padx=4, pady=3, sticky="w"
            )
        else:
            self.var_quantidade = tk.StringVar(value="1")
        linha_filtros.columnconfigure(1, weight=1)

        self._atualizar_unidades()

        self.label_status = tk.Label(
            painel,
            text="Selecione o estado e digite para pesquisar.",
            font=("Arial", 8),
            fg="#555555",
            bg="#ececec",
            anchor="w",
        )
        self.label_status.pack(fill="x", pady=(0, 4))

        painel_resultados = tk.LabelFrame(
            painel, text="Resultados", bg="#ececec", padx=6, pady=4
        )
        painel_resultados.pack(fill="both", expand=True, pady=(0, 8))

        colunas = ("codigo", "descricao", "unidade", "custo")
        self.tree = ttk.Treeview(painel_resultados, columns=colunas, show="headings", height=14)
        self.tree.heading("codigo", text="Código")
        self.tree.heading("descricao", text="Descrição")
        self.tree.heading("unidade", text="Unid.")
        self.tree.heading("custo", text="Custo unit. (R$)")
        self.tree.column("codigo", width=60, minwidth=60, stretch=False, anchor="center")
        self.tree.column("descricao", width=420, minwidth=200, stretch=True)
        self.tree.column("unidade", width=55, minwidth=45, stretch=False, anchor="center")
        self.tree.column("custo", width=110, minwidth=90, stretch=False, anchor="e")

        scroll = ttk.Scrollbar(painel_resultados, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        rodape = tk.Frame(painel, bg="#ececec")
        rodape.pack(fill="x")
        rodape.columnconfigure(1, weight=1)

        ttk.Button(rodape, text="Cancelar", command=self.destroy, style="Delete.TButton").grid(
            row=0, column=0, sticky="w"
        )

        frame_dir = tk.Frame(rodape, bg="#ececec")
        frame_dir.grid(row=0, column=2, sticky="e")
        if self.fechar_unico:
            ttk.Button(
                frame_dir,
                text=self.texto_confirmar,
                command=lambda: self._confirmar(fechar=True),
                style="Add.TButton",
            ).pack(side="left")
        else:
            ttk.Button(
                frame_dir,
                text=self.texto_confirmar,
                command=lambda: self._confirmar(fechar=False),
                style="Add.TButton",
            ).pack(side="left", padx=(0, 8))
            ttk.Button(
                frame_dir,
                text=self.texto_confirmar_fechar,
                command=lambda: self._confirmar(fechar=True),
                style="Save.TButton",
            ).pack(side="left")

        self.var_busca.trace_add("write", self._ao_digitar)
        self.combo_estado.bind("<<ComboboxSelected>>", self._ao_mudar_estado)
        self.combo_unidade.bind("<<ComboboxSelected>>", lambda _e: self._executar_busca())
        self.tree.bind(
            "<Double-1>",
            lambda _e: self._confirmar(fechar=self.fechar_unico),
        )

        if self.ctx.sinapi.empty:
            self.label_status.config(text="Base SINAPI indisponível.", fg="#C62828")

        self.entrada_busca.focus_set()

    def _estado_selecionado(self):
        return estado_do_combo(self.combo_estado.get())

    def _unidade_selecionada(self):
        valor = self.combo_unidade.get().strip()
        return None if not valor or valor == UNIDADE_TODAS else valor

    def _aplicar_unidades(self, unidades):
        valores = [UNIDADE_TODAS] + list(unidades)
        atual = self.combo_unidade.get().strip()
        self.combo_unidade["values"] = valores
        self.combo_unidade.set(atual if atual in valores else UNIDADE_TODAS)

    def _atualizar_unidades(self, consulta=None):
        estado = self._estado_selecionado()
        if consulta is None:
            consulta = self.var_busca.get()
        if consulta and consulta.strip():
            unidades = obter_unidades_sinapi(self.ctx.sinapi, estado or None, consulta)
        else:
            unidades = obter_unidades_sinapi(self.ctx.sinapi, estado or None)
        self._aplicar_unidades(unidades)

    def _ao_mudar_estado(self, _event=None):
        self._atualizar_unidades()
        self._executar_busca()

    def _ao_digitar(self, *_args):
        if self._job_busca is not None:
            self.after_cancel(self._job_busca)
        self._job_busca = self.after(DEBOUNCE_BUSCA_MS, self._executar_busca)

    def _executar_busca(self):
        if self._job_busca is not None:
            self.after_cancel(self._job_busca)
            self._job_busca = None

        estado = self._estado_selecionado()
        consulta = self.var_busca.get()
        if not estado:
            self.label_status.config(text="Selecione um estado.", fg="#C62828")
            return

        resultados, mensagem, unidades = pesquisar_sinapi(
            self.ctx.sinapi,
            estado,
            consulta,
            unidade=self._unidade_selecionada(),
        )
        self._aplicar_unidades(unidades)
        self.tree.delete(*self.tree.get_children())
        for _, linha in resultados.iterrows():
            self.tree.insert(
                "",
                "end",
                values=(
                    str(linha.get("codigo", "")),
                    str(linha.get("descricao", "")),
                    str(linha.get("unidade", "")),
                    _formatar_moeda(linha.get("custo", 0)),
                ),
            )
        cor = "#555555" if not resultados.empty else "#a67c00"
        if "indisponível" in mensagem.lower() or "nenhum item" in mensagem.lower():
            cor = "#C62828"
        self.label_status.config(text=mensagem, fg=cor)

    def _parse_quantidade(self, texto):
        return float(str(texto).strip().replace(",", "."))

    def _confirmar(self, fechar=False):
        selecionado = self.tree.selection()
        if not selecionado:
            messagebox.showinfo(
                "Inserir item",
                "Selecione um item nos resultados.",
                parent=self,
            )
            return

        valores = self.tree.item(selecionado[0], "values")
        if len(valores) < 4:
            return

        codigo, descricao, unidade, custo_fmt = valores
        estado = self._estado_selecionado()
        if not estado:
            messagebox.showwarning(
                "Inserir item",
                "Selecione um estado.",
                parent=self,
            )
            return

        try:
            quantidade = self._parse_quantidade(self.var_quantidade.get())
            if quantidade <= 0:
                raise ValueError
        except ValueError:
            if self.mostrar_quantidade:
                messagebox.showwarning(
                    "Quantidade",
                    "Informe um valor numérico maior que zero.",
                    parent=self,
                )
                return
            quantidade = 1.0

        custo_str = custo_fmt.replace("R$", "").strip().replace(".", "").replace(",", ".")
        try:
            custo = float(custo_str)
        except ValueError:
            custo = 0.0

        self.on_confirmar(codigo, descricao, unidade, custo, quantidade, estado)
        if fechar:
            self.destroy()


class OrcamentoCustomizadoFrame(tk.Frame):
    def __init__(self, parent, ctx, on_voltar):
        super().__init__(parent, bg="#ececec")
        self.ctx = ctx
        self.on_voltar = on_voltar
        self._dados_arquivo = carregar_arquivo()
        self._mapa_combo_ids = {}
        self._trocando_orcamento = False
        self.orcamento = self._carregar_orcamento_ativo()
        self._montar()
        ctx.registrar_callback_sinapi(self._ao_atualizar_sinapi)

    def _montar(self):
        self.label_referencia = criar_barra_modulo(
            self,
            "Orçamento Customizado",
            self.on_voltar,
            texto_referencia=self._texto_referencia(),
        )

        conteudo = tk.Frame(self, bg="#ececec")
        conteudo.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        linha_orc = tk.LabelFrame(
            conteudo,
            text="Orçamento salvo",
            bg="#ececec",
            padx=8,
            pady=6,
        )
        linha_orc.pack(fill="x", padx=4, pady=(0, 8))

        linha_salvo = tk.Frame(linha_orc, bg="#ececec")
        linha_salvo.pack(fill="x")

        tk.Label(linha_salvo, text="Selecionar:", bg="#ececec").pack(side="left")
        self.combo_orcamento = ttk.Combobox(
            linha_salvo, width=22, state="readonly"
        )
        self.combo_orcamento.pack(side="left", padx=(4, 8))
        self.combo_orcamento.bind("<<ComboboxSelected>>", self._ao_trocar_orcamento)

        ttk.Button(
            linha_salvo,
            text="Adicionar orçamento",
            command=self._adicionar_orcamento,
            style="Add.Compact.TButton",
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            linha_salvo,
            text="Editar nome do orçamento",
            command=self._renomear_orcamento,
            style="Edit.Compact.TButton",
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            linha_salvo,
            text="Excluir orçamento",
            command=self._excluir_orcamento,
            style="Delete.Compact.TButton",
        ).pack(side="left", padx=(0, 12))

        tk.Label(linha_salvo, text="Estado:", bg="#ececec").pack(side="left")
        estados = self.ctx.obter_estados()
        self.combo_estado = ttk.Combobox(
            linha_salvo, values=valores_combo_estado(estados), width=12, state="readonly"
        )
        self.combo_estado.pack(side="left", padx=(4, 10))
        self.combo_estado.bind("<<ComboboxSelected>>", self._ao_mudar_estado)

        tk.Label(linha_salvo, text="BDI (%):", bg="#ececec").pack(side="left")
        self.var_bdi = tk.StringVar(value=_formatar_bdi(BDI_PADRAO))
        self.var_bdi.trace_add("write", self._ao_alterar_bdi)
        ttk.Entry(linha_salvo, textvariable=self.var_bdi, width=7).pack(side="left", padx=(4, 0))

        linha_botoes = tk.Frame(conteudo, bg="#ececec")
        linha_botoes.pack(fill="x", padx=4, pady=(0, 8))

        ttk.Button(
            linha_botoes, text="Nova etapa", command=self._novo_grupo, style="Compact.TButton"
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            linha_botoes,
            text="Remover selecionado",
            command=self._remover_selecionado,
            style="Compact.TButton",
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            linha_botoes,
            text="Editar item",
            command=self._editar_item_sinapi,
            style="Accent.Compact.TButton",
        ).pack(side="left", padx=(0, 12))

        ttk.Button(
            linha_botoes,
            text="Inserir item SINAPI",
            command=self._abrir_busca_sinapi,
            style="Compact.TButton",
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            linha_botoes,
            text="Inserir composição PRÓPRIA",
            command=self._adicionar_composicao_propria,
            style="Compact.TButton",
        ).pack(side="left", padx=(0, 12))

        tk.Label(linha_botoes, text="Inserir rápido — Cód.:", bg="#ececec").pack(side="left")
        self.var_codigo_rapido = tk.StringVar()
        entrada_cod = ttk.Entry(linha_botoes, textvariable=self.var_codigo_rapido, width=10)
        entrada_cod.pack(side="left", padx=(4, 8))
        tk.Label(linha_botoes, text="Qtd.:", bg="#ececec").pack(side="left")
        self.var_qtd_rapido = tk.StringVar(value="1")
        entrada_qtd = ttk.Entry(linha_botoes, textvariable=self.var_qtd_rapido, width=8)
        entrada_qtd.pack(side="left", padx=(4, 8))
        ttk.Button(
            linha_botoes, text="Inserir", command=self._inserir_rapido, style="Compact.TButton"
        ).pack(side="left")
        entrada_cod.bind("<Return>", lambda _e: self._inserir_rapido())
        entrada_qtd.bind("<Return>", lambda _e: self._inserir_rapido())

        painel_grade = tk.LabelFrame(
            conteudo,
            text="Estrutura do orçamento",
            bg="#ececec",
            padx=6,
            pady=6,
        )
        painel_grade.pack(fill="both", expand=True, padx=4, pady=(0, 6))

        self.grade = GradeOrcamento(
            painel_grade,
            on_duplo_clique_qtd=self._dialogo_editar_quantidade,
        )
        self.grade.pack(fill="both", expand=True)

        rodape_orc = tk.Frame(
            conteudo, bg="#f5fafc", highlightbackground="#cccccc", highlightthickness=1
        )
        rodape_orc.pack(fill="x", padx=4, pady=(4, 0))

        self.label_total = tk.Label(
            rodape_orc,
            text="Total geral (c/ BDI): R$ 0,00",
            font=("Arial", 11, "bold"),
            fg="#006699",
            bg="#f5fafc",
            anchor="e",
            padx=10,
            pady=8,
        )
        self.label_total.pack(fill="x")

        self._atualizar_combo_orcamentos()
        self._aplicar_orcamento_na_interface()
        self._atualizar_grade()

    def _carregar_orcamento_ativo(self):
        orc_id = self._dados_arquivo.get("orcamento_ativo_id")
        dados = obter_orcamento_dict(self._dados_arquivo, orc_id)
        if dados is None:
            dados = self._dados_arquivo["orcamentos"][0]
        return dict_para_orcamento(dados)

    def _atualizar_combo_orcamentos(self):
        nomes = listar_nomes(self._dados_arquivo)
        self._mapa_combo_ids = {}
        valores = []
        contagem = {}
        for _oid, nome in nomes:
            contagem[nome] = contagem.get(nome, 0) + 1
        for oid, nome in nomes:
            rotulo = nome if contagem[nome] == 1 else f"{nome} ({oid[:8]})"
            self._mapa_combo_ids[rotulo] = oid
            valores.append(rotulo)
        self.combo_orcamento["values"] = valores
        rotulo_atual = self._rotulo_orcamento(self.orcamento.id, self.orcamento.nome)
        if rotulo_atual in valores:
            self.combo_orcamento.set(rotulo_atual)
        elif valores:
            self.combo_orcamento.set(valores[0])

    def _rotulo_orcamento(self, orcamento_id, nome):
        nomes = listar_nomes(self._dados_arquivo)
        contagem = {}
        for _oid, n in nomes:
            contagem[n] = contagem.get(n, 0) + 1
        if contagem.get(nome, 0) == 1:
            return nome
        return f"{nome} ({orcamento_id[:8]})"

    def _aplicar_orcamento_na_interface(self):
        self._trocando_orcamento = True
        try:
            estado = self.orcamento.estado_referencia
            if estado and estado in self.ctx.obter_estados():
                self.combo_estado.set(estado)
            else:
                self.combo_estado.set(PLACEHOLDER_ESTADO)
            self.var_bdi.set(_formatar_bdi(self.orcamento.bdi_percent))
        finally:
            self._trocando_orcamento = False

    def _persistir_orcamento_atual(self):
        estado = self._estado_selecionado()
        self.orcamento.definir_estado_referencia(estado)
        try:
            self.orcamento.definir_bdi(self._parse_bdi(self.var_bdi.get()))
        except ValueError:
            pass
        self._dados_arquivo = atualizar_orcamento_na_lista(self._dados_arquivo, self.orcamento)
        salvar_arquivo(self._dados_arquivo)
        self._atualizar_combo_orcamentos()

    def _ao_trocar_orcamento(self, _event=None):
        if self._trocando_orcamento:
            return
        nome = self.combo_orcamento.get().strip()
        novo_id = self._mapa_combo_ids.get(nome)
        if not novo_id or novo_id == self.orcamento.id:
            return
        self._persistir_orcamento_atual()
        self._dados_arquivo["orcamento_ativo_id"] = novo_id
        self.orcamento = self._carregar_orcamento_ativo()
        self._aplicar_orcamento_na_interface()
        self._atualizar_grade()

    def _adicionar_orcamento(self):
        nome = simpledialog.askstring(
            "Adicionar orçamento",
            "Nome do novo orçamento:",
            parent=self.winfo_toplevel(),
        )
        if not nome or not nome.strip():
            return
        self._persistir_orcamento_atual()
        novo_id = criar_orcamento(self._dados_arquivo, nome)
        self._dados_arquivo = carregar_arquivo()
        self._dados_arquivo["orcamento_ativo_id"] = novo_id
        salvar_arquivo(self._dados_arquivo)
        self.orcamento = self._carregar_orcamento_ativo()
        self._atualizar_combo_orcamentos()
        self._aplicar_orcamento_na_interface()
        self._atualizar_grade()

    def _renomear_orcamento(self):
        nome = simpledialog.askstring(
            "Editar nome",
            "Novo nome do orçamento:",
            initialvalue=self.orcamento.nome,
            parent=self.winfo_toplevel(),
        )
        if not nome or not nome.strip():
            return
        try:
            renomear_orcamento(self._dados_arquivo, self.orcamento.id, nome)
            self.orcamento.definir_nome(nome)
            self._dados_arquivo = carregar_arquivo()
            self._atualizar_combo_orcamentos()
            self.combo_orcamento.set(self._rotulo_orcamento(self.orcamento.id, nome.strip()))
        except ValueError as exc:
            messagebox.showwarning("Orçamento", str(exc), parent=self.winfo_toplevel())

    def _excluir_orcamento(self):
        if not confirmar_exclusao_com_espera(
            self.winfo_toplevel(),
            "Excluir orçamento",
            f"Excluir o orçamento \"{self.orcamento.nome}\"?\nEsta ação não pode ser desfeita.",
            "Excluir orçamento",
        ):
            return
        try:
            novo_id = excluir_orcamento(self._dados_arquivo, self.orcamento.id)
            self._dados_arquivo = carregar_arquivo()
            self._dados_arquivo["orcamento_ativo_id"] = novo_id
            self.orcamento = self._carregar_orcamento_ativo()
            self._atualizar_combo_orcamentos()
            self._aplicar_orcamento_na_interface()
            self._atualizar_grade()
        except ValueError as exc:
            messagebox.showwarning("Orçamento", str(exc), parent=self.winfo_toplevel())

    def _texto_referencia(self):
        ref = self.ctx.sinapi_referencia_rotulo
        if ref == "BASE AUSENTE":
            return "Base não carregada"
        return f"Referência SINAPI: {ref}"

    def _obter_bdi(self):
        return self.orcamento.bdi_percent

    def _parse_bdi(self, texto):
        limpo = str(texto).strip().replace(",", ".")
        if not limpo:
            raise ValueError("Informe o percentual de BDI.")
        valor = float(limpo)
        if valor < 0:
            raise ValueError("O BDI não pode ser negativo.")
        return valor

    def _ao_alterar_bdi(self, *_args):
        if self._trocando_orcamento:
            return
        try:
            bdi = self._parse_bdi(self.var_bdi.get())
        except ValueError:
            return
        self.orcamento.definir_bdi(bdi)
        self._atualizar_grade()

    def _ao_mudar_estado(self, _event=None):
        if self._trocando_orcamento:
            return
        self.orcamento.definir_estado_referencia(self._estado_selecionado())
        self._atualizar_grade()

    def _estado_selecionado(self):
        return estado_do_combo(self.combo_estado.get())

    def _ao_atualizar_sinapi(self):
        estados = self.ctx.obter_estados()
        self.combo_estado["values"] = valores_combo_estado(estados)
        if self.combo_estado.get() not in self.combo_estado["values"]:
            self.combo_estado.set(PLACEHOLDER_ESTADO)
        if self.label_referencia is not None:
            self.label_referencia.config(text=self._texto_referencia())
        self._atualizar_grade()

    def _grupo_id_selecionado(self):
        return self.grade.obter_grupo_id_selecionado()

    def _parse_quantidade(self, texto):
        return float(str(texto).strip().replace(",", "."))

    def _inserir_item_sinapi(
        self, grupo_id, codigo, descricao, unidade, custo, quantidade, estado
    ):
        try:
            item_id = self.orcamento.adicionar_item_sinapi(
                grupo_id, codigo, descricao, unidade, custo, quantidade, estado
            )
        except ValueError as exc:
            messagebox.showwarning("Adicionar item", str(exc), parent=self.winfo_toplevel())
            return None
        self._atualizar_grade()
        self.grade.selecionar_item(item_id)
        return item_id

    def _abrir_busca_sinapi(self):
        grupo_id = self._grupo_id_selecionado()
        if not grupo_id:
            messagebox.showinfo(
                "Inserir item SINAPI",
                "Selecione um grupo (etapa) na estrutura do orçamento.",
                parent=self.winfo_toplevel(),
            )
            return

        def ao_confirmar(codigo, descricao, unidade, custo, quantidade, estado):
            if estado and estado in self.ctx.obter_estados():
                self.combo_estado.set(estado)
            self._inserir_item_sinapi(
                grupo_id, codigo, descricao, unidade, custo, quantidade, estado
            )

        DialogoBuscaSinapi(
            self.winfo_toplevel(),
            self.ctx,
            self._estado_selecionado(),
            ao_confirmar,
        )

    def _inserir_rapido(self):
        grupo_id = self._grupo_id_selecionado()
        if not grupo_id:
            messagebox.showinfo(
                "Inserir rápido",
                "Selecione um grupo (etapa) na estrutura do orçamento.",
                parent=self.winfo_toplevel(),
            )
            return

        codigo = self.var_codigo_rapido.get().strip()
        if not codigo:
            messagebox.showinfo(
                "Inserir rápido",
                "Informe o código SINAPI.",
                parent=self.winfo_toplevel(),
            )
            return

        estado = self._estado_selecionado()
        if not estado:
            messagebox.showwarning(
                "Inserir rápido",
                "Selecione o estado.",
                parent=self.winfo_toplevel(),
            )
            return

        try:
            quantidade = self._parse_quantidade(self.var_qtd_rapido.get())
            if quantidade <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "Inserir rápido",
                "Informe uma quantidade numérica maior que zero.",
                parent=self.winfo_toplevel(),
            )
            return

        linha = obter_item_sinapi(self.ctx.sinapi, codigo, estado)
        if linha is None:
            messagebox.showwarning(
                "Inserir rápido",
                f"Código {codigo} não encontrado para o estado {estado}.",
                parent=self.winfo_toplevel(),
            )
            return

        try:
            custo = float(linha.get("custo", 0))
        except (TypeError, ValueError):
            custo = 0.0

        item_id = self._inserir_item_sinapi(
            grupo_id,
            linha.get("codigo", codigo),
            linha.get("descricao", ""),
            linha.get("unidade", ""),
            custo,
            quantidade,
            estado,
        )
        if item_id:
            self.var_codigo_rapido.set("")

    def _novo_grupo(self):
        nome = simpledialog.askstring(
            "Novo grupo",
            "Nome da etapa (ex.: Serviços preliminares):",
            parent=self.winfo_toplevel(),
        )
        if not nome or not nome.strip():
            return
        try:
            grupo_id = self.orcamento.adicionar_grupo(nome)
        except ValueError as exc:
            messagebox.showwarning("Grupo", str(exc), parent=self.winfo_toplevel())
            return
        self._atualizar_grade()
        self.grade.selecionar_por_id(TIPO_GRUPO, grupo_id)

    def _adicionar_composicao_propria(self):
        grupo_id = self._grupo_id_selecionado()
        if not grupo_id:
            messagebox.showinfo(
                "Composição própria",
                "Selecione um grupo (etapa) na estrutura do orçamento.",
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
        self._atualizar_grade()
        self.grade.selecionar_item(item_id)

    def _meta_selecionada(self):
        return self.grade.obter_meta_selecionada()

    def _remover_selecionado(self):
        meta = self._meta_selecionada()
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
                "Remover a etapa e todos os seus itens?",
                parent=self.winfo_toplevel(),
            ):
                return
            self.orcamento.remover_grupo(meta["id"])
        else:
            self.orcamento.remover_item(meta["id"])

        self._atualizar_grade()

    def _dialogo_editar_quantidade(self, item_id):
        _grupo, item = self.orcamento.obter_item(item_id)
        if item is None:
            return

        def ao_confirmar(texto):
            try:
                self.orcamento.atualizar_quantidade(item_id, self._parse_quantidade(texto))
            except ValueError as exc:
                messagebox.showwarning(
                    "Quantidade", str(exc), parent=self.winfo_toplevel()
                )
                return
            self._atualizar_grade()
            self.grade.selecionar_item(item_id)

        DialogoEditarQuantidade(
            self.winfo_toplevel(),
            rotulo_item(item),
            item["quantidade"],
            ao_confirmar,
        )

    def _editar_item_sinapi(self):
        meta = self._meta_selecionada()
        if not meta or meta["tipo"] != TIPO_SINAPI:
            messagebox.showinfo(
                "Editar item",
                "Selecione um item SINAPI para substituir por outro da base.",
                parent=self.winfo_toplevel(),
            )
            return

        item_id = meta["id"]

        def ao_substituir(codigo, descricao, unidade, custo, _quantidade, estado):
            if estado and estado in self.ctx.obter_estados():
                self.combo_estado.set(estado)
            try:
                self.orcamento.substituir_item_sinapi(
                    item_id, codigo, descricao, unidade, custo, estado
                )
            except ValueError as exc:
                messagebox.showwarning("Editar item", str(exc), parent=self.winfo_toplevel())
                return
            self._atualizar_grade()
            self.grade.selecionar_item(item_id)

        DialogoBuscaSinapi(
            self.winfo_toplevel(),
            self.ctx,
            self._estado_selecionado(),
            ao_substituir,
            titulo="Substituir item SINAPI",
            mostrar_quantidade=False,
            texto_confirmar="Substituir item",
            fechar_unico=True,
        )

    def _atualizar_grade(self):
        self._preencher_grade()

    def _preencher_grade(self):
        scroll = self.grade.posicao_scroll()
        selecao = self.grade.obter_meta_selecionada()
        self.grade.limpar()

        estado_atual = self._estado_selecionado()
        bdi = self._obter_bdi()

        for idx_grupo, grupo in enumerate(self.orcamento.grupos, start=1):
            sub_grupo = subtotal_grupo(grupo, bdi)
            self.grade.adicionar_linha(
                meta={"tipo": TIPO_GRUPO, "id": grupo["id"]},
                valores={
                    "item": str(idx_grupo),
                    "codigo": "",
                    "descricao": grupo["nome"],
                    "quantidade": "",
                    "unidade": "",
                    "custo_unit": "",
                    "custo_bdi": "",
                    "total": _formatar_moeda(sub_grupo),
                },
                estilo="grupo",
            )

            for idx_item, item in enumerate(grupo["itens"], start=1):
                num_item = f"{idx_grupo}.{idx_item}"

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

                    custo_bdi = custo_unitario_com_bdi(custo, bdi)
                    total = subtotal_item(item, bdi)
                    self.grade.adicionar_linha(
                        meta={
                            "tipo": TIPO_SINAPI,
                            "id": item["id"],
                            "grupo_id": grupo["id"],
                        },
                        valores={
                            "item": num_item,
                            "codigo": item["codigo"],
                            "descricao": item["descricao"],
                            "quantidade": _formatar_quantidade(item["quantidade"]),
                            "unidade": item["unidade"],
                            "custo_unit": _formatar_moeda(custo),
                            "custo_bdi": _formatar_moeda(custo_bdi),
                            "total": _formatar_moeda(total),
                        },
                        estilo="item",
                    )
                else:
                    self.grade.adicionar_linha(
                        meta={
                            "tipo": TIPO_COMPOSICAO_PROPRIA,
                            "id": item["id"],
                            "grupo_id": grupo["id"],
                        },
                        valores={
                            "item": num_item,
                            "codigo": "",
                            "descricao": f"[Composição própria] {item['nome']}",
                            "quantidade": _formatar_quantidade(item["quantidade"]),
                            "unidade": item["unidade"],
                            "custo_unit": "—",
                            "custo_bdi": "—",
                            "total": _formatar_moeda(0),
                        },
                        estilo="composicao",
                    )

        bdi_txt = _formatar_bdi(bdi)
        self.label_total.config(
            text=f"Total geral (c/ BDI {bdi_txt}%): {_formatar_moeda(self.orcamento.total())}"
        )
        if selecao:
            self.grade.selecionar_meta(selecao)
        self.grade.restaurar_scroll(scroll)
        self._persistir_orcamento_atual()

    def focar(self):
        pass
