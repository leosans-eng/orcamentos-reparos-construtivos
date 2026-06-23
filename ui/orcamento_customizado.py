import textwrap
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
from core.sinapi_busca import obter_item_sinapi, obter_unidades_sinapi, pesquisar_sinapi
from ui.widgets import COR_TITULO_PADRAO, criar_botao_voltar

DEBOUNCE_BUSCA_MS = 250
UNIDADE_TODAS = "Todas"
ESTILO_TREE_ORC = "OrcTreeview.Treeview"
ALTURA_LINHA_BASE = 22


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


def _quebrar_descricao(texto, largura_px):
    if not texto:
        return ""
    chars = max(24, largura_px // 7)
    linhas = textwrap.wrap(str(texto), width=chars, break_long_words=False)
    return "\n".join(linhas) if linhas else str(texto)


class DialogoBuscaSinapi(tk.Toplevel):
    def __init__(self, parent, ctx, estado_inicial, on_confirmar):
        super().__init__(parent)
        self.ctx = ctx
        self.on_confirmar = on_confirmar
        self._job_busca = None

        self.title("Buscar na SINAPI")
        self.geometry("820x520")
        self.minsize(640, 400)
        self.configure(bg="#ececec")
        self.transient(parent)
        self.grab_set()

        self._montar(estado_inicial)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())

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
            linha_filtros, values=estados, width=8, state="readonly"
        )
        self.combo_estado.grid(row=0, column=1, padx=4, pady=3, sticky="w")
        if estado_inicial and estado_inicial in estados:
            self.combo_estado.set(estado_inicial)
        elif estados:
            self.combo_estado.set("SP" if "SP" in estados else estados[0])

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
        self.entrada_busca = ttk.Entry(linha_filtros, textvariable=self.var_busca, width=48)
        self.entrada_busca.grid(row=1, column=1, columnspan=3, padx=4, pady=3, sticky="ew")
        linha_filtros.columnconfigure(1, weight=1)

        self._atualizar_unidades()

        self.label_status = tk.Label(
            painel,
            text="Digite palavras ou o código SINAPI para pesquisar.",
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

        tk.Label(rodape, text="Quantidade:", bg="#ececec").pack(side="left")
        self.var_quantidade = tk.StringVar(value="1")
        ttk.Entry(rodape, textvariable=self.var_quantidade, width=10).pack(
            side="left", padx=(6, 12)
        )
        ttk.Button(rodape, text="Inserir no grupo", command=self._confirmar).pack(side="left")
        ttk.Button(rodape, text="Cancelar", command=self.destroy).pack(side="right")

        self.var_busca.trace_add("write", self._ao_digitar)
        self.combo_estado.bind("<<ComboboxSelected>>", self._ao_mudar_estado)
        self.combo_unidade.bind("<<ComboboxSelected>>", lambda _e: self._executar_busca())
        self.tree.bind("<Double-1>", lambda _e: self._confirmar())

        if self.ctx.sinapi.empty:
            self.label_status.config(text="Base SINAPI indisponível.", fg="#C62828")

        self.entrada_busca.focus_set()

    def _unidade_selecionada(self):
        valor = self.combo_unidade.get().strip()
        return None if not valor or valor == UNIDADE_TODAS else valor

    def _aplicar_unidades(self, unidades):
        valores = [UNIDADE_TODAS] + list(unidades)
        atual = self.combo_unidade.get().strip()
        self.combo_unidade["values"] = valores
        self.combo_unidade.set(atual if atual in valores else UNIDADE_TODAS)

    def _atualizar_unidades(self, consulta=None):
        estado = self.combo_estado.get().strip()
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

        estado = self.combo_estado.get().strip()
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

    def _confirmar(self):
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
        estado = self.combo_estado.get().strip()

        try:
            quantidade = self._parse_quantidade(self.var_quantidade.get())
            if quantidade <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning(
                "Quantidade",
                "Informe um valor numérico maior que zero.",
                parent=self,
            )
            return

        custo_str = custo_fmt.replace("R$", "").strip().replace(".", "").replace(",", ".")
        try:
            custo = float(custo_str)
        except ValueError:
            custo = 0.0

        self.on_confirmar(codigo, descricao, unidade, custo, quantidade, estado)
        self.destroy()


class OrcamentoCustomizadoFrame(tk.Frame):
    COLUNAS_TREE = (
        "codigo",
        "descricao",
        "quantidade",
        "unidade",
        "custo_unit",
        "custo_bdi",
        "total",
    )

    def __init__(self, parent, ctx, on_voltar):
        super().__init__(parent, bg="#ececec")
        self.ctx = ctx
        self.on_voltar = on_voltar
        self.orcamento = OrcamentoCustomizado(bdi_percent=BDI_PADRAO)
        self._mapa_tree = {}
        self._style_tree_configurado = False
        self._atualizando_tree = False
        self._job_redimensionar = None
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

        conteudo = tk.Frame(self, bg="#ececec")
        conteudo.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        linha_nome = tk.Frame(conteudo, bg="#ececec")
        linha_nome.pack(fill="x", padx=4, pady=(0, 6))

        tk.Label(linha_nome, text="Nome do orçamento:", bg="#ececec").pack(side="left")
        self.var_nome_orcamento = tk.StringVar()
        self.var_nome_orcamento.trace_add("write", self._ao_alterar_nome)
        ttk.Entry(linha_nome, textvariable=self.var_nome_orcamento, width=34).pack(
            side="left", padx=(6, 16)
        )

        tk.Label(linha_nome, text="Estado:", bg="#ececec").pack(side="left")
        estados = self.ctx.obter_estados()
        self.combo_estado = ttk.Combobox(
            linha_nome, values=estados, width=7, state="readonly"
        )
        self.combo_estado.pack(side="left", padx=(6, 16))
        if estados:
            self.combo_estado.set("SP" if "SP" in estados else estados[0])
        self.combo_estado.bind("<<ComboboxSelected>>", self._ao_mudar_estado)

        tk.Label(linha_nome, text="BDI (%):", bg="#ececec").pack(side="left")
        self.var_bdi = tk.StringVar(value=_formatar_bdi(BDI_PADRAO))
        self.var_bdi.trace_add("write", self._ao_alterar_bdi)
        ttk.Entry(linha_nome, textvariable=self.var_bdi, width=8).pack(side="left", padx=(6, 0))

        linha_botoes = tk.Frame(conteudo, bg="#ececec")
        linha_botoes.pack(fill="x", padx=4, pady=(0, 8))

        ttk.Button(linha_botoes, text="Nova etapa", command=self._novo_grupo).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(
            linha_botoes, text="Remover selecionado", command=self._remover_selecionado
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            linha_botoes, text="Editar quantidade", command=self._editar_quantidade_selecionada
        ).pack(side="left", padx=(0, 16))

        ttk.Button(
            linha_botoes, text="Inserir item SINAPI", command=self._abrir_busca_sinapi
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            linha_botoes,
            text="Inserir composição PRÓPRIA",
            command=self._adicionar_composicao_propria,
        ).pack(side="left", padx=(0, 16))

        tk.Label(linha_botoes, text="Inserir rápido — Cód.:", bg="#ececec").pack(side="left")
        self.var_codigo_rapido = tk.StringVar()
        entrada_cod = ttk.Entry(linha_botoes, textvariable=self.var_codigo_rapido, width=10)
        entrada_cod.pack(side="left", padx=(4, 8))
        tk.Label(linha_botoes, text="Qtd.:", bg="#ececec").pack(side="left")
        self.var_qtd_rapido = tk.StringVar(value="1")
        entrada_qtd = ttk.Entry(linha_botoes, textvariable=self.var_qtd_rapido, width=8)
        entrada_qtd.pack(side="left", padx=(4, 8))
        ttk.Button(linha_botoes, text="Inserir", command=self._inserir_rapido).pack(
            side="left"
        )
        entrada_cod.bind("<Return>", lambda _e: self._inserir_rapido())
        entrada_qtd.bind("<Return>", lambda _e: self._inserir_rapido())

        painel_tree = tk.LabelFrame(
            conteudo,
            text="Estrutura do orçamento",
            bg="#ececec",
            padx=6,
            pady=6,
        )
        painel_tree.pack(fill="both", expand=True, padx=4, pady=(0, 6))

        self.tree_orcamento = ttk.Treeview(
            painel_tree,
            columns=self.COLUNAS_TREE,
            show="tree headings",
            height=18,
            selectmode="browse",
            style=ESTILO_TREE_ORC,
        )
        self.tree_orcamento.heading("#0", text="Item")
        self.tree_orcamento.heading("codigo", text="Código")
        self.tree_orcamento.heading("descricao", text="Descrição")
        self.tree_orcamento.heading("quantidade", text="Qtd.")
        self.tree_orcamento.heading("unidade", text="Unid.")
        self.tree_orcamento.heading("custo_unit", text="Custo unit.")
        self.tree_orcamento.heading("custo_bdi", text="Custo c/ BDI")
        self.tree_orcamento.heading("total", text="Total")

        self.tree_orcamento.column("#0", width=60, minwidth=44, stretch=False, anchor="center")
        self.tree_orcamento.column("codigo", width=72, minwidth=60, stretch=False, anchor="center")
        self.tree_orcamento.column("descricao", width=340, minwidth=180, stretch=True)
        self.tree_orcamento.column("quantidade", width=64, minwidth=50, stretch=False, anchor="e")
        self.tree_orcamento.column("unidade", width=48, minwidth=40, stretch=False, anchor="center")
        self.tree_orcamento.column("custo_unit", width=92, minwidth=78, stretch=False, anchor="e")
        self.tree_orcamento.column("custo_bdi", width=92, minwidth=78, stretch=False, anchor="e")
        self.tree_orcamento.column("total", width=96, minwidth=80, stretch=False, anchor="e")

        scroll_orc = ttk.Scrollbar(painel_tree, orient="vertical", command=self.tree_orcamento.yview)
        self.tree_orcamento.configure(yscrollcommand=scroll_orc.set)
        self.tree_orcamento.pack(side="left", fill="both", expand=True)
        scroll_orc.pack(side="right", fill="y")

        self.tree_orcamento.tag_configure("grupo", font=("Arial", 9, "bold"))
        self.tree_orcamento.tag_configure("composicao", foreground="#7b5e00")

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

        self.label_dica = tk.Label(
            conteudo,
            text=(
                "Numeração automática: 1, 2… para etapas; 1.1, 1.2… para itens. "
                "Duplo clique na coluna Qtd. para editar."
            ),
            font=("Arial", 8),
            fg="#666666",
            bg="#ececec",
            justify="left",
        )
        self.label_dica.pack(fill="x", padx=6, pady=(6, 0))

        self.tree_orcamento.bind("<Double-1>", self._ao_duplo_clique_orcamento)
        self.tree_orcamento.bind("<Configure>", self._ao_redimensionar_tree)

        self._atualizar_tree_orcamento()

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

    def _ao_alterar_nome(self, *_args):
        self.orcamento.definir_nome(self.var_nome_orcamento.get())

    def _ao_alterar_bdi(self, *_args):
        try:
            bdi = self._parse_bdi(self.var_bdi.get())
        except ValueError:
            return
        self.orcamento.definir_bdi(bdi)
        self._atualizar_tree_orcamento()

    def _ao_mudar_estado(self, _event=None):
        self._atualizar_tree_orcamento()

    def _ao_atualizar_sinapi(self):
        estados = self.ctx.obter_estados()
        self.combo_estado["values"] = estados
        if estados and self.combo_estado.get() not in estados:
            self.combo_estado.set("SP" if "SP" in estados else estados[0])
        self.label_referencia.config(text=self._texto_referencia())
        self._atualizar_tree_orcamento()

    def _ao_redimensionar_tree(self, _event=None):
        if self._atualizando_tree:
            return
        if self._job_redimensionar is not None:
            self.after_cancel(self._job_redimensionar)
        self._job_redimensionar = self.after(150, self._reempacotar_descricoes)

    def _reempacotar_descricoes(self):
        self._job_redimensionar = None
        if self._atualizando_tree:
            return
        self._atualizar_tree_orcamento()

    def _grupo_id_selecionado(self):
        selecionado = self.tree_orcamento.selection()
        if not selecionado:
            return None
        meta = self._mapa_tree.get(selecionado[0])
        if not meta:
            return None
        if meta["tipo"] == TIPO_GRUPO:
            return meta["id"]
        return meta.get("grupo_id")

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
        self._atualizar_tree_orcamento()
        self._selecionar_item_na_tree(item_id)
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
            self._inserir_item_sinapi(
                grupo_id, codigo, descricao, unidade, custo, quantidade, estado
            )

        DialogoBuscaSinapi(
            self.winfo_toplevel(),
            self.ctx,
            self.combo_estado.get().strip(),
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

        estado = self.combo_estado.get().strip()
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
        self._atualizar_tree_orcamento()
        self._selecionar_grupo_na_tree(grupo_id)

    def _selecionar_grupo_na_tree(self, grupo_id):
        for iid, meta in self._mapa_tree.items():
            if meta.get("tipo") == TIPO_GRUPO and meta.get("id") == grupo_id:
                self.tree_orcamento.selection_set(iid)
                self.tree_orcamento.focus(iid)
                self.tree_orcamento.see(iid)
                break

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
        self._atualizar_tree_orcamento()
        self._selecionar_item_na_tree(item_id)

    def _meta_selecionada(self):
        selecionado = self.tree_orcamento.selection()
        if not selecionado:
            return None, None
        return selecionado[0], self._mapa_tree.get(selecionado[0])

    def _remover_selecionado(self):
        _iid, meta = self._meta_selecionada()
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

        self._atualizar_tree_orcamento()

    def _editar_quantidade_selecionada(self):
        _iid, meta = self._meta_selecionada()
        if not meta or meta["tipo"] == TIPO_GRUPO:
            messagebox.showinfo(
                "Quantidade",
                "Selecione um item para editar a quantidade.",
                parent=self.winfo_toplevel(),
            )
            return
        self._dialogo_editar_quantidade(meta["id"])

    def _ao_duplo_clique_orcamento(self, event):
        iid = self.tree_orcamento.identify_row(event.y)
        coluna = self.tree_orcamento.identify_column(event.x)
        if not iid or coluna != "#3":
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
            self.orcamento.atualizar_quantidade(item_id, self._parse_quantidade(nova))
        except ValueError as exc:
            messagebox.showwarning("Quantidade", str(exc), parent=self.winfo_toplevel())
            return

        self._atualizar_tree_orcamento()
        self._selecionar_item_na_tree(item_id)

    def _aplicar_altura_linhas(self, max_linhas):
        linhas = max(1, max_linhas)
        altura = ALTURA_LINHA_BASE * linhas
        estilo = ttk.Style(self)
        if not self._style_tree_configurado:
            estilo.configure(ESTILO_TREE_ORC, rowheight=altura)
            self._style_tree_configurado = True
        else:
            estilo.configure(ESTILO_TREE_ORC, rowheight=altura)

    def _atualizar_tree_orcamento(self):
        self._atualizando_tree = True
        try:
            self._preencher_tree_orcamento()
        finally:
            self._atualizando_tree = False

    def _preencher_tree_orcamento(self):
        self.tree_orcamento.delete(*self.tree_orcamento.get_children())
        self._mapa_tree.clear()

        estado_atual = self.combo_estado.get().strip()
        bdi = self._obter_bdi()
        largura_desc = self.tree_orcamento.column("descricao", option="width") or 340
        max_linhas = 1

        for idx_grupo, grupo in enumerate(self.orcamento.grupos, start=1):
            num_grupo = str(idx_grupo)
            desc_grupo = _quebrar_descricao(grupo["nome"], largura_desc)
            max_linhas = max(max_linhas, desc_grupo.count("\n") + 1)

            sub_grupo = subtotal_grupo(grupo, bdi)
            iid_grupo = self.tree_orcamento.insert(
                "",
                "end",
                text=num_grupo,
                values=(
                    "",
                    desc_grupo,
                    "",
                    "",
                    "",
                    "",
                    _formatar_moeda(sub_grupo),
                ),
                open=True,
                tags=("grupo",),
            )
            self._mapa_tree[iid_grupo] = {"tipo": TIPO_GRUPO, "id": grupo["id"]}

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
                    desc = _quebrar_descricao(item["descricao"], largura_desc)
                    max_linhas = max(max_linhas, desc.count("\n") + 1)

                    iid_item = self.tree_orcamento.insert(
                        iid_grupo,
                        "end",
                        text=num_item,
                        values=(
                            item["codigo"],
                            desc,
                            _formatar_quantidade(item["quantidade"]),
                            item["unidade"],
                            _formatar_moeda(custo),
                            _formatar_moeda(custo_bdi),
                            _formatar_moeda(total),
                        ),
                    )
                else:
                    desc = _quebrar_descricao(item["nome"], largura_desc)
                    max_linhas = max(max_linhas, desc.count("\n") + 1)
                    iid_item = self.tree_orcamento.insert(
                        iid_grupo,
                        "end",
                        text=num_item,
                        values=(
                            "",
                            desc,
                            _formatar_quantidade(item["quantidade"]),
                            item["unidade"],
                            "—",
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

            sub_atualizado = subtotal_grupo(grupo, bdi)
            valores_grupo = list(self.tree_orcamento.item(iid_grupo, "values"))
            valores_grupo[-1] = _formatar_moeda(sub_atualizado)
            self.tree_orcamento.item(iid_grupo, values=tuple(valores_grupo))

        self._aplicar_altura_linhas(max_linhas)
        bdi_txt = _formatar_bdi(bdi)
        self.label_total.config(
            text=f"Total geral (c/ BDI {bdi_txt}%): {_formatar_moeda(self.orcamento.total())}"
        )

    def focar(self):
        pass
