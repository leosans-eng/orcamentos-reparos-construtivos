"""Módulo de orçamento para Área Comum."""

from __future__ import annotations

import sys
import tkinter as tk
import traceback
from copy import deepcopy
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core.area_comum import (
    BDI_PADRAO,
    CHAVES_PCT_CONDOMINIO,
    LOCAL_CONDOMINIO,
    LOCAL_RESIDENCIAL,
    estruturas_do_local,
    locais_do_rascunho,
    nova_anomalia_orcamento,
    novo_rascunho,
    normalizar_rascunho,
    quantitativos_por_local,
    rascunho_tem_conteudo,
)
from core.area_comum_anomalias import (
    ROTULOS_PERCENTUAIS_ABA1,
    carregar_catalogo,
    nomes_anomalias,
    obter_reparo,
    percentuais_aba1_validos,
    percentuais_dos_fatores,
    perguntas_variaveis_reparo,
    reparo_recomendado,
    valores_considerados_reparo,
)
from core.area_comum_calculos import numero, parse_expressao
from core.area_comum_orcamento import (
    limites_fachada_por_local,
    migrar_extras_para_grupos,
    sincronizar_grupos_anomalias,
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
from core.composicoes_proprias import (
    custo_composicao_propria_item,
    linhas_detalhe_composicao,
    obter_composicao_por_id,
)
from core.composicoes_proprias_storage import listar as listar_composicoes_catalogo
from core.ui_prefs import definir_pref, obter_pref
from core.etapas_predefinidas import aplicar_etapa_no_orcamento
from core.municipios_br import resolver_uf_municipio
from app_paths import asset_path
from core.orcamento_customizado import (
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
from core.orcamento_conversao import novo_id
from core.orcamento_storage import (
    adicionar_orcamento_importado,
    atualizar_orcamento_na_lista,
    obter_orcamento_dict,
)
from core.sinapi_busca import deve_fixar_estado_sinapi, estados_com_codigo, obter_item_sinapi
from ui.area_comum_dados import AbaDadosIniciais
from ui.calculadora import abrir_calculadora
from ui.dialogo_previa_composicao import DialogoPreviaComposicao
from ui.dialogo_config_anomalias_area_comum import DialogoConfigAnomaliasAreaComum
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
from ui.temas import cores_grade, cores_tema, estilos_botao
from ui.widgets import (
    PLACEHOLDER_ESTADO,
    CampoListaPesquisavel,
    criar_barra_modulo,
    estado_do_combo,
    formatar_decimal_br,
    formatar_moeda_br,
    parse_quantidade_expressao,
    perguntar_escolha,
    perguntar_texto,
    valores_combo_estado,
    vincular_tooltip,
)

DEBOUNCE_AUTOSAVE_MS = 1600
DEBOUNCE_MUNICIPIO_MS = 450
DEBOUNCE_CALCULO_MS = 180
HISTORICO_MAX = 40


def _nome_arquivo_sugerido(nome_condominio: str, municipio: str = "", uf: str = "") -> str:
    nome = (nome_condominio or "").strip() or "SEM CONDOMINIO"
    municipio = (municipio or "").strip()
    uf = (uf or "").strip()
    if municipio and uf:
        texto = f"{nome} - {municipio}-{uf}"
    elif municipio:
        texto = f"{nome} - {municipio}"
    elif uf:
        texto = f"{nome} - {uf}"
    else:
        texto = nome
    invalidos = '<>:"/\\|?*'
    for caractere in invalidos:
        texto = texto.replace(caractere, "_")
    texto = " ".join(texto.split())
    return f"{texto}.json"


def _numero_br_fixo(valor, casas: int = 2) -> str:
    """Sempre com as casas pedidas, inclusive zeros à direita."""
    try:
        v = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    texto = f"{v:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _texto_campo_numerico(bruto, *, percentual=False, casas=None) -> str:
    """Formata como o campo faz ao perder o foco.

    Expressão válida vira número formatado; texto inválido é mantido como
    está (nunca vira 0 em silêncio).
    """
    bruto = str(bruto or "").strip()
    if not bruto:
        return ""
    try:
        parse_expressao(bruto)
    except ValueError:
        return bruto
    valor = numero(bruto, percentual=percentual)
    return _numero_br_fixo(valor, casas) if casas is not None else formatar_decimal_br(valor)


def _formatar_moeda(valor):
    return formatar_moeda_br(valor)


def _formatar_quantidade(valor):
    return formatar_decimal_br(valor, casas=4)


def _combo_popdown_aberto(combo) -> bool:
    try:
        nome = combo.tk.call("ttk::combobox::PopdownWindow", combo)
        return bool(int(combo.tk.call("winfo", "ismapped", nome)))
    except (tk.TclError, ValueError, TypeError):
        return False


def _rolar_canvas_ancestral(widget, event):
    atual = widget
    while atual is not None:
        if isinstance(atual, tk.Canvas):
            delta = int(getattr(event, "delta", 0) or 0)
            if delta:
                atual.yview_scroll(int(-1 * (delta / 120)), "units")
            elif getattr(event, "num", None) == 4:
                atual.yview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5:
                atual.yview_scroll(1, "units")
            return True
        atual = getattr(atual, "master", None)
    return False


def _combo_ao_rolar(combo, event):
    """Impede trocar o valor com a roda; com lista aberta, não rola a página."""
    if _combo_popdown_aberto(combo):
        return "break"
    _rolar_canvas_ancestral(combo, event)
    return "break"


def _vincular_combo_fecha_ao_rolar(combo):
    def _ao_roda(event, c=combo):
        return _combo_ao_rolar(c, event)

    def _ao_roda_popdown(event, c=combo):
        # Lista aberta: deixa o Listbox rolar; bloqueia a página.
        if event.widget.winfo_class() == "Listbox":
            return None
        return "break"

    def _ligar_popdown(_event=None, c=combo):
        try:
            nome = c.tk.call("ttk::combobox::PopdownWindow", c)
            raiz = c.nametowidget(nome)
        except (tk.TclError, KeyError):
            return
        alvos = [raiz]
        fila = [raiz]
        while fila:
            widget = fila.pop()
            try:
                filhos = widget.winfo_children()
            except tk.TclError:
                continue
            alvos.extend(filhos)
            fila.extend(filhos)
        for alvo in alvos:
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                if alvo.winfo_class() == "Listbox":
                    # Consome o evento depois do Listbox nativo? Bind sem break
                    # no ancestral já impede a página; no Listbox não interferimos.
                    continue
                alvo.bind(seq, _ao_roda_popdown)

    for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        combo.bind(seq, _ao_roda)
    combo.bind("<ButtonPress-1>", lambda _e: combo.after(1, _ligar_popdown), add="+")
    combo.bind("<Down>", lambda _e: combo.after(1, _ligar_popdown), add="+")
    combo.after_idle(_ligar_popdown)


def _formatar_bdi(valor):
    try:
        texto = f"{float(valor):.2f}".replace(".", ",")
        return texto
    except (TypeError, ValueError):
        return str(valor)


# Campo ou quantitativo da aba 1 -> parte que acende na visão isométrica.
PARTES_ISOMETRICA = {
    "qtd_pavimentos": "pavimentos",
    "pe_direito_m": "pe_direito",
    "perimetro_paredes_externas_bloco_m": "paredes",
    "perimetro_paredes_externas_total_m": "paredes",
    "area_fachada_bloco_m2": "paredes",
    "area_fachada_total_m2": "paredes",
    "perimetro_platibanda_bloco_m": "platibanda",
    "perimetro_platibanda_total_m": "platibanda",
    "altura_platibanda_m": "platibanda",
    "area_construida_m2": "cobertura",
    "qtd_aguas_telhado": "cobertura",
    "perimetro_beiral_m": "beiral",
    "area_cobertura_total_m2": "cobertura",
}


class AreaComumFrame(tk.Frame):
    def __init__(self, parent, ctx, on_voltar, *, offline=False):
        cores = cores_tema(parent)
        super().__init__(parent, bg=cores.fundo)
        self._cores = cores
        self._estilos = estilos_botao(self)
        self._cg = cores_grade(self)
        self.ctx = ctx
        self.on_voltar = on_voltar
        self._offline = bool(offline)
        self._refs_icones = []
        self._sujo = False
        self._carregando = False
        self._sincronizando_percentuais = False
        self._pct_em_edicao = {}
        self._ocupado = False
        self._composicoes_ciclo = None
        self._avisos_ultima_carga = []
        self._total_geral_ultimo = None
        self._observacoes = ""
        self._grade_pendente = False
        self._referencias_ultimo_calculo = None
        self._destaque_mouse = None
        self._destaque_foco = None
        self._entradas_caracteristicas: set = set()
        self._perguntando_uf = False
        self._aplicando_historico = False
        self._caminho_arquivo = None
        self._pular_oferta_autosave = False
        self._job_autosave = None
        self._job_municipio = None
        self._job_calculo = None
        self._job_feedback = None
        self._historico_undo = []
        self._historico_redo = []
        self._snapshot_base = None
        self._binds_historico = []
        self._catalogo = {}
        self._quantitativos = {}
        self._quantitativos_por_local: dict = {}
        self._locais: list[tuple[str, str]] = [(LOCAL_RESIDENCIAL, "Blocos residenciais")]
        self._anomalias_orcamento = []
        self._etapas = []
        self._etapa_por_id = {}
        self._etapa_por_rotulo = {}
        self.orcamento = OrcamentoCustomizado()
        self._orcamento_customizado_id = ""
        self._grade_focar_meta = None
        self.entrada_nome = None
        self.entrada_municipio = None
        self.combo_uf = None
        self.combo_uf_dados = None
        self._janela_orccad = None
        self._orccad_estrutura_id = None

        self.var_nome = tk.StringVar()
        self.var_municipio = tk.StringVar()
        self.var_uf = tk.StringVar(value=PLACEHOLDER_ESTADO)
        self.var_bdi = tk.StringVar(value=BDI_PADRAO)
        self.var_arquivo = tk.StringVar(value="Rascunho novo")
        self.var_feedback = tk.StringVar(value="")
        self.var_total = tk.StringVar(value="Total geral: R$ 0,00")
        self.var_variacao_total = tk.StringVar(value="")
        self._job_variacao_total = None
        self.var_catalogo_anomalia = tk.StringVar()
        self.var_considerar_sp = tk.BooleanVar(value=True)
        self.var_considerar_pintura = tk.BooleanVar(value=True)
        self.var_duas_demaos_selador = tk.BooleanVar(value=True)
        self.var_considerar_entulho = tk.BooleanVar(value=True)
        self.var_considerar_limpeza = tk.BooleanVar(value=True)
        self._pintura_fachada_manual = False
        self.var_percentual_pintura = tk.StringVar(value="—")
        self.var_valor_etapas = {
            "servicos_preliminares": tk.StringVar(value="(—)"),
            "pintura": tk.StringVar(value="(—)"),
            "destinacao_entulho": tk.StringVar(value="(—)"),
            "limpeza_geral": tk.StringVar(value="(—)"),
        }
        self.var_rotulo_condominio = tk.StringVar(value="")

        self._montar()
        self._vincular_sujeira()
        self._vincular_historico_teclado()
        self.ctx.registrar_callback_sinapi(self._ao_atualizar_sinapi)
        self.bind("<Destroy>", self._ao_destruir)
        self.after_idle(self._iniciar_historico)
        self.after_idle(self._oferecer_autosave)

    def focar(self):
        try:
            if self.entrada_nome is not None:
                self.entrada_nome.focus_set()
        except tk.TclError:
            pass

    # ------------------------------------------------- troca de tema
    # Trocar o tema recria a tela; o app pede uma "foto" do trabalho à tela
    # antiga e entrega à nova, com arquivo, "não salvo", histórico e aba.

    def exportar_estado_tema(self) -> dict:
        try:
            aba = self.notebook.index("current")
        except tk.TclError:
            aba = 0
        return {
            "dados": self._capturar_snapshot(),
            "caminho": self._caminho_arquivo,
            "sujo": self._sujo,
            "undo": list(self._historico_undo),
            "redo": list(self._historico_redo),
            "aba": aba,
        }

    def importar_estado_tema(self, estado: dict) -> None:
        # A tela nova não deve perguntar sobre o autosave: o trabalho vem daqui.
        self._pular_oferta_autosave = True
        erro = self._aplicar_rascunho_seguro(
            estado["dados"], caminho=estado.get("caminho"), normalizar=False
        )
        if erro is not None:
            print(f"[ORC] Área Comum: falha ao restaurar após troca de tema: {erro}")
            self._pular_oferta_autosave = False
            return
        self._sujo = bool(estado.get("sujo"))
        self._atualizar_rotulo_arquivo()
        self._historico_undo[:] = estado.get("undo") or []
        self._historico_redo[:] = estado.get("redo") or []
        self._snapshot_base = self._capturar_snapshot()
        self._atualizar_botoes_historico()
        try:
            self.notebook.select(int(estado.get("aba") or 0))
        except (tk.TclError, ValueError):
            pass

    def _texto_referencia(self):
        ref = self.ctx.sinapi_referencia_rotulo
        if ref == "BASE AUSENTE":
            return "Base não carregada"
        return f"Referência SINAPI: {ref}"

    def _voltar(self):
        self._flush_autosave()
        self.on_voltar()

    def _confirmar_saida(self, mensagem=None) -> bool:
        if not self._sujo or not self._caminho_arquivo:
            self._flush_autosave()
            return True
        if not rascunho_tem_conteudo(self._coletar_rascunho()):
            return True
        resposta = messagebox.askyesnocancel(
            "Rascunho não salvo",
            mensagem
            or (
                "Este arquivo JSON tem alterações que ainda não foram gravadas.\n"
                "Deseja salvar antes de continuar?"
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

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        self._montar_aba_dados()
        self._montar_aba_anomalias()
        self._montar_aba_orcamento()
        self._montar_rodape()
        self._catalogo = carregar_catalogo()
        if hasattr(self, "campo_catalogo"):
            self.campo_catalogo.definir_opcoes(nomes_anomalias(self._catalogo))
        self._carregar_etapas()
        self._atualizar_rotulo_condominio()
        self._atualizar_previa_desenho()
        self.notebook.bind("<<NotebookTabChanged>>", self._ao_trocar_aba)
        self.after_idle(self._recalcular)

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

        verde_salvar = "#81c784" if self._cores.escuro else "#2e7d32"
        btn_salvar = criar_botao_ttk_so_icone(
            bloco,
            nome_icone="save-outline",
            command=self._salvar,
            cor_icone=verde_salvar,
            refs=self._refs_icones,
        )
        btn_salvar.pack(side="left", padx=(4, 0))
        vincular_tooltip(btn_salvar, "Salvar rascunho JSON (Ctrl+S)")

        btn_salvar_como = criar_botao_ttk_so_icone(
            bloco,
            nome_icone="save-copy-outline",
            command=lambda: self._salvar(salvar_como=True),
            cor_icone=verde_salvar,
            refs=self._refs_icones,
        )
        btn_salvar_como.pack(side="left", padx=(4, 0))
        vincular_tooltip(btn_salvar_como, "Salvar como — outro arquivo JSON")

        self._montar_rotulo_condominio(barra)

    def _montar_rotulo_arquivo(self, parent):
        tk.Label(
            parent,
            textvariable=self.var_arquivo,
            font=("Segoe UI", 9),
            fg=self._cores.texto_suave,
            bg=self._cores.fundo,
        ).pack(side="right", padx=(0, 12))

    def _montar_rotulo_condominio(self, parent):
        cores = self._cores
        tk.Label(
            parent,
            textvariable=self.var_rotulo_condominio,
            font=("Segoe UI", 11, "bold"),
            fg=cores.titulo,
            bg=cores.fundo,
            anchor="w",
        ).pack(side="left", padx=(16, 8))

    def _montar_condominio_dados(self, parent):
        cores = self._cores
        fundo = cores.fundo
        faixa = tk.Frame(parent, bg=fundo)
        faixa.pack(fill="x", pady=(10, 10), padx=12)

        tk.Label(faixa, text="Nome:", bg=fundo, fg=cores.texto).grid(row=0, column=0, sticky="w")
        self.entrada_nome = ttk.Entry(faixa, textvariable=self.var_nome)
        self.entrada_nome.grid(row=0, column=1, sticky="ew", padx=(6, 16))

        tk.Label(faixa, text="Município:", bg=fundo, fg=cores.texto).grid(
            row=0, column=2, sticky="w"
        )
        self.entrada_municipio = ttk.Entry(faixa, textvariable=self.var_municipio, width=28)
        self.entrada_municipio.grid(row=0, column=3, sticky="ew", padx=(6, 16))
        self.entrada_municipio.bind("<FocusOut>", self._ao_sair_municipio)

        tk.Label(faixa, text="UF:", bg=fundo, fg=cores.texto).grid(row=0, column=4, sticky="w")
        self.combo_uf_dados = ttk.Combobox(
            faixa,
            textvariable=self.var_uf,
            values=valores_combo_estado(self.ctx.obter_estados()),
            width=16,
            state="readonly",
        )
        self.combo_uf_dados.grid(row=0, column=5, sticky="w", padx=(6, 0))
        self.combo_uf_dados.bind("<<ComboboxSelected>>", lambda _e: self._ao_alterar_campo())
        _vincular_combo_fecha_ao_rolar(self.combo_uf_dados)
        self.combo_uf = self.combo_uf_dados
        self.var_nome.trace_add("write", self._forcar_maiusculo_nome)
        self.var_municipio.trace_add("write", self._ao_digitar_municipio)
        self.var_nome.trace_add("write", lambda *_a: self._atualizar_rotulo_condominio())
        self.var_municipio.trace_add("write", lambda *_a: self._atualizar_rotulo_condominio())
        self.var_uf.trace_add("write", lambda *_a: self._atualizar_rotulo_condominio())

        faixa.columnconfigure(1, weight=3)
        faixa.columnconfigure(3, weight=2)

    def _montar_dados_orcamento(self, parent):
        cores = self._cores
        fundo = cores.fundo
        faixa = tk.LabelFrame(
            parent,
            text="Dados do orçamento",
            bg=fundo,
            fg=cores.texto,
            padx=8,
            pady=6,
        )
        faixa.pack(side="left", padx=(12, 0), anchor="n")

        linha_dados = tk.Frame(faixa, bg=fundo)
        linha_dados.pack(fill="x", pady=(0, 4))
        tk.Label(linha_dados, text="BDI (%):", bg=fundo, fg=cores.texto).pack(side="left")
        self.entrada_bdi = ttk.Entry(linha_dados, textvariable=self.var_bdi, width=8)
        self.entrada_bdi.pack(side="left", padx=(4, 0))
        self._vincular_campo_numerico(self.entrada_bdi)

        linha_botoes = tk.Frame(faixa, bg=fundo)
        linha_botoes.pack(fill="x")
        btn_gerar_itens = criar_botao_ttk_com_icone(
            linha_botoes,
            texto="Gerar itens novamente",
            nome_icone="construct-outline",
            command=self._gerar_orcamento,
            estilo=self._estilos.compacto,
            cor_icone=self._estilos.icone,
            refs=self._refs_icones,
        )
        btn_gerar_itens.pack(side="left")
        vincular_tooltip(
            btn_gerar_itens,
            "Recalcula as etapas e itens a partir das anomalias e percentuais",
        )

    def _ligar_destaque_isometrico(self, widgets, parte, *, campo=None):
        """Acende `parte` na visão isométrica com o mouse sobre `widgets`
        e, se houver `campo`, enquanto ele estiver sendo editado."""
        alvos = set()
        pendentes = [w for w in widgets if w is not None]
        while pendentes:
            w = pendentes.pop()
            alvos.add(w)
            pendentes.extend(w.winfo_children())

        def entrar(_event=None):
            self._destaque_mouse = parte
            self._aplicar_destaque_isometrico()

        def conferir_saida():
            # Passar do quadro para um texto dentro dele também gera "saiu";
            # só apaga se o mouse realmente deixou o conjunto.
            try:
                sob = self.winfo_containing(*self.winfo_pointerxy())
            except (tk.TclError, KeyError):
                sob = None
            if sob in alvos:
                return
            if self._destaque_mouse == parte:
                self._destaque_mouse = None
                self._aplicar_destaque_isometrico()

        for w in alvos:
            w.bind("<Enter>", entrar, add="+")
            w.bind("<Leave>", lambda _e: self.after(15, conferir_saida), add="+")
        if campo is not None:

            def focar(_event=None):
                self._destaque_foco = parte
                self._aplicar_destaque_isometrico()

            def desfocar(_event=None):
                if self._destaque_foco == parte:
                    self._destaque_foco = None
                    self._aplicar_destaque_isometrico()

            campo.bind("<FocusIn>", focar, add="+")
            campo.bind("<FocusOut>", desfocar, add="+")

    def _aplicar_destaque_isometrico(self):
        vista = getattr(self, "vista_bloco", None)
        if vista is not None:
            vista.destacar(self._destaque_mouse or self._destaque_foco)

    def _vincular_selecionar_tudo(self, widget):
        def _selecionar(_event=None):
            def aplicar():
                try:
                    widget.select_range(0, "end")
                    widget.icursor("end")
                except tk.TclError:
                    pass

            widget.after_idle(aplicar)

        def _ao_clicar(_event):
            widget.focus_set()
            _selecionar()
            return "break"

        widget.bind("<FocusIn>", _selecionar, add="+")
        widget.bind("<Button-1>", _ao_clicar, add="+")

    def _vincular_campo_numerico(self, widget, *, percentual=False, casas=None):
        self._vincular_selecionar_tudo(widget)
        widget.bind(
            "<FocusOut>",
            lambda _e, p=percentual, c=casas: self._resolver_formula(
                widget, percentual=p, casas=c
            ),
            add="+",
        )

    def _resolver_formula(self, widget, *, percentual=False, casas=None):
        try:
            bruto = widget.get().strip()
        except tk.TclError:
            return
        novo = _texto_campo_numerico(bruto, percentual=percentual, casas=casas)
        if novo == bruto:
            return
        try:
            widget.delete(0, "end")
            widget.insert(0, novo)
        except tk.TclError:
            pass

    def _montar_aba_dados(self):
        self.aba_dados = AbaDadosIniciais(self, self.notebook)
        self.previa_desenho = self.aba_dados.planta
        self.vista_bloco = self.aba_dados.iso

    @property
    def var_percentuais(self) -> dict:
        """Percentuais da aba 1 que a aba 2 lê e grava.

        Os de cobertura, fachada e hall valem para todos os blocos
        residenciais; os de caixas e calçadas, para o condomínio.
        """
        return self.aba_dados.percentuais_aba2()

    def _tipos_para_reparo(self, local=LOCAL_RESIDENCIAL) -> tuple[str, str]:
        """Tipo de estrutura e de cobertura usados para sugerir o reparo."""
        do_local = self.aba_dados.estruturas_do_local(local)
        estrutura = (do_local[0] if do_local else None) or self.aba_dados.atual
        if estrutura is None:
            return "", ""
        return (
            estado_do_combo(estrutura.var_tipo_estrutura.get()),
            estado_do_combo(estrutura.var_tipo_cobertura.get()),
        )

    def _estruturas_mudaram(self, descricao: str) -> None:
        """Estrutura adicionada ou removida na aba 1."""
        self._marcar_sujo()
        self._registrar_historico(descricao)
        self._recalcular()
        self._redesenhar_anomalias_orcamento()

    def _anomalias_no_local(self, local) -> list[dict]:
        return [
            linha for linha in self._anomalias_orcamento
            if str(linha.get("local") or LOCAL_RESIDENCIAL) == local
        ]

    def _remover_anomalias_do_local(self, local) -> None:
        """A estrutura foi removida: as anomalias dela saem junto."""
        self._anomalias_orcamento = [
            linha for linha in self._anomalias_orcamento
            if str(linha.get("local") or LOCAL_RESIDENCIAL) != local
        ]

    def _escolher_local(self, titulo, mensagem, atual=LOCAL_RESIDENCIAL):
        """Lista dos locais; devolve a chave escolhida ou None."""
        rotulos = [rotulo for _chave, rotulo in self._locais]
        chave_por_rotulo = {rotulo: chave for chave, rotulo in self._locais}
        escolhido = self._escolher_lista(
            titulo,
            mensagem,
            rotulos,
            selecionar=dict(self._locais).get(atual),
        )
        return chave_por_rotulo.get(escolhido) if escolhido else None

    def _alterar_local_anomalia(self, item_id):
        linha = next(
            (item for item in self._anomalias_orcamento if item.get("id") == item_id),
            None,
        )
        if linha is None:
            return
        atual = self._local_da_linha(linha)
        nome = linha.get("nome") or "anomalia"
        novo = self._escolher_local("Local da anomalia", f"Onde acontece «{nome}»?", atual)
        if novo is None or novo == atual:
            return
        reparo = self._reparo_da_linha(linha) or {}
        faltantes = self._coletar_percentuais_faltantes(reparo, novo)
        if faltantes is None:
            return
        self._gravar_percentuais_aba1(faltantes, novo)
        linha["local"] = novo
        self._aplicar_percentuais_aba1(
            list(reparo.get("percentuais_aba1") or []),
            linha.get("percentual") or "100",
            origem_nome=nome,
            excluir_id=linha.get("id"),
            local=novo,
        )
        self._marcar_sujo()
        self._registrar_historico("Alterar local da anomalia")
        self._recalcular()
        self._redesenhar_anomalias_orcamento()
        if hasattr(self, "tree_anomalias") and self.tree_anomalias.exists(item_id):
            self.tree_anomalias.selection_set(item_id)
            self.tree_anomalias.see(item_id)

    def _ao_modificar_observacoes(self, _event=None):
        """Mantém uma cópia do texto fora do widget.

        Ao fechar o módulo, o Tk destrói a caixa de texto antes de avisar o
        módulo; sem esta cópia, o último autosave não conseguia ler as
        observações e falhava.
        """
        try:
            self._observacoes = self.texto_obs.get("1.0", "end").strip()
            self.texto_obs.edit_modified(False)
        except tk.TclError:
            pass

    def _texto_observacoes(self) -> str:
        try:
            self._observacoes = self.texto_obs.get("1.0", "end").strip()
        except tk.TclError:
            pass  # widget já destruído: usa a última cópia
        return self._observacoes

    def _montar_aba_anomalias(self):
        cores = self._cores
        fundo = cores.fundo
        aba = ttk.Frame(self.notebook)
        self.notebook.add(aba, text="2. Anomalias")
        self._aba_anomalias = aba

        topo = tk.Frame(aba, bg=fundo)
        topo.pack(fill="x", padx=10, pady=(8, 4))
        # Empacota o botão primeiro (side=right) para não ser empurrado pelo texto.
        criar_botao_ttk_com_icone(
            topo,
            texto="Configurar",
            nome_icone="cog-outline",
            command=self._abrir_config_anomalias,
            estilo=self._estilos.compacto,
            cor_icone=self._estilos.icone,
            refs=self._refs_icones,
        ).pack(side="right", padx=(8, 0))

        form = tk.Frame(aba, bg=fundo)
        form.pack(fill="x", padx=10, pady=(0, 6))
        tk.Label(form, text="Anomalia:", bg=fundo, fg=cores.texto).pack(side="left")
        self.campo_catalogo = CampoListaPesquisavel(
            form,
            textvariable=self.var_catalogo_anomalia,
            largura_minima_lista=380,
            bg=fundo,
        )
        self.campo_catalogo.pack(side="left", fill="x", expand=True, padx=8)
        criar_botao_ttk_com_icone(
            form,
            texto="Adicionar anomalia",
            nome_icone="add-circle-outline",
            command=self._adicionar_anomalia_catalogo,
            estilo=self._estilos.compacto_adicionar,
            cor_icone=self._estilos.icone_adicionar,
            refs=self._refs_icones,
        ).pack(side="left")

        tabela = tk.Frame(aba, bg=fundo)
        tabela.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        self._estilizar_tree_anomalias()
        self.tree_anomalias = ttk.Treeview(
            tabela,
            columns=("local", "reparo", "percentual", "valor", "valor_atual"),
            show="tree headings",
            selectmode="browse",
            style="Anomalias.Treeview",
        )
        self.tree_anomalias.tag_configure("par", background=self._cor_linha_par)
        self.tree_anomalias.tag_configure("impar", background=self._cor_linha_impar)
        self.tree_anomalias.tag_configure("aviso", background=self._cor_linha_aviso)
        self.tree_anomalias.heading("#0", text="Anomalia")
        self.tree_anomalias.heading("local", text="Local", anchor="w")
        self.tree_anomalias.heading("reparo", text="Reparo", anchor="center")
        self.tree_anomalias.heading("percentual", text="% qtd.", anchor="center")
        self.tree_anomalias.heading("valor", text="Quantitativo considerado", anchor="e")
        self.tree_anomalias.heading("valor_atual", text="Valor atual", anchor="e")
        self.tree_anomalias.column("#0", width=260)
        self.tree_anomalias.column("local", width=150, anchor="w")
        self.tree_anomalias.column("reparo", width=200, anchor="center")
        # "% qtd." e "Valor atual" têm conteúdo curto: largura fixa, sem esticar.
        # O espaço que sobra na tela vai para as colunas de texto.
        self.tree_anomalias.column("percentual", width=58, minwidth=50, anchor="center",
                                   stretch=False)
        self.tree_anomalias.column("valor", width=220, anchor="e")
        self.tree_anomalias.column("valor_atual", width=118, minwidth=100, anchor="e",
                                   stretch=False)
        self.tree_anomalias.bind("<Button-1>", self._ao_clique_percentual_anomalia, add="+")
        self.tree_anomalias.bind("<Double-1>", self._ao_duplo_clique_anomalia)
        self.tree_anomalias.bind("<Motion>", self._ao_mover_tree_anomalias)
        self.tree_anomalias.bind("<Leave>", self._ao_sair_tree_anomalias)
        self.tree_anomalias.bind("<MouseWheel>", self._esconder_dica_anomalia, add="+")
        self.tree_anomalias.bind("<Escape>", self._limpar_selecao_anomalias)
        janela = self.winfo_toplevel()
        janela.bind("<Escape>", self._ao_esc_anomalias, add="+")
        janela.bind("<Button-1>", self._ao_clique_fora_anomalias, add="+")

        scroll = ttk.Scrollbar(tabela, orient="vertical", command=self.tree_anomalias.yview)
        self.tree_anomalias.configure(yscrollcommand=scroll.set)
        self.tree_anomalias.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        rodape_anom = tk.Frame(aba, bg=fundo)
        rodape_anom.pack(fill="x", padx=10, pady=(0, 10))
        botoes_anom = tk.Frame(rodape_anom, bg=fundo)
        botoes_anom.pack(side="left")
        criar_botao_ttk_com_icone(
            botoes_anom,
            texto="Remover selecionada",
            nome_icone="trash-outline",
            command=self._remover_anomalia_orcamento,
            estilo=self._estilos.compacto_excluir,
            cor_icone=self._estilos.icone_excluir,
            refs=self._refs_icones,
        ).pack(side="left")
        criar_botao_ttk_com_icone(
            botoes_anom,
            texto="Alterar porcentagem",
            nome_icone="pencil",
            command=self._alterar_percentual_anomalia,
            estilo=self._estilos.compacto_editar,
            cor_icone=self._estilos.icone_editar,
            refs=self._refs_icones,
        ).pack(side="left", padx=(6, 0))

        caixa_etapas = tk.LabelFrame(
            rodape_anom,
            text="Etapas padrão do orçamento",
            bg=fundo,
            fg=cores.texto,
            padx=8,
            pady=4,
        )
        caixa_etapas.pack(side="right")
        cor_valor_etapa = "#6e6e6e" if not cores.escuro else "#c4c4c4"
        self._opcao_etapa_padrao(
            caixa_etapas,
            texto="Serviços Preliminares",
            variavel=self.var_considerar_sp,
            var_valor=self.var_valor_etapas["servicos_preliminares"],
            rotulo="Serviços preliminares",
            cor_valor=cor_valor_etapa,
            separador=True,
        )
        self._opcao_etapa_padrao(
            caixa_etapas,
            texto="Pintura",
            variavel=self.var_considerar_pintura,
            var_valor=self.var_valor_etapas["pintura"],
            var_extra=self.var_percentual_pintura,
            rotulo="Pintura",
            cor_valor=cor_valor_etapa,
            separador=True,
        )
        self._opcao_etapa_padrao(
            caixa_etapas,
            texto="Destinação do Entulho",
            variavel=self.var_considerar_entulho,
            var_valor=self.var_valor_etapas["destinacao_entulho"],
            rotulo="Destinação do entulho",
            cor_valor=cor_valor_etapa,
            separador=True,
        )
        self._opcao_etapa_padrao(
            caixa_etapas,
            texto="Limpeza Geral",
            variavel=self.var_considerar_limpeza,
            var_valor=self.var_valor_etapas["limpeza_geral"],
            rotulo="Limpeza geral",
            cor_valor=cor_valor_etapa,
            separador=False,
        )

    def _opcao_etapa_padrao(
        self,
        parent,
        *,
        texto,
        variavel,
        var_valor,
        rotulo,
        cor_valor,
        separador,
        var_extra=None,
    ):
        fundo = self._cores.fundo
        ttk.Checkbutton(
            parent,
            text=texto,
            variable=variavel,
            command=lambda: self._ao_trocar_etapa_fixa(rotulo, variavel),
        ).pack(side="left")
        if var_extra is not None:
            tk.Label(
                parent,
                textvariable=var_extra,
                bg=fundo,
                fg=cor_valor,
                font=("Segoe UI", 9),
            ).pack(side="left", padx=(6, 0))
        tk.Label(
            parent,
            textvariable=var_valor,
            bg=fundo,
            fg=cor_valor,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(4, 0))
        if separador:
            tk.Label(
                parent,
                text="|",
                bg=fundo,
                fg=self._cores.texto,
                font=("Segoe UI", 9),
            ).pack(side="left", padx=(8, 8))

    def _criar_halo(self, parent, *, padx=3, pady=2):
        return tk.Frame(parent, bg=self._cores.fundo, padx=padx, pady=pady)

    def _montar_aba_orcamento(self):
        cores = self._cores
        fundo = cores.fundo
        aba = ttk.Frame(self.notebook)
        self.notebook.add(aba, text="3. Orçamento")
        self._aba_orcamento = aba

        interior = tk.Frame(aba, bg=fundo)
        interior.pack(fill="both", expand=True)

        linha_acoes = tk.Frame(interior, bg=fundo)
        linha_acoes.pack(fill="x", padx=8, pady=(8, 6))

        bloco_atalhos = tk.Frame(linha_acoes, bg=fundo)
        bloco_atalhos.pack(side="right", anchor="n", pady=(2, 0))
        self._montar_botao_calculadora(bloco_atalhos, side="right")
        self.var_mostrar_legenda = tk.BooleanVar(
            value=bool(obter_pref("legenda_grade_orcamento", True))
        )
        chk_legenda = ttk.Checkbutton(
            bloco_atalhos,
            text="Legenda",
            variable=self.var_mostrar_legenda,
            command=self._ao_alternar_legenda,
            style="Fundo.TCheckbutton",
        )
        chk_legenda.pack(side="right", padx=(0, 2))
        vincular_tooltip(chk_legenda, "Mostrar ou ocultar a legenda de cores da grade")

        frame_etapas = tk.LabelFrame(
            linha_acoes,
            text="Etapas e itens",
            bg=fundo,
            fg=cores.texto,
            padx=8,
            pady=6,
        )
        frame_etapas.pack(side="left", anchor="n")

        linha_etapas_1 = tk.Frame(frame_etapas, bg=fundo)
        linha_etapas_1.pack(fill="x", pady=(0, 4))
        halo_nova = self._criar_halo(linha_etapas_1)
        halo_nova.pack(side="left", padx=(0, 4))
        criar_botao_ttk_com_icone(
            halo_nova,
            texto="Nova etapa",
            nome_icone="add-circle-outline",
            command=self._adicionar_extra_etapa,
            estilo=self._estilos.compacto_adicionar,
            cor_icone=self._estilos.icone_adicionar,
            refs=self._refs_icones,
        ).pack()

        linha_etapas_2 = tk.Frame(frame_etapas, bg=fundo)
        linha_etapas_2.pack(fill="x")
        alinhador_remover = self._criar_halo(linha_etapas_2)
        alinhador_remover.pack(side="left", padx=(0, 4))
        criar_botao_ttk_com_icone(
            alinhador_remover,
            texto="Remover etapa/item",
            nome_icone="remove-circle-outline",
            command=self._remover_extra,
            estilo=self._estilos.compacto_excluir,
            cor_icone=self._estilos.icone_excluir,
            refs=self._refs_icones,
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
            bg=fundo,
            fg=cores.texto,
            padx=8,
            pady=6,
        )
        frame_inserir.pack(side="left", padx=(12, 0), anchor="n")

        linha_inserir_1 = tk.Frame(frame_inserir, bg=fundo)
        linha_inserir_1.pack(fill="x", pady=(0, 4))
        criar_botao_inserir_prominente(
            linha_inserir_1,
            texto="Inserir item SINAPI",
            command=self._abrir_busca_sinapi,
            refs=self._refs_icones,
        ).pack(side="left", padx=(0, 6))
        criar_botao_inserir_prominente(
            linha_inserir_1,
            texto="Inserir composição própria",
            command=self._adicionar_composicao_propria,
            refs=self._refs_icones,
        ).pack(side="left")

        linha_inserir_2 = tk.Frame(frame_inserir, bg=fundo)
        linha_inserir_2.pack(fill="x")
        tk.Label(
            linha_inserir_2, text="Rápido — Cód.:", bg=fundo, fg=cores.texto
        ).pack(side="left")
        self.var_codigo_rapido = tk.StringVar()
        entrada_cod = ttk.Entry(
            linha_inserir_2, textvariable=self.var_codigo_rapido, width=10
        )
        entrada_cod.pack(side="left", padx=(4, 8))
        tk.Label(linha_inserir_2, text="Qtd.:", bg=fundo, fg=cores.texto).pack(
            side="left"
        )
        self.var_qtd_rapido = tk.StringVar(value="1")
        entrada_qtd = ttk.Entry(
            linha_inserir_2, textvariable=self.var_qtd_rapido, width=10
        )
        entrada_qtd.pack(side="left", padx=(4, 8))
        ttk.Button(
            linha_inserir_2,
            text="Inserir",
            command=self._inserir_rapido,
            style=self._estilos.compacto,
        ).pack(side="left")
        entrada_cod.bind("<Return>", lambda _e: self._inserir_rapido())
        entrada_qtd.bind("<Return>", lambda _e: self._inserir_rapido())

        self._montar_dados_orcamento(linha_acoes)

        tabela = tk.Frame(interior, bg=fundo)
        tabela.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._montar_filtro_grade(tabela)
        self.grade = GradeOrcamento(
            tabela,
            on_duplo_clique_qtd=self._dialogo_editar_quantidade,
            on_duplo_clique_codigo=self._editar_item_sinapi,
            on_salvar_nome_grupo=self._salvar_nome_grupo_inline,
            on_tecla_delete=lambda _e: self._remover_extra(),
            on_reordenar_item=self._ao_reordenar_item_arraste,
            on_reordenar_etapa=self._ao_reordenar_etapa_arraste,
            on_menu_contexto=self._ao_menu_contexto_grade,
            on_previa_composicao=self._abrir_previa_composicao,
        )
        self.grade.pack(fill="both", expand=True)
        # Quando a grade aparece (troca de aba ou volta ao módulo), redesenha
        # se algum cálculo aconteceu enquanto ela estava escondida.
        self.grade.bind("<Map>", self._ao_mostrar_grade, add="+")
        self._montar_legenda_grade(tabela)

    def _montar_filtro_grade(self, parent):
        fundo = self._cores.fundo
        self._barra_filtro_grade = tk.Frame(parent, bg=fundo)
        criar_label_icone(
            self._barra_filtro_grade,
            "funnel-outline",
            texto="Filtrar:",
            bg=fundo,
            fg=self._cores.texto_suave,
            cor=self._cores.titulo,
            refs=self._refs_icones,
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
            bg=fundo,
            fg=self._cores.texto_suave,
            font=("Arial", 8),
        ).pack(side="left")
        btn_fechar = tk.Label(
            self._barra_filtro_grade,
            text="✕",
            bg=fundo,
            fg=self._cores.texto_suave,
            font=("Arial", 9),
            cursor="hand2",
            padx=2,
            pady=0,
        )
        btn_fechar.pack(side="left", padx=(4, 0))
        btn_fechar.bind("<Button-1>", lambda _e: self._ocultar_filtro_grade())
        btn_fechar.bind("<Enter>", lambda _e: btn_fechar.configure(fg=self._cores.texto))
        btn_fechar.bind(
            "<Leave>", lambda _e: btn_fechar.configure(fg=self._cores.texto_suave)
        )
        vincular_tooltip(btn_fechar, "Fechar filtro (Esc)")
        self._entrada_filtro_grade.bind("<Escape>", self._ocultar_filtro_grade)

    def _aba_orcamento_visivel(self) -> bool:
        aba = getattr(self, "_aba_orcamento", None)
        if aba is None or not hasattr(self, "notebook"):
            return False
        try:
            return str(self.notebook.select()) == str(aba)
        except tk.TclError:
            return False

    def _ao_tecla_filtro_grade(self, event):
        try:
            if not self.winfo_ismapped():
                return
            if event.widget.winfo_toplevel() is not self.winfo_toplevel():
                return
        except tk.TclError:
            return
        if not self._aba_orcamento_visivel():
            return
        if (
            not self._widget_do_modulo(event.widget)
            and event.widget is not self.winfo_toplevel()
        ):
            return
        return self._mostrar_filtro_grade(event)

    def _mostrar_filtro_grade(self, _event=None):
        barra = getattr(self, "_barra_filtro_grade", None)
        entrada = getattr(self, "_entrada_filtro_grade", None)
        if barra is None or entrada is None or not hasattr(self, "grade"):
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

    def _montar_rodape(self):
        cores = self._cores
        barra = cores.fundo_barra
        rodape = tk.Frame(
            self, bg=barra, highlightbackground=cores.borda_suave, highlightthickness=1
        )
        rodape.pack(fill="x", padx=12, pady=(0, 8))
        linha = tk.Frame(rodape, bg=barra)
        linha.pack(fill="x")

        historico = tk.Frame(linha, bg=barra)
        historico.pack(side="left", padx=10, pady=6)
        self.btn_desfazer = criar_botao_ttk_so_icone(
            historico,
            nome_icone="arrow-undo-sharp",
            command=self._desfazer,
            cor_icone=self._estilos.icone,
            refs=self._refs_icones,
        )
        self.btn_desfazer.pack(side="left", padx=(0, 4))
        vincular_tooltip(self.btn_desfazer, "Desfazer (Ctrl+Z)")
        definir_estado_botao_icone(self.btn_desfazer, "disabled")

        self.btn_refazer = criar_botao_ttk_so_icone(
            historico,
            nome_icone="arrow-redo-sharp",
            command=self._refazer,
            cor_icone=self._estilos.icone,
            refs=self._refs_icones,
        )
        self.btn_refazer.pack(side="left", padx=(0, 10))
        vincular_tooltip(self.btn_refazer, "Refazer (Ctrl+Y)")
        definir_estado_botao_icone(self.btn_refazer, "disabled")

        self.lbl_feedback = tk.Label(
            linha,
            textvariable=self.var_feedback,
            font=("Arial", 10, "bold"),
            fg="#ffb74d" if cores.escuro else "#a67c00",
            bg=barra,
            anchor="w",
        )
        self.lbl_feedback.pack(side="left", fill="x", expand=True, padx=(0, 12))

        container_exportar = tk.Frame(linha, bg=barra)
        container_exportar.pack(side="right", padx=10, pady=6)
        self.btn_salvar_customizados = criar_botao_ttk_com_icone(
            container_exportar,
            texto="Salvar em Orçamentos Customizados",
            nome_icone="save-outline",
            command=self._salvar_em_customizados,
            estilo=self._estilos.compacto,
            cor_icone=self._estilos.icone,
            refs=self._refs_icones,
        )
        self.btn_salvar_customizados.pack(side="left", padx=(0, 10))
        vincular_tooltip(
            self.btn_salvar_customizados,
            "Grava este orçamento na lista de Orçamentos Customizados",
        )

        kwargs_planilha = {
            "text": "Gerar Planilha",
            "command": self._exportar_planilha,
            "font": ("Arial", 10, "bold"),
            "fg": cores.texto if cores.escuro else "#000000",
            "activeforeground": cores.texto if cores.escuro else "#000000",
            "bg": barra,
            "activebackground": cores.fundo_hover,
            "relief": "flat",
            "bd": 0,
            "padx": 2,
            "pady": 0,
            "cursor": "hand2",
            "highlightthickness": 0,
        }
        caminho_excel = asset_path("icons", "excel-preto.png")
        if caminho_excel is not None:
            try:
                self._icone_excel_export = carregar_png_icone(
                    self, "excel-preto.png", inverter=bool(cores.escuro)
                )
                kwargs_planilha["image"] = self._icone_excel_export
                kwargs_planilha["compound"] = "right"
            except (FileNotFoundError, OSError, tk.TclError):
                pass
        self.btn_gerar_planilha = tk.Button(container_exportar, **kwargs_planilha)
        self.btn_gerar_planilha.pack(side="left", padx=(0, 16))
        vincular_tooltip(
            self.btn_gerar_planilha,
            "Gera a planilha Excel — disponível após salvar em Orçamentos Customizados",
        )

        # Variação do total após cada edição. Largura fixa para os botões ao
        # lado não mudarem de lugar quando o texto aparece e some.
        self.lbl_variacao_total = tk.Label(
            container_exportar,
            textvariable=self.var_variacao_total,
            font=("Arial", 10, "bold"),
            bg=barra,
            anchor="e",
            width=18,
        )
        self.lbl_variacao_total.pack(side="left", padx=(0, 6))
        vincular_tooltip(
            self.lbl_variacao_total,
            "Quanto o total mudou com a última alteração",
        )

        tk.Label(
            container_exportar,
            textvariable=self.var_total,
            font=("Arial", 11, "bold"),
            fg=cores.titulo,
            bg=barra,
            anchor="e",
        ).pack(side="left")
        self._atualizar_estado_planilha()

    def _vincular_scroll(self, canvas, interior):
        def _rolar(event):
            try:
                if not canvas.winfo_exists():
                    return
            except tk.TclError:
                return
            fila = [interior]
            while fila:
                widget = fila.pop()
                if isinstance(widget, ttk.Combobox):
                    if _combo_popdown_aberto(widget):
                        # Lista aberta: não rola a página por baixo.
                        return "break"
                try:
                    fila.extend(widget.winfo_children())
                except tk.TclError:
                    pass
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
            self.var_bdi,
        ]
        # Os campos das estruturas e do condomínio (aba 1) se ligam em AbaDadosIniciais.
        for var in variaveis:
            var.trace_add("write", self._ao_alterar_campo)

    def _forcar_maiusculo_nome(self, *_args):
        texto = self.var_nome.get()
        maiusculo = texto.upper()
        if texto == maiusculo:
            return
        widget = self._entrada_nome_focada()
        pos = None
        if widget is not None:
            try:
                pos = widget.index("insert")
            except tk.TclError:
                pos = None
        self.var_nome.set(maiusculo)
        if widget is not None and pos is not None:
            try:
                widget.icursor(pos)
            except tk.TclError:
                pass

    def _ao_digitar_municipio(self, *_args):
        texto = self.var_municipio.get()
        maiusculo = texto.upper()
        if texto != maiusculo:
            widget = self._entrada_municipio_focada()
            pos = None
            if widget is not None:
                try:
                    pos = widget.index("insert")
                except tk.TclError:
                    pos = None
            self.var_municipio.set(maiusculo)
            if widget is not None and pos is not None:
                try:
                    widget.icursor(pos)
                except tk.TclError:
                    pass
        if self._job_municipio is not None:
            try:
                self.after_cancel(self._job_municipio)
            except (tk.TclError, ValueError):
                pass
        self._job_municipio = self.after(DEBOUNCE_MUNICIPIO_MS, self._resolver_uf_municipio)

    def _entrada_nome_focada(self):
        return self._widget_focado(self.entrada_nome)

    def _entrada_municipio_focada(self):
        return self._widget_focado(self.entrada_municipio)

    def _widget_focado(self, *widgets):
        try:
            atual = self.focus_get()
        except tk.TclError:
            return None
        for widget in widgets:
            if widget is not None and atual is widget:
                return widget
        return None

    def _atualizar_rotulo_condominio(self):
        nome = self.var_nome.get().strip()
        municipio = self.var_municipio.get().strip()
        uf = estado_do_combo(self.var_uf.get())
        if municipio and uf:
            local = f"{municipio}/{uf}"
        else:
            local = municipio or uf
        if nome and local:
            texto = f"{nome} - {local}"
        else:
            texto = nome or local
        self.var_rotulo_condominio.set(texto)

    def _abrir_orccad(self):
        """Abre o ORCCAD com a planta da estrutura que está na tela."""
        from ui.orccad import JanelaORCCAD

        if self._janela_orccad is not None:
            try:
                if self._janela_orccad.janela.winfo_exists():
                    self._janela_orccad.trazer_frente()
                    return
            except tk.TclError:
                self._janela_orccad = None

        estrutura = self.aba_dados.atual
        if estrutura is None:
            return
        self._orccad_estrutura_id = estrutura.id
        self._janela_orccad = JanelaORCCAD(
            self.winfo_toplevel(),
            on_salvar_principal=self._ao_salvar_desenho_principal,
            on_fechar=self._ao_fechar_orccad,
            desenho_inicial=estrutura.desenho,
        )
        try:
            self._janela_orccad.janela.title(f"ORC — Desenho de metragens · {estrutura.nome}")
        except tk.TclError:
            pass

    def _ao_fechar_orccad(self):
        self._janela_orccad = None

    def _ao_salvar_desenho_principal(self, desenho, valores):
        estrutura = self.aba_dados.estrutura_por_id(self._orccad_estrutura_id)
        if estrutura is None:
            self._mostrar_feedback("A estrutura dessa planta foi removida.", "orange")
            return
        estrutura.desenho = deepcopy(
            desenho
            or {
                "externa": {"pontos": [], "fechado": False},
                "hall": {"pontos": [], "fechado": False},
            }
        )
        preenchidos = 0
        for chave, texto in (valores or {}).items():
            var = estrutura.vars_medida.get(chave)
            if var is not None and texto:
                var.set(texto)
                preenchidos += 1
        self.aba_dados.atual = estrutura
        self._atualizar_previa_desenho()
        self._marcar_sujo()
        self._registrar_historico(f"Planta de «{estrutura.nome}»")
        self._recalcular()
        self._mostrar_feedback(
            f"Planta de {estrutura.nome} salva: {preenchidos} campo(s) de metragem preenchido(s).",
            "green",
        )

    def _atualizar_previa_desenho(self):
        self.aba_dados.mostrar_desenho()

    def _atualizar_vista_bloco(self, *_args):
        self.aba_dados.mostrar_desenho()

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
        if (
            self._carregando
            or self._aplicando_historico
            or self._sincronizando_percentuais
        ):
            return
        self._marcar_sujo()
        self._agendar_calculo()
        self._registrar_historico("Editar dados", coalescer=True)

    def _ao_trocar_aba(self, _event=None):
        if self._carregando or self._aplicando_historico:
            return
        # Antes recalculava tudo a cada troca de aba. Agora só quando há
        # motivo: uma edição ainda não calculada ou um catálogo que mudou
        # fora deste módulo (composições, etapas, SINAPI, anomalias).
        if self._job_calculo is not None or self._dados_externos_mudaram():
            self._carregar_etapas()
            self._recalcular()
        else:
            self._preencher_grade_se_pendente()

    def _referencias_externas(self) -> tuple:
        """Objetos que mudam quando algum catálogo é alterado.

        Os armazenamentos trocam o objeto do cache a cada alteração; comparar
        com `is` (mesmo objeto?) é instantâneo, sem olhar o conteúdo.
        """
        composicoes = sys.modules.get("core.composicoes_proprias_storage")
        etapas = sys.modules.get("core.etapas_predefinidas_storage")
        return (
            getattr(composicoes, "_catalogo_cache", None),
            getattr(etapas, "_catalogo_cache", None),
            self.ctx.sinapi,
            self._catalogo,
        )

    def _dados_externos_mudaram(self) -> bool:
        anterior = self._referencias_ultimo_calculo
        if anterior is None:
            return True
        return any(a is not b for a, b in zip(self._referencias_externas(), anterior))

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
        for combo in (self.combo_uf, self.combo_uf_dados):
            if combo is None:
                continue
            try:
                combo.configure(values=estados)
            except tk.TclError:
                pass
        if atual in estados:
            self.var_uf.set(atual)
        elif estado_do_combo(atual) not in self.ctx.obter_estados():
            self.var_uf.set(PLACEHOLDER_ESTADO)
        self._atualizar_preview_orcamento()

    def _marcar_sujo(self):
        if self._carregando or self._aplicando_historico:
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
            salvar_autosave(dados, caminho_origem=self._caminho_arquivo)
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
        # Chamado direto (fora do agendamento), cancela o recálculo agendado
        # pela digitação; senão ele rodaria de novo logo depois, à toa.
        if self._job_calculo is not None:
            try:
                self.after_cancel(self._job_calculo)
            except (tk.TclError, ValueError):
                pass
        self._job_calculo = None
        self._sincronizar_percentual_pintura_fachada()
        # Cada local (blocos residenciais, cada outra edificação, todo o
        # condomínio) tem os próprios quantitativos; cada anomalia usa o do seu.
        dados = self.aba_dados.dados_para_calculo()
        self._locais = locais_do_rascunho(dados)
        self._quantitativos_por_local = quantitativos_por_local(dados)
        self._quantitativos = self._quantitativos_por_local[LOCAL_RESIDENCIAL]
        self.aba_dados.atualizar_exibicao()
        self._atualizar_rotulo_percentual_pintura()

        self._atualizar_preview_orcamento()
        self._atualizar_valores_anomalias_orcamento()
        self._referencias_ultimo_calculo = self._referencias_externas()

    def _coletar_rascunho(self) -> dict:
        dados = novo_rascunho()
        dados["condominio"]["nome"] = self.var_nome.get().strip()
        dados["condominio"]["municipio"] = self.var_municipio.get().strip()
        dados["condominio"]["uf"] = estado_do_combo(self.var_uf.get())
        dados["dados_iniciais"]["bdi_percent"] = self.var_bdi.get().strip() or BDI_PADRAO
        self.aba_dados.coletar_em(dados)
        dados["anomalias_orcamento"] = list(self._anomalias_orcamento)
        dados["considerar_servicos_preliminares"] = bool(self.var_considerar_sp.get())
        dados["considerar_pintura"] = bool(self.var_considerar_pintura.get())
        dados["pintura_fachada_manual"] = bool(self._pintura_fachada_manual)
        dados["duas_demaos_fundo_selador"] = bool(self.var_duas_demaos_selador.get())
        dados["considerar_destinacao_entulho"] = bool(self.var_considerar_entulho.get())
        dados["considerar_limpeza_geral"] = bool(self.var_considerar_limpeza.get())
        dados["extras_orcamento"] = []
        dados["orcamento"] = self._orcamento_para_rascunho()
        dados["orcamento_customizado_id"] = str(self._orcamento_customizado_id or "")
        dados["observacoes"] = self._texto_observacoes()
        return dados

    def _orcamento_para_rascunho(self) -> dict:
        dados = self.orcamento.exportar_dict()
        dados["nome"] = self.var_nome.get().strip()
        dados["estado_referencia"] = estado_do_combo(self.var_uf.get())
        dados["bdi_percent"] = numero(self.var_bdi.get())
        return dados

    def _carregar_orcamento_rascunho(self, dados: dict) -> None:
        self._carregar_etapas()
        payload = dict(dados.get("orcamento") or {})
        bdi = payload.get("bdi_percent")
        if bdi in (None, ""):
            payload["bdi_percent"] = numero(self.var_bdi.get()) or 30.62
        try:
            self.orcamento = OrcamentoCustomizado.importar_dict(payload)
        except (TypeError, ValueError):
            self.orcamento = OrcamentoCustomizado()
        extras = list(dados.get("extras_orcamento") or [])
        if extras and not self.orcamento.grupos:
            migrar_extras_para_grupos(
                self.orcamento,
                extras,
                etapas_por_id=self._etapa_por_id,
                sinapi=self.ctx.sinapi,
                uf=estado_do_combo(self.var_uf.get()),
            )

    def _executar_com_carregamento(self, texto, acao, ao_terminar=None):
        """Executa uma operação demorada com um aviso discreto.

        texto aparece na barra de mensagens do módulo (None = só o cursor de
        espera). Durante a operação, `tk busy` cobre a janela com uma camada
        invisível: mostra o cursor de espera e descarta cliques feitos
        enquanto a tela está ocupada, para não serem executados depois sobre
        uma tela que já mudou.
        """
        if self._ocupado:
            acao()  # já dentro de outra operação ocupada
            if ao_terminar is not None:
                ao_terminar()
            return
        self._ocupado = True
        self._carregando = True
        if texto:
            self._mostrar_feedback(texto, "gray", temporario=False)
        topo = self.winfo_toplevel()
        try:
            self.tk.call("tk", "busy", "hold", topo)
            bloqueado = True
        except tk.TclError:
            bloqueado = False
        try:
            self.update_idletasks()  # desenha a mensagem e o cursor antes do trabalho
        except tk.TclError:
            pass
        try:
            acao()
        finally:
            try:
                self.update_idletasks()
            except tk.TclError:
                pass

            def liberar():
                # Roda depois dos cliques que chegaram durante a operação:
                # eles caem na camada do tk busy e são ignorados.
                if bloqueado:
                    try:
                        self.tk.call("tk", "busy", "forget", topo)
                    except tk.TclError:
                        pass
                self._ocupado = False
                self._carregando = False
                if texto and self.var_feedback.get() == texto:
                    self.var_feedback.set("")
                if ao_terminar is not None:
                    ao_terminar()

            try:
                self.after(1, liberar)
            except tk.TclError:
                liberar()

    def _aplicar_rascunho(
        self, dados: dict, *, caminho=None, normalizar=True, verificar_mudancas=False
    ):
        """normalizar=False quando os dados já vêm de carregar_rascunho /
        carregar_autosave, que normalizam na leitura.

        verificar_mudancas=True (abrir arquivo / restaurar autosave) preenche
        self._avisos_ultima_carga com o que mudou em relação ao que foi salvo.
        """
        self._carregando = True
        self._avisos_ultima_carga = []
        if normalizar:
            dados = normalizar_rascunho(dados)
        try:
            self.var_nome.set(dados["condominio"].get("nome", ""))
            self.var_municipio.set(dados["condominio"].get("municipio", ""))
            uf = dados["condominio"].get("uf", "")
            self.var_uf.set(uf if uf else PLACEHOLDER_ESTADO)
            iniciais = dados.get("dados_iniciais") or {}
            self.var_bdi.set(iniciais.get("bdi_percent") or BDI_PADRAO)
            self._observacoes = (dados.get("observacoes") or "").strip()
            self.aba_dados.aplicar(dados)
            self._atualizar_rotulo_condominio()
            self._anomalias_orcamento = list(dados.get("anomalias_orcamento") or [])
            # normalizar_rascunho já preenche os padrões dessas chaves.
            self.var_considerar_sp.set(bool(dados["considerar_servicos_preliminares"]))
            self.var_considerar_pintura.set(bool(dados["considerar_pintura"]))
            manual = dados.get("pintura_fachada_manual")
            if manual is None:
                # Rascunho antigo: se o % de pintura difere do máximo das
                # anomalias, foi ajustado à mão e não pode ser sobrescrito.
                self._pintura_fachada_manual = self._pintura_diverge_do_maximo()
            else:
                self._pintura_fachada_manual = bool(manual)
            self.var_duas_demaos_selador.set(bool(dados["duas_demaos_fundo_selador"]))
            self.var_considerar_entulho.set(bool(dados["considerar_destinacao_entulho"]))
            self.var_considerar_limpeza.set(bool(dados["considerar_limpeza_geral"]))
            self._carregar_orcamento_rascunho(dados)
            self._orcamento_customizado_id = str(
                dados.get("orcamento_customizado_id") or ""
            ).strip()
            self._atualizar_estado_planilha()
            self._redesenhar_anomalias_orcamento(com_valores=False)
            self.texto_obs.delete("1.0", "end")
            obs = dados.get("observacoes") or ""
            if obs:
                self.texto_obs.insert("1.0", obs)
            self._observacoes = obs.strip()
            self._caminho_arquivo = str(caminho) if caminho else None
            self._sujo = False
            self._atualizar_rotulo_arquivo()
            total_salvo = None
            if verificar_mudancas and self.orcamento.grupos:
                # Total com os preços gravados no arquivo, antes de o
                # recálculo aplicar a SINAPI vigente. Rascunhos antigos sem
                # orçamento salvo ficam de fora (não há com o que comparar).
                total_salvo = self._total_geral_calculado(
                    self.orcamento.bdi_percent,
                    self._composicoes_para_calculo(),
                    estado_do_combo(self.var_uf.get()),
                )
            self._recalcular()
            if verificar_mudancas:
                self._avisos_ultima_carga = self._verificar_mudancas_carga(total_salvo)
        finally:
            if self._job_municipio is not None:
                try:
                    self.after_cancel(self._job_municipio)
                except (tk.TclError, ValueError):
                    pass
                self._job_municipio = None
            if not self._ocupado:
                self._carregando = False

    def _verificar_mudancas_carga(self, total_salvo) -> list[dict]:
        """Compara o rascunho carregado com o que estava gravado.

        Cada aviso: {"texto": str, "altera": bool}. "altera" indica que salvar
        de novo vai gravar dados diferentes dos que estavam no arquivo.
        """
        avisos = []
        total_novo = getattr(self, "_total_geral_ultimo", None)
        if total_salvo is not None and total_novo is not None:
            if abs(total_novo - total_salvo) >= 0.01:
                avisos.append(
                    {
                        "texto": (
                            "O total do orçamento mudou ao recalcular com a SINAPI e o "
                            "catálogo atuais:\n"
                            f"    salvo: {_formatar_moeda(total_salvo)}\n"
                            f"    agora: {_formatar_moeda(total_novo)}"
                        ),
                        "altera": True,
                    }
                )
        ausentes = []
        # Consulta direta ao catálogo: obter_reparo() faz deepcopy do cadastro
        # inteiro a cada chamada, caro demais só para checar se existe.
        cadastros = (self._catalogo or {}).get("anomalias") or {}
        for linha in self._anomalias_orcamento:
            cadastro = cadastros.get(linha.get("nome") or "")
            tem_reparo = isinstance(cadastro, dict) and any(
                isinstance(r, dict) for r in (cadastro.get("reparos") or [])
            )
            if not tem_reparo:
                nome = linha.get("nome") or "(sem nome)"
                reparo = linha.get("reparo_nome")
                ausentes.append(f"{nome} — {reparo}" if reparo else nome)
        if ausentes:
            lista = "\n".join(f"    • {item}" for item in ausentes[:10])
            if len(ausentes) > 10:
                lista += f"\n    … e mais {len(ausentes) - 10}"
            avisos.append(
                {
                    "texto": (
                        "Anomalias/reparos do rascunho que não existem mais no "
                        f"catálogo (ficam sem valor):\n{lista}"
                    ),
                    "altera": False,
                }
            )
        uf = estado_do_combo(self.var_uf.get())
        # UFs já listadas no combo: ctx.obter_estados() recalcula a lista a
        # partir da SINAPI inteira (~70 ms por chamada).
        try:
            valores_combo = self.combo_uf.cget("values") if self.combo_uf else ()
        except tk.TclError:
            valores_combo = ()
        ufs_sinapi = {estado_do_combo(v) for v in valores_combo}
        if uf and ufs_sinapi and uf not in ufs_sinapi:
            avisos.append(
                {
                    "texto": f"A UF {uf} não está na base SINAPI carregada; "
                    "os preços podem ficar zerados.",
                    "altera": False,
                }
            )
        return avisos

    def _mostrar_avisos_carga(self, titulo):
        avisos = getattr(self, "_avisos_ultima_carga", None) or []
        if not avisos:
            return
        texto = "\n\n".join(item["texto"] for item in avisos)
        if any(item["altera"] for item in avisos):
            texto += "\n\nO rascunho foi marcado como não salvo para você revisar."
        messagebox.showwarning(titulo, texto, parent=self.winfo_toplevel())

    def _aplicar_rascunho_seguro(
        self, dados: dict, *, caminho=None, normalizar=True, verificar_mudancas=False
    ) -> str | None:
        """Aplica o rascunho; se falhar no meio, volta ao estado anterior.

        Evita que a tela fique com parte do rascunho novo e parte do antigo
        (e que um Ctrl+S grave essa mistura no arquivo anterior).
        Devolve None em caso de sucesso ou a descrição do erro.
        """
        anterior = self._capturar_snapshot()
        caminho_anterior = self._caminho_arquivo
        sujo_anterior = self._sujo
        try:
            self._aplicar_rascunho(
                dados,
                caminho=caminho,
                normalizar=normalizar,
                verificar_mudancas=verificar_mudancas,
            )
            return None
        except Exception as exc:  # noqa: BLE001 — qualquer falha precisa reverter a tela
            traceback.print_exc()
            erro = f"{type(exc).__name__}: {exc}"
        try:
            self._aplicar_rascunho(anterior, caminho=caminho_anterior)
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        self._caminho_arquivo = caminho_anterior
        self._sujo = sujo_anterior
        self._atualizar_rotulo_arquivo()
        return erro

    def _capturar_snapshot(self):
        return deepcopy(self._coletar_rascunho())

    def _iniciar_historico(self):
        self._snapshot_base = self._capturar_snapshot()
        self._atualizar_botoes_historico()

    def _registrar_historico(self, descricao, *, coalescer=False):
        if self._carregando or self._aplicando_historico:
            return
        depois = self._capturar_snapshot()
        antes = self._snapshot_base if self._snapshot_base is not None else depois
        if antes == depois:
            self._snapshot_base = depois
            return
        if (
            coalescer
            and self._historico_undo
            and self._historico_undo[-1]["descricao"] == descricao
        ):
            self._historico_undo[-1]["depois"] = depois
        else:
            self._historico_undo.append(
                {"antes": antes, "depois": depois, "descricao": descricao}
            )
            if len(self._historico_undo) > HISTORICO_MAX:
                del self._historico_undo[0 : len(self._historico_undo) - HISTORICO_MAX]
        self._historico_redo.clear()
        self._snapshot_base = depois
        self._atualizar_botoes_historico()

    def _atualizar_botoes_historico(self):
        definir_estado_botao_icone(
            self.btn_desfazer, "normal" if self._historico_undo else "disabled"
        )
        definir_estado_botao_icone(
            self.btn_refazer, "normal" if self._historico_redo else "disabled"
        )

    def _desfazer(self):
        if not self._historico_undo or self._aplicando_historico:
            return
        entrada = self._historico_undo.pop()
        self._aplicando_historico = True
        try:
            erro = self._aplicar_rascunho_seguro(
                entrada["antes"], caminho=self._caminho_arquivo
            )
            if erro is None:
                self._sujo = True
                self._atualizar_rotulo_arquivo()
                self._agendar_autosave()
        finally:
            self._aplicando_historico = False
        if erro is not None:
            self._historico_undo.append(entrada)
            self._atualizar_botoes_historico()
            self._mostrar_erro_carregamento("Desfazer", erro)
            return
        self._historico_redo.append(entrada)
        self._snapshot_base = self._capturar_snapshot()
        self._atualizar_botoes_historico()
        self._mostrar_feedback(f"Desfeita — {entrada['descricao']}", "orange")

    def _refazer(self):
        if not self._historico_redo or self._aplicando_historico:
            return
        entrada = self._historico_redo.pop()
        self._aplicando_historico = True
        try:
            erro = self._aplicar_rascunho_seguro(
                entrada["depois"], caminho=self._caminho_arquivo
            )
            if erro is None:
                self._sujo = True
                self._atualizar_rotulo_arquivo()
                self._agendar_autosave()
        finally:
            self._aplicando_historico = False
        if erro is not None:
            self._historico_redo.append(entrada)
            self._atualizar_botoes_historico()
            self._mostrar_erro_carregamento("Refazer", erro)
            return
        self._historico_undo.append(entrada)
        self._snapshot_base = self._capturar_snapshot()
        self._atualizar_botoes_historico()
        self._mostrar_feedback(f"Refeita — {entrada['descricao']}", "green")

    def _widget_do_modulo(self, widget) -> bool:
        atual = widget
        while atual is not None:
            if atual is self:
                return True
            try:
                atual = atual.master
            except (tk.TclError, AttributeError):
                return False
        return False

    def _vincular_historico_teclado(self):
        def ao_desfazer(event):
            if not self._widget_do_modulo(event.widget):
                return
            try:
                if not self.winfo_ismapped():
                    return
            except tk.TclError:
                return
            self._desfazer()
            return "break"

        def ao_refazer(event):
            if not self._widget_do_modulo(event.widget):
                return
            try:
                if not self.winfo_ismapped():
                    return
            except tk.TclError:
                return
            self._refazer()
            return "break"

        topo = self.winfo_toplevel()
        for sequencia, callback in (
            ("<Control-z>", ao_desfazer),
            ("<Control-Z>", ao_desfazer),
            ("<Control-y>", ao_refazer),
            ("<Control-Y>", ao_refazer),
            ("<Control-f>", self._ao_tecla_filtro_grade),
            ("<Control-F>", self._ao_tecla_filtro_grade),
        ):
            func_id = topo.bind(sequencia, callback, add="+")
            self._binds_historico.append((topo, sequencia, func_id))
        # Clique fora de um campo de "Características do Empreendimento"
        # tira o foco dele (o desfazer do binding vai junto no _ao_destruir).
        func_id = topo.bind("<Button-1>", self._ao_clicar_fora_do_campo, add="+")
        self._binds_historico.append((topo, "<Button-1>", func_id))

    def _tirar_foco_campo(self):
        """Tira o foco do campo atual (o campo formata o número ao perdê-lo)."""
        try:
            self.focus_set()
        except tk.TclError:
            pass
        return "break"

    def _ao_clicar_fora_do_campo(self, event):
        try:
            focado = self.focus_get()
        except (tk.TclError, KeyError):
            return
        if focado not in self._entradas_caracteristicas:
            return
        # Clique em outro lugar de digitação: ele mesmo recebe o foco.
        if isinstance(event.widget, (tk.Entry, ttk.Entry, tk.Text, tk.Spinbox)):
            return
        self._tirar_foco_campo()

    def _novo(self):
        if self._sujo and not self._confirmar_saida(
            "Há alterações não salvas.\n"
            "Deseja salvar o rascunho JSON antes de começar outro?"
        ):
            return
        if self._carregando:
            return
        if self._sujo and not self._confirmar_saida(
            "Há alterações não salvas.\n"
            "Deseja salvar o rascunho JSON antes de começar outro?"
        ):
            return
        erros = []

        def limpar():
            erro = self._aplicar_rascunho_seguro(novo_rascunho())
            if erro is not None:
                erros.append(erro)
                return
            limpar_autosave()
            self._historico_undo.clear()
            self._historico_redo.clear()
            self._iniciar_historico()

        def ao_terminar():
            if erros:
                self._mostrar_erro_carregamento("Novo rascunho", erros[0])
            else:
                self._mostrar_feedback("Novo rascunho iniciado.", "green")

        self._executar_com_carregamento("Começando um rascunho novo…", limpar, ao_terminar)

    def _abrir(self):
        if self._carregando:
            return
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

        nome_arquivo = Path(caminho).name
        erro_leitura = []
        erros = []

        def carregar():
            try:
                dados = carregar_rascunho(caminho)
            except RascunhoAreaComumError as exc:
                erro_leitura.append(str(exc))
                return
            erro = self._aplicar_rascunho_seguro(
                dados, caminho=caminho, normalizar=False, verificar_mudancas=True
            )
            if erro is not None:
                erros.append(erro)
                return
            # O usuário já decidiu (salvar ou descartar) o trabalho anterior.
            limpar_autosave()
            self._historico_undo.clear()
            self._historico_redo.clear()
            self._iniciar_historico()
            self._marcar_sujo_se_carga_alterou()

        def ao_terminar():
            # Depois de liberar a tela, para a mensagem não abrir com ela ocupada.
            if erro_leitura:
                messagebox.showerror(
                    "Abrir rascunho", erro_leitura[0], parent=self.winfo_toplevel()
                )
            elif erros:
                self._mostrar_erro_carregamento(
                    "Abrir rascunho", erros[0], arquivo=nome_arquivo
                )
            else:
                self._mostrar_feedback(f"Rascunho aberto: {nome_arquivo}", "green")
                self._mostrar_avisos_carga("Abrir rascunho")

        self._executar_com_carregamento("Abrindo rascunho…", carregar, ao_terminar)

    def _salvar(self, *, salvar_como=False) -> bool:
        caminho = None if salvar_como else self._caminho_arquivo
        if not caminho:
            caminho = filedialog.asksaveasfilename(
                title="Salvar rascunho de Área Comum",
                initialdir=str(pasta_rascunhos()),
                initialfile=_nome_arquivo_sugerido(
                    self.var_nome.get(),
                    self.var_municipio.get(),
                    estado_do_combo(self.var_uf.get()),
                ),
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
        # O arquivo agora contém tudo; o autosave antigo só causaria uma oferta
        # de restauração desnecessária na próxima abertura.
        limpar_autosave()
        self._mostrar_feedback(f"Rascunho salvo: {Path(caminho).name}", "green")
        return True

    def _oferecer_autosave(self):
        if self._pular_oferta_autosave:
            return
        resultado = carregar_autosave()
        if not resultado:
            return
        dados, origem = resultado
        if not rascunho_tem_conteudo(dados):
            return
        # Só reconecta ao arquivo de origem se ele ainda existir.
        if origem and not Path(origem).is_file():
            origem = None
        nome = dados.get("condominio", {}).get("nome") or "sem nome"
        detalhe_origem = f"\nArquivo: {Path(origem).name}" if origem else ""
        if not messagebox.askyesno(
            "Rascunho automático",
            "Há um rascunho automático da Área Comum "
            f"({nome}).{detalhe_origem}\nDeseja continuar de onde parou?",
            parent=self.winfo_toplevel(),
        ):
            return
        erros = []

        def restaurar():
            erro = self._aplicar_rascunho_seguro(
                dados, caminho=origem, normalizar=False, verificar_mudancas=True
            )
            if erro is not None:
                erros.append(erro)
                return
            self._sujo = True
            self._atualizar_rotulo_arquivo()
            self._iniciar_historico()

        def ao_terminar():
            if erros:
                self._mostrar_erro_carregamento("Rascunho automático", erros[0])
            else:
                self._mostrar_feedback("Rascunho automático restaurado.", "green")
                self._mostrar_avisos_carga("Rascunho automático")

        self._executar_com_carregamento(
            "Restaurando o rascunho automático…", restaurar, ao_terminar
        )

    def _marcar_sujo_se_carga_alterou(self):
        """Se a carga mudou valores (ex.: SINAPI nova), salvar grava algo
        diferente do arquivo; por isso o rascunho fica como "não salvo"."""
        if any(item["altera"] for item in self._avisos_ultima_carga):
            self._sujo = True
            self._atualizar_rotulo_arquivo()

    def _mostrar_erro_carregamento(self, titulo, erro, *, arquivo=None):
        alvo = f"o rascunho «{arquivo}»" if arquivo else "o rascunho"
        messagebox.showerror(
            titulo,
            f"Não foi possível carregar {alvo}.\n"
            "A tela foi mantida como estava antes da tentativa.\n\n"
            f"Detalhe técnico: {erro}",
            parent=self.winfo_toplevel(),
        )

    def _recarregar_catalogo_anomalias(self):
        self._catalogo = carregar_catalogo()
        nomes = nomes_anomalias(self._catalogo)
        if hasattr(self, "campo_catalogo"):
            self.campo_catalogo.definir_opcoes(nomes)
        self._sincronizar_nomes_reparos_orcamento()
        self._carregar_etapas()
        self._recalcular()
        self._redesenhar_anomalias_orcamento()

    def _sincronizar_nomes_reparos_orcamento(self):
        """Atualiza o nome exibido das anomalias já adicionadas após renomear o reparo."""
        anomalias = (self._catalogo or {}).get("anomalias") or {}
        alterou = False
        for linha in self._anomalias_orcamento:
            cadastro = anomalias.get(linha.get("nome") or "")
            if not isinstance(cadastro, dict):
                continue
            rid = str(linha.get("reparo_id") or "")
            reparos = [r for r in (cadastro.get("reparos") or []) if isinstance(r, dict)]
            reparo = next(
                (item for item in reparos if str(item.get("id") or "") == rid),
                None,
            )
            if reparo is None:
                continue
            nome = str(reparo.get("nome") or "").strip()
            if nome and nome != (linha.get("reparo_nome") or ""):
                linha["reparo_nome"] = nome
                alterou = True
        if alterou:
            self._marcar_sujo()

    def _abrir_config_anomalias(self):
        DialogoConfigAnomaliasAreaComum(
            self.winfo_toplevel(),
            self.ctx,
            on_salvo=self._recarregar_catalogo_anomalias,
        )

    def _escolher_lista(self, titulo, mensagem, opcoes, *, dica="", selecionar=None):
        from ui.temas import aplicar_chrome_dialogo
        from ui.widgets import (
            aplicar_icone_janela,
            centralizar_janela,
            criar_botao_cancelar,
            preparar_toplevel,
        )

        escolhido = {"valor": None}
        dialog = tk.Toplevel(self.winfo_toplevel())
        preparar_toplevel(dialog)
        cores, _estilos = aplicar_chrome_dialogo(dialog)
        fundo = cores.fundo
        dialog.title(titulo)
        aplicar_icone_janela(dialog)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.geometry("420x320")

        painel = tk.Frame(dialog, bg=fundo, padx=14, pady=12)
        painel.pack(fill="both", expand=True)
        tk.Label(
            painel,
            text=mensagem,
            bg=fundo,
            fg=cores.texto,
            justify="left",
            wraplength=380,
            anchor="w",
        ).pack(fill="x", pady=(0, 8))
        if dica:
            tk.Label(
                painel,
                text=dica,
                bg=fundo,
                fg=cores.texto_suave,
                justify="left",
                wraplength=380,
                anchor="w",
            ).pack(fill="x", pady=(0, 8))
        lista = tk.Listbox(painel, exportselection=False)
        lista.pack(fill="both", expand=True)
        for opcao in opcoes:
            lista.insert("end", opcao)
        if opcoes:
            indice = opcoes.index(selecionar) if selecionar in opcoes else 0
            lista.selection_set(indice)
            lista.activate(indice)
            lista.see(indice)

        def confirmar():
            sel = lista.curselection()
            if not sel:
                return
            escolhido["valor"] = opcoes[sel[0]]
            dialog.destroy()

        lista.bind("<Double-1>", lambda _e: confirmar())
        botoes = tk.Frame(painel, bg=fundo)
        botoes.pack(fill="x", pady=(8, 0))
        criar_botao_cancelar(botoes, dialog.destroy).pack(side="right")
        ttk.Button(botoes, text="Usar", command=confirmar, style="Add.TButton").pack(
            side="right", padx=(0, 8)
        )
        dialog.bind("<Escape>", lambda _e: dialog.destroy())
        dialog.update_idletasks()
        centralizar_janela(dialog, self.winfo_toplevel())
        self.wait_window(dialog)
        return escolhido["valor"]

    def _adicionar_anomalia_catalogo(self):
        nome = self.var_catalogo_anomalia.get().strip()
        anomalias = (self._catalogo or {}).get("anomalias") or {}
        if nome not in anomalias:
            self._mostrar_feedback("Selecione uma anomalia cadastrada.", "red")
            return
        reparos = list(anomalias[nome].get("reparos") or [])
        if not reparos:
            self._mostrar_feedback("Essa anomalia ainda não tem reparo cadastrado.", "orange")
            return
        local = LOCAL_RESIDENCIAL
        # Só pergunta o local quando há outras edificações (salão, guarita...).
        if len(self._locais) > 2:
            local = self._escolher_local("Local da anomalia", f"Onde acontece «{nome}»?")
            if local is None:
                return
        reparo = reparos[0]
        if len(reparos) > 1:
            nomes = [r.get("nome") or f"Reparo {i+1}" for i, r in enumerate(reparos)]
            tipo_estrutura, tipo_cobertura = self._tipos_para_reparo(local)
            sugerido, dica = reparo_recomendado(
                anomalias[nome],
                tipo_estrutura=tipo_estrutura,
                tipo_cobertura=tipo_cobertura,
            )
            selecionar = None
            if sugerido is not None:
                for indice, item in enumerate(reparos):
                    if item.get("id") == sugerido.get("id"):
                        selecionar = nomes[indice]
                        break
            escolhido = self._escolher_lista(
                "Escolher reparo",
                f"A anomalia '{nome}' tem mais de um reparo.\nQual deve ser usado?",
                nomes,
                dica=dica,
                selecionar=selecionar,
            )
            if not escolhido:
                return
            reparo = reparos[nomes.index(escolhido)]
        percentuais_novos = self._coletar_percentuais_faltantes(reparo, local)
        if percentuais_novos is None:
            return
        percentual = "100"
        variaveis = self._coletar_variaveis_reparo(reparo)
        if variaveis is None:
            return
        self._gravar_percentuais_aba1(percentuais_novos, local)
        nova = nova_anomalia_orcamento(
            nome=nome,
            reparo_id=reparo.get("id"),
            reparo_nome=reparo.get("nome"),
            percentual=percentual,
            variaveis=variaveis,
            local=local,
        )
        self._aplicar_percentuais_aba1(
            list(reparo.get("percentuais_aba1") or []),
            percentual,
            origem_nome=nome,
            excluir_id=nova.get("id"),
            local=local,
        )
        self._anomalias_orcamento.append(nova)
        self._redesenhar_anomalias_orcamento()
        self._marcar_sujo()
        self._registrar_historico("Adicionar anomalia")
        self._recalcular()
        self._mostrar_feedback(f"Anomalia adicionada: {nome}.", "green")

    def _remover_anomalia_orcamento(self):
        selecao = self.tree_anomalias.selection()
        if not selecao:
            self._mostrar_feedback("Selecione uma anomalia na lista.", "orange")
            return
        item_id = selecao[0]
        self._anomalias_orcamento = [
            i for i in self._anomalias_orcamento if i.get("id") != item_id
        ]
        self._redesenhar_anomalias_orcamento()
        self._marcar_sujo()
        self._registrar_historico("Remover anomalia")
        self._recalcular()

    def _redesenhar_anomalias_orcamento(self, *, com_valores=True):
        """Recria as linhas da árvore.

        com_valores=False insere só nomes; usado na carga do rascunho, em que
        _recalcular() logo em seguida preenche os valores já com os
        quantitativos novos (antes eram calculados duas vezes, a primeira com
        os quantitativos do rascunho anterior).
        """
        if not hasattr(self, "tree_anomalias"):
            return
        selecao = list(self.tree_anomalias.selection())
        for item in self.tree_anomalias.get_children():
            self.tree_anomalias.delete(item)
        if com_valores:
            limites_fachada = self._limites_fachada()
            reduzidas = {str(chave) for chave in limites_fachada[1]}
        for indice, linha in enumerate(self._anomalias_orcamento):
            if com_valores:
                valores = self._valores_linha_anomalia(linha, limites_fachada)
                tags = self._tags_linha_anomalia(indice, linha, reduzidas)
            else:
                valores = (
                    self._rotulo_local(linha),
                    linha.get("reparo_nome") or "Reparo padrão",
                    "",
                    "",
                    "",
                )
                tags = ("par" if indice % 2 else "impar",)
            self.tree_anomalias.insert(
                "",
                "end",
                iid=linha["id"],
                text=linha.get("nome") or "",
                values=valores,
                tags=tags,
            )
        for iid in selecao:
            if self.tree_anomalias.exists(iid):
                self.tree_anomalias.selection_set(iid)
                self.tree_anomalias.see(iid)
                break

    def _atualizar_valores_anomalias_orcamento(self):
        self._atualizar_valores_etapas_padrao()
        if not hasattr(self, "tree_anomalias"):
            return
        limites_fachada = self._limites_fachada()
        reduzidas = {str(chave) for chave in limites_fachada[1]}
        por_id = {item.get("id"): item for item in self._anomalias_orcamento}
        for indice, iid in enumerate(self.tree_anomalias.get_children()):
            linha = por_id.get(iid)
            if linha is None:
                continue
            self.tree_anomalias.item(
                iid,
                values=self._valores_linha_anomalia(linha, limites_fachada),
                tags=self._tags_linha_anomalia(indice, linha, reduzidas),
            )

    def _valores_linha_anomalia(self, linha, limites_fachada=None) -> tuple:
        return (
            self._rotulo_local(linha),
            linha.get("reparo_nome") or "Reparo padrão",
            f"{linha.get('percentual') or '100'}%",
            self._texto_valor_reparo(linha, limites_fachada=limites_fachada),
            self._texto_valor_atual_anomalia(linha),
        )

    def _texto_moeda_grupo(self, grupo) -> str:
        """Custo do grupo já montado na aba 3, com BDI."""
        if not grupo:
            return "—"
        try:
            bdi = numero(self.var_bdi.get())
        except (TypeError, ValueError):
            bdi = 0.0
        total = self._subtotal_grupo_calculado(
            grupo,
            bdi,
            self._composicoes_para_calculo(),
            self._estado_selecionado(),
        )
        if abs(total) < 0.005:
            return "—"
        return _formatar_moeda(total)

    def _texto_valor_atual_anomalia(self, linha) -> str:
        aid = str((linha or {}).get("id") or "")
        grupo = next(
            (
                g
                for g in self.orcamento.grupos
                if str(g.get("anomalia_id") or "") == aid and g.get("origem") == "anomalia"
            ),
            None,
        )
        return self._texto_moeda_grupo(grupo)

    def _atualizar_valores_etapas_padrao(self):
        variaveis = getattr(self, "var_valor_etapas", None)
        if not variaveis:
            return
        por_origem = {
            str(grupo.get("origem") or ""): grupo for grupo in self.orcamento.grupos
        }
        for chave, var in variaveis.items():
            var.set(f"({self._texto_moeda_grupo(por_origem.get(chave))})")
        self._atualizar_rotulo_percentual_pintura()

    def _limites_fachada(self):
        """(limites, avisos) da redução de revestimento de fachada, para todas as linhas."""
        return limites_fachada_por_local(
            self._anomalias_orcamento,
            self._catalogo,
            self._quantitativos or {},
            getattr(self, "_etapa_por_id", None),
            self._quantitativos_por_local,
        )

    # ------------------------------------------------- locais das anomalias
    def _local_da_linha(self, linha) -> str:
        local = str((linha or {}).get("local") or LOCAL_RESIDENCIAL)
        if local not in dict(self._locais):
            return LOCAL_RESIDENCIAL
        return local

    def _rotulo_local(self, linha) -> str:
        return dict(self._locais).get(self._local_da_linha(linha), "Blocos residenciais")

    def _q_da_linha(self, linha) -> dict:
        return self._quantitativos_por_local.get(self._local_da_linha(linha)) or (
            self._quantitativos or {}
        )

    def _ids_estruturas_do_local(self, local) -> set:
        dados = {"estruturas": [{"id": e.id, "tipo": e.tipo} for e in self.aba_dados.estruturas]}
        return {e["id"] for e in estruturas_do_local(dados, local)}

    def _texto_valor_reparo(
        self, linha, *, aplicar_limite=True, limites_fachada=None
    ) -> str:
        """limites_fachada: resultado de _limites_fachada() já calculado pelo
        chamador, para não recalcular a fachada inteira a cada linha."""
        reparo = self._reparo_da_linha(linha)
        if not reparo:
            return "—"
        limites = {}
        avisos = {}
        if aplicar_limite:
            limites, avisos = limites_fachada or self._limites_fachada()
        pares = valores_considerados_reparo(
            reparo,
            self._q_da_linha(linha),
            linha.get("percentual"),
            getattr(self, "_etapa_por_id", None),
            linha.get("variaveis"),
            limites.get(str(linha.get("id") or "")) if aplicar_limite else None,
        )
        if not pares:
            texto = "—"
        else:
            partes = []
            for valor, unid in pares:
                if abs(float(valor or 0)) < 1e-12:
                    continue
                partes.append(f"{formatar_decimal_br(valor, 2)} {unid}".strip())
            texto = " · ".join(partes) if partes else "—"
        if aplicar_limite and avisos.get(str(linha.get("id") or "")) and texto != "—":
            texto = f"{texto} *"
        return texto

    def _aviso_reducao_fachada(self, item_id) -> str:
        if not item_id:
            return ""
        _limites, avisos = self._limites_fachada()
        nomes = avisos.get(str(item_id)) or ()
        if not nomes:
            return ""
        if len(nomes) == 1:
            origem = nomes[0]
        else:
            origem = ", ".join(nomes[:-1]) + " e " + nomes[-1]
        linha = next(
            (item for item in self._anomalias_orcamento if item.get("id") == item_id),
            None,
        )
        sem_limite = self._texto_valor_reparo(linha, aplicar_limite=False) if linha else "—"
        return f"Reduzido por {origem}.\nSem essa redução: {sem_limite}."

    def _tags_linha_anomalia(self, indice, linha, reduzidas) -> tuple[str, ...]:
        if str(linha.get("id") or "") in reduzidas:
            return ("aviso",)
        return ("par" if indice % 2 else "impar",)

    def _reparo_da_linha(self, linha) -> dict | None:
        if not linha:
            return None
        return obter_reparo(
            linha.get("nome") or "",
            linha.get("reparo_id") or "",
            self._catalogo,
        )

    def _linha_tem_variavel(self, event) -> bool:
        try:
            item_id = self.tree_anomalias.identify_row(event.y)
        except tk.TclError:
            return False
        if not item_id:
            return False
        linha = next(
            (item for item in self._anomalias_orcamento if item.get("id") == item_id),
            None,
        )
        reparo = self._reparo_da_linha(linha)
        return bool(
            perguntas_variaveis_reparo(reparo, getattr(self, "_etapa_por_id", None))
        )

    def _coletar_variaveis_reparo(self, reparo, atuais=None):
        """Pergunta cada fator variável. None se o usuário cancelar."""
        pedidos = perguntas_variaveis_reparo(
            reparo, getattr(self, "_etapa_por_id", None)
        )
        if not pedidos:
            return []
        conhecidas = {}
        for item in atuais or []:
            if not isinstance(item, dict):
                continue
            chave = str(item.get("pergunta") or "").strip().casefold()
            if chave:
                conhecidas[chave] = str(
                    item.get("valor") if item.get("valor") is not None else ""
                )
        saida = []
        for pedido in pedidos:
            pergunta = pedido["pergunta"]
            valor = perguntar_texto(
                self.winfo_toplevel(),
                "Quantitativo",
                pergunta,
                valor_inicial=conhecidas.get(pergunta.casefold(), ""),
                texto_ok="Continuar",
            )
            if valor is None:
                return None
            saida.append(
                {
                    "pergunta": pergunta,
                    "valor": str(valor).strip(),
                }
            )
        return saida

    def _alterar_variaveis_anomalia(self, item_id):
        linha = next(
            (item for item in self._anomalias_orcamento if item.get("id") == item_id),
            None,
        )
        if linha is None:
            return
        reparo = self._reparo_da_linha(linha)
        if not perguntas_variaveis_reparo(
            reparo, getattr(self, "_etapa_por_id", None)
        ):
            return
        variaveis = self._coletar_variaveis_reparo(
            reparo, atuais=linha.get("variaveis")
        )
        if variaveis is None:
            return
        if variaveis:
            linha["variaveis"] = variaveis
        else:
            linha.pop("variaveis", None)
        self._marcar_sujo()
        self._registrar_historico("Quantitativo da anomalia")
        self._recalcular()
        self._redesenhar_anomalias_orcamento()
        if hasattr(self, "tree_anomalias") and self.tree_anomalias.exists(item_id):
            self.tree_anomalias.selection_set(item_id)
            self.tree_anomalias.see(item_id)

    def _chaves_percentuais_linha(self, linha) -> list[str]:
        reparo = self._reparo_da_linha(linha) or {}
        return list(reparo.get("percentuais_aba1") or [])

    def _anomalias_que_usam_percentual(
        self, chave, excluir_id=None, *, local=None, origem=None
    ) -> list[dict]:
        """Anomalias cujo reparo usa o percentual `chave` da aba 1.

        local: só as que dividem estruturas com esse local (o mesmo campo da
        aba 1). origem: só as que cobrem a estrutura (ou o condomínio) em que o
        campo foi editado.
        """
        if local is not None:
            alvo = self._ids_estruturas_do_local(local)
        elif origem is not None and origem != LOCAL_CONDOMINIO:
            alvo = {origem}
        else:
            alvo = None
        do_condominio = chave in CHAVES_PCT_CONDOMINIO
        resultado = []
        excluir = str(excluir_id or "")
        for linha in self._anomalias_orcamento:
            if excluir and str(linha.get("id") or "") == excluir:
                continue
            if chave not in self._chaves_percentuais_linha(linha):
                continue
            local_linha = self._local_da_linha(linha)
            if do_condominio:
                # Caixas e calçadas só existem em Blocos residenciais e Todo o condomínio.
                if local_linha not in (LOCAL_RESIDENCIAL, LOCAL_CONDOMINIO):
                    continue
            elif alvo is not None and not (alvo & self._ids_estruturas_do_local(local_linha)):
                continue
            resultado.append(linha)
        return resultado

    def _percentuais_iguais(self, a, b) -> bool:
        try:
            return abs(numero(a, percentual=True) - numero(b, percentual=True)) < 1e-9
        except (TypeError, ValueError):
            return str(a or "").strip() == str(b or "").strip()

    def _aplicar_percentuais_aba1(
        self,
        chaves,
        percentual_texto,
        *,
        origem_nome,
        excluir_id=None,
        local=LOCAL_RESIDENCIAL,
    ) -> bool:
        pcts = self.aba_dados.percentuais_do_local(local)
        chaves = [
            c
            for c in (chaves or [])
            if c in pcts and c != "pintura_fachada"
        ]
        if not chaves:
            return False
        novo_fmt = formatar_decimal_br(numero(percentual_texto, percentual=True))
        conflitos = []
        for chave in chaves:
            atual = (pcts[chave].get() or "").strip()
            if not atual:
                continue
            if self._percentuais_iguais(atual, novo_fmt):
                continue
            donos = self._anomalias_que_usam_percentual(
                chave, excluir_id=excluir_id, local=local
            )
            conflitos.append((chave, atual, donos))
        pular = set()
        if conflitos:
            linhas_msg = []
            for chave, atual, donos in conflitos:
                rotulo = ROTULOS_PERCENTUAIS_ABA1.get(chave, chave)
                extra = ""
                if donos:
                    nomes = ", ".join(
                        str(item.get("nome") or "anomalia") for item in donos
                    )
                    extra = f" (anomalia: {nomes})"
                linhas_msg.append(f"• {rotulo}: {atual}%{extra}")
            if not messagebox.askyesno(
                "Porcentagem já definida",
                "Algumas porcentagens da aba 1 já estão preenchidas:\n\n"
                + "\n".join(linhas_msg)
                + f"\n\nSubstituí-las por {novo_fmt}% de «{origem_nome}»?",
                parent=self.winfo_toplevel(),
            ):
                pular = {chave for chave, _atual, _donos in conflitos}
        mudou = False
        self._sincronizando_percentuais = True
        try:
            for chave in chaves:
                if chave in pular:
                    continue
                atual = (pcts[chave].get() or "").strip()
                if atual and self._percentuais_iguais(atual, novo_fmt):
                    continue
                pcts[chave].set(novo_fmt)
                mudou = True
        finally:
            self._sincronizando_percentuais = False
        return mudou

    def _estilizar_tree_anomalias(self):
        """Faixas alternadas. No tema do Windows a cor da tag só vale sem o fundo travado."""
        cores = self._cores
        self._cor_linha_par = cores.fundo_cartao
        self._cor_linha_impar = (
            cores.fundo_cartao_off if cores.escuro else cores.fundo_destaque
        )
        self._cor_linha_aviso = "#6b5428" if cores.escuro else "#ffe082"
        selecao = "#9ec4d6" if not cores.escuro else cores.fundo_hover
        estilo = ttk.Style(self)
        nome = "Anomalias.Treeview"

        def _sem_trava(opcao):
            return [
                item
                for item in estilo.map("Treeview", query_opt=opcao)
                if item[:2] != ("!disabled", "!selected")
            ]

        estilo.configure(
            nome,
            rowheight=30,
            background=self._cor_linha_par,
            fieldbackground=self._cor_linha_par,
            font=("Segoe UI", 9),
        )
        estilo.map(
            nome,
            background=[("selected", selecao), *_sem_trava("background")],
            foreground=[("selected", cores.texto), *_sem_trava("foreground")],
        )

    def _coluna_tree_anomalias(self, event) -> str:
        """Nome da coluna sob o mouse ("local", "reparo", "percentual"...).

        Pelo nome, e não pela posição (#1, #2…), para que acrescentar uma
        coluna não troque a ação dos cliques.
        """
        try:
            coluna = self.tree_anomalias.identify_column(event.x)
            linha = self.tree_anomalias.identify_row(event.y)
        except tk.TclError:
            return ""
        if not linha or not coluna.startswith("#"):
            return ""
        indice = int(coluna[1:])
        if indice == 0:
            return "anomalia"
        colunas = self.tree_anomalias["columns"]
        return colunas[indice - 1] if indice <= len(colunas) else ""

    def _dica_celula_anomalia(self, event) -> tuple[str, bool]:
        coluna = self._coluna_tree_anomalias(event)
        if coluna == "local":
            return "Alterar local", True
        if coluna == "reparo":
            return "Alterar reparo", True
        if coluna == "percentual":
            return "Alterar percentual", True
        if coluna != "valor":
            return "", False
        partes = []
        clicavel = self._linha_tem_variavel(event)
        if clicavel:
            partes.append("Alterar quantitativo variável")
        try:
            item_id = self.tree_anomalias.identify_row(event.y)
        except tk.TclError:
            item_id = ""
        aviso = self._aviso_reducao_fachada(item_id)
        if aviso:
            partes.append(aviso)
        return "\n".join(partes), clicavel

    def _ao_mover_tree_anomalias(self, event):
        dica, clicavel = self._dica_celula_anomalia(event)
        self.tree_anomalias.configure(cursor="hand2" if clicavel else "")
        try:
            linha = self.tree_anomalias.identify_row(event.y)
            coluna = self.tree_anomalias.identify_column(event.x)
        except tk.TclError:
            linha, coluna = "", ""
        alvo = (linha, coluna) if dica else None
        if alvo == getattr(self, "_dica_anomalia_alvo", None):
            return
        self._esconder_dica_anomalia()
        self._dica_anomalia_alvo = alvo
        if not dica:
            return
        self._dica_anomalia_after = self.after(
            120,
            lambda texto=dica, x=event.x_root + 14, y=event.y_root + 18, celula=alvo: (
                self._mostrar_dica_anomalia(texto, x, y, celula)
            ),
        )

    def _ao_sair_tree_anomalias(self, event):
        largura = self.tree_anomalias.winfo_width()
        altura = self.tree_anomalias.winfo_height()
        if 0 <= event.x < largura and 0 <= event.y < altura:
            return
        self.tree_anomalias.configure(cursor="")
        self._esconder_dica_anomalia()

    def _mostrar_dica_anomalia(self, texto, x, y, celula):
        self._dica_anomalia_after = None
        if celula != getattr(self, "_dica_anomalia_alvo", None):
            return
        from ui.widgets import _limitar_posicao_a_area, _obter_area_util_tela

        janela = tk.Toplevel(self.tree_anomalias)
        janela.wm_overrideredirect(True)
        try:
            janela.attributes("-topmost", True)
        except tk.TclError:
            pass
        tk.Label(
            janela,
            text=texto,
            background="#ffffe0",
            foreground="#000000",
            relief="solid",
            borderwidth=1,
            font=("Arial", 9),
            padx=6,
            pady=3,
        ).pack()
        janela.update_idletasks()
        largura = janela.winfo_reqwidth()
        altura = janela.winfo_reqheight()
        area = _obter_area_util_tela(self.winfo_toplevel())
        x, y = _limitar_posicao_a_area(x, y, largura, altura, area)
        janela.wm_geometry(f"+{x}+{y}")
        self._dica_anomalia_janela = janela

    def _esconder_dica_anomalia(self, _event=None):
        after_id = getattr(self, "_dica_anomalia_after", None)
        if after_id is not None:
            try:
                self.after_cancel(after_id)
            except tk.TclError:
                pass
            self._dica_anomalia_after = None
        janela = getattr(self, "_dica_anomalia_janela", None)
        if janela is not None:
            try:
                janela.destroy()
            except tk.TclError:
                pass
            self._dica_anomalia_janela = None
        self._dica_anomalia_alvo = None

    def _limpar_selecao_anomalias(self, _event=None):
        tree = getattr(self, "tree_anomalias", None)
        if tree is None:
            return "break"
        selecionados = tree.selection()
        if selecionados:
            tree.selection_remove(selecionados)
        return "break"

    def _aba_anomalias_visivel(self) -> bool:
        aba = getattr(self, "_aba_anomalias", None)
        if aba is None or not hasattr(self, "notebook"):
            return False
        try:
            return str(self.notebook.select()) == str(aba)
        except tk.TclError:
            return False

    def _widget_dentro(self, widget, ancestral) -> bool:
        atual = widget
        while atual is not None:
            if atual == ancestral:
                return True
            atual = getattr(atual, "master", None)
        return False

    def _ao_esc_anomalias(self, _event=None):
        if not self._aba_anomalias_visivel():
            return
        try:
            if self.winfo_toplevel().grab_current():
                return
        except tk.TclError:
            return
        self._limpar_selecao_anomalias()

    def _ao_clique_fora_anomalias(self, event):
        if not self._aba_anomalias_visivel():
            return
        try:
            if self.winfo_toplevel().grab_current():
                return
        except tk.TclError:
            return
        widget = event.widget
        if self._widget_dentro(widget, getattr(self, "tree_anomalias", None)):
            return
        if isinstance(
            widget,
            (ttk.Button, ttk.Checkbutton, ttk.Entry, ttk.Combobox, tk.Button),
        ):
            return
        self._limpar_selecao_anomalias()

    def _ao_clique_percentual_anomalia(self, event):
        self._esconder_dica_anomalia()
        try:
            row = self.tree_anomalias.identify_row(event.y)
        except tk.TclError:
            return
        if not row:
            self._limpar_selecao_anomalias()
            return
        coluna = self._coluna_tree_anomalias(event)
        if coluna not in ("local", "reparo", "percentual", "valor"):
            return
        if coluna == "valor" and not self._linha_tem_variavel(event):
            return
        self.tree_anomalias.selection_set(row)
        if coluna == "local":
            self.after_idle(lambda: self._alterar_local_anomalia(row))
        elif coluna == "reparo":
            self.after_idle(lambda: self._alterar_reparo_anomalia(row))
        elif coluna == "percentual":
            self.after_idle(lambda: self._alterar_percentual_anomalia(row))
        else:
            self.after_idle(lambda: self._alterar_variaveis_anomalia(row))
        return "break"

    def _ao_duplo_clique_anomalia(self, event=None):
        if event is not None and self._coluna_tree_anomalias(event) != "percentual":
            return
        selecao = self.tree_anomalias.selection()
        if not selecao:
            row = self.tree_anomalias.identify_row(event.y) if event is not None else ""
            if not row:
                return
            selecao = (row,)
        self._alterar_percentual_anomalia(selecao[0])

    def _ao_trocar_demaos_selador(self):
        if self._carregando or self._aplicando_historico:
            return
        self._marcar_sujo()
        self._registrar_historico("Demãos do fundo selador")
        self._recalcular()
        duas = bool(self.var_duas_demaos_selador.get())
        self._mostrar_feedback(
            "Fundo selador com 2 demãos." if duas else "Fundo selador com 1 demão.",
            "green",
        )

    def _ao_trocar_etapa_fixa(self, rotulo: str, variavel: tk.BooleanVar):
        if self._carregando or self._aplicando_historico:
            return
        self._marcar_sujo()
        self._registrar_historico(rotulo)
        self._recalcular()
        ativo = bool(variavel.get())
        self._mostrar_feedback(
            f"{rotulo} "
            + ("incluído no orçamento." if ativo else "removido do orçamento."),
            "green",
        )

    def _ao_trocar_considerar_sp(self):
        self._ao_trocar_etapa_fixa("Serviços preliminares", self.var_considerar_sp)

    def _alterar_percentual_anomalia(self, item_id=None):
        if item_id is None:
            selecao = self.tree_anomalias.selection() if hasattr(self, "tree_anomalias") else ()
            if not selecao:
                self._mostrar_feedback("Selecione uma anomalia na lista.", "orange")
                return
            item_id = selecao[0]
        linha = next(
            (item for item in self._anomalias_orcamento if item.get("id") == item_id),
            None,
        )
        if linha is None:
            return
        novo = self._perguntar_percentual_anomalia(
            linha.get("nome") or "anomalia",
            valor_inicial=linha.get("percentual") or "100",
        )
        if novo is None:
            return
        if self._percentuais_iguais(novo, linha.get("percentual") or "100"):
            return
        chaves = self._chaves_percentuais_linha(linha)
        if chaves:
            rotulos = ", ".join(
                ROTULOS_PERCENTUAIS_ABA1.get(chave, chave) for chave in chaves
            )
            if messagebox.askyesno(
                "Alterar na aba 1",
                f"Deseja também alterar na aba 1 ({rotulos}) para {novo}%?\n"
                "Isso atualiza o orçamento automaticamente.",
                parent=self.winfo_toplevel(),
            ):
                self._aplicar_percentuais_aba1(
                    chaves,
                    novo,
                    origem_nome=linha.get("nome") or "",
                    excluir_id=linha.get("id"),
                    local=self._local_da_linha(linha),
                )
        linha["percentual"] = novo
        self._marcar_sujo()
        self._registrar_historico("Alterar percentual da anomalia")
        self._recalcular()
        self._redesenhar_anomalias_orcamento()
        if hasattr(self, "tree_anomalias") and self.tree_anomalias.exists(item_id):
            self.tree_anomalias.selection_set(item_id)
            self.tree_anomalias.see(item_id)

    def _alterar_reparo_anomalia(self, item_id):
        linha = next(
            (item for item in self._anomalias_orcamento if item.get("id") == item_id),
            None,
        )
        if linha is None:
            return
        nome = linha.get("nome") or ""
        cadastro = ((self._catalogo or {}).get("anomalias") or {}).get(nome) or {}
        reparos = [r for r in (cadastro.get("reparos") or []) if isinstance(r, dict)]
        if not reparos:
            self._mostrar_feedback("Essa anomalia não tem reparo cadastrado.", "orange")
            return
        if len(reparos) == 1:
            self._mostrar_feedback(
                "Essa anomalia tem apenas um reparo cadastrado.", "orange"
            )
            return
        nomes = [r.get("nome") or f"Reparo {i + 1}" for i, r in enumerate(reparos)]
        atual = linha.get("reparo_nome") or ""
        selecionar = atual if atual in nomes else None
        tipo_estrutura, tipo_cobertura = self._tipos_para_reparo(self._local_da_linha(linha))
        _sugerido, dica = reparo_recomendado(
            cadastro,
            tipo_estrutura=tipo_estrutura,
            tipo_cobertura=tipo_cobertura,
        )
        escolhido = self._escolher_lista(
            "Trocar reparo",
            f"Qual reparo usar em '{nome}'?",
            nomes,
            dica=dica,
            selecionar=selecionar,
        )
        if not escolhido or escolhido == atual:
            return
        reparo = reparos[nomes.index(escolhido)]
        local = self._local_da_linha(linha)
        percentuais_novos = self._coletar_percentuais_faltantes(reparo, local)
        if percentuais_novos is None:
            return
        variaveis = self._coletar_variaveis_reparo(
            reparo, atuais=linha.get("variaveis")
        )
        if variaveis is None:
            return
        self._gravar_percentuais_aba1(percentuais_novos, local)
        linha["reparo_id"] = reparo.get("id") or ""
        linha["reparo_nome"] = reparo.get("nome") or escolhido
        if variaveis:
            linha["variaveis"] = variaveis
        else:
            linha.pop("variaveis", None)
        self._aplicar_percentuais_aba1(
            list(reparo.get("percentuais_aba1") or []),
            linha.get("percentual") or "100",
            origem_nome=nome,
            excluir_id=linha.get("id"),
            local=local,
        )
        self._marcar_sujo()
        self._registrar_historico("Alterar reparo da anomalia")
        self._recalcular()
        self._redesenhar_anomalias_orcamento()
        if hasattr(self, "tree_anomalias") and self.tree_anomalias.exists(item_id):
            self.tree_anomalias.selection_set(item_id)
            self.tree_anomalias.see(item_id)

    def _ao_focar_percentual(self, chave, var=None):
        """var: o campo da estrutura que está sendo editado (aba 1)."""
        var = var if var is not None else self.var_percentuais[chave]
        self._pct_em_edicao[chave] = var.get()

    def _ao_sair_percentual(self, chave, widget, var=None, origem=None):
        """origem: id da estrutura (ou "condominio") do campo editado na aba 1."""
        self._resolver_formula(widget, percentual=True)
        var = var if var is not None else self.var_percentuais[chave]
        if (
            self._carregando
            or self._aplicando_historico
            or self._sincronizando_percentuais
        ):
            return
        atual = var.get()
        anterior = self._pct_em_edicao.get(chave)
        if str(atual or "").strip() == str(anterior or "").strip():
            return
        if (
            str(atual or "").strip()
            and str(anterior or "").strip()
            and self._percentuais_iguais(atual, anterior)
        ):
            return
        if chave == "pintura_fachada":
            self._pintura_fachada_manual = bool(str(atual or "").strip())
            self._marcar_sujo()
            self._agendar_calculo()
            return
        ligadas = self._anomalias_que_usam_percentual(chave, origem=origem)
        if not ligadas:
            return
        bruto = str(atual or "").strip()
        if not bruto:
            return
        novo_fmt = formatar_decimal_br(numero(bruto, percentual=True))
        mudou = False
        for linha in ligadas:
            atual_an = linha.get("percentual") or "100"
            if self._percentuais_iguais(atual_an, novo_fmt):
                continue
            if messagebox.askyesno(
                "Alterar na aba 2",
                f"Deseja também alterar a porcentagem da anomalia "
                f"«{linha.get('nome') or 'anomalia'}» na aba 2 de {atual_an}% "
                f"para {novo_fmt}%?\nIsso atualiza o orçamento automaticamente.",
                parent=self.winfo_toplevel(),
            ):
                linha["percentual"] = novo_fmt
                mudou = True
        if mudou:
            self._redesenhar_anomalias_orcamento()
            self._marcar_sujo()
            self._registrar_historico("Sincronizar percentual da anomalia")
            self._recalcular()

    def _percentuais_pintura_das_anomalias(self, estrutura_id=None) -> list[float]:
        """% das anomalias de pintura que cobrem a estrutura (padrão: o 1º bloco residencial)."""
        if estrutura_id is None:
            primeira = self.aba_dados.primeira_residencial()
            estrutura_id = primeira.id if primeira else None
        valores = []
        for linha in self._anomalias_orcamento:
            if "pintura_fachada" not in self._chaves_percentuais_linha(linha):
                continue
            if estrutura_id not in self._ids_estruturas_do_local(self._local_da_linha(linha)):
                continue
            try:
                valores.append(numero(linha.get("percentual") or "100", percentual=True))
            except (TypeError, ValueError):
                continue
        return valores

    def _pintura_diverge_do_maximo(self) -> bool:
        valores = self._percentuais_pintura_das_anomalias()
        if not valores:
            return False
        atual = (self.var_percentuais["pintura_fachada"].get() or "").strip()
        if not atual:
            return False
        try:
            return not self._percentuais_iguais(atual, max(valores))
        except (TypeError, ValueError):
            return True

    def _sincronizar_percentual_pintura_fachada(self):
        """Pintura da fachada de cada estrutura = maior % das anomalias de
        pintura que acontecem nela (se o usuário não fixou o valor à mão)."""
        if self._pintura_fachada_manual:
            return
        self._sincronizando_percentuais = True
        try:
            for estrutura in self.aba_dados.estruturas:
                valores = self._percentuais_pintura_das_anomalias(estrutura.id)
                if not valores:
                    continue
                fmt = formatar_decimal_br(max(valores))
                var = estrutura.vars_pct["pintura_fachada"]
                atual = (var.get() or "").strip()
                if atual and self._percentuais_iguais(atual, fmt):
                    continue
                var.set(fmt)
        finally:
            self._sincronizando_percentuais = False

    def _atualizar_rotulo_percentual_pintura(self):
        if not hasattr(self, "var_percentual_pintura"):
            return
        bruto = (self.var_percentuais["pintura_fachada"].get() or "").strip()
        if not bruto:
            self.var_percentual_pintura.set("—")
            return
        try:
            texto = formatar_decimal_br(numero(bruto, percentual=True))
        except (TypeError, ValueError):
            self.var_percentual_pintura.set("—")
            return
        self.var_percentual_pintura.set(f"{texto}%")

    def _coletar_percentuais_faltantes(
        self, reparo, local=LOCAL_RESIDENCIAL
    ) -> dict[str, str] | None:
        """Pergunta os percentuais da aba 1 que a fórmula usa e ainda estão vazios.

        None se o usuário cancelar. Os que a anomalia já declara são preenchidos
        depois com o percentual dela, então não entram nesta pergunta.
        """
        declarados = set(percentuais_aba1_validos((reparo or {}).get("percentuais_aba1")))
        declarados.discard("pintura_fachada")
        pcts = self.aba_dados.percentuais_do_local(local)
        respostas: dict[str, str] = {}
        for chave in percentuais_dos_fatores(
            reparo, getattr(self, "_etapa_por_id", None)
        ):
            if chave in declarados or chave not in pcts:
                continue
            if (pcts[chave].get() or "").strip():
                continue
            rotulo = ROTULOS_PERCENTUAIS_ABA1.get(chave, chave)
            valor = self._perguntar_percentual_aba1(rotulo)
            if valor is None:
                return None
            respostas[chave] = valor
        return respostas

    def _perguntar_percentual_aba1(self, rotulo: str):
        while True:
            texto = perguntar_texto(
                self.winfo_toplevel(),
                "Percentual da aba 1",
                f"«{rotulo}» está vazio na aba 1.\nQual percentual deve ser adotado?",
                valor_inicial="",
                texto_ok="Usar",
                largura_entrada=12,
            )
            if texto is None:
                return None
            bruto = str(texto).strip()
            if not bruto:
                self._mostrar_feedback("Informe o percentual.", "red")
                continue
            try:
                parse_expressao(bruto)
                valor = numero(bruto, percentual=True)
            except (TypeError, ValueError):
                self._mostrar_feedback("Percentual inválido.", "red")
                continue
            if valor < 0:
                self._mostrar_feedback("Percentual inválido.", "red")
                continue
            return formatar_decimal_br(valor)

    def _gravar_percentuais_aba1(self, valores: dict[str, str], local=LOCAL_RESIDENCIAL) -> None:
        if not valores:
            return
        pcts = self.aba_dados.percentuais_do_local(local)
        self._sincronizando_percentuais = True
        try:
            for chave, valor in valores.items():
                var = pcts.get(chave)
                if var is not None:
                    var.set(valor)
        finally:
            self._sincronizando_percentuais = False

    def _perguntar_percentual_anomalia(self, nome: str, valor_inicial: str = "100"):
        texto = perguntar_texto(
            self.winfo_toplevel(),
            "Percentual da anomalia",
            f"Qual percentual de quantitativo aplicar em '{nome}'?",
            valor_inicial=str(valor_inicial or "100"),
            texto_ok="Usar",
            largura_entrada=12,
        )
        if texto is None:
            return None
        bruto = str(texto).strip() or "100"
        try:
            parse_expressao(bruto)
        except ValueError:
            self._mostrar_feedback("Percentual inválido.", "red")
            return None
        valor = numero(bruto, percentual=True)
        if valor < 0:
            self._mostrar_feedback("Percentual inválido.", "red")
            return None
        return formatar_decimal_br(valor)

    def _carregar_etapas(self):
        try:
            from core.etapas_predefinidas_storage import (
                carregar,
                listar,
                obter_cache_catalogo,
            )

            if obter_cache_catalogo() is None:
                carregar()
            self._etapas = listar()
        except (ValueError, OSError):
            self._etapas = []
        self._etapa_por_rotulo = {}
        self._etapa_por_id = {}
        for etapa in self._etapas:
            rotulo = etapa.get("nome") or ""
            self._etapa_por_rotulo[rotulo] = etapa
            ident = str(etapa.get("id") or "")
            if ident:
                self._etapa_por_id[ident] = etapa

    def _listar_composicoes(self):
        try:
            return listar_composicoes_catalogo()
        except (ValueError, OSError, TypeError):
            return []

    def _composicoes_para_calculo(self):
        """Catálogo só para leitura, reaproveitado até o próximo ciclo ocioso do Tk.

        listar() faz deepcopy do catálogo inteiro (e pode ir à API se o cache
        estiver vazio); antes isso acontecia uma vez por linha de anomalia.
        Não repassar a diálogos: eles devem receber _listar_composicoes().
        """
        if self._composicoes_ciclo is None:
            self._composicoes_ciclo = self._listar_composicoes()
            try:
                self.after_idle(self._descartar_composicoes_ciclo)
            except tk.TclError:
                self._composicoes_ciclo = None
                return self._listar_composicoes()
        return self._composicoes_ciclo

    def _descartar_composicoes_ciclo(self):
        self._composicoes_ciclo = None

    def _adicionar_extra_etapa(self):
        from ui.orcamento_customizado import DialogoNovaEtapa

        self._carregar_etapas()
        modelos = list(self._etapas)
        catalogo = self._listar_composicoes()

        def ao_confirmar(nome, etapa_id):
            avisos = []
            try:
                if etapa_id:
                    etapa = self._etapa_por_id.get(str(etapa_id))
                    if etapa is None:
                        messagebox.showwarning(
                            "Nova etapa",
                            "O modelo selecionado não foi encontrado.",
                            parent=self.winfo_toplevel(),
                        )
                        return False
                    grupo_id, avisos = aplicar_etapa_no_orcamento(
                        self.orcamento,
                        etapa,
                        self.ctx.sinapi,
                        estado_do_combo(self.var_uf.get()),
                        catalogo,
                        nome_override=nome,
                    )
                else:
                    grupo_id = self.orcamento.adicionar_grupo(nome)
            except ValueError as exc:
                messagebox.showwarning(
                    "Nova etapa", str(exc), parent=self.winfo_toplevel()
                )
                return False

            grupo = self.orcamento.obter_grupo(grupo_id)
            if grupo is not None:
                grupo["origem"] = "manual"

            if avisos:
                messagebox.showwarning(
                    "Nova etapa",
                    "Etapa criada com avisos:\n\n" + "\n".join(avisos),
                    parent=self.winfo_toplevel(),
                )

            self._grade_focar_meta = {"tipo": TIPO_GRUPO, "id": grupo_id}
            self._marcar_sujo()
            self._registrar_historico("Etapa criada")
            self._recalcular()
            self._mostrar_feedback("Etapa adicionada ao orçamento.", "green")
            return True

        DialogoNovaEtapa(self.winfo_toplevel(), modelos, ao_confirmar)

    def _estado_selecionado(self):
        return estado_do_combo(self.var_uf.get())

    def _abrir_calculadora(self):
        abrir_calculadora(self.winfo_toplevel())

    def _montar_botao_calculadora(self, parent, *, side="left"):
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
            self._refs_icones.append(icone)
            kwargs["image"] = icone
        except (ImportError, FileNotFoundError, tk.TclError, OSError):
            kwargs["text"] = "Calc"
            kwargs["font"] = ("Arial", 9)
            kwargs["fg"] = self._cores.titulo
            kwargs["activeforeground"] = self._cores.titulo
        botao = tk.Button(parent, **kwargs)
        botao.pack(side=side)
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

    def _grupo_id_selecionado(self):
        if not hasattr(self, "grade"):
            return None
        return self.grade.obter_grupo_id_selecionado()

    def _meta_selecionada(self):
        if not hasattr(self, "grade"):
            return None
        return self.grade.obter_meta_selecionada()

    def _grupo_eh_anomalia(self, grupo_id) -> bool:
        grupo = self.orcamento.obter_grupo(grupo_id) if grupo_id else None
        return bool(grupo and grupo.get("origem") == "anomalia")

    def _estado_item_deve_fixar(self, estado_item, codigo=None):
        return deve_fixar_estado_sinapi(
            self.ctx.sinapi,
            codigo or "",
            estado_item,
            self._estado_selecionado(),
        )

    def _registrar_item_grade(self, descricao, focar_meta):
        self._grade_focar_meta = focar_meta
        self._marcar_sujo()
        self._registrar_historico(descricao)
        self._preencher_grade()

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
            messagebox.showwarning(
                "Adicionar item", str(exc), parent=self.winfo_toplevel()
            )
            return None
        self._registrar_item_grade(
            "Item SINAPI inserido",
            {"tipo": TIPO_SINAPI, "id": item_id, "grupo_id": grupo_id},
        )
        self._mostrar_feedback(f"Item {codigo} inserido.", "green")
        return item_id

    def _abrir_busca_sinapi(self):
        from ui.orcamento_customizado import DialogoBuscaSinapi

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
        from ui.orcamento_customizado import DialogoEstadoItemSinapi

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
                "Selecione o estado do condomínio na aba 1.",
                parent=self.winfo_toplevel(),
            )
            return

        try:
            quantidade = parse_quantidade_expressao(self.var_qtd_rapido.get())
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

    def _adicionar_composicao_propria(self):
        from ui.orcamento_customizado import DialogoBuscaComposicaoPropria

        grupo_id = self._grupo_id_selecionado()
        if not grupo_id:
            messagebox.showinfo(
                "Composição própria",
                "Selecione uma etapa na estrutura do orçamento.",
                parent=self.winfo_toplevel(),
            )
            return

        catalogo = self._listar_composicoes()
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
            self._registrar_item_grade(
                "Composição própria inserida",
                {
                    "tipo": TIPO_COMPOSICAO_PROPRIA,
                    "id": item_id,
                    "grupo_id": grupo_id,
                },
            )

        DialogoBuscaComposicaoPropria(
            self.winfo_toplevel(),
            self.ctx,
            catalogo,
            self._estado_selecionado(),
            ao_confirmar,
        )

    def _remover_extra(self):
        if not hasattr(self, "grade"):
            return
        metas = self.grade.obter_metas_selecionadas()
        if not metas:
            self._mostrar_feedback("Selecione uma etapa ou item para remover.", "orange")
            return
        grupos = [m for m in metas if m.get("tipo") == TIPO_GRUPO]
        itens = [m for m in metas if m.get("tipo") != TIPO_GRUPO]
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
            if self._grupo_eh_anomalia(grupos[0].get("id")):
                messagebox.showinfo(
                    "Remover etapa",
                    "Etapas geradas por anomalias são removidas na aba 2.",
                    parent=self.winfo_toplevel(),
                )
                return
            if not messagebox.askyesno(
                "Remover etapa",
                "Remover a etapa e todos os seus itens?",
                parent=self.winfo_toplevel(),
            ):
                return
            self.orcamento.remover_grupo(grupos[0]["id"])
            self._registrar_item_grade("Etapa removida", [])
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
        self._registrar_item_grade(
            "Itens removidos" if len(itens) > 1 else "Item removido",
            [],
        )

    def _dialogo_editar_quantidade(self, item_id):
        from ui.orcamento_customizado import DialogoEditarQuantidade

        grupo, item = self.orcamento.obter_item(item_id)
        if item is None:
            return

        def ao_confirmar(texto):
            try:
                qtd = parse_quantidade_expressao(texto)
                self.orcamento.atualizar_quantidade(item_id, qtd)
            except ValueError as exc:
                messagebox.showwarning(
                    "Quantidade", str(exc), parent=self.winfo_toplevel()
                )
                return
            _, atualizado = self.orcamento.obter_item(item_id)
            if atualizado is not None:
                atualizado["qtd_manual"] = True
            self._registrar_item_grade(
                "Quantidade alterada",
                {
                    "tipo": item["tipo"],
                    "id": item_id,
                    "grupo_id": grupo["id"] if grupo else None,
                },
            )

        DialogoEditarQuantidade(
            self.winfo_toplevel(),
            rotulo_item(item),
            item["quantidade"],
            ao_confirmar,
        )

    def _ao_menu_contexto_grade(self, meta, event):
        menu = tk.Menu(self, tearoff=0)
        eh_etapa = meta.get("tipo") == TIPO_GRUPO
        if eh_etapa:
            menu.add_command(
                label="Remover etapa",
                command=self._remover_extra,
            )
        else:
            if meta.get("tipo") == TIPO_COMPOSICAO_PROPRIA:
                menu.add_command(
                    label="Ver composição",
                    command=lambda m=dict(meta): self._abrir_previa_composicao(m),
                )
                discriminar = bool(meta.get("discriminar_componentes"))
                _grupo, item = self.orcamento.obter_item(meta.get("id"))
                if item is not None:
                    discriminar = bool(item.get("discriminar_componentes"))
                menu._var_discriminar = tk.BooleanVar(value=discriminar)
                menu.add_checkbutton(
                    label="Discriminar no Excel/Word",
                    variable=menu._var_discriminar,
                    command=lambda iid=meta.get("id"), var=menu._var_discriminar, gid=meta.get("grupo_id"): (
                        self._definir_discriminar_composicao(
                            iid, bool(var.get()), grupo_id=gid
                        )
                    ),
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
                command=self._remover_extra,
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
        catalogo = self._listar_composicoes()
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
            self._definir_discriminar_composicao(
                iid,
                valor,
                grupo_id=grupo["id"] if grupo else meta.get("grupo_id"),
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

    def _definir_discriminar_composicao(self, item_id, discriminar, *, grupo_id=None):
        grupo, item = self.orcamento.obter_item(item_id)
        if item is None:
            return
        if bool(item.get("discriminar_componentes")) == bool(discriminar):
            return
        try:
            self.orcamento.definir_discriminar_componentes(item_id, discriminar)
        except ValueError as exc:
            messagebox.showwarning(
                "Composição própria",
                str(exc),
                parent=self.winfo_toplevel(),
            )
            return
        self._registrar_item_grade(
            "Discriminação da composição alterada",
            {
                "tipo": TIPO_COMPOSICAO_PROPRIA,
                "id": item_id,
                "grupo_id": grupo["id"] if grupo else grupo_id,
            },
        )

    def _alterar_estado_item(self):
        from ui.orcamento_customizado import DialogoEstadoItemSinapi

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
            self._registrar_item_grade(
                "UF do item alterada",
                {
                    "tipo": meta["tipo"],
                    "id": item_id,
                    "grupo_id": grupo["id"] if grupo else meta.get("grupo_id"),
                },
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
        catalogo = self._listar_composicoes()
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
        from ui.orcamento_customizado import DialogoBuscaSinapi

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
        catalogo = self._listar_composicoes()

        def ao_substituir_sinapi(
            codigo, descricao, unidade, custo, _quantidade, estado, tipo_sinapi=""
        ):
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
                messagebox.showwarning(
                    "Editar item", str(exc), parent=self.winfo_toplevel()
                )
                return
            self._registrar_item_grade(
                "Item substituído",
                {
                    "tipo": TIPO_SINAPI,
                    "id": item_id,
                    "grupo_id": meta.get("grupo_id"),
                },
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
                messagebox.showwarning(
                    "Editar item", str(exc), parent=self.winfo_toplevel()
                )
                return
            self._registrar_item_grade(
                "Item substituído",
                {
                    "tipo": TIPO_COMPOSICAO_PROPRIA,
                    "id": item_id,
                    "grupo_id": meta.get("grupo_id"),
                },
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

    def _salvar_nome_grupo_inline(self, grupo_id, nome) -> bool:
        if self._grupo_eh_anomalia(grupo_id):
            self._mostrar_feedback(
                "O nome desta etapa segue a anomalia da aba 2.",
                "orange",
            )
            return False
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
        self._grade_focar_meta = {"tipo": TIPO_GRUPO, "id": grupo_id}
        self._marcar_sujo()
        self._registrar_historico("Etapa renomeada")
        self._recalcular()
        return True

    def _ao_reordenar_item_arraste(self, item_id, novo_indice):
        grupo, item = self.orcamento.obter_item(item_id)
        try:
            if not self.orcamento.mover_item_para_indice(item_id, novo_indice):
                return False
        except ValueError as exc:
            messagebox.showwarning("Item", str(exc), parent=self.winfo_toplevel())
            return False
        self._registrar_item_grade(
            "Item reordenado",
            {
                "tipo": item.get("tipo") if item else None,
                "id": item_id,
                "grupo_id": grupo.get("id") if grupo else None,
            },
        )
        return True

    def _ao_reordenar_etapa_arraste(self, grupo_id, novo_indice):
        try:
            if not self.orcamento.mover_grupo_para_indice(grupo_id, novo_indice):
                return False
        except ValueError as exc:
            messagebox.showwarning("Etapa", str(exc), parent=self.winfo_toplevel())
            return False
        self._grade_focar_meta = {"tipo": TIPO_GRUPO, "id": grupo_id}
        self._marcar_sujo()
        self._registrar_historico("Etapa reordenada")
        self._recalcular()
        return True

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

    def _atualizar_preview_orcamento(self):
        uf = estado_do_combo(self.var_uf.get())
        bdi = numero(self.var_bdi.get())
        try:
            self.orcamento.definir_bdi(bdi)
        except (TypeError, ValueError):
            bdi = self.orcamento.bdi_percent
        self.orcamento.definir_nome(self.var_nome.get().strip())
        self.orcamento.definir_estado_referencia(uf)

        sincronizar_grupos_anomalias(
            self.orcamento,
            anomalias=self._anomalias_orcamento,
            catalogo=self._catalogo,
            quantitativos=self._quantitativos,
            quantitativos_por_local=self._quantitativos_por_local,
            rotulos_locais=dict(self._locais),
            etapas_por_id=self._etapa_por_id,
            sinapi=self.ctx.sinapi,
            uf=uf,
            considerar_servicos_preliminares=bool(self.var_considerar_sp.get()),
            considerar_pintura=bool(self.var_considerar_pintura.get()),
            duas_demaos_fundo_selador=bool(self.var_duas_demaos_selador.get()),
            considerar_destinacao_entulho=bool(self.var_considerar_entulho.get()),
            considerar_limpeza_geral=bool(self.var_considerar_limpeza.get()),
        )
        itens_uf_fixada = {
            item["id"]: {
                "estado": item.get("estado"),
                "custo_unitario": item.get("custo_unitario"),
            }
            for grupo in self.orcamento.grupos
            for item in grupo.get("itens") or []
            if item.get("estado_fixado")
        }
        sincronizar_precos_sinapi_no_orcamento(self.orcamento, self.ctx.sinapi, uf)
        if itens_uf_fixada:
            for grupo in self.orcamento.grupos:
                for item in grupo.get("itens") or []:
                    salvo = itens_uf_fixada.get(item.get("id"))
                    if not salvo:
                        continue
                    item["estado"] = salvo.get("estado")
                    item["estado_fixado"] = True
                    if salvo.get("custo_unitario") is not None:
                        item["custo_unitario"] = salvo["custo_unitario"]
        self._preencher_grade()

    def _mostrar_variacao_total(self, variacao):
        if abs(variacao) < 0.005:
            return
        if variacao > 0:
            texto = f"+ {_formatar_moeda(variacao)}"
            cor = "#ffb74d" if self._cores.escuro else "#a67c00"
        else:
            texto = f"− {_formatar_moeda(-variacao)}"
            cor = "#66bb6a" if self._cores.escuro else "#2e7d32"
        self.var_variacao_total.set(texto)
        try:
            self.lbl_variacao_total.configure(fg=cor)
        except (tk.TclError, AttributeError):
            pass
        if self._job_variacao_total is not None:
            try:
                self.after_cancel(self._job_variacao_total)
            except (tk.TclError, ValueError):
                pass
        self._job_variacao_total = self.after(6000, self._limpar_variacao_total)

    def _limpar_variacao_total(self):
        self._job_variacao_total = None
        self.var_variacao_total.set("")

    def _grade_visivel(self) -> bool:
        """A aba 3 está selecionada e o módulo está na tela."""
        try:
            return (
                self.notebook.select() == str(self._aba_orcamento)
                and bool(self.winfo_ismapped())
            )
        except (tk.TclError, AttributeError):
            return True  # na dúvida, redesenha (comportamento antigo)

    def _ao_mostrar_grade(self, _event=None):
        if self._grade_pendente and not self._carregando:
            self.after_idle(self._preencher_grade_se_pendente)

    def _preencher_grade_se_pendente(self):
        if self._grade_pendente and not self._carregando and self._grade_visivel():
            self._preencher_grade()

    def _preencher_grade(self):
        catalogo = self._composicoes_para_calculo()
        estado_atual = estado_do_combo(self.var_uf.get())
        bdi = self.orcamento.bdi_percent
        total = self._total_geral_calculado(bdi, catalogo, estado_atual)
        anterior = self._total_geral_ultimo
        self._total_geral_ultimo = total
        # Abrir rascunho e Desfazer/Refazer já têm mensagem própria.
        if (
            anterior is not None
            and not self._carregando
            and not self._aplicando_historico
        ):
            self._mostrar_variacao_total(total - anterior)
        self.var_total.set(
            f"Total geral (c/ BDI {_formatar_bdi(bdi)}%): {_formatar_moeda(total)}"
        )
        if not hasattr(self, "grade"):
            return
        if not self._grade_visivel():
            # Redesenhar a grade é a parte mais cara do recálculo (~1.000
            # widgets). Escondida, ela só é refeita quando voltar a aparecer.
            self._grade_pendente = True
            return
        self._grade_pendente = False
        # Com muitos itens, refazer a grade ainda leva ~1,5 s: mostra o cursor
        # de espera (sem texto, para não apagar outra mensagem da barra).
        self._executar_com_carregamento(
            None, lambda: self._reconstruir_grade(catalogo, estado_atual, bdi)
        )

    def _reconstruir_grade(self, catalogo, estado_atual, bdi):
        self.grade.iniciar_reconstrucao()
        fracao = self.grade.salvar_fracao_scroll()
        focar = self._grade_focar_meta
        self._grade_focar_meta = None
        if focar is None:
            selecoes = self.grade.obter_metas_selecionadas()
        elif focar == []:
            selecoes = []
        elif isinstance(focar, dict):
            selecoes = [focar]
        else:
            selecoes = list(focar)
        self.grade.limpar()

        for idx_grupo, grupo in enumerate(self.orcamento.grupos, start=1):
            sub_grupo = self._subtotal_grupo_calculado(
                grupo, bdi, catalogo, estado_atual
            )
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
                    total_item = subtotal_item(item, bdi)
                    indisponivel = item_indisponivel_na_base(
                        item, self.ctx.sinapi, catalogo, estado_atual
                    )
                    usa_uf_alt = item_usa_estado_alternativo(
                        item, estado_atual, catalogo, self.ctx.sinapi
                    )
                    descricao = item["descricao"]
                    if usa_uf_alt:
                        uf_alt = estado_efetivo_item(
                            item, estado_atual, self.ctx.sinapi
                        )
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
                            "total": _formatar_moeda(total_item),
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
                    total_item = custo_bdi * item["quantidade"]
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
                            "custo_unit": _formatar_moeda(custo_unit)
                            if estado_atual
                            else "—",
                            "custo_bdi": _formatar_moeda(custo_bdi)
                            if estado_atual
                            else "—",
                            "total": _formatar_moeda(total_item)
                            if estado_atual
                            else "—",
                        },
                        estilo="composicao",
                        alerta_depreciado=tem_depreciado,
                        alerta_estado_alternativo=usa_uf_alt
                        and not tem_depreciado
                        and not discriminar,
                        alerta_discriminar=discriminar and not tem_depreciado,
                    )

        self.grade.finalizar_reconstrucao(fracao, selecoes)
        if hasattr(self, "var_filtro_grade"):
            self.grade.aplicar_filtro(self.var_filtro_grade.get())
        if not self.orcamento.grupos:
            self.grade.definir_vazio(
                "Nenhuma etapa neste orçamento.\n"
                "Inclua anomalias na aba 2 ou clique em \"Nova etapa\" para começar."
            )

    def _gerar_orcamento(self):
        self._recalcular()
        try:
            self.notebook.select(self._aba_orcamento)
        except (tk.TclError, AttributeError):
            pass
        self._mostrar_feedback("Itens gerados novamente.", "green")

    def _atualizar_estado_planilha(self):
        botao = getattr(self, "btn_gerar_planilha", None)
        if botao is None:
            return
        liberado = bool(str(self._orcamento_customizado_id or "").strip())
        try:
            botao.configure(
                state=("normal" if liberado else "disabled"),
                cursor=("hand2" if liberado else "arrow"),
            )
        except tk.TclError:
            pass

    def _nome_orcamento_customizado(self) -> str:
        nome = self.var_nome.get().strip() or "SEM CONDOMINIO"
        municipio = self.var_municipio.get().strip()
        uf = estado_do_combo(self.var_uf.get())
        if municipio and uf:
            return f"{nome} - {municipio}-{uf}"
        if municipio:
            return f"{nome} - {municipio}"
        if uf:
            return f"{nome} - {uf}"
        return nome

    def _preparar_orcamento_para_customizados(self) -> bool:
        if not self.orcamento.grupos:
            messagebox.showwarning(
                "Salvar em Orçamentos Customizados",
                "Não há etapas/itens para salvar.\n"
                "Gere os itens novamente ou inclua anomalias na aba 2.",
                parent=self.winfo_toplevel(),
            )
            return False
        uf = estado_do_combo(self.var_uf.get())
        if not uf:
            messagebox.showwarning(
                "Salvar em Orçamentos Customizados",
                "Selecione a UF do condomínio antes de salvar.",
                parent=self.winfo_toplevel(),
            )
            return False
        self._atualizar_preview_orcamento()
        self.orcamento.definir_nome(self._nome_orcamento_customizado())
        self.orcamento.definir_estado_referencia(uf)
        try:
            self.orcamento.definir_bdi(numero(self.var_bdi.get()))
        except (TypeError, ValueError):
            pass
        return True

    def _registro_customizado_vinculado(self):
        ident = str(self._orcamento_customizado_id or "").strip()
        if not ident:
            return None
        try:
            return obter_orcamento_dict(ident)
        except ValueError:
            return None

    def _salvar_em_customizados(self):
        if not self._preparar_orcamento_para_customizados():
            return
        registro = self._registro_customizado_vinculado()
        substituir = False
        if registro is not None:
            nome_salvo = str(registro.get("nome") or "sem nome").strip() or "sem nome"
            escolha = messagebox.askyesnocancel(
                "Orçamento já salvo",
                f"Este rascunho já está em Orçamentos Customizados como "
                f"«{nome_salvo}».\n\n"
                "Deseja substituir o arquivo já salvo?\n\n"
                "Sim — substituir o orçamento salvo\n"
                "Não — salvar como cópia nova\n"
                "Cancelar — não salvar",
                parent=self.winfo_toplevel(),
            )
            if escolha is None:
                return
            substituir = bool(escolha)
        try:
            if substituir and registro is not None:
                self.orcamento.id = str(registro.get("id") or self._orcamento_customizado_id)
                self.orcamento.versao = int(registro.get("versao", 1) or 1)
                atualizar_orcamento_na_lista(self.orcamento)
                self._orcamento_customizado_id = str(self.orcamento.id)
                mensagem = "Orçamento customizado atualizado."
            else:
                copia = deepcopy(self.orcamento)
                copia.id = novo_id()
                copia.versao = 1
                salvo_id = adicionar_orcamento_importado(copia)
                self._orcamento_customizado_id = str(salvo_id)
                self.orcamento.id = str(salvo_id)
                self.orcamento.versao = getattr(copia, "versao", 1)
                mensagem = (
                    "Cópia salva em Orçamentos Customizados."
                    if registro is not None
                    else "Salvo em Orçamentos Customizados."
                )
        except ValueError as exc:
            messagebox.showwarning(
                "Salvar em Orçamentos Customizados",
                str(exc),
                parent=self.winfo_toplevel(),
            )
            return
        self._atualizar_estado_planilha()
        self._marcar_sujo()
        self._mostrar_feedback(mensagem, "green")

    def _exportar_planilha(self):
        if not str(self._orcamento_customizado_id or "").strip():
            messagebox.showinfo(
                "Gerar Planilha",
                "Salve o orçamento em Orçamentos Customizados antes de gerar a planilha.",
                parent=self.winfo_toplevel(),
            )
            return
        if not self.orcamento.grupos:
            messagebox.showwarning(
                "Gerar Planilha",
                "Não há etapas/itens para exportar.",
                parent=self.winfo_toplevel(),
            )
            return
        if hasattr(self, "grade") and self.grade.tem_itens_depreciados():
            messagebox.showerror(
                "Gerar Planilha",
                "Há composições/insumos depreciados. Por favor, altere para um item atual.",
                parent=self.winfo_toplevel(),
            )
            return
        # Import só aqui: abrir a Área Comum não precisa pagar por ele.
        from ui.dialogo_selecionar_modelo_planilha import DialogoSelecionarModeloPlanilha

        DialogoSelecionarModeloPlanilha(
            self.winfo_toplevel(),
            on_selecionar=self._ao_selecionar_modelo_planilha,
        )

    def _ao_selecionar_modelo_planilha(self, numero):
        # Import só aqui: a exportação carrega o openpyxl (~0,3 s), que não
        # precisa pesar na abertura do módulo para quem não gera planilha.
        from core.exportacao_planilha_orcamento import (
            exportar_orcamento_customizado_modelo4,
            exportar_orcamento_customizado_modelo_formatado,
        )

        referencia = getattr(self.ctx, "sinapi_referencia_rotulo", "") or "BASE AUSENTE"
        if referencia == "BASE AUSENTE":
            referencia = "Base não carregada"
        parent = self.winfo_toplevel()
        catalogo = self._listar_composicoes()
        estado = estado_do_combo(self.var_uf.get())
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

    def _mostrar_feedback(self, texto, cor="gray", *, temporario=True):
        cores = self._cores
        mapa = {
            "green": "#2e7d32",
            "orange": "#ffb74d" if cores.escuro else "#a67c00",
            "red": cores.perigo,
            "gray": cores.texto_suave,
        }
        self.var_feedback.set(texto)
        try:
            self.lbl_feedback.configure(fg=mapa.get(cor, cor))
        except tk.TclError:
            pass
        if self._job_feedback is not None:
            try:
                self.after_cancel(self._job_feedback)
            except (tk.TclError, ValueError):
                pass
            self._job_feedback = None
        if temporario:
            self._job_feedback = self.after(5000, lambda: self.var_feedback.set(""))

    def _ao_destruir(self, event=None):
        if event is not None and event.widget is not self:
            return
        if self._janela_orccad is not None:
            try:
                self._janela_orccad._fechar()
            except tk.TclError:
                pass
            self._janela_orccad = None
        self._flush_autosave()
        for widget, sequencia, func_id in self._binds_historico:
            try:
                widget.unbind(sequencia, func_id)
            except tk.TclError:
                pass
        self._binds_historico.clear()
        topo = self.winfo_toplevel()
        try:
            topo.unbind("<Control-s>")
            topo.unbind("<Control-S>")
        except tk.TclError:
            pass
