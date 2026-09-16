"""Módulo de orçamento para Área Comum (prévia, acesso restrito)."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core.area_comum import (
    ANOMALIAS_MODELO,
    CAMPOS_MEDIDA,
    TIPOS_EMPREENDIMENTO,
    TIPOS_ESQUADRIA,
    nova_esquadria,
    novo_item_anomalia_nova,
    novo_percentual,
    novo_rascunho,
    normalizar_rascunho,
    rascunho_tem_conteudo,
)
from core.area_comum_storage import (
    RascunhoAreaComumError,
    carregar_autosave,
    carregar_rascunho,
    limpar_autosave,
    pasta_rascunhos,
    salvar_autosave,
    salvar_rascunho,
)
from core.municipios_br import resolver_uf_municipio
from ui.dialogo_admin_usuarios import usuario_atual_eh_admin
from ui.icones import criar_botao_ttk_com_icone, criar_botao_ttk_so_icone
from ui.temas import cores_tema, estilos_botao
from ui.widgets import (
    PLACEHOLDER_ESTADO,
    CampoListaPesquisavel,
    criar_barra_modulo,
    estado_do_combo,
    formatar_decimal_br,
    parse_decimal_br,
    perguntar_escolha,
    valores_combo_estado,
    vincular_tooltip,
)

DEBOUNCE_AUTOSAVE_MS = 1600
DEBOUNCE_MUNICIPIO_MS = 450
DEBOUNCE_CALCULO_MS = 180


def acesso_area_comum_liberado(*, offline: bool = False) -> bool:
    """Prévia visível para admin; no modo offline não há papéis, então libera."""
    if offline:
        return True
    return usuario_atual_eh_admin()


def _numero(texto, padrao=0.0) -> float:
    try:
        return parse_decimal_br(texto)
    except ValueError:
        return padrao


def _nome_arquivo_sugerido(nome_condominio: str) -> str:
    texto = (nome_condominio or "").strip() or "sem_condominio"
    invalidos = '<>:"/\\|?*'
    for caractere in invalidos:
        texto = texto.replace(caractere, "_")
    texto = "_".join(texto.split())
    return f"area_comum_{texto}.json"


class AreaComumFrame(tk.Frame):
    def __init__(self, parent, ctx, on_voltar):
        cores = cores_tema(parent)
        super().__init__(parent, bg=cores.fundo)
        self._cores = cores
        self._estilos = estilos_botao(self)
        self.ctx = ctx
        self.on_voltar = on_voltar
        self._refs_icones = []
        self._sujo = False
        self._carregando = False
        self._perguntando_uf = False
        self._caminho_arquivo = None
        self._job_autosave = None
        self._job_municipio = None
        self._job_calculo = None
        self._job_feedback = None
        self._percentual_vars = []
        self._cards_anomalia = {}
        self._composicoes = []
        self._composicao_por_rotulo = {}

        self.var_nome = tk.StringVar()
        self.var_municipio = tk.StringVar()
        self.var_uf = tk.StringVar(value=PLACEHOLDER_ESTADO)
        self.var_tipo = tk.StringVar()
        self.var_blocos = tk.StringVar()
        self.var_pavimentos = tk.StringVar()
        self.var_unidades = tk.StringVar()
        self.var_bdi = tk.StringVar(value="30,45")
        self.var_medidas = {chave: tk.StringVar() for chave, _rotulo in CAMPOS_MEDIDA}
        self.var_arquivo = tk.StringVar(value="Rascunho novo")
        self.var_feedback = tk.StringVar(value="")
        self.var_esq_tipo = tk.StringVar()
        self.var_esq_largura = tk.StringVar()
        self.var_esq_altura = tk.StringVar()
        self.var_esq_qtd = tk.StringVar(value="1")
        self.var_nova_anomalia = tk.StringVar()
        self.var_nova_composicao = tk.StringVar()
        self.var_nova_qtd = tk.StringVar(value="1")

        self._montar()
        self._vincular_sujeira()
        self.ctx.registrar_callback_sinapi(self._ao_atualizar_sinapi)
        self.bind("<Destroy>", self._ao_destruir)
        self.after_idle(self._oferecer_autosave)

    def focar(self):
        try:
            self.entrada_nome.focus_set()
        except tk.TclError:
            pass

    def _texto_referencia(self):
        ref = self.ctx.sinapi_referencia_rotulo
        if ref == "BASE AUSENTE":
            return "Base não carregada"
        return f"Referência SINAPI: {ref}"

    def _voltar(self):
        if not self._confirmar_saida():
            return
        self.on_voltar()

    def _confirmar_saida(self, mensagem=None) -> bool:
        if not self._sujo:
            return True
        resposta = messagebox.askyesnocancel(
            "Rascunho não salvo",
            mensagem
            or (
                "Há alterações não salvas neste orçamento de Área Comum.\n"
                "Deseja salvar o rascunho JSON antes de sair?"
            ),
            parent=self.winfo_toplevel(),
        )
        if resposta is None:
            return False
        if resposta:
            return self._salvar()
        self._flush_autosave()
        return True

    def _montar(self):
        cores = self._cores
        fundo = cores.fundo
        criar_barra_modulo(
            self,
            "Área Comum",
            self._voltar,
            texto_referencia=self._texto_referencia(),
            montar_acoes_apos_titulo=self._montar_acoes_barra,
            montar_acoes_antes_referencia=self._montar_rotulo_arquivo,
        )

        aviso = tk.Label(
            self,
            text="Prévia em desenvolvimento — visível apenas para administradores.",
            font=("Segoe UI", 8, "italic"),
            fg=cores.texto_suave,
            bg=fundo,
            anchor="w",
        )
        aviso.pack(fill="x", padx=12, pady=(0, 4))

        self._montar_cabecalho_persistente()

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        self.notebook.bind("<<NotebookTabChanged>>", self._ao_trocar_aba)

        self._montar_aba_dados()
        self._montar_aba_esquadrias()
        self._montar_aba_anomalias()
        self._montar_aba_novas()
        self._montar_rodape()
        self._carregar_composicoes()
        self._recalcular()

        topo = self.winfo_toplevel()
        topo.bind("<Control-s>", self._ao_atalho_salvar)
        topo.bind("<Control-S>", self._ao_atalho_salvar)

    def _montar_acoes_barra(self, barra):
        estilos = self._estilos
        fundo = self._cores.fundo
        bloco = tk.Frame(barra, bg=fundo)
        bloco.pack(side="left", padx=(10, 0))

        btn_novo = criar_botao_ttk_so_icone(
            bloco,
            nome_icone="add-circle-outline",
            command=self._novo,
            cor_icone=estilos.icone,
            refs=self._refs_icones,
        )
        btn_novo.pack(side="left")
        vincular_tooltip(btn_novo, "Novo rascunho")

        btn_abrir = criar_botao_ttk_so_icone(
            bloco,
            nome_icone="folder-open-outline",
            command=self._abrir,
            cor_icone=estilos.icone,
            refs=self._refs_icones,
        )
        btn_abrir.pack(side="left", padx=(4, 0))
        vincular_tooltip(btn_abrir, "Abrir rascunho JSON")

        btn_salvar = criar_botao_ttk_so_icone(
            bloco,
            nome_icone="save-outline",
            command=self._salvar,
            cor_icone=estilos.icone_salvar,
            refs=self._refs_icones,
        )
        btn_salvar.pack(side="left", padx=(4, 0))
        vincular_tooltip(btn_salvar, "Salvar rascunho JSON (Ctrl+S)")

    def _montar_rotulo_arquivo(self, parent):
        tk.Label(
            parent,
            textvariable=self.var_arquivo,
            font=("Segoe UI", 9),
            fg=self._cores.texto_suave,
            bg=self._cores.fundo,
        ).pack(side="right", padx=(0, 12))

    def _montar_cabecalho_persistente(self):
        cores = self._cores
        fundo = cores.fundo
        faixa = tk.LabelFrame(
            self,
            text="Condomínio (sempre visível)",
            bg=fundo,
            fg=cores.texto,
            padx=10,
            pady=8,
        )
        faixa.pack(fill="x", padx=12, pady=(0, 6))

        tk.Label(faixa, text="Nome:", bg=fundo, fg=cores.texto).grid(
            row=0, column=0, sticky="w"
        )
        self.entrada_nome = ttk.Entry(faixa, textvariable=self.var_nome)
        self.entrada_nome.grid(row=0, column=1, sticky="ew", padx=(6, 16))

        tk.Label(faixa, text="Município:", bg=fundo, fg=cores.texto).grid(
            row=0, column=2, sticky="w"
        )
        self.entrada_municipio = ttk.Entry(faixa, textvariable=self.var_municipio, width=28)
        self.entrada_municipio.grid(row=0, column=3, sticky="ew", padx=(6, 16))
        self.entrada_municipio.bind("<FocusOut>", self._ao_sair_municipio)

        tk.Label(faixa, text="UF:", bg=fundo, fg=cores.texto).grid(
            row=0, column=4, sticky="w"
        )
        self.combo_uf = ttk.Combobox(
            faixa,
            textvariable=self.var_uf,
            values=valores_combo_estado(self.ctx.obter_estados()),
            width=10,
            state="readonly",
        )
        self.combo_uf.grid(row=0, column=5, sticky="w", padx=(6, 0))
        self.combo_uf.bind("<<ComboboxSelected>>", lambda _e: self._recalcular())

        faixa.columnconfigure(1, weight=3)
        faixa.columnconfigure(3, weight=2)

        self.var_nome.trace_add("write", self._forcar_maiusculo_nome)
        self.var_municipio.trace_add("write", self._ao_digitar_municipio)

    def _montar_aba_dados(self):
        cores = self._cores
        fundo = cores.fundo
        interior = self._aba_rolavel("1. Dados iniciais")

        bloco_qtd = tk.LabelFrame(
            interior,
            text="Quantidades do empreendimento",
            bg=fundo,
            fg=cores.texto,
            padx=10,
            pady=8,
        )
        bloco_qtd.pack(fill="x", pady=(8, 8), padx=8)

        tk.Label(bloco_qtd, text="Tipo:", bg=fundo, fg=cores.texto).grid(
            row=0, column=0, sticky="w", pady=3
        )
        combo_tipo = ttk.Combobox(
            bloco_qtd,
            textvariable=self.var_tipo,
            values=TIPOS_EMPREENDIMENTO,
            state="readonly",
            width=28,
        )
        combo_tipo.grid(row=0, column=1, sticky="w", padx=(6, 18), pady=3)

        tk.Label(bloco_qtd, text="Blocos / torres:", bg=fundo, fg=cores.texto).grid(
            row=0, column=2, sticky="w", pady=3
        )
        ttk.Entry(bloco_qtd, textvariable=self.var_blocos, width=10).grid(
            row=0, column=3, sticky="w", padx=(6, 18), pady=3
        )

        tk.Label(bloco_qtd, text="Pavimentos:", bg=fundo, fg=cores.texto).grid(
            row=1, column=0, sticky="w", pady=3
        )
        ttk.Entry(bloco_qtd, textvariable=self.var_pavimentos, width=10).grid(
            row=1, column=1, sticky="w", padx=(6, 18), pady=3
        )

        tk.Label(bloco_qtd, text="Unidades / imóveis:", bg=fundo, fg=cores.texto).grid(
            row=1, column=2, sticky="w", pady=3
        )
        ttk.Entry(bloco_qtd, textvariable=self.var_unidades, width=10).grid(
            row=1, column=3, sticky="w", padx=(6, 18), pady=3
        )

        tk.Label(bloco_qtd, text="BDI (%):", bg=fundo, fg=cores.texto).grid(
            row=2, column=0, sticky="w", pady=3
        )
        ttk.Entry(bloco_qtd, textvariable=self.var_bdi, width=10).grid(
            row=2, column=1, sticky="w", padx=(6, 18), pady=3
        )

        bloco_medidas = tk.LabelFrame(
            interior,
            text="Medidas globais (base dos cálculos)",
            bg=fundo,
            fg=cores.texto,
            padx=10,
            pady=8,
        )
        bloco_medidas.pack(fill="x", pady=(0, 8), padx=8)
        for indice, (chave, rotulo) in enumerate(CAMPOS_MEDIDA):
            linha = indice // 2
            coluna = (indice % 2) * 2
            tk.Label(bloco_medidas, text=rotulo + ":", bg=fundo, fg=cores.texto).grid(
                row=linha, column=coluna, sticky="w", pady=3, padx=(0, 6)
            )
            ttk.Entry(
                bloco_medidas, textvariable=self.var_medidas[chave], width=14
            ).grid(row=linha, column=coluna + 1, sticky="w", padx=(0, 24), pady=3)

        bloco_pct = tk.LabelFrame(
            interior,
            text="Percentuais de quantitativos (globais)",
            bg=fundo,
            fg=cores.texto,
            padx=10,
            pady=8,
        )
        bloco_pct.pack(fill="x", pady=(0, 8), padx=8)
        tk.Label(
            bloco_pct,
            text=(
                "Use para taxas do empreendimento inteiro (ex.: % de unidades "
                "com determinada patologia). O % de cada anomalia fica na aba 3."
            ),
            bg=fundo,
            fg=cores.texto_suave,
            wraplength=920,
            justify="left",
            anchor="w",
        ).pack(fill="x", pady=(0, 6))

        self.frame_percentuais = tk.Frame(bloco_pct, bg=fundo)
        self.frame_percentuais.pack(fill="x")
        criar_botao_ttk_com_icone(
            bloco_pct,
            texto="Adicionar percentual",
            nome_icone="add-circle-outline",
            command=self._adicionar_percentual,
            estilo=self._estilos.compacto_adicionar,
            cor_icone=self._estilos.icone_adicionar,
            refs=self._refs_icones,
        ).pack(anchor="w", pady=(6, 0))

        bloco_obs = tk.LabelFrame(
            interior,
            text="Observações",
            bg=fundo,
            fg=cores.texto,
            padx=10,
            pady=8,
        )
        bloco_obs.pack(fill="both", expand=True, pady=(0, 12), padx=8)
        self.texto_obs = tk.Text(bloco_obs, height=4, wrap="word")
        self.texto_obs.pack(fill="both", expand=True)
        self.texto_obs.bind("<KeyRelease>", lambda _e: self._marcar_sujo())

        self._redesenhar_percentuais([])

    def _montar_aba_esquadrias(self):
        cores = self._cores
        fundo = cores.fundo
        aba = ttk.Frame(self.notebook)
        self.notebook.add(aba, text="2. Esquadrias")

        dica = tk.Label(
            aba,
            text=(
                "Cadastre as tipologias de esquadria da fachada. A área total "
                "entra nos cálculos de vedação, peitoril e desconto da alvenaria."
            ),
            bg=fundo,
            fg=cores.texto_suave,
            wraplength=960,
            justify="left",
            anchor="w",
        )
        dica.pack(fill="x", padx=10, pady=(8, 4))

        form = tk.LabelFrame(
            aba, text="Nova tipologia", bg=fundo, fg=cores.texto, padx=8, pady=6
        )
        form.pack(fill="x", padx=10, pady=(0, 6))

        tk.Label(form, text="Tipo:", bg=fundo, fg=cores.texto).grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            form,
            textvariable=self.var_esq_tipo,
            values=TIPOS_ESQUADRIA,
            width=22,
        ).grid(row=0, column=1, padx=(6, 12), pady=3)

        tk.Label(form, text="Largura (m):", bg=fundo, fg=cores.texto).grid(
            row=0, column=2, sticky="w"
        )
        ttk.Entry(form, textvariable=self.var_esq_largura, width=10).grid(
            row=0, column=3, padx=(6, 12), pady=3
        )
        tk.Label(form, text="Altura (m):", bg=fundo, fg=cores.texto).grid(
            row=0, column=4, sticky="w"
        )
        ttk.Entry(form, textvariable=self.var_esq_altura, width=10).grid(
            row=0, column=5, padx=(6, 12), pady=3
        )
        tk.Label(form, text="Quantidade:", bg=fundo, fg=cores.texto).grid(
            row=0, column=6, sticky="w"
        )
        ttk.Entry(form, textvariable=self.var_esq_qtd, width=8).grid(
            row=0, column=7, padx=(6, 12), pady=3
        )
        criar_botao_ttk_com_icone(
            form,
            texto="Adicionar",
            nome_icone="add-circle-outline",
            command=self._adicionar_esquadria,
            estilo=self._estilos.compacto_adicionar,
            cor_icone=self._estilos.icone_adicionar,
            refs=self._refs_icones,
        ).grid(row=0, column=8, padx=(4, 0))

        tabela = tk.Frame(aba, bg=fundo)
        tabela.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        colunas = ("tipo", "largura", "altura", "qtd", "area_un", "area_total")
        self.tree_esquadrias = ttk.Treeview(
            tabela, columns=colunas, show="headings", selectmode="browse"
        )
        self.tree_esquadrias.heading("tipo", text="Tipo")
        self.tree_esquadrias.heading("largura", text="Largura (m)")
        self.tree_esquadrias.heading("altura", text="Altura (m)")
        self.tree_esquadrias.heading("qtd", text="Qtd.")
        self.tree_esquadrias.heading("area_un", text="Área un. (m²)")
        self.tree_esquadrias.heading("area_total", text="Área total (m²)")
        self.tree_esquadrias.column("tipo", width=220, anchor="w")
        for col in ("largura", "altura", "qtd", "area_un", "area_total"):
            self.tree_esquadrias.column(col, width=110, anchor="center")
        scroll = ttk.Scrollbar(
            tabela, orient="vertical", command=self.tree_esquadrias.yview
        )
        self.tree_esquadrias.configure(yscrollcommand=scroll.set)
        self.tree_esquadrias.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        rodape = tk.Frame(aba, bg=fundo)
        rodape.pack(fill="x", padx=10, pady=(0, 10))
        criar_botao_ttk_com_icone(
            rodape,
            texto="Remover selecionada",
            nome_icone="trash-outline",
            command=self._remover_esquadria,
            estilo=self._estilos.compacto_excluir,
            cor_icone=self._estilos.icone_excluir,
            refs=self._refs_icones,
        ).pack(side="left")
        self.lbl_total_esquadrias = tk.Label(
            rodape,
            text="Área total de esquadrias: 0 m²",
            bg=fundo,
            fg=cores.titulo,
            font=("Segoe UI", 10, "bold"),
        )
        self.lbl_total_esquadrias.pack(side="right")
        self._esquadrias = []

    def _montar_aba_anomalias(self):
        cores = self._cores
        fundo = cores.fundo
        aba = ttk.Frame(self.notebook)
        self.notebook.add(aba, text="3. Anomalias")

        tk.Label(
            aba,
            text=(
                "Cards das anomalias mais usadas, com quantitativos ao vivo nas "
                "caixas cinzas. A árvore à direita consolida o que já foi calculado "
                "— vamos decidir juntos se o detalhe SINAPI fica no card, na árvore, ou nos dois."
            ),
            bg=fundo,
            fg=cores.texto_suave,
            wraplength=1100,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=10, pady=(8, 4))

        painel = ttk.Panedwindow(aba, orient=tk.HORIZONTAL)
        painel.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        esquerda = tk.Frame(painel, bg=fundo)
        direita = tk.Frame(painel, bg=fundo)
        painel.add(esquerda, weight=3)
        painel.add(direita, weight=2)

        canvas = tk.Canvas(esquerda, highlightthickness=0, bg=fundo)
        scroll = ttk.Scrollbar(esquerda, orient="vertical", command=canvas.yview)
        cards = tk.Frame(canvas, bg=fundo)
        cards.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        janela = canvas.create_window((0, 0), window=cards, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(janela, width=e.width))
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self._vincular_scroll(canvas, cards)

        for modelo in ANOMALIAS_MODELO:
            self._criar_card_anomalia(cards, modelo)

        tk.Label(
            direita,
            text="Prévia consolidada",
            bg=fundo,
            fg=cores.titulo,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 4))
        colunas = ("item", "unid", "qtd")
        self.tree_previa = ttk.Treeview(
            direita, columns=colunas, show="tree headings", selectmode="browse"
        )
        self.tree_previa.heading("#0", text="Anomalia")
        self.tree_previa.heading("item", text="Quantitativo")
        self.tree_previa.heading("unid", text="Unid.")
        self.tree_previa.heading("qtd", text="Qtd.")
        self.tree_previa.column("#0", width=180)
        self.tree_previa.column("item", width=140)
        self.tree_previa.column("unid", width=60, anchor="center")
        self.tree_previa.column("qtd", width=80, anchor="e")
        scroll_p = ttk.Scrollbar(
            direita, orient="vertical", command=self.tree_previa.yview
        )
        self.tree_previa.configure(yscrollcommand=scroll_p.set)
        self.tree_previa.pack(side="left", fill="both", expand=True)
        scroll_p.pack(side="right", fill="y")

    def _criar_card_anomalia(self, parent, modelo):
        cores = self._cores
        fundo = cores.fundo
        card = tk.LabelFrame(
            parent,
            text=modelo["nome"],
            bg=fundo,
            fg=cores.texto,
            padx=8,
            pady=8,
        )
        card.pack(fill="x", pady=(0, 8), padx=4)

        campos = {}
        linha_campos = tk.Frame(card, bg=fundo)
        linha_campos.pack(fill="x", pady=(0, 8))
        for campo in modelo["campos"]:
            bloco = tk.Frame(linha_campos, bg=fundo)
            bloco.pack(side="left", padx=(0, 16))
            tk.Label(
                bloco,
                text=f"{campo['rotulo']}:",
                bg=fundo,
                fg=cores.texto,
            ).pack(side="left")
            var = tk.StringVar()
            entrada = ttk.Entry(bloco, textvariable=var, width=10)
            entrada.pack(side="left", padx=(6, 4))
            tk.Label(
                bloco, text=campo["unidade"], bg=fundo, fg=cores.texto_suave
            ).pack(side="left")
            var.trace_add("write", self._ao_alterar_campo)
            campos[campo["id"]] = var

        caixas = {}
        linha_caixas = tk.Frame(card, bg=fundo)
        linha_caixas.pack(fill="x")
        for quant in modelo["quantitativos"]:
            caixa = tk.Frame(
                linha_caixas,
                bg=cores.fundo_cartao_off,
                highlightbackground=cores.borda_suave,
                highlightthickness=1,
                padx=10,
                pady=6,
            )
            caixa.pack(side="left", padx=(0, 8))
            var_valor = tk.StringVar(value="—")
            tk.Label(
                caixa,
                textvariable=var_valor,
                bg=cores.fundo_cartao_off,
                fg=cores.titulo,
                font=("Segoe UI", 11, "bold"),
            ).pack()
            tk.Label(
                caixa,
                text=f"{quant['rotulo']} ({quant['unidade']})",
                bg=cores.fundo_cartao_off,
                fg=cores.texto_suave,
                font=("Segoe UI", 8),
            ).pack()
            caixas[quant["id"]] = var_valor

        self._cards_anomalia[modelo["id"]] = {
            "modelo": modelo,
            "campos": campos,
            "caixas": caixas,
        }

    def _montar_aba_novas(self):
        cores = self._cores
        fundo = cores.fundo
        aba = ttk.Frame(self.notebook)
        self.notebook.add(aba, text="4. Novas anomalias")

        tk.Label(
            aba,
            text=(
                "Para situações específicas: dê um nome à anomalia, busque uma "
                "composição própria já cadastrada e informe o quantitativo."
            ),
            bg=fundo,
            fg=cores.texto_suave,
            wraplength=960,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=10, pady=(8, 4))

        form = tk.LabelFrame(
            aba, text="Incluir composição", bg=fundo, fg=cores.texto, padx=8, pady=6
        )
        form.pack(fill="x", padx=10, pady=(0, 6))
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=2)

        tk.Label(form, text="Nome da anomalia:", bg=fundo, fg=cores.texto).grid(
            row=0, column=0, sticky="w", pady=3
        )
        ttk.Entry(form, textvariable=self.var_nova_anomalia).grid(
            row=0, column=1, sticky="ew", padx=(6, 16), pady=3
        )
        tk.Label(form, text="Quantidade:", bg=fundo, fg=cores.texto).grid(
            row=0, column=2, sticky="w", pady=3
        )
        ttk.Entry(form, textvariable=self.var_nova_qtd, width=10).grid(
            row=0, column=3, sticky="w", padx=(6, 0), pady=3
        )

        tk.Label(form, text="Composição própria:", bg=fundo, fg=cores.texto).grid(
            row=1, column=0, sticky="w", pady=3
        )
        self.campo_composicao = CampoListaPesquisavel(
            form,
            textvariable=self.var_nova_composicao,
            largura_minima_lista=420,
            bg=fundo,
        )
        self.campo_composicao.grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=(6, 12), pady=3
        )
        criar_botao_ttk_com_icone(
            form,
            texto="Adicionar",
            nome_icone="add-circle-outline",
            command=self._adicionar_anomalia_nova,
            estilo=self._estilos.compacto_adicionar,
            cor_icone=self._estilos.icone_adicionar,
            refs=self._refs_icones,
        ).grid(row=1, column=3, sticky="w")

        tabela = tk.Frame(aba, bg=fundo)
        tabela.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        colunas = ("codigo", "item", "unid", "qtd")
        self.tree_novas = ttk.Treeview(
            tabela, columns=colunas, show="tree headings", selectmode="browse"
        )
        self.tree_novas.heading("#0", text="Anomalia")
        self.tree_novas.heading("codigo", text="Código")
        self.tree_novas.heading("item", text="Composição")
        self.tree_novas.heading("unid", text="Unid.")
        self.tree_novas.heading("qtd", text="Qtd.")
        self.tree_novas.column("#0", width=200)
        self.tree_novas.column("codigo", width=90)
        self.tree_novas.column("item", width=360)
        self.tree_novas.column("unid", width=70, anchor="center")
        self.tree_novas.column("qtd", width=80, anchor="e")
        scroll = ttk.Scrollbar(tabela, orient="vertical", command=self.tree_novas.yview)
        self.tree_novas.configure(yscrollcommand=scroll.set)
        self.tree_novas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        criar_botao_ttk_com_icone(
            aba,
            texto="Remover selecionado",
            nome_icone="trash-outline",
            command=self._remover_anomalia_nova,
            estilo=self._estilos.compacto_excluir,
            cor_icone=self._estilos.icone_excluir,
            refs=self._refs_icones,
        ).pack(anchor="w", padx=10, pady=(0, 10))
        self._anomalias_novas = []

    def _montar_rodape(self):
        cores = self._cores
        fundo = cores.fundo
        rodape = tk.Frame(self, bg=fundo)
        rodape.pack(fill="x", padx=12, pady=(0, 8))

        self.lbl_feedback = tk.Label(
            rodape,
            textvariable=self.var_feedback,
            bg=fundo,
            fg=cores.texto_suave,
            anchor="w",
        )
        self.lbl_feedback.pack(side="left", fill="x", expand=True)

        btn_custom = criar_botao_ttk_com_icone(
            rodape,
            texto="Salvar em Orçamentos Customizados",
            nome_icone="save-outline",
            command=self._salvar_em_customizados,
            estilo=self._estilos.compacto,
            cor_icone=self._estilos.icone,
            refs=self._refs_icones,
        )
        btn_custom.pack(side="right")
        vincular_tooltip(
            btn_custom,
            "Depois que o orçamento estiver gerado, gravar na lista compartilhada.",
        )

        btn_gerar = criar_botao_ttk_com_icone(
            rodape,
            texto="Gerar orçamento",
            nome_icone="construct-outline",
            command=self._gerar_orcamento,
            estilo=self._estilos.compacto,
            cor_icone=self._estilos.icone,
            refs=self._refs_icones,
        )
        btn_gerar.pack(side="right", padx=(0, 8))
        vincular_tooltip(
            btn_gerar,
            "A geração da planilha entra na próxima etapa deste módulo.",
        )

    def _aba_rolavel(self, titulo):
        cores = self._cores
        fundo = cores.fundo
        aba = ttk.Frame(self.notebook)
        self.notebook.add(aba, text=titulo)
        canvas = tk.Canvas(aba, highlightthickness=0, bg=fundo)
        scroll = ttk.Scrollbar(aba, orient="vertical", command=canvas.yview)
        interior = tk.Frame(canvas, bg=fundo)
        interior.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        janela = canvas.create_window((0, 0), window=interior, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)

        def _ajustar_largura(event):
            canvas.itemconfigure(janela, width=event.width)

        canvas.bind("<Configure>", _ajustar_largura)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self._vincular_scroll(canvas, interior)
        return interior

    def _vincular_scroll(self, canvas, interior):
        def _rolar(event):
            try:
                if not canvas.winfo_exists():
                    return
            except tk.TclError:
                return
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _entrar(_event=None):
            canvas.bind_all("<MouseWheel>", _rolar)

        def _sair(_event=None):
            try:
                x, y = canvas.winfo_pointerx(), canvas.winfo_pointery()
                x0 = canvas.winfo_rootx()
                y0 = canvas.winfo_rooty()
                if x0 <= x <= x0 + canvas.winfo_width() and y0 <= y <= y0 + canvas.winfo_height():
                    return
            except tk.TclError:
                pass
            canvas.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", _entrar)
        interior.bind("<Enter>", _entrar)
        canvas.bind("<Leave>", _sair)
        interior.bind("<Leave>", _sair)

    def _vincular_sujeira(self):
        variaveis = [
            self.var_nome,
            self.var_municipio,
            self.var_uf,
            self.var_tipo,
            self.var_blocos,
            self.var_pavimentos,
            self.var_unidades,
            self.var_bdi,
            *self.var_medidas.values(),
        ]
        for var in variaveis:
            var.trace_add("write", self._ao_alterar_campo)

    def _forcar_maiusculo_nome(self, *_args):
        texto = self.var_nome.get()
        maiusculo = texto.upper()
        if texto != maiusculo:
            pos = self.entrada_nome.index("insert")
            self.var_nome.set(maiusculo)
            try:
                self.entrada_nome.icursor(pos)
            except tk.TclError:
                pass

    def _ao_digitar_municipio(self, *_args):
        texto = self.var_municipio.get()
        maiusculo = texto.upper()
        if texto != maiusculo:
            pos = self.entrada_municipio.index("insert")
            self.var_municipio.set(maiusculo)
            try:
                self.entrada_municipio.icursor(pos)
            except tk.TclError:
                pass
        if self._job_municipio is not None:
            try:
                self.after_cancel(self._job_municipio)
            except (tk.TclError, ValueError):
                pass
        self._job_municipio = self.after(DEBOUNCE_MUNICIPIO_MS, self._resolver_uf_municipio)

    def _ao_sair_municipio(self, _event=None):
        self._resolver_uf_municipio()

    def _resolver_uf_municipio(self):
        self._job_municipio = None
        if self._carregando or self._perguntando_uf:
            return
        municipio = self.var_municipio.get().strip()
        if not municipio:
            return
        resultado = resolver_uf_municipio(municipio)
        estados = set(self.ctx.obter_estados())
        if resultado.motivo == "ok" and resultado.uf:
            if resultado.uf in estados:
                if estado_do_combo(self.var_uf.get()) != resultado.uf:
                    self.var_uf.set(resultado.uf)
                    self._mostrar_feedback(
                        f"UF definida a partir do município: {resultado.uf}.",
                        "green",
                    )
            else:
                self._mostrar_feedback(
                    f"Município em {resultado.uf}, mas não há SINAPI para essa UF.",
                    "orange",
                    temporario=False,
                )
            return
        if resultado.motivo == "ambigua":
            ufs = [uf for uf in resultado.ufs_possiveis if uf in estados] or list(
                resultado.ufs_possiveis
            )
            self._perguntando_uf = True
            try:
                escolhido = perguntar_escolha(
                    self.winfo_toplevel(),
                    "Selecionar estado",
                    f"A cidade '{resultado.cidade.title()}' existe em mais de um estado.\n"
                    "Qual é o estado deste condomínio?",
                    ufs,
                )
            finally:
                self._perguntando_uf = False
            if escolhido:
                self.var_uf.set(escolhido)
                self._mostrar_feedback(f"UF definida: {escolhido}.", "green")
            return
        if resultado.motivo == "nao_encontrada":
            self._mostrar_feedback(
                "Município não reconhecido. Selecione a UF manualmente.",
                "orange",
                temporario=False,
            )

    def _ao_alterar_campo(self, *_args):
        self._marcar_sujo()
        self._agendar_calculo()

    def _ao_trocar_aba(self, _event=None):
        self._recalcular()

    def _ao_atalho_salvar(self, _event=None):
        try:
            visivel = bool(self.winfo_ismapped())
        except tk.TclError:
            visivel = False
        if not visivel:
            return
        self._salvar()
        return "break"

    def _ao_atualizar_sinapi(self):
        estados = valores_combo_estado(self.ctx.obter_estados())
        atual = self.var_uf.get()
        self.combo_uf.configure(values=estados)
        if atual in estados:
            self.var_uf.set(atual)
        elif estado_do_combo(atual) not in self.ctx.obter_estados():
            self.var_uf.set(PLACEHOLDER_ESTADO)

    def _marcar_sujo(self):
        if self._carregando:
            return
        self._sujo = True
        self._atualizar_rotulo_arquivo()
        self._agendar_autosave()

    def _atualizar_rotulo_arquivo(self):
        if self._caminho_arquivo is None:
            texto = "Rascunho novo"
        else:
            texto = Path(self._caminho_arquivo).name
        if self._sujo:
            texto = f"{texto} • não salvo"
        self.var_arquivo.set(texto)

    def _agendar_autosave(self):
        if self._job_autosave is not None:
            try:
                self.after_cancel(self._job_autosave)
            except (tk.TclError, ValueError):
                pass
        self._job_autosave = self.after(DEBOUNCE_AUTOSAVE_MS, self._flush_autosave)

    def _flush_autosave(self):
        self._job_autosave = None
        if not self._sujo:
            return
        dados = self._coletar_rascunho()
        if not rascunho_tem_conteudo(dados):
            return
        try:
            salvar_autosave(dados)
        except OSError:
            pass

    def _agendar_calculo(self):
        if self._job_calculo is not None:
            try:
                self.after_cancel(self._job_calculo)
            except (tk.TclError, ValueError):
                pass
        self._job_calculo = self.after(DEBOUNCE_CALCULO_MS, self._recalcular)

    def _recalcular(self):
        self._job_calculo = None
        self._atualizar_cards_anomalia()
        self._atualizar_total_esquadrias()

    def _medida(self, chave: str) -> float:
        return _numero(self.var_medidas[chave].get())

    def _atualizar_cards_anomalia(self):
        if not hasattr(self, "tree_previa"):
            return
        for item in self.tree_previa.get_children():
            self.tree_previa.delete(item)
        for modelo in ANOMALIAS_MODELO:
            card = self._cards_anomalia.get(modelo["id"])
            if not card:
                continue
            linhas = []
            for quant in modelo["quantitativos"]:
                base = self._medida(quant["medida"])
                percentual = _numero(card["campos"][quant["campo"]].get())
                valor = base * (percentual / 100.0) if percentual else 0.0
                texto = formatar_decimal_br(valor, 2) if valor else "—"
                card["caixas"][quant["id"]].set(texto)
                if valor:
                    linhas.append((quant["rotulo"], quant["unidade"], texto))
            if linhas:
                pai = self.tree_previa.insert(
                    "", "end", text=modelo["nome"], values=("", "", "")
                )
                for rotulo, unid, qtd in linhas:
                    self.tree_previa.insert(
                        pai, "end", text="", values=(rotulo, unid, qtd)
                    )
                self.tree_previa.item(pai, open=True)

    def _redesenhar_percentuais(self, itens):
        for filho in self.frame_percentuais.winfo_children():
            filho.destroy()
        self._percentual_vars = []
        fundo = self._cores.fundo
        if not itens:
            tk.Label(
                self.frame_percentuais,
                text="Nenhum percentual global cadastrado.",
                bg=fundo,
                fg=self._cores.texto_suave,
            ).pack(anchor="w")
            return
        cab = tk.Frame(self.frame_percentuais, bg=fundo)
        cab.pack(fill="x")
        tk.Label(cab, text="Descrição", bg=fundo, fg=self._cores.texto_suave).pack(
            side="left", padx=(0, 8)
        )
        tk.Label(cab, text="% ", bg=fundo, fg=self._cores.texto_suave).pack(
            side="left", padx=(280, 0)
        )
        for item in itens:
            self._criar_linha_percentual(item)

    def _criar_linha_percentual(self, item):
        fundo = self._cores.fundo
        linha = tk.Frame(self.frame_percentuais, bg=fundo)
        linha.pack(fill="x", pady=2)
        var_nome = tk.StringVar(value=item.get("nome", ""))
        var_valor = tk.StringVar(value=item.get("valor", ""))
        ttk.Entry(linha, textvariable=var_nome).pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )
        ttk.Entry(linha, textvariable=var_valor, width=8).pack(side="left")
        tk.Label(linha, text="%", bg=fundo, fg=self._cores.texto).pack(
            side="left", padx=(4, 8)
        )
        item_id = item.get("id")
        criar_botao_ttk_so_icone(
            linha,
            nome_icone="trash-outline",
            command=lambda i=item_id: self._remover_percentual(i),
            cor_icone=self._estilos.icone_excluir,
            refs=self._refs_icones,
        ).pack(side="left")
        var_nome.trace_add("write", self._ao_alterar_campo)
        var_valor.trace_add("write", self._ao_alterar_campo)
        self._percentual_vars.append(
            {"id": item_id, "nome": var_nome, "valor": var_valor, "frame": linha}
        )

    def _adicionar_percentual(self):
        if not self._percentual_vars and self.frame_percentuais.winfo_children():
            for filho in self.frame_percentuais.winfo_children():
                filho.destroy()
        item = novo_percentual()
        self._criar_linha_percentual(item)
        self._marcar_sujo()

    def _remover_percentual(self, item_id):
        restantes = []
        for registro in self._percentual_vars:
            if registro["id"] == item_id:
                registro["frame"].destroy()
            else:
                restantes.append(registro)
        self._percentual_vars = restantes
        if not self._percentual_vars:
            self._redesenhar_percentuais([])
        self._marcar_sujo()

    def _adicionar_esquadria(self):
        tipo = self.var_esq_tipo.get().strip()
        if not tipo:
            self._mostrar_feedback("Informe o tipo da esquadria.", "red")
            return
        linha = nova_esquadria(
            tipo=tipo,
            largura=self.var_esq_largura.get(),
            altura=self.var_esq_altura.get(),
            quantidade=self.var_esq_qtd.get() or "1",
        )
        self._esquadrias.append(linha)
        self._redesenhar_esquadrias()
        self.var_esq_largura.set("")
        self.var_esq_altura.set("")
        self.var_esq_qtd.set("1")
        self._marcar_sujo()

    def _remover_esquadria(self):
        selecionado = self.tree_esquadrias.selection()
        if not selecionado:
            self._mostrar_feedback("Selecione uma esquadria na lista.", "orange")
            return
        item_id = selecionado[0]
        self._esquadrias = [e for e in self._esquadrias if e["id"] != item_id]
        self._redesenhar_esquadrias()
        self._marcar_sujo()

    def _area_esquadria(self, item):
        largura = _numero(item.get("largura_m"))
        altura = _numero(item.get("altura_m"))
        qtd = _numero(item.get("quantidade"), 0.0)
        area_un = largura * altura
        return area_un, area_un * qtd

    def _redesenhar_esquadrias(self):
        for item in self.tree_esquadrias.get_children():
            self.tree_esquadrias.delete(item)
        for linha in self._esquadrias:
            area_un, area_total = self._area_esquadria(linha)
            self.tree_esquadrias.insert(
                "",
                "end",
                iid=linha["id"],
                values=(
                    linha["tipo"],
                    linha["largura_m"],
                    linha["altura_m"],
                    linha["quantidade"],
                    formatar_decimal_br(area_un, 2) if area_un else "—",
                    formatar_decimal_br(area_total, 2) if area_total else "—",
                ),
            )
        self._atualizar_total_esquadrias()

    def _atualizar_total_esquadrias(self):
        if not hasattr(self, "lbl_total_esquadrias"):
            return
        total = sum(self._area_esquadria(item)[1] for item in self._esquadrias)
        self.lbl_total_esquadrias.configure(
            text=f"Área total de esquadrias: {formatar_decimal_br(total, 2)} m²"
        )

    def _carregar_composicoes(self):
        try:
            from core.composicoes_proprias_storage import (
                carregar,
                listar,
                obter_cache_catalogo,
            )

            if obter_cache_catalogo() is None:
                carregar()
            self._composicoes = listar()
        except (ValueError, OSError):
            self._composicoes = []
        rotulos = []
        self._composicao_por_rotulo = {}
        for comp in self._composicoes:
            rotulo = f"{comp.get('codigo', '')} — {comp.get('nome', '')}"
            rotulos.append(rotulo)
            self._composicao_por_rotulo[rotulo] = comp
        if hasattr(self, "campo_composicao"):
            self.campo_composicao.definir_opcoes(rotulos)

    def _adicionar_anomalia_nova(self):
        nome = self.var_nova_anomalia.get().strip()
        if not nome:
            self._mostrar_feedback("Informe o nome da nova anomalia.", "red")
            return
        rotulo = self.var_nova_composicao.get().strip()
        composicao = self._composicao_por_rotulo.get(rotulo)
        if composicao is None:
            self._mostrar_feedback("Selecione uma composição própria da lista.", "red")
            return
        qtd = self.var_nova_qtd.get().strip() or "1"
        self._anomalias_novas.append(
            novo_item_anomalia_nova(
                nome_anomalia=nome,
                composicao_catalogo_id=composicao.get("id"),
                codigo=composicao.get("codigo"),
                nome_item=composicao.get("nome"),
                unidade=composicao.get("unidade"),
                quantidade=qtd,
            )
        )
        self._redesenhar_novas()
        self.var_nova_composicao.set("")
        self.var_nova_qtd.set("1")
        self._marcar_sujo()
        self._mostrar_feedback("Composição adicionada à nova anomalia.", "green")

    def _remover_anomalia_nova(self):
        selecionado = self.tree_novas.selection()
        if not selecionado:
            self._mostrar_feedback("Selecione um item para remover.", "orange")
            return
        item_id = selecionado[0]
        pai = self.tree_novas.parent(item_id)
        alvo = item_id if not pai else item_id
        if not pai:
            nome = self.tree_novas.item(item_id, "text")
            self._anomalias_novas = [
                i for i in self._anomalias_novas if i.get("nome_anomalia") != nome
            ]
        else:
            self._anomalias_novas = [
                i for i in self._anomalias_novas if i.get("id") != alvo
            ]
        self._redesenhar_novas()
        self._marcar_sujo()

    def _redesenhar_novas(self):
        for item in self.tree_novas.get_children():
            self.tree_novas.delete(item)
        grupos = {}
        for linha in self._anomalias_novas:
            grupos.setdefault(linha["nome_anomalia"] or "(sem nome)", []).append(linha)
        for nome, itens in grupos.items():
            pai = self.tree_novas.insert("", "end", text=nome, values=("", "", "", ""))
            for linha in itens:
                self.tree_novas.insert(
                    pai,
                    "end",
                    iid=linha["id"],
                    text="",
                    values=(
                        linha.get("codigo", ""),
                        linha.get("nome_item", ""),
                        linha.get("unidade", ""),
                        linha.get("quantidade", ""),
                    ),
                )
            self.tree_novas.item(pai, open=True)

    def _coletar_rascunho(self) -> dict:
        dados = novo_rascunho()
        dados["condominio"]["nome"] = self.var_nome.get().strip()
        dados["condominio"]["municipio"] = self.var_municipio.get().strip()
        dados["condominio"]["uf"] = estado_do_combo(self.var_uf.get())
        dados["dados_iniciais"]["tipo_empreendimento"] = self.var_tipo.get().strip()
        dados["dados_iniciais"]["qtd_blocos"] = self.var_blocos.get().strip()
        dados["dados_iniciais"]["qtd_pavimentos"] = self.var_pavimentos.get().strip()
        dados["dados_iniciais"]["qtd_unidades"] = self.var_unidades.get().strip()
        dados["dados_iniciais"]["bdi_percent"] = self.var_bdi.get().strip()
        for chave, var in self.var_medidas.items():
            dados["dados_iniciais"]["medidas"][chave] = var.get().strip()
        dados["dados_iniciais"]["percentuais"] = [
            {
                "id": item["id"],
                "nome": item["nome"].get().strip(),
                "valor": item["valor"].get().strip(),
            }
            for item in self._percentual_vars
        ]
        dados["esquadrias"] = list(self._esquadrias)
        for ident, card in self._cards_anomalia.items():
            dados["anomalias"][ident] = {
                campo_id: var.get().strip()
                for campo_id, var in card["campos"].items()
            }
        dados["anomalias_novas"] = list(self._anomalias_novas)
        dados["observacoes"] = self.texto_obs.get("1.0", "end").strip()
        return dados

    def _aplicar_rascunho(self, dados: dict, *, caminho=None):
        self._carregando = True
        dados = normalizar_rascunho(dados)
        try:
            self.var_nome.set(dados["condominio"].get("nome", ""))
            self.var_municipio.set(dados["condominio"].get("municipio", ""))
            uf = dados["condominio"].get("uf", "")
            self.var_uf.set(uf if uf else PLACEHOLDER_ESTADO)
            iniciais = dados.get("dados_iniciais") or {}
            self.var_tipo.set(iniciais.get("tipo_empreendimento", ""))
            self.var_blocos.set(iniciais.get("qtd_blocos", ""))
            self.var_pavimentos.set(iniciais.get("qtd_pavimentos", ""))
            self.var_unidades.set(iniciais.get("qtd_unidades", ""))
            self.var_bdi.set(iniciais.get("bdi_percent", "30,45"))
            medidas = iniciais.get("medidas") or {}
            for chave, var in self.var_medidas.items():
                var.set(medidas.get(chave, ""))
            self._redesenhar_percentuais(iniciais.get("percentuais") or [])
            self._esquadrias = list(dados.get("esquadrias") or [])
            self._redesenhar_esquadrias()
            anomalias = dados.get("anomalias") or {}
            for ident, card in self._cards_anomalia.items():
                valores = anomalias.get(ident) or {}
                for campo_id, var in card["campos"].items():
                    var.set(valores.get(campo_id, ""))
            self._anomalias_novas = list(dados.get("anomalias_novas") or [])
            self._redesenhar_novas()
            self.texto_obs.delete("1.0", "end")
            obs = dados.get("observacoes") or ""
            if obs:
                self.texto_obs.insert("1.0", obs)
            self._caminho_arquivo = str(caminho) if caminho else None
            self._sujo = False
            self._atualizar_rotulo_arquivo()
            self._recalcular()
        finally:
            if self._job_municipio is not None:
                try:
                    self.after_cancel(self._job_municipio)
                except (tk.TclError, ValueError):
                    pass
                self._job_municipio = None
            self._carregando = False

    def _novo(self):
        if self._sujo and not self._confirmar_saida(
            "Há alterações não salvas.\n"
            "Deseja salvar o rascunho JSON antes de começar outro?"
        ):
            return
        self._aplicar_rascunho(novo_rascunho())
        limpar_autosave()
        self._mostrar_feedback("Novo rascunho iniciado.", "green")

    def _abrir(self):
        if self._sujo and not self._confirmar_saida(
            "Há alterações não salvas.\n"
            "Deseja salvar o rascunho JSON antes de abrir outro?"
        ):
            return
        caminho = filedialog.askopenfilename(
            title="Abrir rascunho de Área Comum",
            initialdir=str(pasta_rascunhos()),
            filetypes=[("Rascunho JSON", "*.json"), ("Todos os arquivos", "*.*")],
            parent=self.winfo_toplevel(),
        )
        if not caminho:
            return
        try:
            dados = carregar_rascunho(caminho)
        except RascunhoAreaComumError as exc:
            messagebox.showerror("Abrir rascunho", str(exc), parent=self.winfo_toplevel())
            return
        self._aplicar_rascunho(dados, caminho=caminho)
        self._mostrar_feedback(f"Rascunho aberto: {Path(caminho).name}", "green")

    def _salvar(self, *, salvar_como=False) -> bool:
        caminho = None if salvar_como else self._caminho_arquivo
        if not caminho:
            caminho = filedialog.asksaveasfilename(
                title="Salvar rascunho de Área Comum",
                initialdir=str(pasta_rascunhos()),
                initialfile=_nome_arquivo_sugerido(self.var_nome.get()),
                defaultextension=".json",
                filetypes=[("Rascunho JSON", "*.json")],
                parent=self.winfo_toplevel(),
            )
        if not caminho:
            return False
        try:
            salvar_rascunho(self._coletar_rascunho(), caminho)
        except OSError as exc:
            messagebox.showerror(
                "Salvar rascunho",
                f"Não foi possível gravar o arquivo:\n{exc}",
                parent=self.winfo_toplevel(),
            )
            return False
        self._caminho_arquivo = str(caminho)
        self._sujo = False
        self._atualizar_rotulo_arquivo()
        self._mostrar_feedback(f"Rascunho salvo: {Path(caminho).name}", "green")
        return True

    def _oferecer_autosave(self):
        dados = carregar_autosave()
        if not dados or not rascunho_tem_conteudo(dados):
            return
        nome = dados.get("condominio", {}).get("nome") or "sem nome"
        if not messagebox.askyesno(
            "Rascunho automático",
            "Há um rascunho automático da Área Comum "
            f"({nome}).\nDeseja continuar de onde parou?",
            parent=self.winfo_toplevel(),
        ):
            return
        self._aplicar_rascunho(dados)
        self._sujo = True
        self._atualizar_rotulo_arquivo()
        self._mostrar_feedback("Rascunho automático restaurado.", "green")

    def _gerar_orcamento(self):
        messagebox.showinfo(
            "Área Comum",
            "A geração da planilha entra na próxima etapa, depois de "
            "amarrarmos as anomalias às composições próprias.",
            parent=self.winfo_toplevel(),
        )

    def _salvar_em_customizados(self):
        messagebox.showinfo(
            "Área Comum",
            "Quando o orçamento estiver gerado, esta opção vai gravá-lo "
            "na lista de Orçamentos Customizados. Por enquanto o rascunho "
            "fica só no JSON local.",
            parent=self.winfo_toplevel(),
        )

    def _mostrar_feedback(self, texto, cor="gray", *, temporario=True):
        self.var_feedback.set(texto)
        try:
            self.lbl_feedback.configure(fg=cor)
        except tk.TclError:
            pass
        if self._job_feedback is not None:
            try:
                self.after_cancel(self._job_feedback)
            except (tk.TclError, ValueError):
                pass
            self._job_feedback = None
        if temporario:
            self._job_feedback = self.after(
                5000, lambda: self.var_feedback.set("")
            )

    def _ao_destruir(self, event=None):
        if event is not None and event.widget is not self:
            return
        self._flush_autosave()
        topo = self.winfo_toplevel()
        try:
            topo.unbind("<Control-s>")
            topo.unbind("<Control-S>")
        except tk.TclError:
            pass
