import tkinter as tk
from tkinter import messagebox, ttk

from app_paths import asset_path
from core.composicoes_proprias import custo_composicao_propria_item, filtrar_composicoes_catalogo
from core.exportacao_planilha_orcamento import (
    exportar_orcamento_customizado_modelo4,
    exportar_orcamento_customizado_modelo_formatado,
)
from core.composicoes_proprias_storage import listar as listar_composicoes_catalogo
from core.importacao_i9 import importar_planilha_i9
from core.orcamento_customizado import (
    BDI_PADRAO,
    TIPO_COMPOSICAO_PROPRIA,
    TIPO_GRUPO,
    TIPO_SINAPI,
    OrcamentoCustomizado,
    custo_unitario_com_bdi,
    item_indisponivel_na_base,
    rotulo_item,
    rotulo_tipo_sinapi,
    sincronizar_precos_sinapi_no_orcamento,
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
from core.sinapi_busca import (
    TIPO_COMPOSICAO,
    TIPO_INSUMO,
    TIPO_TODOS,
    VALORES_FILTRO_TIPO,
    nome_tipo_sinapi,
    obter_item_sinapi,
    obter_unidades_sinapi,
    pesquisar_sinapi,
    tipo_sinapi_para_filtro,
)
from ui.dialogo_importar_i9 import DialogoImportarI9
from ui.dialogo_selecionar_modelo_planilha import DialogoSelecionarModeloPlanilha
from ui.grade_orcamento import GradeOrcamento
from ui.icones import criar_botao_inserir_prominente, criar_botao_ttk_com_icone
from ui.widgets import (
    PLACEHOLDER_ESTADO,
    aplicar_icone_janela,
    centralizar_janela,
    preparar_toplevel,
    confirmar_exclusao_com_espera,
    criar_barra_modulo,
    estado_do_combo,
    perguntar_texto,
    valores_combo_estado,
    formatar_decimal_br,
    formatar_moeda_br,
    formatar_quantidade_edicao,
    parse_decimal_br,
)

DEBOUNCE_BUSCA_MS = 250
UNIDADE_TODAS = "Todas"


def _formatar_moeda(valor):
    return formatar_moeda_br(valor)


def _formatar_quantidade(valor):
    return formatar_decimal_br(valor, casas=4)


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
        preparar_toplevel(self)
        self.on_confirmar = on_confirmar
        self.title("Editar quantidade")
        aplicar_icone_janela(self)
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
        self.var_quantidade = tk.StringVar(
            value=formatar_quantidade_edicao(quantidade_atual)
        )
        entrada = ttk.Entry(linha_qtd, textvariable=self.var_quantidade, width=14)
        entrada.pack(side="left", padx=(8, 0))
        entrada.focus_set()
        entrada.select_range(0, "end")
        entrada.bind("<Return>", lambda _e: self._confirmar())
        entrada.bind("<Escape>", lambda _e: self.destroy())

        botoes = ttk.Frame(painel)
        botoes.pack(fill="x")
        ttk.Button(botoes, text="Cancelar", command=self.destroy, style="Delete.TButton").pack(
            side="right", padx=(6, 0)
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


class DialogoTrocarOrdemEtapa(tk.Toplevel):
    def __init__(self, parent, nome_etapa, posicao_atual, opcoes_posicao, on_confirmar):
        super().__init__(parent)
        preparar_toplevel(self)
        self.on_confirmar = on_confirmar
        self.title("Trocar ordem da etapa")
        aplicar_icone_janela(self)
        self.configure(bg="#ececec")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        painel = tk.Frame(self, bg="#ececec", padx=16, pady=14)
        painel.pack(fill="both", expand=True)

        tk.Label(
            painel,
            text="Etapa selecionada:",
            font=("Arial", 9, "bold"),
            fg="#444444",
            bg="#ececec",
            anchor="w",
        ).pack(fill="x")

        tk.Label(
            painel,
            text=f"{posicao_atual} — {nome_etapa}",
            font=("Arial", 9),
            fg="#333333",
            bg="#f5fafc",
            anchor="w",
            padx=8,
            pady=8,
        ).pack(fill="x", pady=(4, 12))

        linha_pos = tk.Frame(painel, bg="#ececec")
        linha_pos.pack(fill="x", pady=(0, 12))
        tk.Label(linha_pos, text="Nova posição:", bg="#ececec").pack(side="left")

        indice_inicial = max(0, min(posicao_atual - 1, len(opcoes_posicao) - 1))
        self.var_posicao = tk.StringVar(value=opcoes_posicao[indice_inicial])
        self.combo_posicao = ttk.Combobox(
            linha_pos,
            textvariable=self.var_posicao,
            values=opcoes_posicao,
            state="readonly",
            width=42,
        )
        self.combo_posicao.pack(side="left", padx=(8, 0), fill="x", expand=True)
        self.combo_posicao.current(indice_inicial)
        self.combo_posicao.focus_set()

        botoes = ttk.Frame(painel)
        botoes.pack(fill="x")
        ttk.Button(botoes, text="Cancelar", command=self.destroy, style="Delete.TButton").pack(
            side="right", padx=(6, 0)
        )
        ttk.Button(botoes, text="Confirmar", command=self._confirmar, style="Add.TButton").pack(
            side="right"
        )

        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        centralizar_janela(self, parent)

    def _confirmar(self):
        indice = self.combo_posicao.current()
        if indice < 0:
            messagebox.showwarning(
                "Trocar ordem da etapa",
                "Selecione uma posição válida.",
                parent=self,
            )
            return
        self.on_confirmar(indice + 1)
        self.destroy()


ETAPA_EM_BRANCO = "— Etapa em branco —"


class DialogoNovaEtapa(tk.Toplevel):
    def __init__(self, parent, modelos, on_confirmar):
        super().__init__(parent)
        preparar_toplevel(self)
        self.on_confirmar = on_confirmar
        self._modelos_por_nome = {m["nome"]: m for m in modelos}
        self.title("Nova etapa")
        aplicar_icone_janela(self)
        self.configure(bg="#ececec")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        painel = tk.Frame(self, bg="#ececec", padx=16, pady=14)
        painel.pack(fill="both", expand=True)

        tk.Label(
            painel,
            text="Nome da etapa:",
            bg="#ececec",
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self.var_nome = tk.StringVar()
        entrada_nome = ttk.Entry(painel, textvariable=self.var_nome, width=44)
        entrada_nome.pack(fill="x", pady=(0, 12))

        tk.Label(
            painel,
            text="Modelo (opcional):",
            bg="#ececec",
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        opcoes = [ETAPA_EM_BRANCO] + [m["nome"] for m in modelos]
        self.var_modelo = tk.StringVar(value=ETAPA_EM_BRANCO)
        self.combo_modelo = ttk.Combobox(
            painel,
            textvariable=self.var_modelo,
            values=opcoes,
            state="readonly",
            width=42,
        )
        self.combo_modelo.pack(fill="x", pady=(0, 8))
        self.combo_modelo.bind("<<ComboboxSelected>>", self._ao_mudar_modelo)

        botoes = ttk.Frame(painel)
        botoes.pack(fill="x")
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
        entrada_nome.focus_set()

    def _ao_mudar_modelo(self, _event=None):
        modelo = self.var_modelo.get().strip()
        if modelo and modelo != ETAPA_EM_BRANCO:
            self.var_nome.set(modelo)

    def _confirmar(self):
        nome = self.var_nome.get().strip()
        if not nome:
            messagebox.showwarning(
                "Nova etapa",
                "Informe o nome da etapa.",
                parent=self,
            )
            return

        modelo = self.var_modelo.get().strip()
        etapa_id = None
        if modelo and modelo != ETAPA_EM_BRANCO:
            etapa = self._modelos_por_nome.get(modelo)
            if etapa is not None:
                etapa_id = etapa["id"]

        if self.on_confirmar(nome, etapa_id):
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
        incluir_composicoes_proprias=False,
        catalogo_composicoes=None,
        on_confirmar_propria=None,
        texto_item_substituindo=None,
    ):
        super().__init__(parent)
        preparar_toplevel(self)
        self.ctx = ctx
        self.on_confirmar = on_confirmar
        self.on_confirmar_propria = on_confirmar_propria
        self.incluir_composicoes_proprias = incluir_composicoes_proprias
        self.catalogo_composicoes = list(catalogo_composicoes or [])
        self.texto_item_substituindo = (texto_item_substituindo or "").strip() or None
        self.label_item_substituindo = None
        self._job_busca = None
        self.mostrar_quantidade = mostrar_quantidade
        self.texto_confirmar = texto_confirmar
        self.texto_confirmar_fechar = texto_confirmar_fechar
        self.fechar_unico = fechar_unico
        self._ultima_largura_wrap = 0

        self.title(titulo)
        self.geometry("1100x700")
        self.minsize(700, 480)
        aplicar_icone_janela(self)
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

        tk.Label(linha_filtros, text="Tipo (I/C):", bg="#ececec").grid(
            row=0, column=4, padx=(14, 4), pady=3, sticky="w"
        )
        self.combo_tipo = ttk.Combobox(
            linha_filtros, values=list(VALORES_FILTRO_TIPO), width=12, state="readonly"
        )
        self.combo_tipo.grid(row=0, column=5, padx=4, pady=3, sticky="w")
        self.combo_tipo.set(TIPO_TODOS)

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

        colunas = ("codigo", "tipo_ic", "descricao", "unidade", "custo")
        self.tree = ttk.Treeview(painel_resultados, columns=colunas, show="headings", height=12)
        self.tree.heading("codigo", text="Código")
        self.tree.heading("tipo_ic", text="I/C")
        self.tree.heading("descricao", text="Descrição")
        self.tree.heading("unidade", text="Unid.")
        self.tree.heading("custo", text="Custo unit. (R$)")
        self.tree.column("codigo", width=60, minwidth=60, stretch=False, anchor="center")
        self.tree.column("tipo_ic", width=36, minwidth=32, stretch=False, anchor="center")
        self.tree.column("descricao", width=400, minwidth=200, stretch=True)
        self.tree.column("unidade", width=55, minwidth=45, stretch=False, anchor="center")
        self.tree.column("custo", width=110, minwidth=90, stretch=False, anchor="e")

        scroll = ttk.Scrollbar(painel_resultados, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        if self.texto_item_substituindo:
            painel_atual = tk.LabelFrame(
                painel, text="Item a substituir", bg="#ececec", padx=6, pady=4
            )
            painel_atual.pack(fill="x", pady=(0, 6))
            frame_atual = tk.Frame(
                painel_atual,
                bg="#e8ecf0",
                highlightbackground="#cccccc",
                highlightthickness=1,
            )
            frame_atual.pack(fill="x")
            self.label_item_substituindo = tk.Label(
                frame_atual,
                text=self.texto_item_substituindo,
                font=("Arial", 9),
                fg="#333333",
                bg="#e8ecf0",
                justify="left",
                anchor="w",
                padx=10,
                pady=8,
            )
            self.label_item_substituindo.pack(fill="x")

        titulo_detalhe = (
            "Novo item selecionado" if self.texto_item_substituindo else "Detalhes"
        )
        painel_detalhe = tk.LabelFrame(
            painel, text=titulo_detalhe, bg="#ececec", padx=6, pady=4
        )
        painel_detalhe.pack(fill="x", pady=(0, 8))

        texto_detalhe_inicial = (
            "Selecione o novo item na lista para comparar."
            if self.texto_item_substituindo
            else "Selecione um item na lista para ver os detalhes."
        )
        frame_detalhe = tk.Frame(
            painel_detalhe,
            bg="#f5fafc",
            highlightbackground="#cccccc",
            highlightthickness=1,
        )
        frame_detalhe.pack(fill="x")

        self.label_detalhe = tk.Label(
            frame_detalhe,
            text=texto_detalhe_inicial,
            font=("Arial", 9),
            fg="#444444",
            bg="#f5fafc",
            justify="left",
            anchor="w",
            padx=10,
            pady=8,
        )
        self.label_detalhe.pack(fill="x")

        rodape = tk.Frame(painel, bg="#ececec")
        rodape.pack(fill="x")

        botoes_acao = tk.Frame(rodape, bg="#ececec")
        botoes_acao.pack(side="right")
        ttk.Button(
            botoes_acao, text="Cancelar", command=self.destroy, style="Delete.TButton"
        ).pack(side="right")
        if self.fechar_unico:
            ttk.Button(
                botoes_acao,
                text=self.texto_confirmar,
                command=lambda: self._confirmar(fechar=True),
                style="Add.TButton",
            ).pack(side="right", padx=(0, 8))
        else:
            ttk.Button(
                botoes_acao,
                text=self.texto_confirmar_fechar,
                command=lambda: self._confirmar(fechar=True),
                style="Save.TButton",
            ).pack(side="right", padx=(0, 8))
            ttk.Button(
                botoes_acao,
                text=self.texto_confirmar,
                command=lambda: self._confirmar(fechar=False),
                style="Add.TButton",
            ).pack(side="right", padx=(0, 8))

        self.var_busca.trace_add("write", self._ao_digitar)
        self.combo_estado.bind("<<ComboboxSelected>>", self._ao_mudar_estado)
        self.combo_unidade.bind("<<ComboboxSelected>>", lambda _e: self._executar_busca())
        self.combo_tipo.bind("<<ComboboxSelected>>", lambda _e: self._executar_busca())
        self.tree.bind("<<TreeviewSelect>>", self._ao_selecionar_item)
        self.tree.bind(
            "<Double-1>",
            lambda _e: self._confirmar(fechar=self.fechar_unico),
        )
        self.bind("<Configure>", self._ao_redimensionar)

        if self.ctx.sinapi.empty:
            self.label_status.config(text="Base SINAPI indisponível.", fg="#C62828")

        self.entrada_busca.focus_set()
        self.after_idle(self._ajustar_layout_detalhe)

    def _ao_redimensionar(self, event=None):
        if event is not None and event.widget is not self:
            return
        self._ajustar_layout_detalhe()

    def _ajustar_layout_detalhe(self):
        self.update_idletasks()
        largura = self.winfo_width()
        if largura < 200 or largura == self._ultima_largura_wrap:
            return
        self._ultima_largura_wrap = largura
        wrap = max(280, largura - 48)
        self.label_detalhe.config(wraplength=wrap)
        if self.label_item_substituindo is not None:
            self.label_item_substituindo.config(wraplength=wrap)

    def _ao_selecionar_item(self, _event=None):
        selecionado = self.tree.selection()
        if not selecionado:
            return
        valores = self.tree.item(selecionado[0], "values")
        if len(valores) < 5:
            return
        codigo, tipo_ic, descricao, unidade, custo = valores
        estado = self._estado_selecionado()
        tipo_rotulo = nome_tipo_sinapi(tipo_ic) or tipo_ic
        self.label_detalhe.config(
            text=(
                f"Código: {codigo}  ·  {tipo_rotulo}  ·  Estado: {estado}  ·  "
                f"Unidade: {unidade}  ·  Custo: {custo}\n{descricao}"
            ),
        )

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
            tipo=self._tipo_selecionado_sinapi(),
        )
        self._aplicar_unidades(unidades)
        self.tree.delete(*self.tree.get_children())

        tipo_filtro = self.combo_tipo.get().strip()
        incluir_proprias = (
            self.incluir_composicoes_proprias
            and self.catalogo_composicoes
            and tipo_filtro in (TIPO_TODOS, TIPO_COMPOSICAO)
        )

        for _, linha in resultados.iterrows():
            self.tree.insert(
                "",
                "end",
                values=(
                    str(linha.get("codigo", "")),
                    str(linha.get("tipo", "")).strip().upper()[:1] or "—",
                    str(linha.get("descricao", "")),
                    str(linha.get("unidade", "")),
                    _formatar_moeda(linha.get("custo", 0)),
                ),
            )

        if incluir_proprias:
            from core.composicoes_proprias import calcular_custo_unitario

            unidade = self._unidade_selecionada()
            for comp in filtrar_composicoes_catalogo(
                self.catalogo_composicoes, consulta, unidade
            ):
                custo, _ = calcular_custo_unitario(comp, self.ctx.sinapi, estado)
                self.tree.insert(
                    "",
                    "end",
                    iid=f"p:{comp['id']}",
                    values=(
                        comp.get("codigo", ""),
                        "P",
                        comp.get("nome", ""),
                        comp.get("unidade", ""),
                        _formatar_moeda(custo),
                    ),
                )

        if incluir_proprias and not self.tree.get_children() and consulta.strip():
            mensagem = (
                "Nenhum insumo, composição SINAPI ou composição própria encontrada. "
                "Tente sinônimos ou menos palavras."
            )
        elif incluir_proprias and self.tree.get_children() and consulta.strip():
            total = len(self.tree.get_children())
            mensagem = f"{total} resultado(s) encontrado(s) (SINAPI e composições próprias)."

        self.label_detalhe.config(text="Selecione um item na lista para ver os detalhes.")
        cor = "#555555" if self.tree.get_children() else "#a67c00"
        if "indisponível" in mensagem.lower() or "nenhum item" in mensagem.lower():
            cor = "#C62828"
        self.label_status.config(text=mensagem, fg=cor)

    def _tipo_selecionado_sinapi(self):
        selecao = self.combo_tipo.get().strip()
        if selecao == TIPO_COMPOSICAO and self.incluir_composicoes_proprias:
            return "C"
        return tipo_sinapi_para_filtro(selecao)

    def _parse_quantidade(self, texto):
        return parse_decimal_br(texto)

    def _confirmar(self, fechar=False):
        selecionado = self.tree.selection()
        if not selecionado:
            messagebox.showinfo(
                "Inserir item",
                "Selecione um item nos resultados.",
                parent=self,
            )
            return

        iid = selecionado[0]
        if str(iid).startswith("p:"):
            self._confirmar_propria(iid, fechar)
            return

        valores = self.tree.item(iid, "values")
        if len(valores) < 5:
            return

        codigo, tipo_ic, descricao, unidade, custo_fmt = valores
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

        self.on_confirmar(
            codigo, descricao, unidade, custo, quantidade, estado, tipo_ic if tipo_ic != "—" else ""
        )
        if fechar:
            self.destroy()

    def _confirmar_propria(self, iid, fechar=False):
        if not self.on_confirmar_propria:
            messagebox.showinfo(
                "Composição própria",
                "Seleção de composição própria não disponível neste contexto.",
                parent=self,
            )
            return

        comp_id = str(iid)[2:]
        comp = next(
            (c for c in self.catalogo_composicoes if c.get("id") == comp_id),
            None,
        )
        if comp is None:
            return

        if self.mostrar_quantidade:
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
        else:
            quantidade = 1.0

        self.on_confirmar_propria(comp, quantidade)
        if fechar:
            self.destroy()


class DialogoBuscaComposicaoPropria(tk.Toplevel):
    def __init__(
        self,
        parent,
        ctx,
        catalogo,
        estado_inicial,
        on_confirmar,
        *,
        mostrar_quantidade=True,
        titulo="Inserir composição própria",
        texto_confirmar="Inserir",
    ):
        super().__init__(parent)
        preparar_toplevel(self)
        self.ctx = ctx
        self.catalogo = catalogo
        self.on_confirmar = on_confirmar
        self.mostrar_quantidade = mostrar_quantidade
        self.texto_confirmar = texto_confirmar
        self._ultima_largura_wrap = 0

        self.title(titulo)
        self.geometry("900x620")
        self.minsize(640, 420)
        aplicar_icone_janela(self)
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

        tk.Label(linha_filtros, text="Filtrar:", bg="#ececec").grid(
            row=1, column=0, padx=(0, 4), pady=3, sticky="w"
        )
        self.var_busca = tk.StringVar()
        self.var_busca.trace_add("write", lambda *_a: self._atualizar_lista())
        ttk.Entry(linha_filtros, textvariable=self.var_busca, width=36).grid(
            row=1, column=1, padx=4, pady=3, sticky="ew"
        )

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

        painel_resultados = tk.LabelFrame(
            painel, text="Composições cadastradas", bg="#ececec", padx=6, pady=4
        )
        painel_resultados.pack(fill="both", expand=True, pady=(0, 8))

        colunas = ("codigo", "nome", "unidade", "custo")
        self.tree = ttk.Treeview(painel_resultados, columns=colunas, show="headings", height=12)
        self.tree.heading("codigo", text="Código")
        self.tree.heading("nome", text="Nome")
        self.tree.heading("unidade", text="Unid.")
        self.tree.heading("custo", text="Custo unit. (R$)")
        self.tree.column("codigo", width=60, minwidth=60, stretch=False, anchor="center")
        self.tree.column("nome", width=420, minwidth=200, stretch=True)
        self.tree.column("unidade", width=55, minwidth=45, stretch=False, anchor="center")
        self.tree.column("custo", width=110, minwidth=90, stretch=False, anchor="e")

        scroll = ttk.Scrollbar(painel_resultados, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        painel_detalhe = tk.Frame(
            painel, bg="#f5fafc", highlightbackground="#cccccc", highlightthickness=1
        )
        painel_detalhe.pack(fill="x", pady=(0, 8))

        self.label_detalhe = tk.Label(
            painel_detalhe,
            text="Selecione uma composição na lista para ver os detalhes.",
            font=("Arial", 9),
            fg="#444444",
            bg="#f5fafc",
            justify="left",
            anchor="w",
            padx=10,
            pady=8,
        )
        self.label_detalhe.pack(fill="x")

        rodape = tk.Frame(painel, bg="#ececec")
        rodape.pack(fill="x")
        botoes_acao = tk.Frame(rodape, bg="#ececec")
        botoes_acao.pack(side="right")
        ttk.Button(
            botoes_acao, text="Cancelar", command=self.destroy, style="Delete.TButton"
        ).pack(side="right")
        ttk.Button(
            botoes_acao,
            text=self.texto_confirmar,
            command=self._confirmar,
            style="Add.TButton",
        ).pack(side="right", padx=(0, 8))

        self.combo_estado.bind("<<ComboboxSelected>>", self._atualizar_lista)
        self.tree.bind("<<TreeviewSelect>>", self._ao_selecionar_item)
        self.tree.bind("<Double-1>", lambda _e: self._confirmar())
        self.bind("<Configure>", self._ao_redimensionar)

        self._atualizar_lista()
        self.after_idle(self._ajustar_layout_detalhe)

    def _ao_redimensionar(self, event=None):
        if event is not None and event.widget is not self:
            return
        self._ajustar_layout_detalhe()

    def _ajustar_layout_detalhe(self):
        self.update_idletasks()
        largura = self.winfo_width()
        if largura < 200 or largura == self._ultima_largura_wrap:
            return
        self._ultima_largura_wrap = largura
        self.label_detalhe.config(wraplength=max(280, largura - 48))

    def _estado_selecionado(self):
        return estado_do_combo(self.combo_estado.get())

    def _filtrar_catalogo(self):
        texto = self.var_busca.get().strip().lower()
        if not texto:
            return list(self.catalogo)
        filtradas = []
        for comp in self.catalogo:
            codigo = str(comp.get("codigo", "")).lower()
            nome = str(comp.get("nome", "")).lower()
            if texto in codigo or texto in nome:
                filtradas.append(comp)
        return filtradas

    def _atualizar_lista(self, _event=None):
        from core.composicoes_proprias import calcular_custo_unitario

        self.tree.delete(*self.tree.get_children())
        estado = self._estado_selecionado()
        for comp in self._filtrar_catalogo():
            custo, _ = calcular_custo_unitario(comp, self.ctx.sinapi, estado)
            self.tree.insert(
                "",
                "end",
                iid=comp["id"],
                values=(
                    comp.get("codigo", ""),
                    comp.get("nome", ""),
                    comp.get("unidade", ""),
                    _formatar_moeda(custo) if estado else "—",
                ),
            )
        self.label_detalhe.config(text="Selecione uma composição na lista para ver os detalhes.")

    def _ao_selecionar_item(self, _event=None):
        selecionado = self.tree.selection()
        if not selecionado:
            return
        comp_id = selecionado[0]
        comp = next((c for c in self.catalogo if c.get("id") == comp_id), None)
        if comp is None:
            return
        estado = self._estado_selecionado()
        from core.composicoes_proprias import calcular_custo_unitario

        custo, tem_dep = calcular_custo_unitario(comp, self.ctx.sinapi, estado)
        aviso = " · ATENÇÃO: há componentes SINAPI depreciados" if tem_dep else ""
        self.label_detalhe.config(
            text=(
                f"Código: {comp.get('codigo', '')}  ·  Unidade: {comp.get('unidade', '')}  ·  "
                f"Custo unit.: {_formatar_moeda(custo) if estado else '—'}{aviso}\n"
                f"{comp.get('nome', '')}"
            ),
        )

    def _parse_quantidade(self, texto):
        return parse_decimal_br(texto)

    def _confirmar(self):
        selecionado = self.tree.selection()
        if not selecionado:
            messagebox.showinfo(
                "Inserir composição",
                "Selecione uma composição na lista.",
                parent=self,
            )
            return

        comp_id = selecionado[0]
        comp = next((c for c in self.catalogo if c.get("id") == comp_id), None)
        if comp is None:
            return

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

        self.on_confirmar(comp, quantidade)
        self.destroy()


class OrcamentoCustomizadoFrame(tk.Frame):
    def __init__(self, parent, ctx, on_voltar):
        super().__init__(parent, bg="#ececec")
        self.ctx = ctx
        self.on_voltar = on_voltar
        self._dados_arquivo = carregar_arquivo()
        self._mapa_combo_ids = {}
        self._trocando_orcamento = False
        self._icone_excel_export = None
        self._icones_botoes = []
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
            linha_salvo, width=50, state="readonly"
        )
        self.combo_orcamento.pack(side="left", padx=(4, 8))
        self.combo_orcamento.bind("<<ComboboxSelected>>", self._ao_trocar_orcamento)

        criar_botao_ttk_com_icone(
            linha_salvo,
            texto="Adicionar orçamento",
            nome_icone="add-circle-outline",
            command=self._adicionar_orcamento,
            estilo="Add.Compact.TButton",
            refs=self._icones_botoes,
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            linha_salvo,
            text="Editar nome do orçamento",
            command=self._renomear_orcamento,
            style="Edit.Compact.TButton",
        ).pack(side="left", padx=(0, 4))
        criar_botao_ttk_com_icone(
            linha_salvo,
            texto="Excluir orçamento",
            nome_icone="trash-outline",
            command=self._excluir_orcamento,
            estilo="Delete.Compact.TButton",
            refs=self._icones_botoes,
        ).pack(side="left", padx=(0, 4))
        criar_botao_ttk_com_icone(
            linha_salvo,
            texto="Importar i9",
            nome_icone="attach-outline",
            command=self._importar_i9,
            estilo="Compact.TButton",
            refs=self._icones_botoes,
        ).pack(side="left", padx=(0, 12))

        frame_direita = tk.Frame(linha_salvo, bg="#ececec")
        frame_direita.pack(side="right")

        tk.Label(frame_direita, text="BDI (%):", bg="#ececec").pack(side="left")
        self.var_bdi = tk.StringVar(value=_formatar_bdi(BDI_PADRAO))
        self.var_bdi.trace_add("write", self._ao_alterar_bdi)
        ttk.Entry(frame_direita, textvariable=self.var_bdi, width=7).pack(
            side="left", padx=(4, 10)
        )

        tk.Label(frame_direita, text="Estado:", bg="#ececec").pack(side="left")
        estados = self.ctx.obter_estados()
        self.combo_estado = ttk.Combobox(
            frame_direita, values=valores_combo_estado(estados), width=12, state="readonly"
        )
        self.combo_estado.pack(side="left", padx=(4, 0))
        self.combo_estado.bind("<<ComboboxSelected>>", self._ao_mudar_estado)

        linha_acoes = tk.Frame(conteudo, bg="#ececec")
        linha_acoes.pack(fill="x", padx=4, pady=(0, 8))

        frame_etapas = tk.LabelFrame(
            linha_acoes,
            text="Etapas e itens",
            bg="#ececec",
            padx=8,
            pady=6,
        )
        frame_etapas.pack(side="left")

        linha_etapas_1 = tk.Frame(frame_etapas, bg="#ececec")
        linha_etapas_1.pack(fill="x", pady=(0, 4))
        criar_botao_ttk_com_icone(
            linha_etapas_1,
            texto="Nova etapa",
            nome_icone="add-circle-outline",
            command=self._novo_grupo,
            estilo="Add.Compact.TButton",
            refs=self._icones_botoes,
        ).pack(side="left", padx=(0, 4))

        linha_etapas_2 = tk.Frame(frame_etapas, bg="#ececec")
        linha_etapas_2.pack(fill="x")
        criar_botao_ttk_com_icone(
            linha_etapas_2,
            texto="Remover etapa/item",
            nome_icone="remove-circle-outline",
            command=self._remover_selecionado,
            estilo="Delete.Compact.TButton",
            refs=self._icones_botoes,
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            linha_etapas_2,
            text="Item ↑",
            command=lambda: self._mover_item(-1),
            style="Compact.TButton",
        ).pack(side="left", padx=(0, 4))
        ttk.Button(
            linha_etapas_2,
            text="Item ↓",
            command=lambda: self._mover_item(1),
            style="Compact.TButton",
        ).pack(side="left")

        frame_inserir = tk.LabelFrame(
            linha_acoes,
            text="Inserir itens",
            bg="#ececec",
            padx=8,
            pady=6,
        )
        frame_inserir.pack(side="left", padx=(12, 0))

        self.frame_area_reservada = tk.Frame(linha_acoes, bg="#ececec")
        self.frame_area_reservada.pack(side="left", fill="x", expand=True)

        linha_inserir_1 = tk.Frame(frame_inserir, bg="#ececec")
        linha_inserir_1.pack(fill="x", pady=(0, 4))
        criar_botao_inserir_prominente(
            linha_inserir_1,
            texto="Inserir item SINAPI",
            command=self._abrir_busca_sinapi,
            refs=self._icones_botoes,
        ).pack(side="left", padx=(0, 6))
        criar_botao_inserir_prominente(
            linha_inserir_1,
            texto="Inserir composição PRÓPRIA",
            command=self._adicionar_composicao_propria,
            refs=self._icones_botoes,
        ).pack(side="left")

        linha_inserir_2 = tk.Frame(frame_inserir, bg="#ececec")
        linha_inserir_2.pack(fill="x")
        tk.Label(linha_inserir_2, text="Rápido — Cód.:", bg="#ececec").pack(side="left")
        self.var_codigo_rapido = tk.StringVar()
        entrada_cod = ttk.Entry(linha_inserir_2, textvariable=self.var_codigo_rapido, width=10)
        entrada_cod.pack(side="left", padx=(4, 8))
        tk.Label(linha_inserir_2, text="Qtd.:", bg="#ececec").pack(side="left")
        self.var_qtd_rapido = tk.StringVar(value="1")
        entrada_qtd = ttk.Entry(linha_inserir_2, textvariable=self.var_qtd_rapido, width=8)
        entrada_qtd.pack(side="left", padx=(4, 8))
        ttk.Button(
            linha_inserir_2, text="Inserir", command=self._inserir_rapido, style="Compact.TButton"
        ).pack(side="left")
        entrada_cod.bind("<Return>", lambda _e: self._inserir_rapido())
        entrada_qtd.bind("<Return>", lambda _e: self._inserir_rapido())

        painel_grade = tk.LabelFrame(
            conteudo,
            text=(
                "Estrutura do orçamento  ·  Duplo clique: nº da etapa (reordenar), "
                "descrição da etapa (renomear), código/qtd. do item (editar)  ·  "
                "Ctrl/Shift+clique: seleção múltipla  ·  Delete: remover"
            ),
            bg="#ececec",
            padx=6,
            pady=6,
        )
        painel_grade.pack(fill="both", expand=True, padx=4, pady=(0, 6))

        self.grade = GradeOrcamento(
            painel_grade,
            on_duplo_clique_qtd=self._dialogo_editar_quantidade,
            on_duplo_clique_codigo=self._editar_item_sinapi,
            on_duplo_clique_descricao_grupo=self._renomear_grupo,
            on_duplo_clique_item_grupo=self._trocar_ordem_etapa,
            on_tecla_delete=lambda _e: self._remover_selecionado(silencioso=True),
        )
        self.grade.pack(fill="both", expand=True)

        for tecla in ("<Delete>", "<KP_Delete>"):
            self.bind(tecla, self._ao_tecla_delete_orcamento, add="+")
            painel_grade.bind(tecla, self._ao_tecla_delete_orcamento, add="+")

        rodape_orc = tk.Frame(
            conteudo, bg="#f5fafc", highlightbackground="#cccccc", highlightthickness=1
        )
        rodape_orc.pack(fill="x", padx=4, pady=(4, 0))

        linha_total = tk.Frame(rodape_orc, bg="#f5fafc")
        linha_total.pack(fill="x")

        container_total = tk.Frame(linha_total, bg="#f5fafc")
        container_total.pack(side="right", padx=10, pady=8)

        kwargs_botao_excel = {
            "text": "Gerar Planilha",
            "command": self._exportar_planilha,
            "font": ("Arial", 10, "bold"),
            "fg": "#000000",
            "activeforeground": "#000000",
            "bg": "#f5fafc",
            "activebackground": "#e8f0f3",
            "relief": "flat",
            "bd": 0,
            "padx": 2,
            "pady": 0,
            "cursor": "hand2",
            "highlightthickness": 0,
        }
        caminho_icone_excel = asset_path("icons", "excel-preto.png")
        if caminho_icone_excel is not None:
            self._icone_excel_export = tk.PhotoImage(file=str(caminho_icone_excel))
            kwargs_botao_excel["image"] = self._icone_excel_export
            kwargs_botao_excel["compound"] = "right"
        tk.Button(container_total, **kwargs_botao_excel).pack(side="left", padx=(0, 16))

        self.label_total = tk.Label(
            container_total,
            text="Total geral (c/ BDI): R$ 0,00",
            font=("Arial", 11, "bold"),
            fg="#006699",
            bg="#f5fafc",
            anchor="e",
        )
        self.label_total.pack(side="left")

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
        nome = perguntar_texto(
            self.winfo_toplevel(),
            "Adicionar orçamento",
            "Nome do novo orçamento:",
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
        nome = perguntar_texto(
            self.winfo_toplevel(),
            "Editar nome",
            "Novo nome do orçamento:",
            valor_inicial=self.orcamento.nome,
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

    def _importar_i9(self):
        def ao_importar(caminho):
            try:
                resultado = importar_planilha_i9(
                    caminho,
                    listar_composicoes_catalogo(),
                    self.ctx.sinapi,
                )
            except (OSError, ValueError) as exc:
                messagebox.showerror(
                    "Importar i9",
                    str(exc),
                    parent=self.winfo_toplevel(),
                )
                raise

            self._persistir_orcamento_atual()
            self._dados_arquivo = atualizar_orcamento_na_lista(
                self._dados_arquivo, resultado.orcamento
            )
            salvar_arquivo(self._dados_arquivo)
            self.orcamento = dict_para_orcamento(
                obter_orcamento_dict(self._dados_arquivo, resultado.orcamento.id)
            )
            self._atualizar_combo_orcamentos()
            self.combo_orcamento.set(
                self._rotulo_orcamento(self.orcamento.id, self.orcamento.nome)
            )
            self._aplicar_orcamento_na_interface()
            self._atualizar_grade()

            resumo = (
                f"Orçamento \"{self.orcamento.nome}\" importado com sucesso.\n"
                f"{resultado.grupos_importados} etapa(s) e "
                f"{resultado.itens_importados} item(ns) adicionados."
            )
            if resultado.avisos:
                avisos = "\n".join(f"• {aviso}" for aviso in resultado.avisos[:8])
                if len(resultado.avisos) > 8:
                    avisos += f"\n• ... e mais {len(resultado.avisos) - 8} aviso(s)."
                messagebox.showwarning(
                    "Importar i9",
                    f"{resumo}\n\nAvisos:\n{avisos}",
                    parent=self.winfo_toplevel(),
                )
            else:
                messagebox.showinfo(
                    "Importar i9",
                    resumo,
                    parent=self.winfo_toplevel(),
                )

        DialogoImportarI9(self.winfo_toplevel(), on_importar=ao_importar)

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
        return parse_decimal_br(texto)

    def _inserir_item_sinapi(
        self, grupo_id, codigo, descricao, unidade, custo, quantidade, estado, tipo_sinapi=""
    ):
        try:
            item_id = self.orcamento.adicionar_item_sinapi(
                grupo_id,
                codigo,
                descricao,
                unidade,
                custo,
                quantidade,
                estado,
                tipo_sinapi,
            )
        except ValueError as exc:
            messagebox.showwarning("Adicionar item", str(exc), parent=self.winfo_toplevel())
            return None
        self._atualizar_grade(
            focar_meta={
                "tipo": TIPO_SINAPI,
                "id": item_id,
                "grupo_id": grupo_id,
            }
        )
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

        def ao_confirmar(codigo, descricao, unidade, custo, quantidade, estado, tipo_sinapi=""):
            if estado and estado in self.ctx.obter_estados():
                self.combo_estado.set(estado)
            self._inserir_item_sinapi(
                grupo_id,
                codigo,
                descricao,
                unidade,
                custo,
                quantidade,
                estado,
                tipo_sinapi,
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
            str(linha.get("tipo", "")).strip().upper()[:1],
        )
        if item_id:
            self.var_codigo_rapido.set("")

    def _novo_grupo(self):
        from core.etapas_predefinidas import aplicar_etapa_no_orcamento
        from core.etapas_predefinidas_storage import listar as listar_etapas_predefinidas
        from core.etapas_predefinidas_storage import obter_por_id as obter_etapa_predefinida

        modelos = listar_etapas_predefinidas()
        catalogo = listar_composicoes_catalogo()

        def ao_confirmar(nome, etapa_id):
            avisos = []
            try:
                if etapa_id:
                    etapa = obter_etapa_predefinida(etapa_id)
                    if etapa is None:
                        messagebox.showwarning(
                            "Nova etapa",
                            "O modelo selecionado não foi encontrado.",
                            parent=self.winfo_toplevel(),
                        )
                        return False
                    estado = self._estado_selecionado()
                    grupo_id, avisos = aplicar_etapa_no_orcamento(
                        self.orcamento,
                        etapa,
                        self.ctx.sinapi,
                        estado,
                        catalogo,
                        nome_override=nome,
                    )
                    if estado:
                        self._sincronizar_precos_sinapi(estado)
                else:
                    grupo_id = self.orcamento.adicionar_grupo(nome)
            except ValueError as exc:
                messagebox.showwarning(
                    "Nova etapa", str(exc), parent=self.winfo_toplevel()
                )
                return False

            if avisos:
                messagebox.showwarning(
                    "Nova etapa",
                    "Etapa criada com avisos:\n\n" + "\n".join(avisos),
                    parent=self.winfo_toplevel(),
                )

            self._atualizar_grade(focar_meta={"tipo": TIPO_GRUPO, "id": grupo_id})
            return True

        DialogoNovaEtapa(self.winfo_toplevel(), modelos, ao_confirmar)

    def _adicionar_composicao_propria(self):
        grupo_id = self._grupo_id_selecionado()
        if not grupo_id:
            messagebox.showinfo(
                "Composição própria",
                "Selecione um grupo (etapa) na estrutura do orçamento.",
                parent=self.winfo_toplevel(),
            )
            return

        catalogo = listar_composicoes_catalogo()
        if not catalogo:
            messagebox.showinfo(
                "Composição própria",
                "Nenhuma composição cadastrada. Configure em "
                "\"Configurar Composições Próprias\" no Hub.",
                parent=self.winfo_toplevel(),
            )
            return

        def ao_confirmar(comp, quantidade):
            try:
                item_id = self.orcamento.adicionar_composicao_propria(
                    grupo_id,
                    comp["id"],
                    comp.get("codigo", ""),
                    comp.get("nome", ""),
                    comp.get("unidade", ""),
                    quantidade,
                )
            except ValueError as exc:
                messagebox.showwarning(
                    "Composição própria", str(exc), parent=self.winfo_toplevel()
                )
                return
            self._atualizar_grade(
                focar_meta={
                    "tipo": TIPO_COMPOSICAO_PROPRIA,
                    "id": item_id,
                    "grupo_id": grupo_id,
                }
            )

        DialogoBuscaComposicaoPropria(
            self.winfo_toplevel(),
            self.ctx,
            catalogo,
            self._estado_selecionado(),
            ao_confirmar,
        )

    def _renomear_grupo(self, grupo_id=None):
        if not grupo_id:
            meta = self._meta_selecionada()
            if not meta or meta["tipo"] != TIPO_GRUPO:
                messagebox.showinfo(
                    "Editar nome da etapa",
                    "Selecione uma etapa na estrutura do orçamento.",
                    parent=self.winfo_toplevel(),
                )
                return
            grupo_id = meta["id"]
        grupo = self.orcamento.obter_grupo(grupo_id)
        if grupo is None:
            return
        nome = perguntar_texto(
            self.winfo_toplevel(),
            "Editar nome da etapa",
            "Novo nome da etapa:",
            valor_inicial=grupo["nome"],
        )
        if not nome or not nome.strip():
            return
        try:
            self.orcamento.renomear_grupo(grupo_id, nome)
        except ValueError as exc:
            messagebox.showwarning("Etapa", str(exc), parent=self.winfo_toplevel())
            return
        self._atualizar_grade(focar_meta={"tipo": TIPO_GRUPO, "id": grupo_id})

    def _trocar_ordem_etapa(self, grupo_id=None):
        if not grupo_id:
            meta = self._meta_selecionada()
            if not meta or meta["tipo"] != TIPO_GRUPO:
                messagebox.showinfo(
                    "Trocar ordem da etapa",
                    "Selecione a linha da etapa (cabeçalho do grupo) para reordenar.",
                    parent=self.winfo_toplevel(),
                )
                return
            grupo_id = meta["id"]
        grupo = self.orcamento.obter_grupo(grupo_id)
        if grupo is None:
            return

        indice_atual = next(
            (i for i, g in enumerate(self.orcamento.grupos) if g["id"] == grupo_id),
            None,
        )
        if indice_atual is None:
            return

        posicao_atual = indice_atual + 1
        opcoes_posicao = [
            f"{idx} — {g['nome']}"
            for idx, g in enumerate(self.orcamento.grupos, start=1)
        ]

        def ao_confirmar(posicao):
            try:
                if not self.orcamento.mover_grupo_para_posicao(grupo_id, posicao):
                    return
            except ValueError as exc:
                messagebox.showwarning(
                    "Trocar ordem da etapa",
                    str(exc),
                    parent=self.winfo_toplevel(),
                )
                return
            self._atualizar_grade(focar_meta={"tipo": TIPO_GRUPO, "id": grupo_id})

        DialogoTrocarOrdemEtapa(
            self.winfo_toplevel(),
            grupo["nome"],
            posicao_atual,
            opcoes_posicao,
            ao_confirmar,
        )

    def _mover_item(self, delta):
        meta = self._meta_selecionada()
        if not meta or meta["tipo"] == TIPO_GRUPO:
            messagebox.showinfo(
                "Mover item",
                "Selecione um item para mover dentro da etapa.",
                parent=self.winfo_toplevel(),
            )
            return
        item_id = meta["id"]
        try:
            if not self.orcamento.mover_item(item_id, delta):
                return
        except ValueError as exc:
            messagebox.showwarning("Item", str(exc), parent=self.winfo_toplevel())
            return
        self._atualizar_grade(
            focar_meta={"tipo": meta["tipo"], "id": item_id, "grupo_id": meta.get("grupo_id")}
        )

    def _meta_selecionada(self):
        return self.grade.obter_meta_selecionada()

    _CLASSES_ENTRADA = frozenset({"TEntry", "Entry", "TCombobox", "Combobox"})

    def _foco_em_campo_edicao(self):
        atual = self.focus_get()
        while atual is not None:
            if atual.winfo_class() in self._CLASSES_ENTRADA:
                return True
            atual = atual.master
        return False

    def _ao_tecla_delete_orcamento(self, _event=None):
        if self._foco_em_campo_edicao():
            return
        self._remover_selecionado(silencioso=True)
        return "break"

    def _remover_selecionado(self, silencioso=False):
        metas = self.grade.obter_metas_selecionadas()
        if not metas:
            if not silencioso:
                messagebox.showinfo(
                    "Remover",
                    "Selecione um grupo ou item para remover.",
                    parent=self.winfo_toplevel(),
                )
            return

        grupos = [m for m in metas if m["tipo"] == TIPO_GRUPO]
        itens = [m for m in metas if m["tipo"] != TIPO_GRUPO]

        if grupos and itens:
            messagebox.showinfo(
                "Remover",
                "Selecione apenas etapas ou apenas itens para remover.",
                parent=self.winfo_toplevel(),
            )
            return

        if len(grupos) > 1:
            messagebox.showinfo(
                "Remover",
                "Remova uma etapa por vez.",
                parent=self.winfo_toplevel(),
            )
            return

        if len(grupos) == 1:
            if not messagebox.askyesno(
                "Remover grupo",
                "Remover a etapa e todos os seus itens?",
                parent=self.winfo_toplevel(),
            ):
                return
            self.orcamento.remover_grupo(grupos[0]["id"])
            self._atualizar_grade(focar_meta=[])
            return

        if len(itens) > 1:
            if not messagebox.askyesno(
                "Remover itens",
                f"Remover os {len(itens)} itens selecionados?",
                parent=self.winfo_toplevel(),
            ):
                return

        for meta in itens:
            self.orcamento.remover_item(meta["id"])

        self._atualizar_grade(focar_meta=[])

    def _dialogo_editar_quantidade(self, item_id):
        grupo, item = self.orcamento.obter_item(item_id)
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
            self._atualizar_grade(
                focar_meta={
                    "tipo": item["tipo"],
                    "id": item_id,
                    "grupo_id": grupo["id"] if grupo else None,
                }
            )

        DialogoEditarQuantidade(
            self.winfo_toplevel(),
            rotulo_item(item),
            item["quantidade"],
            ao_confirmar,
        )

    def _texto_item_para_substituicao(self, item):
        estado = self._estado_selecionado()
        catalogo = listar_composicoes_catalogo()
        if item["tipo"] == TIPO_SINAPI:
            tipo_rotulo = rotulo_tipo_sinapi(item, self.ctx.sinapi) or "—"
            estado_item = item.get("estado") or estado or "—"
            return (
                f"Código: {item['codigo']}  ·  {tipo_rotulo}  ·  Estado: {estado_item}  ·  "
                f"Unidade: {item['unidade']}  ·  Custo: {_formatar_moeda(item['custo_unitario'])}\n"
                f"{item['descricao']}"
            )
        if item["tipo"] == TIPO_COMPOSICAO_PROPRIA:
            custo_unit, _ = custo_composicao_propria_item(
                item, catalogo, self.ctx.sinapi, estado
            )
            codigo = item.get("codigo", "") or "—"
            custo_fmt = _formatar_moeda(custo_unit) if estado else "—"
            return (
                f"Composição própria  ·  Código: {codigo}  ·  "
                f"Unidade: {item.get('unidade', '')}  ·  Custo: {custo_fmt}\n"
                f"{item.get('nome', '')}"
            )
        return rotulo_item(item)

    def _editar_item_sinapi(self, meta=None):
        from_duplo_clique = meta is not None
        meta = meta or self._meta_selecionada()
        if not meta or meta["tipo"] == TIPO_GRUPO:
            messagebox.showinfo(
                "Editar item",
                "Selecione um item (SINAPI ou composição própria) para substituir.",
                parent=self.winfo_toplevel(),
            )
            return

        if not from_duplo_clique and len(self.grade.obter_metas_selecionadas()) > 1:
            messagebox.showinfo(
                "Editar item",
                "Selecione apenas um item para editar.",
                parent=self.winfo_toplevel(),
            )
            return

        item_id = meta["id"]
        _grupo, item = self.orcamento.obter_item(item_id)
        if item is None:
            return
        catalogo = listar_composicoes_catalogo()

        def ao_substituir_sinapi(codigo, descricao, unidade, custo, _quantidade, estado, tipo_sinapi=""):
            if estado and estado in self.ctx.obter_estados():
                self.combo_estado.set(estado)
            try:
                self.orcamento.substituir_item_sinapi(
                    item_id, codigo, descricao, unidade, custo, estado, tipo_sinapi
                )
            except ValueError as exc:
                messagebox.showwarning("Editar item", str(exc), parent=self.winfo_toplevel())
                return
            self._atualizar_grade(
                focar_meta={
                    "tipo": TIPO_SINAPI,
                    "id": item_id,
                    "grupo_id": meta.get("grupo_id"),
                }
            )

        def ao_substituir_propria(comp, _quantidade):
            try:
                self.orcamento.substituir_por_composicao_propria(
                    item_id,
                    comp["id"],
                    comp.get("codigo", ""),
                    comp.get("nome", ""),
                    comp.get("unidade", ""),
                )
            except ValueError as exc:
                messagebox.showwarning("Editar item", str(exc), parent=self.winfo_toplevel())
                return
            self._atualizar_grade(
                focar_meta={
                    "tipo": TIPO_COMPOSICAO_PROPRIA,
                    "id": item_id,
                    "grupo_id": meta.get("grupo_id"),
                }
            )

        DialogoBuscaSinapi(
            self.winfo_toplevel(),
            self.ctx,
            self._estado_selecionado(),
            ao_substituir_sinapi,
            titulo="Substituir item",
            mostrar_quantidade=False,
            texto_confirmar="Substituir item",
            fechar_unico=True,
            incluir_composicoes_proprias=bool(catalogo),
            catalogo_composicoes=catalogo,
            on_confirmar_propria=ao_substituir_propria,
            texto_item_substituindo=self._texto_item_para_substituicao(item),
        )

    def _exportar_planilha(self):
        if self.grade.tem_itens_depreciados():
            messagebox.showerror(
                "Gerar Planilha",
                "Há composições/insumos depreciados. Por favor, altere para um item atual.",
                parent=self.winfo_toplevel(),
            )
            return

        DialogoSelecionarModeloPlanilha(
            self.winfo_toplevel(),
            on_selecionar=self._ao_selecionar_modelo_planilha,
        )

    def _ao_selecionar_modelo_planilha(self, numero):
        referencia = self.ctx.sinapi_referencia_rotulo
        if referencia == "BASE AUSENTE":
            referencia = "Base não carregada"
        parent = self.winfo_toplevel()
        catalogo = listar_composicoes_catalogo()
        estado = self._estado_selecionado()
        sinapi = self.ctx.sinapi

        if numero in (1, 2, 3):
            exportar_orcamento_customizado_modelo_formatado(
                parent,
                numero,
                self.orcamento,
                catalogo,
                sinapi,
                estado,
                referencia,
            )
        elif numero == 4:
            exportar_orcamento_customizado_modelo4(
                parent,
                self.orcamento,
                catalogo,
                sinapi,
                estado,
                referencia,
            )
        else:
            return

        self._persistir_orcamento_atual()

    def _atualizar_grade(self, focar_meta=None):
        self._preencher_grade(focar_meta=focar_meta)

    def _selecoes_para_reconstrucao(self, focar_meta):
        if focar_meta is not None:
            if focar_meta == []:
                return []
            if isinstance(focar_meta, dict):
                return [focar_meta]
            return list(focar_meta)
        return self.grade.obter_metas_selecionadas()

    def _sincronizar_precos_sinapi(self, estado_atual):
        sincronizar_precos_sinapi_no_orcamento(
            self.orcamento, self.ctx.sinapi, estado_atual
        )

    def _subtotal_grupo_calculado(self, grupo, bdi, catalogo, estado):
        total = 0.0
        for item in grupo.get("itens", []):
            if item["tipo"] == TIPO_SINAPI:
                total += subtotal_item(item, bdi)
            elif item["tipo"] == TIPO_COMPOSICAO_PROPRIA:
                custo_unit, _ = custo_composicao_propria_item(
                    item, catalogo, self.ctx.sinapi, estado
                )
                sub = custo_unit * item["quantidade"]
                if bdi:
                    sub = custo_unitario_com_bdi(custo_unit, bdi) * item["quantidade"]
                total += sub
        return total

    def _total_geral_calculado(self, bdi, catalogo, estado):
        return sum(
            self._subtotal_grupo_calculado(g, bdi, catalogo, estado)
            for g in self.orcamento.grupos
        )

    def _preencher_grade(self, focar_meta=None):
        self.grade.iniciar_reconstrucao()
        fracao = self.grade.salvar_fracao_scroll()
        selecoes = self._selecoes_para_reconstrucao(focar_meta)
        self.grade.limpar()

        estado_atual = self._estado_selecionado()
        bdi = self._obter_bdi()
        catalogo = listar_composicoes_catalogo()
        self._sincronizar_precos_sinapi(estado_atual)

        for idx_grupo, grupo in enumerate(self.orcamento.grupos, start=1):
            sub_grupo = self._subtotal_grupo_calculado(grupo, bdi, catalogo, estado_atual)
            self.grade.adicionar_linha(
                meta={"tipo": TIPO_GRUPO, "id": grupo["id"]},
                valores={
                    "item": str(idx_grupo),
                    "codigo": "",
                    "tipo_ic": "",
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
                    custo_bdi = custo_unitario_com_bdi(custo, bdi)
                    total = subtotal_item(item, bdi)
                    indisponivel = item_indisponivel_na_base(
                        item, self.ctx.sinapi, catalogo, estado_atual
                    )
                    self.grade.adicionar_linha(
                        meta={
                            "tipo": TIPO_SINAPI,
                            "id": item["id"],
                            "grupo_id": grupo["id"],
                        },
                        valores={
                            "item": num_item,
                            "codigo": item["codigo"],
                            "tipo_ic": rotulo_tipo_sinapi(item, self.ctx.sinapi),
                            "descricao": item["descricao"],
                            "quantidade": _formatar_quantidade(item["quantidade"]),
                            "unidade": item["unidade"],
                            "custo_unit": _formatar_moeda(custo),
                            "custo_bdi": _formatar_moeda(custo_bdi),
                            "total": _formatar_moeda(total),
                        },
                        estilo="item",
                        alerta_depreciado=indisponivel,
                    )
                else:
                    custo_unit, tem_depreciado = custo_composicao_propria_item(
                        item, catalogo, self.ctx.sinapi, estado_atual
                    )
                    custo_bdi = custo_unitario_com_bdi(custo_unit, bdi)
                    total = custo_bdi * item["quantidade"]
                    self.grade.adicionar_linha(
                        meta={
                            "tipo": TIPO_COMPOSICAO_PROPRIA,
                            "id": item["id"],
                            "grupo_id": grupo["id"],
                        },
                        valores={
                            "item": num_item,
                            "codigo": item.get("codigo", ""),
                            "tipo_ic": "",
                            "descricao": item.get("nome", ""),
                            "quantidade": _formatar_quantidade(item["quantidade"]),
                            "unidade": item["unidade"],
                            "custo_unit": _formatar_moeda(custo_unit) if estado_atual else "—",
                            "custo_bdi": _formatar_moeda(custo_bdi) if estado_atual else "—",
                            "total": _formatar_moeda(total) if estado_atual else "—",
                        },
                        estilo="composicao",
                        alerta_depreciado=tem_depreciado,
                    )

        bdi_txt = _formatar_bdi(bdi)
        self.label_total.config(
            text=(
                f"Total geral (c/ BDI {bdi_txt}%): "
                f"{_formatar_moeda(self._total_geral_calculado(bdi, catalogo, estado_atual))}"
            )
        )
        self.grade.finalizar_reconstrucao(fracao, selecoes)
        self._persistir_orcamento_atual()

    def focar(self):
        pass
