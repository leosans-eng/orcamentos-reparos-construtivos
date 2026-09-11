import tkinter as tk
from copy import deepcopy
from tkinter import messagebox, ttk

from app_paths import asset_path
from core.composicoes_proprias import (
    custo_composicao_propria_item,
    filtrar_composicoes_catalogo,
    linhas_detalhe_composicao,
    obter_composicao_por_id,
)
from core.exportacao_planilha_orcamento import (
    exportar_orcamento_customizado_modelo4,
    exportar_orcamento_customizado_modelo_formatado,
)
from core.composicoes_proprias_storage import listar as listar_composicoes_catalogo
from core.orcamento_customizado import (
    BDI_PADRAO,
    TIPO_COMPOSICAO_PROPRIA,
    TIPO_GRUPO,
    TIPO_SINAPI,
    OrcamentoCustomizado,
    custo_unitario_com_bdi,
    item_indisponivel_na_base,
    item_usa_estado_alternativo,
    estado_efetivo_item,
    rotulo_item,
    rotulo_tipo_sinapi,
    sincronizar_precos_sinapi_no_orcamento,
    subtotal_item,
)
from core.orcamento_conversao import dict_para_orcamento
from core.orcamento_storage import (
    atualizar_orcamento_na_lista,
    invalidar_orcamento_cache,
    obter_cache_orcamento,
    obter_orcamento_dict,
    renomear_orcamento,
)
from core.sinapi_busca import (
    TIPO_COMPOSICAO,
    TIPO_INSUMO,
    TIPO_TODOS,
    VALORES_FILTRO_TIPO,
    deve_fixar_estado_sinapi,
    estados_com_codigo,
    nome_tipo_sinapi,
    obter_item_sinapi,
    obter_unidades_sinapi,
    pesquisar_sinapi,
    tipo_sinapi_para_filtro,
)
from ui.calculadora import abrir_calculadora
from ui.dialogo_previa_composicao import DialogoPreviaComposicao
from ui.dialogo_selecionar_modelo_planilha import DialogoSelecionarModeloPlanilha
from core.ui_prefs import definir_pref, obter_pref
from ui.temas import aplicar_chrome_dialogo, cores_grade, cores_tema, estilos_botao
from ui.grade_orcamento import GradeOrcamento
from ui.icones import (
    carregar_png_icone,
    criar_botao_inserir_prominente,
    criar_botao_ttk_com_icone,
    criar_botao_ttk_so_icone,
    criar_icone_svg,
    criar_label_icone,
    definir_estado_botao_icone,
)
from ui.recarga_catalogo import RecarregadorCatalogo
from ui.widgets import (
    PLACEHOLDER_ESTADO,
    CampoListaPesquisavel,
    ControleAtualizacaoPagina,
    aplicar_icone_janela,
    centralizar_janela,
    preparar_toplevel,
    criar_barra_modulo,
    criar_botao_cancelar,
    estado_do_combo,
    focar_entrada_apos_exibir,
    perguntar_texto,
    valores_combo_estado,
    formatar_decimal_br,
    formatar_moeda_br,
    formatar_quantidade_edicao,
    parse_quantidade_expressao,
    vincular_tooltip,
)

DEBOUNCE_BUSCA_MS = 250
UNIDADE_TODAS = "Todas"
HISTORICO_MAX = 40
DESCRICAO_BDI = "BDI alterado"
COR_ALERTA_VAZIO = "#ffe082"
INTERVALO_ALERTA_VAZIO_MS = 550


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
        aplicar_chrome_dialogo(self)
        self.on_confirmar = on_confirmar
        self.title("Editar quantidade")
        aplicar_icone_janela(self)
        self.configure(bg=self._cores.fundo)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        largura_wrap = min(560, max(280, parent.winfo_screenwidth() - 120))

        painel = tk.Frame(self, bg=self._cores.fundo, padx=16, pady=14)
        painel.pack(fill="both", expand=True)

        tk.Label(
            painel,
            text="Item:",
            font=("Arial", 9, "bold"),
            fg=self._cores.texto,
            bg=self._cores.fundo,
            anchor="w",
        ).pack(fill="x")

        tk.Label(
            painel,
            text=descricao_item,
            font=("Arial", 9),
            fg=self._cores.texto,
            bg=self._cores.fundo_destaque,
            justify="left",
            anchor="w",
            wraplength=largura_wrap,
            padx=8,
            pady=8,
        ).pack(fill="x", pady=(4, 12))

        linha_qtd = tk.Frame(painel, bg=self._cores.fundo)
        linha_qtd.pack(fill="x", pady=(0, 4))
        tk.Label(linha_qtd, text="Nova quantidade:", bg=self._cores.fundo, fg=self._cores.texto).pack(side="left")
        self.var_quantidade = tk.StringVar(
            value=formatar_quantidade_edicao(quantidade_atual)
        )
        entrada = ttk.Entry(linha_qtd, textvariable=self.var_quantidade, width=18)
        entrada.pack(side="left", padx=(8, 0))
        self._entrada_quantidade = entrada
        entrada.bind("<Return>", lambda _e: self._confirmar())
        entrada.bind("<Escape>", lambda _e: self.destroy())

        tk.Label(
            painel,
            text="É possível usar expressões como 12,5*15  ou  2+3*4",
            font=("Arial", 8),
            fg=self._cores.texto_suave,
            bg=self._cores.fundo,
            anchor="w",
        ).pack(fill="x", pady=(0, 10))

        botoes = ttk.Frame(painel)
        botoes.pack(fill="x")
        criar_botao_cancelar(botoes, self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(botoes, text="OK", command=self._confirmar, style=self._estilos.adicionar).pack(
            side="right"
        )

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        centralizar_janela(self, parent)
        focar_entrada_apos_exibir(entrada, selecionar=True)

    def _confirmar(self):
        self.on_confirmar(self.var_quantidade.get())
        self.destroy()


class DialogoEstadoItemSinapi(tk.Toplevel):
    """Escolhe a UF de preço de um item sem alterar o estado do orçamento."""

    def __init__(
        self,
        parent,
        descricao_item,
        codigo,
        estados_disponiveis,
        estado_atual,
        estado_orcamento,
        on_confirmar,
    ):
        super().__init__(parent)
        preparar_toplevel(self)
        aplicar_chrome_dialogo(self)
        self.on_confirmar = on_confirmar
        self.estados_disponiveis = list(estados_disponiveis)
        self.estado_orcamento = str(estado_orcamento or "").strip()
        self.title("Estado do item (UF)")
        aplicar_icone_janela(self)
        self.configure(bg=self._cores.fundo)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        largura_wrap = min(560, max(280, parent.winfo_screenwidth() - 120))
        painel = tk.Frame(self, bg=self._cores.fundo, padx=16, pady=14)
        painel.pack(fill="both", expand=True)

        tk.Label(
            painel,
            text=f"Código {codigo}",
            font=("Arial", 9, "bold"),
            fg=self._cores.texto,
            bg=self._cores.fundo,
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            painel,
            text=descricao_item,
            font=("Arial", 9),
            fg=self._cores.texto,
            bg=self._cores.fundo_destaque,
            justify="left",
            anchor="w",
            wraplength=largura_wrap,
            padx=8,
            pady=8,
        ).pack(fill="x", pady=(4, 8))

        msg_orc = (
            f"Estado do orçamento: {self.estado_orcamento}."
            if self.estado_orcamento
            else "Orçamento sem estado de referência."
        )
        tk.Label(
            painel,
            text=(
                f"{msg_orc}\n"
                "Altere apenas a UF deste item para usar o preço de outro estado "
                "(ex.: item existente só na SINAPI SP)."
            ),
            bg=self._cores.fundo,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(0, 10))

        linha = tk.Frame(painel, bg=self._cores.fundo)
        linha.pack(fill="x", pady=(0, 12))
        tk.Label(linha, text="UF do item:", bg=self._cores.fundo, fg=self._cores.texto).pack(side="left")
        self.combo_estado = ttk.Combobox(
            linha,
            values=self.estados_disponiveis,
            width=8,
            state="readonly",
        )
        self.combo_estado.pack(side="left", padx=(8, 0))
        estado_inicial = str(estado_atual or "").strip()
        if estado_inicial in self.estados_disponiveis:
            self.combo_estado.set(estado_inicial)
        elif self.estado_orcamento in self.estados_disponiveis:
            self.combo_estado.set(self.estado_orcamento)
        elif "SP" in self.estados_disponiveis:
            self.combo_estado.set("SP")
        elif self.estados_disponiveis:
            self.combo_estado.set(self.estados_disponiveis[0])

        botoes = ttk.Frame(painel)
        botoes.pack(fill="x")
        criar_botao_cancelar(botoes, self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(
            botoes, text="Aplicar", command=self._confirmar, style=self._estilos.adicionar
        ).pack(side="right")

        self.bind("<Return>", lambda _e: self._confirmar())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        centralizar_janela(self, parent)
        self.combo_estado.focus_set()

    def _confirmar(self):
        estado = str(self.combo_estado.get() or "").strip()
        if not estado:
            messagebox.showwarning(
                "Estado do item",
                "Selecione um estado.",
                parent=self,
            )
            return
        self.on_confirmar(estado)
        self.destroy()


class DialogoTrocarOrdemEtapa(tk.Toplevel):
    def __init__(self, parent, nome_etapa, posicao_atual, opcoes_posicao, on_confirmar):
        super().__init__(parent)
        preparar_toplevel(self)
        aplicar_chrome_dialogo(self)
        self.on_confirmar = on_confirmar
        self.title("Trocar ordem da etapa")
        aplicar_icone_janela(self)
        self.configure(bg=self._cores.fundo)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        painel = tk.Frame(self, bg=self._cores.fundo, padx=16, pady=14)
        painel.pack(fill="both", expand=True)

        tk.Label(
            painel,
            text="Etapa selecionada:",
            font=("Arial", 9, "bold"),
            fg=self._cores.texto,
            bg=self._cores.fundo,
            anchor="w",
        ).pack(fill="x")

        tk.Label(
            painel,
            text=f"{posicao_atual} — {nome_etapa}",
            font=("Arial", 9),
            fg=self._cores.texto,
            bg=self._cores.fundo_destaque,
            anchor="w",
            padx=8,
            pady=8,
        ).pack(fill="x", pady=(4, 12))

        linha_pos = tk.Frame(painel, bg=self._cores.fundo)
        linha_pos.pack(fill="x", pady=(0, 12))
        tk.Label(linha_pos, text="Nova posição:", bg=self._cores.fundo, fg=self._cores.texto).pack(side="left")

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

        botoes = ttk.Frame(painel)
        botoes.pack(fill="x")
        criar_botao_cancelar(botoes, self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(botoes, text="Confirmar", command=self._confirmar, style=self._estilos.adicionar).pack(
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
        aplicar_chrome_dialogo(self)
        self.on_confirmar = on_confirmar
        self._modelos_por_nome = {m["nome"]: m for m in modelos}
        self._opcoes_modelo = [ETAPA_EM_BRANCO] + [m["nome"] for m in modelos]
        self.title("Nova etapa")
        aplicar_icone_janela(self)
        self.configure(bg=self._cores.fundo)
        self.transient(parent)
        self.grab_set()
        self.resizable(True, False)
        self.minsize(480, 0)

        painel = tk.Frame(self, bg=self._cores.fundo, padx=20, pady=16)
        painel.pack(fill="x")

        tk.Label(
            painel,
            text="Nome da etapa:",
            bg=self._cores.fundo,
            fg=self._cores.texto,
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self.var_nome = tk.StringVar()
        self.entrada_nome = ttk.Entry(painel, textvariable=self.var_nome, width=52)
        self.entrada_nome.pack(fill="x", pady=(0, 14))

        tk.Label(
            painel,
            text="Modelo (opcional) — digite para filtrar:",
            bg=self._cores.fundo,
            fg=self._cores.texto,
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self.var_modelo = tk.StringVar(value=ETAPA_EM_BRANCO)
        self.campo_modelo = CampoListaPesquisavel(
            painel,
            textvariable=self.var_modelo,
            on_escolher=self._ao_escolher_modelo,
            altura_lista=8,
            largura_minima_lista=280,
            bg=self._cores.fundo,
        )
        self.campo_modelo.definir_opcoes(self._opcoes_modelo)
        self.campo_modelo.pack(fill="x", pady=(0, 10))

        botoes = ttk.Frame(painel)
        botoes.pack(fill="x")
        criar_botao_cancelar(botoes, self._fechar).pack(side="right", padx=(6, 0))
        ttk.Button(botoes, text="Criar", command=self._confirmar, style=self._estilos.adicionar).pack(
            side="right"
        )

        self.bind("<Escape>", lambda _e: self._fechar())
        self.bind("<Return>", lambda _e: self._confirmar())
        self.protocol("WM_DELETE_WINDOW", self._fechar)
        self.update_idletasks()
        centralizar_janela(self, parent)
        focar_entrada_apos_exibir(self.entrada_nome)

    def _ao_escolher_modelo(self, valor: str):
        if valor and valor != ETAPA_EM_BRANCO:
            self.var_nome.set(valor)
        self._focar_nome_etapa()

    def _focar_nome_etapa(self):
        def aplicar():
            try:
                self.lift()
                self.grab_set()
                self.entrada_nome.focus_force()
                self.entrada_nome.selection_range(0, "end")
                self.entrada_nome.icursor("end")
            except tk.TclError:
                pass

        self.after_idle(aplicar)
        self.after(50, aplicar)

    def _fechar(self):
        self.campo_modelo.fechar_lista()
        self.destroy()

    def _resolver_modelo(self, texto: str):
        texto = (texto or "").strip()
        if not texto or texto == ETAPA_EM_BRANCO:
            return None
        texto_fold = texto.casefold()
        for nome, etapa in self._modelos_por_nome.items():
            if nome.casefold() == texto_fold:
                return etapa
        comeca = [
            (nome, etapa)
            for nome, etapa in self._modelos_por_nome.items()
            if nome.casefold().startswith(texto_fold)
        ]
        if len(comeca) == 1:
            return comeca[0][1]
        contem = [
            (nome, etapa)
            for nome, etapa in self._modelos_por_nome.items()
            if texto_fold in nome.casefold()
        ]
        if len(contem) == 1:
            return contem[0][1]
        if comeca:
            return comeca[0][1]
        if contem:
            return contem[0][1]
        return None

    def _confirmar(self):
        nome = self.var_nome.get().strip()
        if not nome:
            messagebox.showwarning(
                "Nova etapa",
                "Informe o nome da etapa.",
                parent=self,
            )
            return

        modelo_digitado = self.var_modelo.get().strip()
        etapa_id = None
        if modelo_digitado and modelo_digitado != ETAPA_EM_BRANCO:
            etapa = self._resolver_modelo(modelo_digitado)
            if etapa is None:
                messagebox.showwarning(
                    "Nova etapa",
                    f"Nenhum modelo encontrado para '{modelo_digitado}'.\n"
                    "Digite mais letras, escolha um item da lista ou use "
                    f'"{ETAPA_EM_BRANCO}".',
                    parent=self,
                )
                return
            etapa_id = etapa["id"]
            self.var_modelo.set(etapa["nome"])

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
        texto_confirmar="Inserir na etapa",
        texto_confirmar_fechar="Inserir e fechar",
        fechar_unico=False,
        incluir_composicoes_proprias=False,
        catalogo_composicoes=None,
        on_confirmar_propria=None,
        texto_item_substituindo=None,
    ):
        super().__init__(parent)
        preparar_toplevel(self)
        aplicar_chrome_dialogo(self)
        self.ctx = ctx
        self.on_confirmar = on_confirmar
        self.on_confirmar_propria = on_confirmar_propria
        self.incluir_composicoes_proprias = incluir_composicoes_proprias
        self.catalogo_composicoes = list(catalogo_composicoes or [])
        self.texto_item_substituindo = (texto_item_substituindo or "").strip() or None
        self.label_item_substituindo = None
        self._job_busca = None
        self._refs_icones = []
        self.mostrar_quantidade = mostrar_quantidade
        self.texto_confirmar = texto_confirmar
        self.texto_confirmar_fechar = texto_confirmar_fechar
        self.fechar_unico = fechar_unico
        self._ultima_largura_wrap = 0

        self.title(titulo)
        self.geometry("1100x700")
        self.minsize(700, 480)
        aplicar_icone_janela(self)
        self.configure(bg=self._cores.fundo)
        self.transient(parent)
        self.grab_set()

        self._montar(estado_inicial)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        centralizar_janela(self, parent)
        focar_entrada_apos_exibir(self.entrada_busca)

    def _montar(self, estado_inicial):
        painel = tk.Frame(self, bg=self._cores.fundo, padx=12, pady=10)
        painel.pack(fill="both", expand=True)

        linha_filtros = tk.Frame(painel, bg=self._cores.fundo)
        linha_filtros.pack(fill="x", pady=(0, 6))

        tk.Label(linha_filtros, text="Estado:", bg=self._cores.fundo, fg=self._cores.texto).grid(
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

        tk.Label(linha_filtros, text="Unidade:", bg=self._cores.fundo, fg=self._cores.texto).grid(
            row=0, column=2, padx=(14, 4), pady=3, sticky="w"
        )
        self.combo_unidade = ttk.Combobox(
            linha_filtros, values=[UNIDADE_TODAS], width=10, state="readonly"
        )
        self.combo_unidade.grid(row=0, column=3, padx=4, pady=3, sticky="w")
        self.combo_unidade.set(UNIDADE_TODAS)

        tk.Label(linha_filtros, text="Tipo (I/C):", bg=self._cores.fundo).grid(
            row=0, column=4, padx=(14, 4), pady=3, sticky="w"
        )
        self.combo_tipo = ttk.Combobox(
            linha_filtros, values=list(VALORES_FILTRO_TIPO), width=12, state="readonly"
        )
        self.combo_tipo.grid(row=0, column=5, padx=4, pady=3, sticky="w")
        self.combo_tipo.set(TIPO_TODOS)

        criar_label_icone(
            linha_filtros,
            "funnel-outline",
            texto="Filtrar:",
            bg=self._cores.fundo,
            fg=self._cores.texto_suave,
            cor=self._cores.titulo,
            refs=self._refs_icones,
        ).grid(row=1, column=0, padx=(0, 4), pady=3, sticky="w")
        self.var_busca = tk.StringVar()
        self.entrada_busca = ttk.Entry(linha_filtros, textvariable=self.var_busca, width=36)
        self.entrada_busca.grid(row=1, column=1, padx=4, pady=3, sticky="ew")

        if self.mostrar_quantidade:
            tk.Label(linha_filtros, text="Quantidade:", bg=self._cores.fundo, fg=self._cores.texto).grid(
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
            fg=self._cores.texto_suave,
            bg=self._cores.fundo,
            anchor="w",
        )
        self.label_status.pack(fill="x", pady=(0, 4))

        painel_resultados = tk.LabelFrame(
            painel, text="Resultados", bg=self._cores.fundo, fg=self._cores.texto_suave, padx=6, pady=4
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
                painel, text="Item a substituir", bg=self._cores.fundo, fg=self._cores.texto_suave, padx=6, pady=4
            )
            painel_atual.pack(fill="x", pady=(0, 6))
            frame_atual = tk.Frame(
                painel_atual,
                bg=self._cores.fundo_destaque,
                highlightbackground=self._cores.borda_suave,
                highlightthickness=1,
            )
            frame_atual.pack(fill="x")
            self.label_item_substituindo = tk.Label(
                frame_atual,
                text=self.texto_item_substituindo,
                font=("Arial", 9),
                fg=self._cores.texto,
                bg=self._cores.fundo_destaque,
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
            painel, text=titulo_detalhe, bg=self._cores.fundo, fg=self._cores.texto_suave, padx=6, pady=4
        )
        painel_detalhe.pack(fill="x", pady=(0, 8))

        texto_detalhe_inicial = (
            "Selecione o novo item na lista para comparar."
            if self.texto_item_substituindo
            else "Selecione um item na lista para ver os detalhes."
        )
        frame_detalhe = tk.Frame(
            painel_detalhe,
            bg=self._cores.fundo_destaque,
            highlightbackground=self._cores.borda_suave,
            highlightthickness=1,
        )
        frame_detalhe.pack(fill="x")

        self.label_detalhe = tk.Label(
            frame_detalhe,
            text=texto_detalhe_inicial,
            font=("Arial", 9),
            fg=self._cores.texto,
            bg=self._cores.fundo_destaque,
            justify="left",
            anchor="w",
            padx=10,
            pady=8,
        )
        self.label_detalhe.pack(fill="x")

        rodape = tk.Frame(painel, bg=self._cores.fundo)
        rodape.pack(fill="x")

        botoes_acao = tk.Frame(rodape, bg=self._cores.fundo)
        botoes_acao.pack(side="right")
        criar_botao_cancelar(botoes_acao, self.destroy).pack(side="right")
        if self.fechar_unico:
            criar_botao_ttk_com_icone(
                botoes_acao,
                texto=self.texto_confirmar,
                nome_icone="add-circle-outline",
                command=lambda: self._confirmar(fechar=True),
                estilo=self._estilos.adicionar,
                cor_icone=self._estilos.icone_adicionar,
                refs=self._refs_icones,
            ).pack(side="right", padx=(0, 8))
        else:
            criar_botao_ttk_com_icone(
                botoes_acao,
                texto=self.texto_confirmar_fechar,
                nome_icone="save-outline",
                command=lambda: self._confirmar(fechar=True),
                estilo=self._estilos.salvar,
                cor_icone=self._estilos.icone_salvar,
                refs=self._refs_icones,
            ).pack(side="right", padx=(0, 8))
            criar_botao_ttk_com_icone(
                botoes_acao,
                texto=self.texto_confirmar,
                nome_icone="add-circle-outline",
                command=lambda: self._confirmar(fechar=False),
                estilo=self._estilos.adicionar,
                cor_icone=self._estilos.icone_adicionar,
                refs=self._refs_icones,
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
            self.label_status.config(text="Base SINAPI indisponível.", fg=self._cores.perigo)

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
            self.label_status.config(text="Selecione um estado.", fg=self._cores.perigo)
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
        self.label_status.config(
            text=mensagem,
            fg=self._cor_status(mensagem, vazio=not self.tree.get_children()),
        )

    def _cor_status(self, mensagem, *, vazio=False):
        cores = self._cores
        texto = (mensagem or "").lower()
        if "indisponível" in texto or "nenhum item" in texto or "nenhum insumo" in texto:
            return cores.perigo
        if vazio:
            return "#ffb74d" if cores.escuro else "#a67c00"
        return cores.texto_suave

    def _tipo_selecionado_sinapi(self):
        selecao = self.combo_tipo.get().strip()
        if selecao == TIPO_COMPOSICAO and self.incluir_composicoes_proprias:
            return "C"
        return tipo_sinapi_para_filtro(selecao)

    def _parse_quantidade(self, texto):
        return parse_quantidade_expressao(texto)

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
        aplicar_chrome_dialogo(self)
        self.ctx = ctx
        self.catalogo = catalogo
        self.on_confirmar = on_confirmar
        self.mostrar_quantidade = mostrar_quantidade
        self.texto_confirmar = texto_confirmar
        self._ultima_largura_wrap = 0
        self._refs_icones = []

        self.title(titulo)
        self.geometry("900x620")
        self.minsize(640, 420)
        aplicar_icone_janela(self)
        self.configure(bg=self._cores.fundo)
        self.transient(parent)
        self.grab_set()

        self._montar(estado_inicial)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        centralizar_janela(self, parent)
        focar_entrada_apos_exibir(self.entrada_busca)

    def _montar(self, estado_inicial):
        painel = tk.Frame(self, bg=self._cores.fundo, padx=12, pady=10)
        painel.pack(fill="both", expand=True)

        linha_filtros = tk.Frame(painel, bg=self._cores.fundo)
        linha_filtros.pack(fill="x", pady=(0, 6))

        tk.Label(linha_filtros, text="Estado:", bg=self._cores.fundo, fg=self._cores.texto).grid(
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

        criar_label_icone(
            linha_filtros,
            "funnel-outline",
            texto="Filtrar:",
            bg=self._cores.fundo,
            fg=self._cores.texto_suave,
            cor=self._cores.titulo,
            refs=self._refs_icones,
        ).grid(row=1, column=0, padx=(0, 4), pady=3, sticky="w")
        self.var_busca = tk.StringVar()
        self.var_busca.trace_add("write", lambda *_a: self._atualizar_lista())
        self.entrada_busca = ttk.Entry(linha_filtros, textvariable=self.var_busca, width=36)
        self.entrada_busca.grid(row=1, column=1, padx=4, pady=3, sticky="ew")

        if self.mostrar_quantidade:
            tk.Label(linha_filtros, text="Quantidade:", bg=self._cores.fundo, fg=self._cores.texto).grid(
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
            painel, text="Composições cadastradas", bg=self._cores.fundo, fg=self._cores.texto_suave, padx=6, pady=4
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
            painel, bg=self._cores.fundo_destaque, highlightbackground=self._cores.borda_suave, highlightthickness=1
        )
        painel_detalhe.pack(fill="x", pady=(0, 8))

        self.label_detalhe = tk.Label(
            painel_detalhe,
            text="Selecione uma composição na lista para ver os detalhes.",
            font=("Arial", 9),
            fg=self._cores.texto,
            bg=self._cores.fundo_destaque,
            justify="left",
            anchor="w",
            padx=10,
            pady=8,
        )
        self.label_detalhe.pack(fill="x")

        rodape = tk.Frame(painel, bg=self._cores.fundo)
        rodape.pack(fill="x")
        botoes_acao = tk.Frame(rodape, bg=self._cores.fundo)
        botoes_acao.pack(side="right")
        criar_botao_cancelar(botoes_acao, self.destroy).pack(side="right")
        criar_botao_ttk_com_icone(
            botoes_acao,
            texto=self.texto_confirmar,
            nome_icone="add-circle-outline",
            command=self._confirmar,
            estilo=self._estilos.adicionar,
            cor_icone=self._estilos.icone_adicionar,
            refs=self._refs_icones,
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
        return parse_quantidade_expressao(texto)

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
    def __init__(self, parent, ctx, on_voltar, *, orcamento_id=None):
        cores = cores_tema(parent)
        super().__init__(parent, bg=cores.fundo)
        self._cores = cores
        self._estilos = estilos_botao(self)
        self._cg = cores_grade(self)
        self.ctx = ctx
        self.on_voltar = on_voltar
        self._orcamento_id = orcamento_id
        self._trocando_orcamento = False
        self._orcamento_sujo = False
        self._aplicando_historico = False
        self._historico_undo = []
        self._historico_redo = []
        self._snapshot_base = None
        self._binds_historico = []
        self._icone_excel_export = None
        self._icones_botoes = []
        self._alerta_vazio_job = None
        self._alerta_vazio_aceso = False
        self._alerta_precisa_etapa = False
        self._alerta_precisa_estado = False
        self.orcamento = self._carregar_orcamento_por_id(orcamento_id)
        self._recarregador = RecarregadorCatalogo(
            self,
            obter_cache=lambda: obter_cache_orcamento(self.orcamento.id),
            carregar_rede=lambda: obter_orcamento_dict(self.orcamento.id, forcar_rede=True),
            ao_aplicar=self._aplicar_orcamento_recarregado,
            ao_erro=self._ao_erro_recarga_orcamento,
            ao_inicio=self._ao_inicio_carregamento,
            ao_fim=self._ao_fim_carregamento,
        )
        self._montar()
        ctx.registrar_callback_sinapi(self._ao_atualizar_sinapi)

    def destroy(self):
        self._parar_alerta_orcamento_vazio()
        self._desvincular_atalhos_historico()
        super().destroy()

    def _sincronizar_alertas_iniciais(self):
        self._alerta_precisa_etapa = not bool(getattr(self.orcamento, "grupos", None))
        self._alerta_precisa_estado = not bool(self._estado_selecionado())
        if self._alerta_precisa_etapa or self._alerta_precisa_estado:
            self._iniciar_alerta_orcamento_vazio()
            self._aplicar_alerta_orcamento_vazio(self._alerta_vazio_aceso)
            return
        self._parar_alerta_orcamento_vazio()

    def _iniciar_alerta_orcamento_vazio(self):
        if self._alerta_vazio_job is not None:
            return
        self._garantir_estilo_alerta_vazio()
        self._alerta_vazio_aceso = False
        self._pulsar_alerta_orcamento_vazio()

    def _parar_alerta_orcamento_vazio(self):
        job = self._alerta_vazio_job
        self._alerta_vazio_job = None
        self._alerta_vazio_aceso = False
        self._alerta_precisa_etapa = False
        self._alerta_precisa_estado = False
        if job is not None:
            try:
                self.after_cancel(job)
            except (tk.TclError, ValueError):
                pass
        self._aplicar_alerta_orcamento_vazio(False)

    def _pulsar_alerta_orcamento_vazio(self):
        self._alerta_vazio_job = None
        self._alerta_vazio_aceso = not self._alerta_vazio_aceso
        self._aplicar_alerta_orcamento_vazio(self._alerta_vazio_aceso)
        try:
            self._alerta_vazio_job = self.after(
                INTERVALO_ALERTA_VAZIO_MS, self._pulsar_alerta_orcamento_vazio
            )
        except tk.TclError:
            self._alerta_vazio_job = None

    def _garantir_estilo_alerta_vazio(self):
        """Estilo de pulso com o mesmo padding do botão compacto (não muda o tamanho)."""
        raiz = self.winfo_toplevel()
        tema = getattr(raiz, "_orc_tema_atual", None)
        estilo_base = self._estilos.compacto_adicionar
        estilo_alerta = f"AlertaVazio.{estilo_base}"
        chave = (tema, estilo_base, bool(self._cores.escuro))
        if getattr(raiz, "_orc_alerta_vazio_chave", None) == chave:
            self._estilo_alerta_nova_etapa = estilo_alerta
            return
        style = ttk.Style(self)
        padding = style.lookup(estilo_base, "padding") or (4, 1)
        cor_texto = COR_ALERTA_VAZIO if self._cores.escuro else "#1a1a1a"
        style.configure(
            estilo_alerta,
            padding=padding,
            foreground=cor_texto,
            background=COR_ALERTA_VAZIO,
            focuscolor="none",
        )
        style.map(
            estilo_alerta,
            foreground=[("active", cor_texto), ("pressed", cor_texto)],
            background=[
                ("disabled", "#e0e0e0"),
                ("active", "#ffd54f"),
                ("pressed", "#f9a825"),
            ],
        )
        style.configure(
            "AlertaVazio.TCombobox",
            fieldbackground=COR_ALERTA_VAZIO,
            background=COR_ALERTA_VAZIO,
        )
        style.map(
            "AlertaVazio.TCombobox",
            fieldbackground=[
                ("readonly", COR_ALERTA_VAZIO),
                ("disabled", COR_ALERTA_VAZIO),
            ],
            background=[("readonly", COR_ALERTA_VAZIO)],
        )
        raiz._orc_alerta_vazio_chave = chave
        self._estilo_alerta_nova_etapa = estilo_alerta

    def _aplicar_alerta_orcamento_vazio(self, aceso: bool):
        etapa_acesa = aceso and self._alerta_precisa_etapa
        estado_aceso = aceso and self._alerta_precisa_estado
        self._pintar_halo(getattr(self, "_halo_nova_etapa", None), etapa_acesa)
        self._pintar_halo(getattr(self, "_halo_estado", None), estado_aceso)
        botao = getattr(self, "btn_nova_etapa", None)
        if botao is not None:
            estilo_alerta = getattr(
                self, "_estilo_alerta_nova_etapa", f"AlertaVazio.{self._estilos.compacto_adicionar}"
            )
            try:
                botao.configure(
                    style=estilo_alerta if etapa_acesa else self._estilos.compacto_adicionar
                )
            except tk.TclError:
                pass
        combo = getattr(self, "combo_estado", None)
        if combo is not None:
            try:
                combo.configure(
                    style="AlertaVazio.TCombobox" if estado_aceso else "TCombobox"
                )
            except tk.TclError:
                pass

    def _criar_halo(self, parent, *, padx=3, pady=2):
        """Moldura com folga igual nos quatro lados para o pulso amarelo."""
        return tk.Frame(parent, bg=self._cores.fundo, padx=padx, pady=pady)

    def _pintar_halo(self, halo, aceso: bool):
        if halo is None:
            return
        try:
            halo.configure(bg=COR_ALERTA_VAZIO if aceso else self._cores.fundo)
        except tk.TclError:
            pass

    def _montar_botao_recarregar_cabecalho(self, parent):
        self._controle_atualizacao = ControleAtualizacaoPagina(
            parent,
            command=self.recarregar_orcamento,
            refs=self._icones_botoes,
        )

    def _ao_erro_recarga_orcamento(self, mensagem: str, avisar_erro: bool):
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

    def _aplicar_orcamento_recarregado(self, registro: dict):
        self._orcamento_sujo = False
        self.orcamento = dict_para_orcamento(registro)
        self._aplicar_orcamento_na_interface()
        self._atualizar_grade()
        self._reiniciar_historico()

    def recarregar_orcamento(self, *, forcar_rede: bool = True):
        if self._orcamento_sujo and forcar_rede:
            if not messagebox.askyesno(
                "Atualizar orçamento",
                "Há alterações não salvas. Recarregar do servidor e descartá-las?",
                parent=self.winfo_toplevel(),
            ):
                return
        self._recarregador.solicitar(forcar_rede=forcar_rede, avisar_erro=True)

    def _montar(self):
        self.label_referencia = criar_barra_modulo(
            self,
            "Orçamento Customizado",
            self._voltar_para_selecao,
            texto_referencia=self._texto_referencia(),
            montar_acoes_apos_titulo=self._montar_botao_recarregar_cabecalho,
            montar_acoes_antes_referencia=self._montar_botao_calculadora_cabecalho,
        )

        conteudo = tk.Frame(self, bg=self._cores.fundo)
        conteudo.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        linha_cabecalho = tk.Frame(conteudo, bg=self._cores.fundo)
        linha_cabecalho.pack(fill="x", padx=4, pady=(0, 8))

        self.label_nome_orcamento = tk.Label(
            linha_cabecalho,
            text="",
            bg=self._cores.fundo,
            fg=self._cores.titulo,
            font=("Arial", 11, "bold"),
            anchor="w",
        )
        self.label_nome_orcamento.pack(side="left")
        btn_renomear = criar_botao_ttk_so_icone(
            linha_cabecalho,
            nome_icone="pencil",
            command=self._renomear_orcamento,
            estilo=self._estilos.compacto_editar,
            cor_icone=self._estilos.icone_editar,
            refs=self._icones_botoes,
        )
        btn_renomear.pack(side="left", padx=(8, 0))
        vincular_tooltip(btn_renomear, "Editar nome")

        self.var_mostrar_legenda = tk.BooleanVar(
            value=bool(obter_pref("legenda_grade_orcamento", True))
        )
        chk_legenda = ttk.Checkbutton(
            linha_cabecalho,
            text="Legenda",
            variable=self.var_mostrar_legenda,
            command=self._ao_alternar_legenda,
            style="Cartao.TCheckbutton",
        )
        chk_legenda.pack(side="right")
        vincular_tooltip(chk_legenda, "Mostrar ou ocultar a legenda de cores da grade")

        linha_acoes = tk.Frame(conteudo, bg=self._cores.fundo)
        linha_acoes.pack(fill="x", padx=4, pady=(0, 8))

        frame_etapas = tk.LabelFrame(
            linha_acoes,
            text="Etapas e itens",
            bg=self._cores.fundo,
            fg=self._cores.texto,
            padx=8,
            pady=6,
        )
        frame_etapas.pack(side="left", anchor="n")

        linha_etapas_1 = tk.Frame(frame_etapas, bg=self._cores.fundo)
        linha_etapas_1.pack(fill="x", pady=(0, 4))
        self._halo_nova_etapa = self._criar_halo(linha_etapas_1)
        self._halo_nova_etapa.pack(side="left", padx=(0, 4))
        self.btn_nova_etapa = criar_botao_ttk_com_icone(
            self._halo_nova_etapa,
            texto="Nova etapa",
            nome_icone="add-circle-outline",
            command=self._novo_grupo,
            estilo=self._estilos.compacto_adicionar,
            cor_icone=self._estilos.icone_adicionar,
            refs=self._icones_botoes,
        )
        self.btn_nova_etapa.pack()

        linha_etapas_2 = tk.Frame(frame_etapas, bg=self._cores.fundo)
        linha_etapas_2.pack(fill="x")
        alinhador_remover = self._criar_halo(linha_etapas_2)
        alinhador_remover.pack(side="left", padx=(0, 4))
        criar_botao_ttk_com_icone(
            alinhador_remover,
            texto="Remover etapa/item",
            nome_icone="remove-circle-outline",
            command=self._remover_selecionado,
            estilo=self._estilos.compacto_excluir,
            cor_icone=self._estilos.icone_excluir,
            refs=self._icones_botoes,
        ).pack()
        alinhador_uf = self._criar_halo(linha_etapas_2)
        alinhador_uf.pack(side="left")
        ttk.Button(
            alinhador_uf,
            text="Estado do item (UF)",
            command=self._alterar_estado_item,
            style=self._estilos.compacto,
        ).pack()

        frame_inserir = tk.LabelFrame(
            linha_acoes,
            text="Inserir itens",
            bg=self._cores.fundo,
            fg=self._cores.texto,
            padx=8,
            pady=6,
        )
        frame_inserir.pack(side="left", padx=(12, 0), anchor="n")

        linha_inserir_1 = tk.Frame(frame_inserir, bg=self._cores.fundo)
        linha_inserir_1.pack(fill="x", pady=(0, 4))
        criar_botao_inserir_prominente(
            linha_inserir_1,
            texto="Inserir item SINAPI",
            command=self._abrir_busca_sinapi,
            refs=self._icones_botoes,
        ).pack(side="left", padx=(0, 6))
        criar_botao_inserir_prominente(
            linha_inserir_1,
            texto="Inserir composição própria",
            command=self._adicionar_composicao_propria,
            refs=self._icones_botoes,
        ).pack(side="left")

        linha_inserir_2 = tk.Frame(frame_inserir, bg=self._cores.fundo)
        linha_inserir_2.pack(fill="x")
        tk.Label(linha_inserir_2, text="Rápido — Cód.:", bg=self._cores.fundo, fg=self._cores.texto).pack(side="left")
        self.var_codigo_rapido = tk.StringVar()
        entrada_cod = ttk.Entry(linha_inserir_2, textvariable=self.var_codigo_rapido, width=10)
        entrada_cod.pack(side="left", padx=(4, 8))
        tk.Label(linha_inserir_2, text="Qtd.:", bg=self._cores.fundo, fg=self._cores.texto).pack(side="left")
        self.var_qtd_rapido = tk.StringVar(value="1")
        entrada_qtd = ttk.Entry(linha_inserir_2, textvariable=self.var_qtd_rapido, width=10)
        entrada_qtd.pack(side="left", padx=(4, 8))
        ttk.Button(
            linha_inserir_2, text="Inserir", command=self._inserir_rapido, style=self._estilos.compacto
        ).pack(side="left")
        entrada_cod.bind("<Return>", lambda _e: self._inserir_rapido())
        entrada_qtd.bind("<Return>", lambda _e: self._inserir_rapido())

        frame_dados = tk.LabelFrame(
            linha_acoes,
            text="Dados do orçamento",
            bg=self._cores.fundo,
            fg=self._cores.texto,
            padx=8,
            pady=6,
        )
        frame_dados.pack(side="left", padx=(12, 0), anchor="n")

        linha_dados = tk.Frame(frame_dados, bg=self._cores.fundo)
        linha_dados.pack(fill="x", pady=(0, 4))
        tk.Label(linha_dados, text="BDI (%):", bg=self._cores.fundo, fg=self._cores.texto).pack(side="left")
        self.var_bdi = tk.StringVar(value=_formatar_bdi(BDI_PADRAO))
        self.var_bdi.trace_add("write", self._ao_alterar_bdi)
        ttk.Entry(linha_dados, textvariable=self.var_bdi, width=7).pack(
            side="left", padx=(4, 10)
        )

        tk.Label(linha_dados, text="Estado:", bg=self._cores.fundo, fg=self._cores.texto).pack(side="left")
        estados = self.ctx.obter_estados()
        self._halo_estado = self._criar_halo(linha_dados)
        self._halo_estado.pack(side="left", padx=(4, 0))
        self.combo_estado = ttk.Combobox(
            self._halo_estado,
            values=valores_combo_estado(estados),
            width=12,
            state="readonly",
        )
        self.combo_estado.pack()
        self.combo_estado.bind("<<ComboboxSelected>>", self._ao_mudar_estado)

        # Espaçador para igualar a altura dos painéis de duas linhas à esquerda.
        tk.Frame(frame_dados, bg=self._cores.fundo, height=1).pack(fill="x")

        self.frame_area_reservada = tk.Frame(linha_acoes, bg=self._cores.fundo)
        self.frame_area_reservada.pack(side="left", fill="x", expand=True)

        titulo_grade = tk.Frame(conteudo, bg=self._cores.fundo)
        tk.Label(
            titulo_grade,
            text="Estrutura do orçamento",
            bg=self._cores.fundo,
            fg=self._cores.texto,
            font=("Arial", 9, "bold"),
        ).pack(side="left")
        btn_ajuda = tk.Label(
            titulo_grade,
            text="?",
            bg=self._cores.fundo_destaque,
            fg=self._cores.titulo,
            font=("Arial", 9, "bold"),
            width=2,
            cursor="hand2",
            relief="solid",
            bd=1,
        )
        btn_ajuda.pack(side="left", padx=(6, 0))
        vincular_tooltip(
            btn_ajuda,
            "Ctrl+F: filtrar por código ou descrição\n"
            "Arraste pelo nº (ou ⠿ na etapa) para reordenar\n"
            "Duplo clique: nome da etapa, código ou quantidade\n"
            "Lupa na composição própria: ver itens cadastrados\n"
            "Botão direito: menu do item\n"
            "Ctrl/Shift+clique: seleção múltipla\n"
            "Delete: remover",
        )

        painel_grade = tk.LabelFrame(
            conteudo,
            labelwidget=titulo_grade,
            bg=self._cores.fundo,
            fg=self._cores.texto_suave,
            padx=6,
            pady=6,
        )
        painel_grade.pack(fill="both", expand=True, padx=4, pady=(0, 6))

        self._barra_filtro_grade = tk.Frame(painel_grade, bg=self._cores.fundo)
        criar_label_icone(
            self._barra_filtro_grade,
            "funnel-outline",
            texto="Filtrar:",
            bg=self._cores.fundo,
            fg=self._cores.texto_suave,
            cor=self._cores.titulo,
            refs=self._icones_botoes,
        ).pack(side="left", padx=(0, 4))
        self.var_filtro_grade = tk.StringVar()
        self.var_filtro_grade.trace_add("write", self._ao_filtrar_grade)
        self._entrada_filtro_grade = ttk.Entry(
            self._barra_filtro_grade, textvariable=self.var_filtro_grade, width=28
        )
        self._entrada_filtro_grade.pack(side="left", padx=(0, 8))
        tk.Label(
            self._barra_filtro_grade,
            text="código ou descrição  ·  Esc",
            bg=self._cores.fundo,
            fg=self._cores.texto_suave,
            font=("Arial", 8),
        ).pack(side="left")
        btn_fechar_filtro = tk.Label(
            self._barra_filtro_grade,
            text="✕",
            bg=self._cores.fundo,
            fg=self._cores.texto_suave,
            font=("Arial", 9),
            cursor="hand2",
            padx=2,
            pady=0,
        )
        btn_fechar_filtro.pack(side="left", padx=(4, 0))
        btn_fechar_filtro.bind("<Button-1>", lambda _e: self._ocultar_filtro_grade())
        btn_fechar_filtro.bind(
            "<Enter>", lambda _e: btn_fechar_filtro.configure(fg=self._cores.texto)
        )
        btn_fechar_filtro.bind(
            "<Leave>", lambda _e: btn_fechar_filtro.configure(fg=self._cores.texto_suave)
        )
        vincular_tooltip(btn_fechar_filtro, "Fechar filtro (Esc)")
        self._entrada_filtro_grade.bind("<Escape>", self._ocultar_filtro_grade)

        self._banner_depreciados = tk.Frame(
            painel_grade,
            bg=self._cg.banner,
            highlightbackground=self._cg.banner_borda,
            highlightthickness=1,
        )
        tk.Label(
            self._banner_depreciados,
            text=(
                "Há itens depreciados ou indisponíveis na base atual. "
                "Substitua-os (duplo clique no código) antes de gerar a planilha."
            ),
            bg=self._cg.banner,
            fg=self._cg.banner_texto,
            font=("Arial", 9),
            anchor="w",
            justify="left",
            padx=8,
            pady=6,
        ).pack(fill="x")

        self.grade = GradeOrcamento(
            painel_grade,
            on_duplo_clique_qtd=self._dialogo_editar_quantidade,
            on_duplo_clique_codigo=self._editar_item_sinapi,
            on_duplo_clique_item_grupo=self._trocar_ordem_etapa,
            on_salvar_nome_grupo=self._salvar_nome_grupo_inline,
            on_tecla_delete=lambda _e: self._remover_selecionado(silencioso=True),
            on_reordenar_item=self._ao_reordenar_item_arraste,
            on_reordenar_etapa=self._ao_reordenar_etapa_arraste,
            on_menu_contexto=self._ao_menu_contexto_grade,
            on_previa_composicao=self._abrir_previa_composicao,
        )
        self.grade.pack(fill="both", expand=True)

        self._montar_legenda_grade(painel_grade)

        for tecla in ("<Delete>", "<KP_Delete>"):
            self.bind(tecla, self._ao_tecla_delete_orcamento, add="+")
            painel_grade.bind(tecla, self._ao_tecla_delete_orcamento, add="+")

        bg_barra = self._cores.fundo_barra
        rodape_orc = tk.Frame(
            conteudo, bg=bg_barra, highlightbackground=self._cores.borda_suave, highlightthickness=1
        )
        rodape_orc.pack(fill="x", padx=4, pady=(4, 0))

        linha_total = tk.Frame(rodape_orc, bg=bg_barra)
        linha_total.pack(fill="x")

        container_historico = tk.Frame(linha_total, bg=bg_barra)
        container_historico.pack(side="left", padx=10, pady=6)

        self.btn_desfazer = criar_botao_ttk_so_icone(
            container_historico,
            nome_icone="caret-back-outline",
            command=self._desfazer,
            cor_icone=self._estilos.icone,
            refs=self._icones_botoes,
        )
        self.btn_desfazer.pack(side="left", padx=(0, 4))
        vincular_tooltip(self.btn_desfazer, "Desfazer (Ctrl+Z)")
        definir_estado_botao_icone(self.btn_desfazer, "disabled")

        self.btn_refazer = criar_botao_ttk_so_icone(
            container_historico,
            nome_icone="caret-forward-outline",
            command=self._refazer,
            cor_icone=self._estilos.icone,
            refs=self._icones_botoes,
        )
        self.btn_refazer.pack(side="left", padx=(0, 10))
        vincular_tooltip(self.btn_refazer, "Refazer (Ctrl+Y)")
        definir_estado_botao_icone(self.btn_refazer, "disabled")

        self.label_ultima_acao = tk.Label(
            container_historico,
            text="",
            font=("Arial", 9),
            fg=self._cores.texto_suave,
            bg=bg_barra,
            anchor="w",
        )
        self.label_ultima_acao.pack(side="left")

        container_total = tk.Frame(linha_total, bg=bg_barra)
        container_total.pack(side="right", padx=10, pady=8)

        cores = self._cores
        kwargs_botao_excel = {
            "text": "Gerar Planilha",
            "command": self._exportar_planilha,
            "font": ("Arial", 10, "bold"),
            "fg": cores.texto if cores.escuro else "#000000",
            "activeforeground": cores.texto if cores.escuro else "#000000",
            "bg": bg_barra,
            "activebackground": cores.fundo_hover,
            "relief": "flat",
            "bd": 0,
            "padx": 2,
            "pady": 0,
            "cursor": "hand2",
            "highlightthickness": 0,
        }
        caminho_icone_excel = asset_path("icons", "excel-preto.png")
        if caminho_icone_excel is not None:
            try:
                self._icone_excel_export = carregar_png_icone(
                    self, "excel-preto.png", inverter=bool(cores.escuro)
                )
                kwargs_botao_excel["image"] = self._icone_excel_export
                kwargs_botao_excel["compound"] = "right"
            except (FileNotFoundError, OSError, tk.TclError):
                pass
        tk.Button(container_total, **kwargs_botao_excel).pack(side="left", padx=(0, 16))

        self.label_total = tk.Label(
            container_total,
            text="Total geral (c/ BDI): R$ 0,00",
            font=("Arial", 11, "bold"),
            fg=self._cores.titulo,
            bg=bg_barra,
            anchor="e",
        )
        self.label_total.pack(side="left")

        self._aplicar_orcamento_na_interface()
        self._atualizar_grade()
        self._reiniciar_historico()
        self._vincular_atalhos_historico()

    def definir_orcamento(self, orcamento_id):
        if orcamento_id and orcamento_id != getattr(self.orcamento, "id", None):
            if self._orcamento_sujo:
                if not self._persistir_orcamento_atual():
                    return
        self._orcamento_id = orcamento_id
        self._orcamento_sujo = False
        self.orcamento = self._carregar_orcamento_por_id(orcamento_id)
        self._aplicar_orcamento_na_interface()
        self._atualizar_grade()
        self._reiniciar_historico()

    def _voltar_para_selecao(self):
        if self._orcamento_sujo:
            if not self._persistir_orcamento_atual():
                return
        self.on_voltar()

    def _carregar_orcamento_por_id(self, orcamento_id):
        registro = obter_orcamento_dict(orcamento_id)
        if registro is None:
            raise ValueError(f"Orçamento não encontrado: {orcamento_id}")
        return dict_para_orcamento(registro)

    def _atualizar_rotulo_nome(self):
        nome = self.orcamento.nome or "Sem nome"
        self.label_nome_orcamento.config(text=nome)

    def _aplicar_orcamento_na_interface(self):
        self._trocando_orcamento = True
        try:
            self._atualizar_rotulo_nome()
            estado = self.orcamento.estado_referencia
            if estado and estado in self.ctx.obter_estados():
                self.combo_estado.set(estado)
            else:
                self.combo_estado.set(PLACEHOLDER_ESTADO)
            self.var_bdi.set(_formatar_bdi(self.orcamento.bdi_percent))
        finally:
            self._trocando_orcamento = False

    def _persistir_orcamento_atual(self):
        if not self._orcamento_sujo:
            return True
        estado = self._estado_selecionado()
        self.orcamento.definir_estado_referencia(estado)
        try:
            self.orcamento.definir_bdi(self._parse_bdi(self.var_bdi.get()))
        except ValueError:
            pass
        try:
            atualizar_orcamento_na_lista(self.orcamento)
            self._orcamento_sujo = False
            return True
        except ValueError as exc:
            self._tratar_erro_salvamento(exc)
            return False

    def _tratar_erro_salvamento(self, exc: ValueError):
        mensagem = str(exc)
        messagebox.showwarning("Orçamento", mensagem, parent=self.winfo_toplevel())
        if "Recarregue" in mensagem:
            self._recarregar_do_servidor()

    def _recarregar_do_servidor(self):
        invalidar_orcamento_cache(self.orcamento.id)
        self._orcamento_sujo = False
        self.orcamento = self._carregar_orcamento_por_id(self.orcamento.id)
        self._aplicar_orcamento_na_interface()
        self._atualizar_grade()
        self._reiniciar_historico()

    def _capturar_snapshot(self):
        return {
            "grupos": deepcopy(self.orcamento.grupos),
            "bdi_percent": float(self.orcamento.bdi_percent),
            "estado_referencia": str(self.orcamento.estado_referencia or ""),
        }

    def _reiniciar_historico(self):
        self._historico_undo.clear()
        self._historico_redo.clear()
        self._snapshot_base = self._capturar_snapshot()
        self._definir_feedback_acao("")
        self._atualizar_botoes_historico()

    def _definir_feedback_acao(self, texto):
        if not hasattr(self, "label_ultima_acao"):
            return
        texto = str(texto or "").strip()
        self.label_ultima_acao.config(
            text=f"Última ação: {texto}" if texto else ""
        )

    def _atualizar_botoes_historico(self):
        if not hasattr(self, "btn_desfazer"):
            return
        definir_estado_botao_icone(
            self.btn_desfazer, "normal" if self._historico_undo else "disabled"
        )
        definir_estado_botao_icone(
            self.btn_refazer, "normal" if self._historico_redo else "disabled"
        )

    def _empilhar_historico(self, antes, depois, descricao):
        if (
            self._historico_undo
            and descricao == DESCRICAO_BDI
            and self._historico_undo[-1]["descricao"] == DESCRICAO_BDI
        ):
            self._historico_undo[-1]["depois"] = depois
        else:
            self._historico_undo.append(
                {"antes": antes, "depois": depois, "descricao": descricao}
            )
            if len(self._historico_undo) > HISTORICO_MAX:
                del self._historico_undo[0 : len(self._historico_undo) - HISTORICO_MAX]
        self._historico_redo.clear()
        self._atualizar_botoes_historico()

    def _aplicar_snapshot_historico(self, snap, feedback):
        self._aplicando_historico = True
        try:
            self.orcamento.grupos = deepcopy(snap["grupos"])
            self.orcamento.bdi_percent = float(snap["bdi_percent"])
            self.orcamento.estado_referencia = str(snap.get("estado_referencia") or "")
            self._aplicar_orcamento_na_interface()
            self._orcamento_sujo = True
            self._preencher_grade()
            self._snapshot_base = self._capturar_snapshot()
            self._definir_feedback_acao(feedback)
            self._atualizar_botoes_historico()
            self._persistir_orcamento_atual()
        finally:
            self._aplicando_historico = False

    def _desfazer(self):
        if not self._historico_undo or self._aplicando_historico:
            return
        entrada = self._historico_undo.pop()
        self._historico_redo.append(entrada)
        self._aplicar_snapshot_historico(
            entrada["antes"], f"Desfeita — {entrada['descricao']}"
        )

    def _refazer(self):
        if not self._historico_redo or self._aplicando_historico:
            return
        entrada = self._historico_redo.pop()
        self._historico_undo.append(entrada)
        self._aplicar_snapshot_historico(
            entrada["depois"], f"Refeita — {entrada['descricao']}"
        )

    def _widget_pertence_ao_editor(self, widget):
        atual = widget
        while atual is not None:
            if atual is self:
                return True
            try:
                atual = atual.master
            except (tk.TclError, AttributeError):
                return False
        return False

    def _ao_tecla_desfazer(self, event):
        if not self._widget_pertence_ao_editor(event.widget):
            return
        if self._foco_em_campo_edicao():
            return
        self._desfazer()
        return "break"

    def _ao_tecla_refazer(self, event):
        if not self._widget_pertence_ao_editor(event.widget):
            return
        if self._foco_em_campo_edicao():
            return
        self._refazer()
        return "break"

    def _vincular_atalhos_historico(self):
        self._desvincular_atalhos_historico()
        top = self.winfo_toplevel()
        pares = (
            ("<Control-z>", self._ao_tecla_desfazer),
            ("<Control-Z>", self._ao_tecla_desfazer),
            ("<Control-y>", self._ao_tecla_refazer),
            ("<Control-Y>", self._ao_tecla_refazer),
            ("<Control-Shift-z>", self._ao_tecla_refazer),
            ("<Control-Shift-Z>", self._ao_tecla_refazer),
            ("<Control-f>", self._ao_tecla_filtro_grade),
            ("<Control-F>", self._ao_tecla_filtro_grade),
        )
        for sequencia, callback in pares:
            func_id = top.bind(sequencia, callback, add="+")
            self._binds_historico.append((top, sequencia, func_id))

    def _desvincular_atalhos_historico(self):
        for widget, sequencia, func_id in self._binds_historico:
            try:
                widget.unbind(sequencia, func_id)
            except tk.TclError:
                pass
        self._binds_historico.clear()

    def _registrar_alteracao(self, focar_meta=None, *, descricao="Alteração"):
        antes = self._snapshot_base
        self._orcamento_sujo = True
        self._preencher_grade(focar_meta)
        depois = self._capturar_snapshot()
        if antes is not None and not self._aplicando_historico:
            self._empilhar_historico(antes, depois, descricao)
            self._definir_feedback_acao(descricao)
        self._snapshot_base = depois
        self._persistir_orcamento_atual()

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
            registro = renomear_orcamento(self.orcamento.id, nome)
            self.orcamento.definir_nome(nome)
            self.orcamento.versao = int(registro.get("versao", getattr(self.orcamento, "versao", 1)))
            self._atualizar_rotulo_nome()
        except ValueError as exc:
            mensagem = str(exc)
            messagebox.showwarning("Orçamento", mensagem, parent=self.winfo_toplevel())
            if "Recarregue" in mensagem:
                self._recarregar_do_servidor()

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
        if self._trocando_orcamento or self._aplicando_historico:
            return
        try:
            bdi = self._parse_bdi(self.var_bdi.get())
        except ValueError:
            return
        self.orcamento.definir_bdi(bdi)
        self._registrar_alteracao(descricao=DESCRICAO_BDI)

    def _ao_mudar_estado(self, _event=None):
        if self._trocando_orcamento or self._aplicando_historico:
            return
        self.orcamento.definir_estado_referencia(self._estado_selecionado())
        self._sincronizar_alertas_iniciais()
        self._registrar_alteracao(descricao="Estado do orçamento alterado")

    def _abrir_calculadora(self):
        abrir_calculadora(self.winfo_toplevel())

    def _montar_botao_calculadora_cabecalho(self, parent):
        self._montar_botao_calculadora(parent, side="right")

    def _montar_botao_calculadora(self, parent, *, side="left"):
        """Botão flat só com ícone — mesmo visual de Gerar Planilha / Abrir SINAPI."""
        kwargs = {
            "command": self._abrir_calculadora,
            "bg": self._cores.fundo,
            "activebackground": self._cores.fundo_hover,
            "relief": "flat",
            "bd": 0,
            "padx": 4,
            "pady": 0,
            "cursor": "hand2",
            "highlightthickness": 0,
        }
        try:
            icone = criar_icone_svg(
                parent, "calculator-outline", altura=20, cor=self._cores.titulo
            )
            self._icones_botoes.append(icone)
            kwargs["image"] = icone
        except (ImportError, FileNotFoundError, tk.TclError, OSError):
            kwargs["text"] = "Calc"
            kwargs["font"] = ("Arial", 9)
            kwargs["fg"] = self._cores.titulo
            kwargs["activeforeground"] = self._cores.titulo
        botao = tk.Button(parent, **kwargs)
        botao.pack(side=side, padx=(0, 10))
        vincular_tooltip(botao, "Abrir Calculadora")

    def _montar_legenda_grade(self, parent):
        self._frame_legenda = tk.Frame(parent, bg=self._cores.fundo)
        self._conteudo_legenda = tk.Frame(self._frame_legenda, bg=self._cores.fundo)
        tk.Label(
            self._conteudo_legenda,
            text="Legenda:",
            bg=self._cores.fundo,
            fg=self._cores.texto_suave,
            font=("Arial", 8, "bold"),
        ).pack(side="left", padx=(0, 8))
        cg = self._cg
        for cor, texto in (
            (cg.grupo, "Etapa"),
            (cg.alerta_depreciado, "Depreciado / indisponível"),
            (cg.estado_alternativo, "UF alternativa"),
            (cg.composicao, "Composição própria"),
            (cg.discriminar, "Discriminar no Excel/Word"),
        ):
            amostra = tk.Frame(
                self._conteudo_legenda,
                bg=cor,
                width=12,
                height=12,
                highlightbackground=self._cores.borda_suave,
                highlightthickness=1,
            )
            amostra.pack(side="left", padx=(0, 4))
            amostra.pack_propagate(False)
            tk.Label(
                self._conteudo_legenda,
                text=texto,
                bg=self._cores.fundo,
                fg=self._cores.texto_suave,
                font=("Arial", 8),
            ).pack(side="left", padx=(0, 12))
        self._conteudo_legenda.pack(side="left", fill="x", expand=True)
        self._aplicar_visibilidade_legenda()

    def _ao_alternar_legenda(self):
        definir_pref("legenda_grade_orcamento", bool(self.var_mostrar_legenda.get()))
        self._aplicar_visibilidade_legenda()

    def _aplicar_visibilidade_legenda(self):
        frame = getattr(self, "_frame_legenda", None)
        if frame is None:
            return
        if self.var_mostrar_legenda.get():
            if not frame.winfo_ismapped():
                frame.pack(fill="x", pady=(6, 0))
        else:
            try:
                frame.pack_forget()
            except tk.TclError:
                pass

    def _ao_tecla_filtro_grade(self, event):
        if not self.winfo_ismapped():
            return
        try:
            if event.widget.winfo_toplevel() is not self.winfo_toplevel():
                return
        except tk.TclError:
            return
        return self._mostrar_filtro_grade(event)

    def _mostrar_filtro_grade(self, _event=None):
        barra = getattr(self, "_barra_filtro_grade", None)
        entrada = getattr(self, "_entrada_filtro_grade", None)
        if barra is None or entrada is None:
            return "break"
        if not barra.winfo_ismapped():
            barra.pack(fill="x", pady=(0, 6), before=self.grade)
        entrada.focus_set()
        entrada.selection_range(0, "end")
        return "break"

    def _ocultar_filtro_grade(self, _event=None):
        barra = getattr(self, "_barra_filtro_grade", None)
        if barra is not None:
            try:
                barra.pack_forget()
            except tk.TclError:
                pass
        if hasattr(self, "var_filtro_grade"):
            self.var_filtro_grade.set("")
        if hasattr(self, "grade"):
            self.grade.aplicar_filtro("")
            self.grade.focus_set()
        return "break"

    def _ao_filtrar_grade(self, *_args):
        if hasattr(self, "grade"):
            self.grade.aplicar_filtro(self.var_filtro_grade.get())

    def _ao_menu_contexto_grade(self, meta, event):
        menu = tk.Menu(self, tearoff=0)
        eh_etapa = meta.get("tipo") == TIPO_GRUPO
        if eh_etapa:
            menu.add_command(
                label="Remover etapa",
                command=lambda: self._remover_selecionado(silencioso=False),
            )
        else:
            if meta.get("tipo") == TIPO_COMPOSICAO_PROPRIA:
                menu.add_command(
                    label="Ver composição",
                    command=lambda m=dict(meta): self._abrir_previa_composicao(m),
                )
                menu.add_separator()
            menu.add_command(
                label="Substituir item",
                command=lambda m=dict(meta): self._editar_item_sinapi(m),
            )
            menu.add_command(
                label="Alterar UF",
                command=self._alterar_estado_item,
            )
            menu.add_command(
                label="Editar quantidade",
                command=lambda: self._dialogo_editar_quantidade(meta.get("id")),
            )
            menu.add_separator()
            menu.add_command(
                label="Remover",
                command=lambda: self._remover_selecionado(silencioso=False),
            )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _abrir_previa_composicao(self, meta=None):
        meta = meta or self._meta_selecionada()
        if not meta or meta.get("tipo") != TIPO_COMPOSICAO_PROPRIA:
            return
        item_id = meta.get("id")
        grupo, item = self.orcamento.obter_item(item_id)
        if item is None:
            return
        catalogo = listar_composicoes_catalogo()
        composicao = obter_composicao_por_id(
            catalogo, item.get("composicao_catalogo_id")
        )
        estado = self._estado_selecionado()
        estado_calc = estado_efetivo_item(item, estado, self.ctx.sinapi)
        linhas = linhas_detalhe_composicao(
            composicao,
            self.ctx.sinapi,
            estado_calc,
            item.get("quantidade", 0),
        )
        custo_unit, _ = custo_composicao_propria_item(
            item, catalogo, self.ctx.sinapi, estado
        )
        try:
            quantidade = float(item.get("quantidade") or 0)
        except (TypeError, ValueError):
            quantidade = 0.0
        total = custo_unit * quantidade

        def ao_alterar_discriminar(iid, valor):
            try:
                self.orcamento.definir_discriminar_componentes(iid, valor)
            except ValueError as exc:
                messagebox.showwarning(
                    "Composição própria",
                    str(exc),
                    parent=self.winfo_toplevel(),
                )
                return
            self._registrar_alteracao(
                focar_meta={
                    "tipo": TIPO_COMPOSICAO_PROPRIA,
                    "id": iid,
                    "grupo_id": grupo["id"] if grupo else meta.get("grupo_id"),
                },
                descricao="Discriminação da composição alterada",
            )

        DialogoPreviaComposicao(
            self.winfo_toplevel(),
            item=item,
            composicao=composicao,
            estado=estado_calc,
            linhas=linhas,
            custo_unitario=custo_unit,
            total=total,
            on_alterar_discriminar=ao_alterar_discriminar,
        )

    def _atualizar_banner_depreciados(self):
        banner = getattr(self, "_banner_depreciados", None)
        if banner is None:
            return
        if self.grade.tem_itens_depreciados():
            if not banner.winfo_ismapped():
                banner.pack(fill="x", pady=(0, 6), before=self.grade)
        else:
            try:
                banner.pack_forget()
            except tk.TclError:
                pass

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
        if not self._aplicando_historico:
            self._snapshot_base = self._capturar_snapshot()

    def _grupo_id_selecionado(self):
        return self.grade.obter_grupo_id_selecionado()

    def _parse_quantidade(self, texto):
        return parse_quantidade_expressao(texto)

    def _inserir_item_sinapi(
        self,
        grupo_id,
        codigo,
        descricao,
        unidade,
        custo,
        quantidade,
        estado,
        tipo_sinapi="",
        *,
        estado_fixado=False,
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
                estado_fixado=estado_fixado,
            )
        except ValueError as exc:
            messagebox.showwarning("Adicionar item", str(exc), parent=self.winfo_toplevel())
            return None
        self._registrar_alteracao(
            focar_meta={
                "tipo": TIPO_SINAPI,
                "id": item_id,
                "grupo_id": grupo_id,
            },
            descricao="Item SINAPI inserido",
        )
        return item_id

    def _estado_item_deve_fixar(self, estado_item, codigo=None):
        return deve_fixar_estado_sinapi(
            self.ctx.sinapi,
            codigo or "",
            estado_item,
            self._estado_selecionado(),
        )

    def _abrir_busca_sinapi(self):
        grupo_id = self._grupo_id_selecionado()
        if not grupo_id:
            messagebox.showinfo(
                "Inserir item SINAPI",
                "Selecione uma etapa na estrutura do orçamento.",
                parent=self.winfo_toplevel(),
            )
            return

        def ao_confirmar(codigo, descricao, unidade, custo, quantidade, estado, tipo_sinapi=""):
            self._inserir_item_sinapi(
                grupo_id,
                codigo,
                descricao,
                unidade,
                custo,
                quantidade,
                estado,
                tipo_sinapi,
                estado_fixado=self._estado_item_deve_fixar(estado, codigo),
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
                "Selecione uma etapa na estrutura do orçamento.",
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
        if linha is not None:
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
            return

        estados_alt = estados_com_codigo(self.ctx.sinapi, codigo)
        if not estados_alt:
            messagebox.showwarning(
                "Inserir rápido",
                f"Código {codigo} não encontrado em nenhum estado da base.",
                parent=self.winfo_toplevel(),
            )
            return

        def ao_escolher_uf(uf):
            linha_alt = obter_item_sinapi(self.ctx.sinapi, codigo, uf)
            if linha_alt is None:
                messagebox.showwarning(
                    "Inserir rápido",
                    f"Código {codigo} não encontrado para o estado {uf}.",
                    parent=self.winfo_toplevel(),
                )
                return
            try:
                custo_alt = float(linha_alt.get("custo", 0))
            except (TypeError, ValueError):
                custo_alt = 0.0
            item_id = self._inserir_item_sinapi(
                grupo_id,
                linha_alt.get("codigo", codigo),
                linha_alt.get("descricao", ""),
                linha_alt.get("unidade", ""),
                custo_alt,
                quantidade,
                uf,
                str(linha_alt.get("tipo", "")).strip().upper()[:1],
                estado_fixado=True,
            )
            if item_id:
                self.var_codigo_rapido.set("")

        DialogoEstadoItemSinapi(
            self.winfo_toplevel(),
            f"Código {codigo} ausente em {estado}. Escolha outra UF para o preço.",
            codigo,
            estados_alt,
            "SP" if "SP" in estados_alt else estados_alt[0],
            estado,
            ao_escolher_uf,
        )

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

            self._registrar_alteracao(
                focar_meta={"tipo": TIPO_GRUPO, "id": grupo_id},
                descricao="Etapa criada",
            )
            return True

        DialogoNovaEtapa(self.winfo_toplevel(), modelos, ao_confirmar)

    def _adicionar_composicao_propria(self):
        grupo_id = self._grupo_id_selecionado()
        if not grupo_id:
            messagebox.showinfo(
                "Composição própria",
                "Selecione uma etapa na estrutura do orçamento.",
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
            self._registrar_alteracao(
                focar_meta={
                    "tipo": TIPO_COMPOSICAO_PROPRIA,
                    "id": item_id,
                    "grupo_id": grupo_id,
                },
                descricao="Composição própria inserida",
            )

        DialogoBuscaComposicaoPropria(
            self.winfo_toplevel(),
            self.ctx,
            catalogo,
            self._estado_selecionado(),
            ao_confirmar,
        )

    def _salvar_nome_grupo_inline(self, grupo_id, nome) -> bool:
        nome = str(nome or "").strip()
        if not nome:
            messagebox.showwarning(
                "Etapa",
                "Informe o nome da etapa.",
                parent=self.winfo_toplevel(),
            )
            return False
        try:
            self.orcamento.renomear_grupo(grupo_id, nome)
        except ValueError as exc:
            messagebox.showwarning("Etapa", str(exc), parent=self.winfo_toplevel())
            return False
        self._registrar_alteracao(
            focar_meta={"tipo": TIPO_GRUPO, "id": grupo_id},
            descricao="Etapa renomeada",
        )
        return True

    def _dialogo_editar_quantidade(self, item_id):
        grupo, item = self.orcamento.obter_item(item_id)
        if item is None:
            return

        def ao_confirmar(texto):
            try:
                self.orcamento.atualizar_quantidade(
                    item_id, self._parse_quantidade(texto)
                )
            except ValueError as exc:
                messagebox.showwarning(
                    "Quantidade", str(exc), parent=self.winfo_toplevel()
                )
                return
            self._registrar_alteracao(
                focar_meta={
                    "tipo": item["tipo"],
                    "id": item_id,
                    "grupo_id": grupo["id"] if grupo else None,
                },
                descricao="Quantidade alterada",
            )

        DialogoEditarQuantidade(
            self.winfo_toplevel(),
            rotulo_item(item),
            item["quantidade"],
            ao_confirmar,
        )

    def _trocar_ordem_etapa(self, grupo_id=None):
        if not grupo_id:
            meta = self._meta_selecionada()
            if not meta or meta["tipo"] != TIPO_GRUPO:
                messagebox.showinfo(
                    "Trocar ordem da etapa",
                    "Selecione a linha da etapa para reordenar (ou arraste pelo número).",
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
            self._registrar_alteracao(
                focar_meta={"tipo": TIPO_GRUPO, "id": grupo_id},
                descricao="Ordem da etapa alterada",
            )

        DialogoTrocarOrdemEtapa(
            self.winfo_toplevel(),
            grupo["nome"],
            posicao_atual,
            opcoes_posicao,
            ao_confirmar,
        )

    def _ao_reordenar_item_arraste(self, item_id, novo_indice):
        try:
            if not self.orcamento.mover_item_para_indice(item_id, novo_indice):
                return False
        except ValueError as exc:
            messagebox.showwarning("Item", str(exc), parent=self.winfo_toplevel())
            return False
        grupo, item = self.orcamento.obter_item(item_id)
        tipo = item.get("tipo") if item else None
        grupo_id = grupo.get("id") if grupo else None
        self._registrar_alteracao(
            focar_meta={"tipo": tipo, "id": item_id, "grupo_id": grupo_id},
            descricao="Item reordenado",
        )
        return True

    def _ao_reordenar_etapa_arraste(self, grupo_id, novo_indice):
        try:
            if not self.orcamento.mover_grupo_para_indice(grupo_id, novo_indice):
                return False
        except ValueError as exc:
            messagebox.showwarning("Etapa", str(exc), parent=self.winfo_toplevel())
            return False
        self._registrar_alteracao(
            focar_meta={"tipo": TIPO_GRUPO, "id": grupo_id},
            descricao="Etapa reordenada",
        )
        return True

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
                    "Selecione uma etapa ou item para remover.",
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
                "Remover etapa",
                "Remover a etapa e todos os seus itens?",
                parent=self.winfo_toplevel(),
            ):
                return
            self.orcamento.remover_grupo(grupos[0]["id"])
            self._registrar_alteracao(focar_meta=[], descricao="Etapa removida")
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

        descricao_remocao = (
            "Itens removidos" if len(itens) > 1 else "Item removido"
        )
        self._registrar_alteracao(focar_meta=[], descricao=descricao_remocao)

    def _alterar_estado_item(self):
        meta = self._meta_selecionada()
        if not meta or meta["tipo"] not in (TIPO_SINAPI, TIPO_COMPOSICAO_PROPRIA):
            messagebox.showinfo(
                "Estado do item",
                "Selecione um item SINAPI ou composição própria para alterar a UF.",
                parent=self.winfo_toplevel(),
            )
            return
        if len(self.grade.obter_metas_selecionadas()) > 1:
            messagebox.showinfo(
                "Estado do item",
                "Selecione apenas um item.",
                parent=self.winfo_toplevel(),
            )
            return

        item_id = meta["id"]
        grupo, item = self.orcamento.obter_item(item_id)
        if item is None:
            return

        estado_orc = self._estado_selecionado()
        if meta["tipo"] == TIPO_SINAPI:
            estados_alt = estados_com_codigo(self.ctx.sinapi, item["codigo"])
            if not estados_alt:
                messagebox.showwarning(
                    "Estado do item",
                    f"Código {item['codigo']} não encontrado em nenhum estado da base.",
                    parent=self.winfo_toplevel(),
                )
                return
            codigo_rotulo = item["codigo"]
            estado_atual = item.get("estado") or estado_orc
        else:
            estados_alt = self.ctx.obter_estados()
            if not estados_alt:
                messagebox.showwarning(
                    "Estado do item",
                    "Nenhum estado disponível na base SINAPI.",
                    parent=self.winfo_toplevel(),
                )
                return
            codigo_rotulo = item.get("codigo", "") or "Composição própria"
            estado_atual = item.get("estado") or estado_orc

        def ao_confirmar(uf):
            try:
                if meta["tipo"] == TIPO_SINAPI:
                    self.orcamento.definir_estado_item_sinapi(
                        item_id, uf, self.ctx.sinapi
                    )
                else:
                    self.orcamento.definir_estado_item_composicao(item_id, uf)
            except ValueError as exc:
                messagebox.showwarning(
                    "Estado do item", str(exc), parent=self.winfo_toplevel()
                )
                return
            self._registrar_alteracao(
                focar_meta={
                    "tipo": meta["tipo"],
                    "id": item_id,
                    "grupo_id": grupo["id"] if grupo else meta.get("grupo_id"),
                },
                descricao="UF do item alterada",
            )

        DialogoEstadoItemSinapi(
            self.winfo_toplevel(),
            rotulo_item(item),
            codigo_rotulo,
            estados_alt,
            estado_atual,
            estado_orc,
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
            try:
                self.orcamento.substituir_item_sinapi(
                    item_id,
                    codigo,
                    descricao,
                    unidade,
                    custo,
                    estado,
                    tipo_sinapi,
                    estado_fixado=self._estado_item_deve_fixar(estado, codigo),
                )
            except ValueError as exc:
                messagebox.showwarning("Editar item", str(exc), parent=self.winfo_toplevel())
                return
            self._registrar_alteracao(
                focar_meta={
                    "tipo": TIPO_SINAPI,
                    "id": item_id,
                    "grupo_id": meta.get("grupo_id"),
                },
                descricao="Item substituído",
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
            self._registrar_alteracao(
                focar_meta={
                    "tipo": TIPO_COMPOSICAO_PROPRIA,
                    "id": item_id,
                    "grupo_id": meta.get("grupo_id"),
                },
                descricao="Item substituído",
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
                    usa_uf_alt = item_usa_estado_alternativo(
                        item, estado_atual, catalogo, self.ctx.sinapi
                    )
                    descricao = item["descricao"]
                    if usa_uf_alt:
                        uf_alt = estado_efetivo_item(item, estado_atual, self.ctx.sinapi)
                        descricao = f"{descricao}  [{uf_alt}]"
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
                            "descricao": descricao,
                            "quantidade": _formatar_quantidade(item["quantidade"]),
                            "unidade": item["unidade"],
                            "custo_unit": _formatar_moeda(custo),
                            "custo_bdi": _formatar_moeda(custo_bdi),
                            "total": _formatar_moeda(total),
                        },
                        estilo="item",
                        alerta_depreciado=indisponivel,
                        alerta_estado_alternativo=usa_uf_alt and not indisponivel,
                    )
                else:
                    custo_unit, tem_depreciado = custo_composicao_propria_item(
                        item, catalogo, self.ctx.sinapi, estado_atual
                    )
                    custo_bdi = custo_unitario_com_bdi(custo_unit, bdi)
                    total = custo_bdi * item["quantidade"]
                    usa_uf_alt = item_usa_estado_alternativo(
                        item, estado_atual, catalogo, self.ctx.sinapi
                    )
                    descricao = item.get("nome", "")
                    if item.get("estado_fixado") and item.get("estado"):
                        descricao = f"{descricao}  [{item.get('estado', '')}]"
                    discriminar = bool(item.get("discriminar_componentes"))
                    self.grade.adicionar_linha(
                        meta={
                            "tipo": TIPO_COMPOSICAO_PROPRIA,
                            "id": item["id"],
                            "grupo_id": grupo["id"],
                            "discriminar_componentes": discriminar,
                        },
                        valores={
                            "item": num_item,
                            "codigo": item.get("codigo", ""),
                            "tipo_ic": "",
                            "descricao": descricao,
                            "quantidade": _formatar_quantidade(item["quantidade"]),
                            "unidade": item["unidade"],
                            "custo_unit": _formatar_moeda(custo_unit) if estado_atual else "—",
                            "custo_bdi": _formatar_moeda(custo_bdi) if estado_atual else "—",
                            "total": _formatar_moeda(total) if estado_atual else "—",
                        },
                        estilo="composicao",
                        alerta_depreciado=tem_depreciado,
                        alerta_estado_alternativo=usa_uf_alt
                        and not tem_depreciado
                        and not discriminar,
                        alerta_discriminar=discriminar and not tem_depreciado,
                    )

        bdi_txt = _formatar_bdi(bdi)
        self.label_total.config(
            text=(
                f"Total geral (c/ BDI {bdi_txt}%): "
                f"{_formatar_moeda(self._total_geral_calculado(bdi, catalogo, estado_atual))}"
            )
        )
        self.grade.finalizar_reconstrucao(fracao, selecoes)
        if not self.orcamento.grupos:
            self.grade.definir_vazio(
                "Nenhuma etapa neste orçamento.\n"
                "Selecione um Estado e clique em \"Nova etapa\" para começar."
            )
        self._sincronizar_alertas_iniciais()
        filtro = ""
        if hasattr(self, "var_filtro_grade"):
            filtro = self.var_filtro_grade.get()
        self.grade.aplicar_filtro(filtro)
        self._atualizar_banner_depreciados()

    def focar(self):
        self.recarregar_orcamento(forcar_rede=False)
