"""Módulo de orçamento para Área Comum."""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
import traceback
from copy import deepcopy
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core.area_comum import (
    BDI_PADRAO,
    CAMPOS_MEDIDA_AUTO,
    CAMPOS_MEDIDA_EDITAVEIS,
    CAMPOS_RESUMO_FACHADA,
    ESQUADRIAS_MODELO,
    PERCENTUAIS_MODELO,
    TIPOS_COBERTURA,
    TIPOS_ESTRUTURA,
    nova_anomalia_orcamento,
    novo_rascunho,
    normalizar_rascunho,
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
    limitar_revestimento_fachada,
    reparo_recomendado,
    valores_considerados_reparo,
)
from core.area_comum_calculos import calcular_quantitativos, numero, parse_expressao
from core.area_comum_orcamento import (
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
from core.sinapi_busca import deve_fixar_estado_sinapi, estados_com_codigo, obter_item_sinapi
from ui.calculadora import abrir_calculadora
from ui.dialogo_previa_composicao import DialogoPreviaComposicao
from ui.dialogo_config_anomalias_area_comum import DialogoConfigAnomaliasAreaComum
from ui.desenho_2d import CHAVES_MEDIDA_ORCCAD, PreviaDesenho2D, VistaIsometricaBloco
from ui.grade_orcamento import GradeOrcamento
from ui.icones import (
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


def _nome_arquivo_sugerido(nome_condominio: str) -> str:
    texto = (nome_condominio or "").strip() or "sem_condominio"
    invalidos = '<>:"/\\|?*'
    for caractere in invalidos:
        texto = texto.replace(caractere, "_")
    texto = "_".join(texto.split())
    return f"area_comum_{texto}.json"


def _fmt(valor, casas=2, *, inteiro=False) -> str:
    if valor is None or valor == 0:
        return "—"
    if inteiro:
        return formatar_decimal_br(valor, 0)
    return formatar_decimal_br(valor, casas)


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


def _fmt_medida(valor, unidade: str) -> str:
    if valor is None or valor == 0:
        return "—"
    return f"{_numero_br_fixo(valor)} {unidade}"


CHAVES_INTEIRAS = {
    "qtd_aptos_por_bloco",
    "qtd_aptos_total",
    "caixas_inspecao_total",
    "caixas_gordura_total",
}


def _formatar_moeda(valor):
    return formatar_moeda_br(valor)


def _formatar_quantidade(valor):
    return formatar_decimal_br(valor, casas=4)


def _largura_combo_para_opcoes(combo, textos) -> int:
    """Largura em caracteres do campo de texto (a seta do combo fica além disso)."""
    try:
        fonte = tkfont.Font(font=combo.cget("font") or "TkDefaultFont")
    except tk.TclError:
        fonte = tkfont.nametofont("TkDefaultFont")
    px = max((fonte.measure(str(texto)) for texto in textos), default=60)
    zero = max(fonte.measure("0"), 1)
    return max(1, (px + zero - 1) // zero)


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
        self._painel_carregamento = None
        self._lbl_etapa_carregamento = None
        self._composicoes_ciclo = None
        self._avisos_ultima_carga = []
        self._total_geral_ultimo = None
        self._perguntando_uf = False
        self._aplicando_historico = False
        self._caminho_arquivo = None
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
        self._anomalias_orcamento = []
        self._etapas = []
        self._etapa_por_id = {}
        self._etapa_por_rotulo = {}
        self.orcamento = OrcamentoCustomizado()
        self._grade_focar_meta = None
        self.entrada_nome = None
        self.entrada_municipio = None
        self.combo_uf = None
        self.combo_uf_dados = None
        self._desenho_principal = {
            "externa": {"pontos": [], "fechado": False},
            "hall": {"pontos": [], "fechado": False},
        }
        self._janela_orccad = None

        self.var_nome = tk.StringVar()
        self.var_municipio = tk.StringVar()
        self.var_uf = tk.StringVar(value=PLACEHOLDER_ESTADO)
        self.var_bdi = tk.StringVar(value=BDI_PADRAO)
        self.var_tipo_estrutura = tk.StringVar(value=PLACEHOLDER_ESTADO)
        self.var_tipo_cobertura = tk.StringVar(value=PLACEHOLDER_ESTADO)
        self.var_medidas = {
            chave: tk.StringVar() for chave, _rotulo in CAMPOS_MEDIDA_EDITAVEIS
        }
        self.var_medidas_auto = {
            chave: tk.StringVar(value="—") for chave, _rotulo, _unidade in CAMPOS_MEDIDA_AUTO
        }
        self.var_resumo = {
            chave: tk.StringVar(value="—") for chave, _rotulo, _un in CAMPOS_RESUMO_FACHADA
        }
        self.var_percentuais = {item[0]: tk.StringVar(value=item[2]) for item in PERCENTUAIS_MODELO}
        self.var_pct_qtd = {item[0]: tk.StringVar(value="—") for item in PERCENTUAIS_MODELO}
        self.var_esquadrias = {}
        for modelo in ESQUADRIAS_MODELO:
            self.var_esquadrias[modelo["id"]] = {
                "dim_x": tk.StringVar(),
                "dim_y": tk.StringVar(),
                "h_peitoril": tk.StringVar(),
                "qtd_por_pav": tk.StringVar(),
                "perimetro": tk.StringVar(value="—"),
                "pingadeira": tk.StringVar(value="—"),
                "area": tk.StringVar(value="—"),
                "sem_perimetro": bool(modelo.get("sem_perimetro")),
            }
        self.var_esquadrias_total = {
            "qtd_por_pav": tk.StringVar(value="—"),
            "perimetro": tk.StringVar(value="—"),
            "pingadeira": tk.StringVar(value="—"),
            "area": tk.StringVar(value="—"),
        }
        self.var_arquivo = tk.StringVar(value="Rascunho novo")
        self.var_feedback = tk.StringVar(value="")
        self.var_total = tk.StringVar(value="Total geral: R$ 0,00")
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
        self.var_legenda_desenho = tk.StringVar(value="Ainda não há planta salva.")

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
        faixa = tk.LabelFrame(
            parent,
            text="Condomínio",
            bg=fundo,
            fg=cores.texto,
            padx=10,
            pady=8,
        )
        faixa.pack(fill="x", pady=(8, 8), padx=8)

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
        criar_botao_ttk_com_icone(
            linha_botoes,
            texto="Gerar orçamento",
            nome_icone="construct-outline",
            command=self._gerar_orcamento,
            estilo=self._estilos.compacto,
            cor_icone=self._estilos.icone,
            refs=self._refs_icones,
        ).pack(side="left")
        criar_botao_ttk_com_icone(
            linha_botoes,
            texto="Salvar em Orçamentos Customizados",
            nome_icone="save-outline",
            command=self._salvar_em_customizados,
            estilo=self._estilos.compacto,
            cor_icone=self._estilos.icone,
            refs=self._refs_icones,
        ).pack(side="left", padx=(6, 0))

    def _caixa(self, parent, var, rotulo, unidade="", wraplength=168, *, compacta=False):
        cores = self._cores
        caixa = tk.Frame(
            parent,
            bg=cores.fundo_cartao_off,
            highlightbackground=cores.borda_suave,
            highlightthickness=1,
            padx=6 if compacta else 8,
            pady=1 if compacta else 4,
        )
        texto = rotulo if compacta or not unidade else f"{rotulo} ({unidade})"
        fonte_valor = ("Segoe UI", 9 if compacta else 10, "bold")
        valor = tk.Label(
            caixa,
            textvariable=var,
            bg=cores.fundo_cartao_off,
            fg=cores.titulo,
            font=fonte_valor,
        )
        legenda = tk.Label(
            caixa,
            text=texto,
            bg=cores.fundo_cartao_off,
            fg=cores.texto_suave,
            font=("Segoe UI", 8),
            wraplength=wraplength,
            justify="left" if compacta else "center",
            anchor="w" if compacta else "center",
        )
        if compacta:
            caixa.valor_num = valor
            caixa.unidade = unidade
            unidade_lbl = tk.Label(
                caixa,
                text=unidade,
                bg=cores.fundo_cartao_off,
                fg=cores.titulo,
                font=fonte_valor,
            )
            caixa.valor_un = unidade_lbl
            caixa.folga_un = 4
            valor.configure(anchor="e")
            unidade_lbl.configure(anchor="w")
            valor.grid(row=0, column=0, sticky="nes")
            unidade_lbl.grid(row=0, column=1, sticky="nsw", padx=(caixa.folga_un, 0))
            legenda.grid(row=0, column=2, sticky="nsw", padx=(6, 0))
            caixa.rowconfigure(0, weight=1)
            caixa.columnconfigure(2, weight=1)
        else:
            valor.pack()
            legenda.pack()
        return caixa

    def _grade_caixas(self, parent, itens, colunas=5, *, compacta=False, wraplength=168):
        caixas = []
        for indice, item in enumerate(itens):
            var, rotulo = item[0], item[1]
            unidade = item[2] if len(item) > 2 else ""
            linha, col = divmod(indice, colunas)
            caixa = self._caixa(
                parent,
                var,
                rotulo,
                unidade,
                wraplength=wraplength,
                compacta=compacta,
            )
            caixa.grid(
                row=linha,
                column=col,
                sticky="nsew",
                padx=(0, 6),
                pady=2 if compacta else 4,
            )
            if compacta:
                caixas.append(caixa)
                var.trace_add("write", self._agendar_alinhamento_caixas)
        for col in range(colunas):
            parent.columnconfigure(col, weight=1)
        if caixas:
            grupos = getattr(self, "_grupos_caixas_compactas", None)
            if grupos is None:
                grupos = []
                self._grupos_caixas_compactas = grupos
            grupos.append(caixas)
            self._agendar_alinhamento_caixas()

    def _igualar_altura_titulos(self, *titulos):
        """A borda do quadro passa no meio do título. Alturas diferentes deslocam essa linha."""
        try:
            if not all(titulo.winfo_exists() for titulo in titulos):
                return
            self.update_idletasks()
            altura = max(titulo.winfo_reqheight() for titulo in titulos)
            for titulo in titulos:
                titulo.configure(width=max(titulo.winfo_reqwidth(), 1), height=altura)
                titulo.pack_propagate(False)
        except tk.TclError:
            return

    def _agendar_alinhamento_caixas(self, *_args):
        if getattr(self, "_job_alinhar_caixas", None) is not None:
            return
        self._job_alinhar_caixas = self.after_idle(self._aplicar_alinhamento_caixas)

    def _aplicar_alinhamento_caixas(self):
        self._job_alinhar_caixas = None
        try:
            self.update_idletasks()
        except tk.TclError:
            return
        for caixas in getattr(self, "_grupos_caixas_compactas", ()):
            maior = 0
            maior_un = 0
            for caixa in caixas:
                try:
                    maior = max(maior, caixa.valor_num.winfo_reqwidth())
                    if caixa.valor_un is not None:
                        maior_un = max(
                            maior_un,
                            caixa.valor_un.winfo_reqwidth() + caixa.folga_un,
                        )
                except tk.TclError:
                    return
            for caixa in caixas:
                caixa.columnconfigure(0, minsize=maior)
                caixa.columnconfigure(1, minsize=maior_un)

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
        cores = self._cores
        fundo = cores.fundo
        interior = self._aba_rolavel("1. Dados iniciais")
        self._montar_condominio_dados(interior)

        bloco_qtd = tk.LabelFrame(
            interior,
            text="Características do Empreendimento",
            bg=fundo,
            fg=cores.texto,
            padx=10,
            pady=8,
        )
        bloco_qtd.pack(fill="x", pady=(8, 8), padx=8)
        bloco_qtd.columnconfigure(0, weight=1)
        bloco_qtd.columnconfigure(1, weight=1, minsize=320)
        bloco_qtd.rowconfigure(0, weight=1)

        campos = tk.Frame(bloco_qtd, bg=fundo)
        campos.grid(row=0, column=0, sticky="nsew")
        campos.columnconfigure(1, weight=1)
        campos.columnconfigure(3, weight=1)

        caracteristicas = (
            ("tipo_estrutura", "Tipo de estrutura", TIPOS_ESTRUTURA, self.var_tipo_estrutura),
            ("tipo_cobertura", "Tipo de cobertura", TIPOS_COBERTURA, self.var_tipo_cobertura),
        )
        textos_tipos = (PLACEHOLDER_ESTADO, *TIPOS_ESTRUTURA, *TIPOS_COBERTURA)
        largura_tipos = None
        for col_grupo, (_chave, rotulo, opcoes, var) in enumerate(caracteristicas):
            col = col_grupo * 2
            tk.Label(
                campos, text=rotulo + ":", bg=fundo, fg=cores.texto, anchor="w"
            ).grid(row=0, column=col, sticky="w", pady=2, padx=(0, 6))
            combo = ttk.Combobox(
                campos,
                textvariable=var,
                values=(PLACEHOLDER_ESTADO, *opcoes),
                state="readonly",
            )
            if largura_tipos is None:
                largura_tipos = _largura_combo_para_opcoes(combo, textos_tipos)
            combo.configure(width=largura_tipos)
            combo.grid(row=0, column=col + 1, sticky="w", pady=2, padx=(0, 18))
            combo.bind("<<ComboboxSelected>>", lambda _e: self._ao_alterar_campo())
            _vincular_combo_fecha_ao_rolar(combo)

        linha_vazia = tk.Frame(campos, bg=fundo, height=16)
        linha_vazia.grid(row=1, column=0, columnspan=4, sticky="ew")
        linha_vazia.grid_propagate(False)

        for indice, (chave, rotulo) in enumerate(CAMPOS_MEDIDA_EDITAVEIS):
            linha = 2 + indice // 2
            col = (indice % 2) * 2
            tk.Label(campos, text=rotulo + ":", bg=fundo, fg=cores.texto, anchor="w").grid(
                row=linha, column=col, sticky="w", pady=2, padx=(0, 6)
            )
            # Mesmo widget em todos (tk.Entry): no Windows o ttk ignora
            # fieldbackground, e misturar ttk/tk desalinha a coluna.
            fundo_campo = (
                cores.fundo_cartao_off
                if chave in CHAVES_MEDIDA_ORCCAD
                else cores.fundo_cartao
            )
            entrada = tk.Entry(
                campos,
                textvariable=self.var_medidas[chave],
                width=12,
                bg=fundo_campo,
                fg=cores.texto,
                insertbackground=cores.texto,
                relief="solid",
                bd=1,
                highlightthickness=0,
            )
            entrada.grid(row=linha, column=col + 1, sticky="w", pady=2, padx=(0, 18))
            self._vincular_campo_numerico(entrada)

        linha_auto = 2 + (len(CAMPOS_MEDIDA_EDITAVEIS) + 1) // 2
        tk.Label(
            campos,
            text="Quantitativos calculados automaticamente",
            bg=fundo,
            fg=cores.titulo,
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).grid(row=linha_auto, column=0, columnspan=4, sticky="w", pady=(10, 2))
        caixas_auto = tk.Frame(campos, bg=fundo)
        caixas_auto.grid(row=linha_auto + 1, column=0, columnspan=4, sticky="ew")
        self._grade_caixas(
            caixas_auto,
            [
                (self.var_medidas_auto[chave], rotulo, unidade)
                for chave, rotulo, unidade in CAMPOS_MEDIDA_AUTO
            ],
            colunas=2,
            compacta=True,
            wraplength=150,
        )

        lado_desenho = tk.Frame(bloco_qtd, bg=fundo)
        lado_desenho.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        lado_desenho.rowconfigure(1, weight=1)
        lado_desenho.rowconfigure(3, weight=1)
        lado_desenho.columnconfigure(0, weight=1)
        criar_botao_ttk_com_icone(
            lado_desenho,
            texto="Abrir ORCCAD",
            nome_icone="cube-outline",
            command=self._abrir_orccad,
            estilo=self._estilos.compacto,
            cor_icone=self._estilos.icone,
            refs=self._refs_icones,
        ).grid(row=0, column=0, sticky="w")
        self.previa_desenho = PreviaDesenho2D(lado_desenho, largura=340, altura=220)
        self.previa_desenho.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        tk.Label(
            lado_desenho,
            textvariable=self.var_legenda_desenho,
            bg=fundo,
            fg=cores.titulo,
            font=("Segoe UI", 8),
            anchor="w",
            justify="left",
            wraplength=340,
        ).grid(row=2, column=0, sticky="ew", pady=(4, 0))
        self.vista_bloco = VistaIsometricaBloco(lado_desenho, largura=340, altura=220)
        self.vista_bloco.grid(row=3, column=0, sticky="nsew", pady=(8, 0))

        faixa_esq = tk.Frame(interior, bg=fundo)
        faixa_esq.pack(fill="x", pady=(0, 8), padx=8)

        titulo_esq = tk.Frame(faixa_esq, bg=fundo)
        tk.Label(
            titulo_esq,
            text="Medidas das esquadrias",
            bg=fundo,
            fg=cores.texto,
        ).pack(side="left")
        caixa_info_esq = tk.Frame(
            titulo_esq,
            bg=fundo,
            highlightbackground=cores.borda_suave,
            highlightthickness=1,
            bd=0,
            cursor="hand2",
        )
        caixa_info_esq.pack(side="left", padx=(4, 0))
        info_esq = tk.Label(
            caixa_info_esq,
            text="?",
            bg=fundo,
            fg=cores.texto_suave,
            font=("Segoe UI", 8),
            cursor="hand2",
            relief="flat",
            bd=0,
            padx=3,
            pady=0,
        )
        info_esq.pack()
        texto_dica_esq = (
            "Perímetro, pingadeira e área são por pavimento.\n"
            "A área de esquadrias (janelas, porta do hall e cobogós) "
            "é descontada da fachada.\n"
            "Área de janelas, perímetro e pingadeira não incluem "
            "a porta do hall nem os cobogós."
        )
        vincular_tooltip(caixa_info_esq, texto_dica_esq)
        vincular_tooltip(info_esq, texto_dica_esq)
        bloco_esq = tk.LabelFrame(
            faixa_esq,
            labelwidget=titulo_esq,
            bg=fundo,
            fg=cores.texto,
            padx=10,
            pady=8,
        )
        bloco_esq.pack(side="left", fill="y", anchor="n")
        self._bloco_esquadrias = bloco_esq
        janela_esq = self.winfo_toplevel()
        janela_esq.bind("<Escape>", self._ao_esc_esquadrias, add="+")
        janela_esq.bind("<Button-1>", self._ao_clique_fora_esquadrias, add="+")

        cabecalhos = (
            "Esquadria",
            "Dim. X (m)",
            "Dim. Y (m)",
            "H peitoril (m)",
            "Qtde. por pav.",
            "Perímetro",
            "Pingadeira",
            "Área",
        )
        for col, texto in enumerate(cabecalhos):
            tk.Label(
                bloco_esq,
                text=texto,
                bg=fundo,
                fg=cores.texto,
                font=("Segoe UI", 8, "bold"),
            ).grid(row=0, column=col, padx=4, pady=(0, 4), sticky="w")

        for indice, modelo in enumerate(ESQUADRIAS_MODELO, start=1):
            ident = modelo["id"]
            vars_e = self.var_esquadrias[ident]
            tk.Label(bloco_esq, text=modelo["rotulo"], bg=fundo, fg=cores.texto, anchor="w").grid(
                row=indice, column=0, sticky="w", padx=4, pady=2
            )
            for col, chave_e in enumerate(("dim_x", "dim_y", "h_peitoril", "qtd_por_pav"), start=1):
                entrada_e = ttk.Entry(bloco_esq, textvariable=vars_e[chave_e], width=9)
                entrada_e.grid(row=indice, column=col, padx=4)
                self._vincular_campo_numerico(entrada_e, casas=2)
            for col, chave in enumerate(("perimetro", "pingadeira", "area"), start=5):
                tk.Label(
                    bloco_esq,
                    textvariable=vars_e[chave],
                    bg=cores.fundo_cartao_off,
                    fg=cores.titulo,
                    width=12,
                    relief="solid",
                    bd=1,
                ).grid(row=indice, column=col, padx=4, pady=2)

        linha_total = len(ESQUADRIAS_MODELO) + 1
        tk.Label(
            bloco_esq,
            text="TOTAL POR PAVIMENTO",
            bg=fundo,
            fg=cores.titulo,
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).grid(
            row=linha_total,
            column=0,
            columnspan=4,
            sticky="w",
            padx=4,
            pady=(6, 2),
        )
        tk.Label(
            bloco_esq,
            textvariable=self.var_esquadrias_total["qtd_por_pav"],
            bg=cores.fundo_cartao_off,
            fg=cores.titulo,
            font=("Segoe UI", 9, "bold"),
            width=10,
            relief="solid",
            bd=1,
        ).grid(row=linha_total, column=4, padx=4, pady=(6, 2))
        for col, chave in enumerate(("perimetro", "pingadeira", "area"), start=5):
            tk.Label(
                bloco_esq,
                textvariable=self.var_esquadrias_total[chave],
                bg=cores.fundo_cartao_off,
                fg=cores.titulo,
                font=("Segoe UI", 9, "bold"),
                width=12,
                relief="solid",
                bd=1,
            ).grid(row=linha_total, column=col, padx=4, pady=(6, 2))

        titulo_res = tk.Frame(faixa_esq, bg=fundo)
        tk.Label(
            titulo_res,
            text="Quantitativos de esquadrias e fachada",
            bg=fundo,
            fg=cores.texto,
        ).pack(side="left")
        bloco_res = tk.LabelFrame(
            faixa_esq,
            labelwidget=titulo_res,
            bg=fundo,
            fg=cores.texto,
            padx=10,
            pady=8,
        )
        bloco_res.pack(side="left", fill="both", expand=True, anchor="n", padx=(12, 0))
        self.after_idle(lambda: self._igualar_altura_titulos(titulo_esq, titulo_res))
        grade_res = tk.Frame(bloco_res, bg=fundo)
        grade_res.pack(fill="both", expand=True)
        self._grade_caixas(
            grade_res,
            [
                (self.var_resumo[chave], rotulo, unidade)
                for chave, rotulo, unidade in CAMPOS_RESUMO_FACHADA
            ],
            colunas=2,
            compacta=True,
            wraplength=180,
        )

        titulo_pct = tk.Frame(interior, bg=fundo)
        tk.Label(
            titulo_pct,
            text="Percentuais de quantitativos",
            bg=fundo,
            fg=cores.texto,
        ).pack(side="left")
        ttk.Checkbutton(
            titulo_pct,
            text="2 demãos de fundo selador",
            variable=self.var_duas_demaos_selador,
            command=self._ao_trocar_demaos_selador,
        ).pack(side="right", padx=(24, 0))
        bloco_pct = tk.LabelFrame(
            interior,
            labelwidget=titulo_pct,
            bg=fundo,
            fg=cores.texto,
            padx=10,
            pady=8,
        )
        bloco_pct.pack(fill="x", pady=(0, 8), padx=8)

        colunas_pct = 3
        colunas_frame = []
        for col_grupo in range(colunas_pct):
            if col_grupo:
                sep = tk.Frame(bloco_pct, bg=cores.borda_suave, width=1)
                sep.pack(side="left", fill="y", padx=10, pady=2)
            col_frame = tk.Frame(bloco_pct, bg=fundo)
            col_frame.pack(side="left", fill="both", expand=True, anchor="n")
            colunas_frame.append(col_frame)

        for indice, (chave, rotulo, _padrao, _qtd_chave, _unidade) in enumerate(
            PERCENTUAIS_MODELO
        ):
            col_grupo = indice % colunas_pct
            linha = indice // colunas_pct
            parent = colunas_frame[col_grupo]
            tk.Label(
                parent,
                text=rotulo + " (%):",
                bg=fundo,
                fg=cores.texto,
                anchor="w",
            ).grid(row=linha, column=0, sticky="w", pady=3, padx=(0, 6))
            entrada_pct = ttk.Entry(
                parent, textvariable=self.var_percentuais[chave], width=5
            )
            entrada_pct.grid(row=linha, column=1, sticky="w", pady=3, padx=(0, 4))
            self._vincular_campo_numerico(entrada_pct, percentual=True)
            entrada_pct.bind(
                "<FocusIn>",
                lambda _e, c=chave: self._ao_focar_percentual(c),
                add="+",
            )
            entrada_pct.bind(
                "<FocusOut>",
                lambda _e, c=chave, w=entrada_pct: self._ao_sair_percentual(c, w),
                add="+",
            )
            tk.Label(
                parent,
                textvariable=self.var_pct_qtd[chave],
                bg=cores.fundo_cartao_off,
                fg=cores.titulo,
                width=10,
                relief="solid",
                bd=1,
                anchor="e",
            ).grid(row=linha, column=2, sticky="w", pady=3)

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
        self.texto_obs.bind("<KeyRelease>", lambda _e: self._ao_alterar_campo())

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
            columns=("reparo", "percentual", "valor", "valor_atual"),
            show="tree headings",
            selectmode="browse",
            style="Anomalias.Treeview",
        )
        self.tree_anomalias.tag_configure("par", background=self._cor_linha_par)
        self.tree_anomalias.tag_configure("impar", background=self._cor_linha_impar)
        self.tree_anomalias.tag_configure("aviso", background=self._cor_linha_aviso)
        self.tree_anomalias.heading("#0", text="Anomalia")
        self.tree_anomalias.heading("reparo", text="Reparo", anchor="center")
        self.tree_anomalias.heading("percentual", text="% qtd.", anchor="center")
        self.tree_anomalias.heading("valor", text="Quantitativo considerado", anchor="e")
        self.tree_anomalias.heading("valor_atual", text="Valor atual", anchor="e")
        self.tree_anomalias.column("#0", width=260)
        self.tree_anomalias.column("reparo", width=200, anchor="center")
        self.tree_anomalias.column("percentual", width=58, anchor="center")
        self.tree_anomalias.column("valor", width=220, anchor="e")
        self.tree_anomalias.column("valor_atual", width=120, anchor="e")
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

        tk.Label(
            linha,
            textvariable=self.var_total,
            font=("Arial", 11, "bold"),
            fg=cores.titulo,
            bg=barra,
            anchor="e",
        ).pack(side="right", padx=10, pady=6)

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
            self.var_tipo_estrutura,
            self.var_tipo_cobertura,
            *self.var_medidas.values(),
            *self.var_percentuais.values(),
        ]
        for grupo in self.var_esquadrias.values():
            variaveis.extend(
                [grupo["dim_x"], grupo["dim_y"], grupo["h_peitoril"], grupo["qtd_por_pav"]]
            )
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
        from ui.orccad import JanelaORCCAD

        if self._janela_orccad is not None:
            try:
                if self._janela_orccad.janela.winfo_exists():
                    self._janela_orccad.trazer_frente()
                    return
            except tk.TclError:
                self._janela_orccad = None

        self._janela_orccad = JanelaORCCAD(
            self.winfo_toplevel(),
            on_salvar_principal=self._ao_salvar_desenho_principal,
            on_fechar=self._ao_fechar_orccad,
            desenho_inicial=self._desenho_principal,
        )

    def _ao_fechar_orccad(self):
        self._janela_orccad = None

    def _ao_salvar_desenho_principal(self, desenho, valores):
        self._desenho_principal = deepcopy(
            desenho
            or {
                "externa": {"pontos": [], "fechado": False},
                "hall": {"pontos": [], "fechado": False},
            }
        )
        for chave, texto in (valores or {}).items():
            if chave in self.var_medidas and texto:
                self.var_medidas[chave].set(texto)
        self._atualizar_previa_desenho()
        self._marcar_sujo()
        self._registrar_historico("Planta do condomínio")
        self._recalcular()
        n = len(valores or {})
        self._mostrar_feedback(
            f"Planta salva: {n} campo(s) de metragem preenchido(s).",
            "green",
        )

    def _atualizar_previa_desenho(self):
        if hasattr(self, "previa_desenho"):
            self.previa_desenho.definir(self._desenho_principal)
        from core.desenho_geometria import dict_para_camadas, resultado_desenho

        camadas = dict_para_camadas(self._desenho_principal)
        ext_pts, ext_fech = camadas["externa"]
        hall_pts, hall_fech = camadas["hall"]
        self._atualizar_vista_bloco(ext_pts, ext_fech)
        if len(ext_pts) < 2 and len(hall_pts) < 2:
            self.var_legenda_desenho.set("Ainda não há planta salva.")
            return
        partes = []
        if len(ext_pts) >= 2:
            res = resultado_desenho(ext_pts, fechado=ext_fech)
            if res.fechado:
                partes.append(
                    f"Externa — Área: {formatar_decimal_br(res.area_m2, 2)} m² · "
                    f"Perímetro: {formatar_decimal_br(res.perimetro_m, 2)} m"
                )
            else:
                partes.append(
                    f"Externa (aberta) — Perímetro: "
                    f"{formatar_decimal_br(res.perimetro_m, 2)} m"
                )
        if len(hall_pts) >= 2:
            res_h = resultado_desenho(hall_pts, fechado=hall_fech)
            if res_h.fechado:
                partes.append(
                    f"Hall — Área: {formatar_decimal_br(res_h.area_m2, 2)} m² · "
                    f"Perímetro: {formatar_decimal_br(res_h.perimetro_m, 2)} m"
                )
            else:
                partes.append(
                    f"Hall (aberto) — Perímetro: "
                    f"{formatar_decimal_br(res_h.perimetro_m, 2)} m"
                )
        self.var_legenda_desenho.set("\n".join(partes))

    def _atualizar_vista_bloco(self, pontos=None, fechado=None):
        if not hasattr(self, "vista_bloco"):
            return
        if pontos is None:
            from core.desenho_geometria import dict_para_camadas

            camadas = dict_para_camadas(self._desenho_principal)
            pontos, fechado = camadas["externa"]
        pe = numero(self.var_medidas["pe_direito_m"].get())
        pav = numero(self.var_medidas["qtd_pavimentos"].get())
        self.vista_bloco.definir(pontos, bool(fechado), pe, pav)

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
        self._carregar_etapas()
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
        self._job_calculo = None
        self._sincronizar_percentual_pintura_fachada()
        medidas = {chave: var.get() for chave, var in self.var_medidas.items()}
        esquadrias = []
        for modelo in ESQUADRIAS_MODELO:
            vars_e = self.var_esquadrias[modelo["id"]]
            esquadrias.append(
                {
                    "id": modelo["id"],
                    "sem_perimetro": bool(modelo.get("sem_perimetro")),
                    "cobogo": bool(modelo.get("cobogo")),
                    "dim_x": vars_e["dim_x"].get(),
                    "dim_y": vars_e["dim_y"].get(),
                    "h_peitoril": vars_e["h_peitoril"].get(),
                    "qtd_por_pav": vars_e["qtd_por_pav"].get(),
                }
            )
        percentuais = {chave: var.get() for chave, var in self.var_percentuais.items()}
        q = calcular_quantitativos(medidas, esquadrias, percentuais)
        self._quantitativos = q
        self._atualizar_vista_bloco()

        for chave, _rotulo, _unidade in CAMPOS_MEDIDA_AUTO:
            self.var_medidas_auto[chave].set(
                _fmt(q.get(chave, 0), inteiro=chave in CHAVES_INTEIRAS)
            )
        for chave, _rotulo, unidade in CAMPOS_RESUMO_FACHADA:
            self.var_resumo[chave].set(
                _fmt(q.get(chave, 0), inteiro=not unidade)
            )
        for chave, _rotulo, _padrao, qtd_chave, unidade in PERCENTUAIS_MODELO:
            texto = _fmt(q.get(qtd_chave, 0))
            if texto != "—":
                texto = f"{texto} {unidade}"
            self.var_pct_qtd[chave].set(texto)

        linhas_esq = q.get("esquadrias") or {}
        for modelo in ESQUADRIAS_MODELO:
            calc = linhas_esq.get(modelo["id"]) or {}
            vars_e = self.var_esquadrias[modelo["id"]]
            vars_e["perimetro"].set(_fmt_medida(calc.get("perimetro_pav_m", 0), "m"))
            vars_e["pingadeira"].set(_fmt_medida(calc.get("pingadeira_pav_m", 0), "m"))
            vars_e["area"].set(_fmt_medida(calc.get("area_pav_m2", 0), "m²"))
        qtd_pav = q.get("esquadria_qtd_pav", 0)
        self.var_esquadrias_total["qtd_por_pav"].set(
            _numero_br_fixo(qtd_pav) if qtd_pav else "—"
        )
        self.var_esquadrias_total["perimetro"].set(
            _fmt_medida(q.get("esquadria_perimetro_pav_m", 0), "m")
        )
        self.var_esquadrias_total["pingadeira"].set(
            _fmt_medida(q.get("esquadria_pingadeira_pav_m", 0), "m")
        )
        self.var_esquadrias_total["area"].set(
            _fmt_medida(q.get("esquadria_area_pav_m2", 0), "m²")
        )

        self._atualizar_preview_orcamento()
        self._atualizar_valores_anomalias_orcamento()

    def _coletar_rascunho(self) -> dict:
        dados = novo_rascunho()
        dados["condominio"]["nome"] = self.var_nome.get().strip()
        dados["condominio"]["municipio"] = self.var_municipio.get().strip()
        dados["condominio"]["uf"] = estado_do_combo(self.var_uf.get())
        dados["dados_iniciais"]["bdi_percent"] = self.var_bdi.get().strip() or BDI_PADRAO
        dados["dados_iniciais"]["tipo_estrutura"] = estado_do_combo(
            self.var_tipo_estrutura.get()
        )
        dados["dados_iniciais"]["tipo_cobertura"] = estado_do_combo(
            self.var_tipo_cobertura.get()
        )
        for chave, var in self.var_medidas.items():
            dados["dados_iniciais"]["medidas"][chave] = var.get().strip()
        dados["dados_iniciais"]["percentuais"] = {
            chave: var.get().strip() for chave, var in self.var_percentuais.items()
        }
        dados["dados_iniciais"]["desenho_principal"] = deepcopy(
            self._desenho_principal
            or {
                "externa": {"pontos": [], "fechado": False},
                "hall": {"pontos": [], "fechado": False},
            }
        )
        esquadrias = []
        for modelo in ESQUADRIAS_MODELO:
            vars_e = self.var_esquadrias[modelo["id"]]
            esquadrias.append(
                {
                    "id": modelo["id"],
                    "rotulo": modelo["rotulo"],
                    "sem_perimetro": bool(modelo.get("sem_perimetro")),
                    "cobogo": bool(modelo.get("cobogo")),
                    "dim_x": vars_e["dim_x"].get().strip(),
                    "dim_y": vars_e["dim_y"].get().strip(),
                    "h_peitoril": vars_e["h_peitoril"].get().strip(),
                    "qtd_por_pav": vars_e["qtd_por_pav"].get().strip(),
                }
            )
        dados["esquadrias"] = esquadrias
        dados["anomalias_orcamento"] = list(self._anomalias_orcamento)
        dados["considerar_servicos_preliminares"] = bool(self.var_considerar_sp.get())
        dados["considerar_pintura"] = bool(self.var_considerar_pintura.get())
        dados["pintura_fachada_manual"] = bool(self._pintura_fachada_manual)
        dados["duas_demaos_fundo_selador"] = bool(self.var_duas_demaos_selador.get())
        dados["considerar_destinacao_entulho"] = bool(self.var_considerar_entulho.get())
        dados["considerar_limpeza_geral"] = bool(self.var_considerar_limpeza.get())
        dados["extras_orcamento"] = []
        dados["orcamento"] = self._orcamento_para_rascunho()
        dados["observacoes"] = self.texto_obs.get("1.0", "end").strip()
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

    def _mostrar_painel_carregamento(self, texto):
        """Janela própria, desenhada antes do trabalho. Continua visível com a principal congelada."""
        if self._painel_carregamento is not None:
            return
        from ui.widgets import aplicar_icone_janela, centralizar_janela, preparar_toplevel

        topo = self.winfo_toplevel()
        painel = tk.Toplevel(topo)
        preparar_toplevel(painel)
        painel.title("Carregando")
        painel.transient(topo)
        painel.resizable(False, False)
        painel.configure(bg=self._cores.fundo, cursor="watch")
        aplicar_icone_janela(painel)
        painel.protocol("WM_DELETE_WINDOW", lambda: None)
        corpo = tk.Frame(painel, bg=self._cores.fundo, padx=28, pady=18)
        corpo.pack()
        tk.Label(
            corpo,
            text=texto,
            bg=self._cores.fundo,
            fg=self._cores.texto,
            font=("Arial", 12, "bold"),
        ).pack(anchor="w")
        # Etapa atual; largura fixa para a janela não mudar de tamanho a cada etapa.
        self._lbl_etapa_carregamento = tk.Label(
            corpo,
            text="",
            width=36,
            anchor="w",
            bg=self._cores.fundo,
            fg=self._cores.texto,
            font=("Arial", 10),
        )
        self._lbl_etapa_carregamento.pack(anchor="w", pady=(8, 0))
        tk.Label(
            corpo,
            text="Aguarde. A janela principal pode parar de responder.",
            bg=self._cores.fundo,
            fg=self._cores.texto_suave,
            font=("Arial", 9),
        ).pack(anchor="w", pady=(6, 0))
        self._painel_carregamento = painel
        self._carregando = True
        centralizar_janela(painel, topo)
        try:
            painel.attributes("-topmost", True)
        except tk.TclError:
            pass
        try:
            painel.grab_set()
        except tk.TclError:
            pass
        painel.lift()
        try:
            painel.update()
        except tk.TclError:
            pass

    def _ocultar_painel_carregamento(self, ao_terminar=None):
        self._carregando = True
        painel = self._painel_carregamento
        if painel is not None:
            try:
                painel.lift()
            except tk.TclError:
                pass
        try:
            self.update_idletasks()
        except tk.TclError:
            pass

        def fechar():
            painel = self._painel_carregamento
            self._painel_carregamento = None
            self._lbl_etapa_carregamento = None
            self._carregando = False
            if painel is not None:
                try:
                    painel.grab_release()
                except tk.TclError:
                    pass
                try:
                    painel.destroy()
                except tk.TclError:
                    pass
            if ao_terminar is not None:
                ao_terminar()

        try:
            self.after(1, fechar)
        except tk.TclError:
            fechar()

    def _etapa_carregamento(self, texto):
        """Mostra a etapa atual na janela "Carregando", se ela estiver aberta.

        Só update_idletasks (redesenho), sem processar eventos: a carga
        continua atômica e o usuário não consegue interagir no meio dela.
        """
        rotulo = self._lbl_etapa_carregamento
        if rotulo is None or self._painel_carregamento is None:
            return
        try:
            rotulo.configure(text=texto)
            self._painel_carregamento.update_idletasks()
        except tk.TclError:
            pass

    def _executar_com_carregamento(self, texto, acao, ao_terminar=None):
        self._mostrar_painel_carregamento(texto)
        try:
            acao()
        finally:
            self._ocultar_painel_carregamento(ao_terminar)

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
        # Recálculo agendado por edições anteriores ficaria redundante:
        # _recalcular() roda ao final da carga.
        if self._job_calculo is not None:
            try:
                self.after_cancel(self._job_calculo)
            except (tk.TclError, ValueError):
                pass
            self._job_calculo = None
        try:
            self._etapa_carregamento("Aplicando dados iniciais…")
            self.var_nome.set(dados["condominio"].get("nome", ""))
            self.var_municipio.set(dados["condominio"].get("municipio", ""))
            uf = dados["condominio"].get("uf", "")
            self.var_uf.set(uf if uf else PLACEHOLDER_ESTADO)
            iniciais = dados.get("dados_iniciais") or {}
            self.var_bdi.set(iniciais.get("bdi_percent") or BDI_PADRAO)
            estrutura = (iniciais.get("tipo_estrutura") or "").strip()
            self.var_tipo_estrutura.set(estrutura if estrutura else PLACEHOLDER_ESTADO)
            cobertura = (iniciais.get("tipo_cobertura") or "").strip()
            self.var_tipo_cobertura.set(cobertura if cobertura else PLACEHOLDER_ESTADO)
            medidas = iniciais.get("medidas") or {}
            for chave, var in self.var_medidas.items():
                var.set(medidas.get(chave, ""))
            percentuais = iniciais.get("percentuais") or {}
            for chave, var in self.var_percentuais.items():
                var.set(percentuais.get(chave, ""))
            from core.desenho_geometria import dict_para_camadas, desenho_camadas_para_dict

            brutos = iniciais.get("desenho_principal") or {}
            camadas = dict_para_camadas(brutos)
            self._desenho_principal = desenho_camadas_para_dict(
                externa_pontos=camadas["externa"][0],
                externa_fechado=camadas["externa"][1],
                hall_pontos=camadas["hall"][0],
                hall_fechado=camadas["hall"][1],
            )
            self._atualizar_previa_desenho()
            self._atualizar_rotulo_condominio()
            for item in dados.get("esquadrias") or []:
                ident = item.get("id")
                if ident not in self.var_esquadrias:
                    continue
                for chave_e in ("dim_x", "dim_y", "h_peitoril", "qtd_por_pav"):
                    self.var_esquadrias[ident][chave_e].set(
                        _texto_campo_numerico(item.get(chave_e), casas=2)
                    )
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
            self._etapa_carregamento("Montando orçamento…")
            self._carregar_orcamento_rascunho(dados)
            self._redesenhar_anomalias_orcamento(com_valores=False)
            self.texto_obs.delete("1.0", "end")
            obs = dados.get("observacoes") or ""
            if obs:
                self.texto_obs.insert("1.0", obs)
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
            self._etapa_carregamento("Calculando quantitativos e preços…")
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
            if self._painel_carregamento is None:
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

        self._executar_com_carregamento("Iniciando novo rascunho…", limpar, ao_terminar)

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
            # A leitura acontece com o painel já visível (arquivo grande ou em rede).
            self._etapa_carregamento(f"Lendo {nome_arquivo}…")
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
            # Só depois de fechar o painel: ele é topmost e esconderia a mensagem.
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

        self._executar_com_carregamento("Carregando rascunho…", carregar, ao_terminar)

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
        # O arquivo agora contém tudo; o autosave antigo só causaria uma oferta
        # de restauração desnecessária na próxima abertura.
        limpar_autosave()
        self._mostrar_feedback(f"Rascunho salvo: {Path(caminho).name}", "green")
        return True

    def _oferecer_autosave(self):
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

        self._executar_com_carregamento("Carregando rascunho…", restaurar, ao_terminar)

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
        reparo = reparos[0]
        if len(reparos) > 1:
            nomes = [r.get("nome") or f"Reparo {i+1}" for i, r in enumerate(reparos)]
            sugerido, dica = reparo_recomendado(
                anomalias[nome],
                tipo_estrutura=estado_do_combo(self.var_tipo_estrutura.get()),
                tipo_cobertura=estado_do_combo(self.var_tipo_cobertura.get()),
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
        percentuais_novos = self._coletar_percentuais_faltantes(reparo)
        if percentuais_novos is None:
            return
        percentual = "100"
        variaveis = self._coletar_variaveis_reparo(reparo)
        if variaveis is None:
            return
        self._gravar_percentuais_aba1(percentuais_novos)
        nova = nova_anomalia_orcamento(
            nome=nome,
            reparo_id=reparo.get("id"),
            reparo_nome=reparo.get("nome"),
            percentual=percentual,
            variaveis=variaveis,
        )
        self._aplicar_percentuais_aba1(
            list(reparo.get("percentuais_aba1") or []),
            percentual,
            origem_nome=nome,
            excluir_id=nova.get("id"),
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
                valores = (linha.get("reparo_nome") or "Reparo padrão", "", "", "")
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
        return limitar_revestimento_fachada(
            self._anomalias_orcamento,
            self._catalogo,
            self._quantitativos or {},
            getattr(self, "_etapa_por_id", None),
        )

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
            self._quantitativos or {},
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
        _limites, avisos = limitar_revestimento_fachada(
            self._anomalias_orcamento,
            self._catalogo,
            self._quantitativos or {},
            getattr(self, "_etapa_por_id", None),
        )
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

    def _anomalias_que_usam_percentual(self, chave, excluir_id=None) -> list[dict]:
        resultado = []
        excluir = str(excluir_id or "")
        for linha in self._anomalias_orcamento:
            if excluir and str(linha.get("id") or "") == excluir:
                continue
            if chave in self._chaves_percentuais_linha(linha):
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
    ) -> bool:
        chaves = [
            c
            for c in (chaves or [])
            if c in self.var_percentuais and c != "pintura_fachada"
        ]
        if not chaves:
            return False
        novo_fmt = formatar_decimal_br(numero(percentual_texto, percentual=True))
        conflitos = []
        for chave in chaves:
            atual = (self.var_percentuais[chave].get() or "").strip()
            if not atual:
                continue
            if self._percentuais_iguais(atual, novo_fmt):
                continue
            donos = self._anomalias_que_usam_percentual(chave, excluir_id=excluir_id)
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
                atual = (self.var_percentuais[chave].get() or "").strip()
                if atual and self._percentuais_iguais(atual, novo_fmt):
                    continue
                self.var_percentuais[chave].set(novo_fmt)
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
        try:
            coluna = self.tree_anomalias.identify_column(event.x)
            linha = self.tree_anomalias.identify_row(event.y)
        except tk.TclError:
            return ""
        if not linha:
            return ""
        return coluna

    def _dica_celula_anomalia(self, event) -> tuple[str, bool]:
        coluna = self._coluna_tree_anomalias(event)
        if coluna == "#1":
            return "Alterar reparo", True
        if coluna == "#2":
            return "Alterar percentual", True
        if coluna != "#3":
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

    def _foco_em_entrada_esquadria(self) -> bool:
        try:
            foco = self.focus_get()
        except tk.TclError:
            return False
        return isinstance(foco, (tk.Entry, ttk.Entry)) and self._widget_dentro(
            foco, getattr(self, "_bloco_esquadrias", None)
        )

    def _soltar_foco_esquadrias(self):
        try:
            self.winfo_toplevel().focus_set()
        except tk.TclError:
            return

    def _ao_esc_esquadrias(self, _event=None):
        try:
            if self.winfo_toplevel().grab_current():
                return
        except tk.TclError:
            return
        if not self._foco_em_entrada_esquadria():
            return
        self._soltar_foco_esquadrias()
        return "break"

    def _ao_clique_fora_esquadrias(self, event):
        try:
            if self.winfo_toplevel().grab_current():
                return
        except tk.TclError:
            return
        if not self._foco_em_entrada_esquadria():
            return
        widget = event.widget
        if isinstance(widget, (tk.Entry, ttk.Entry)) and self._widget_dentro(
            widget, self._bloco_esquadrias
        ):
            return
        self._soltar_foco_esquadrias()

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
        if coluna not in ("#1", "#2", "#3"):
            return
        if coluna == "#3" and not self._linha_tem_variavel(event):
            return
        self.tree_anomalias.selection_set(row)
        if coluna == "#1":
            self.after_idle(lambda: self._alterar_reparo_anomalia(row))
        elif coluna == "#2":
            self.after_idle(lambda: self._alterar_percentual_anomalia(row))
        else:
            self.after_idle(lambda: self._alterar_variaveis_anomalia(row))
        return "break"

    def _ao_duplo_clique_anomalia(self, event=None):
        if event is not None and self._coluna_tree_anomalias(event) != "#2":
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
        _sugerido, dica = reparo_recomendado(
            cadastro,
            tipo_estrutura=estado_do_combo(self.var_tipo_estrutura.get()),
            tipo_cobertura=estado_do_combo(self.var_tipo_cobertura.get()),
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
        percentuais_novos = self._coletar_percentuais_faltantes(reparo)
        if percentuais_novos is None:
            return
        variaveis = self._coletar_variaveis_reparo(
            reparo, atuais=linha.get("variaveis")
        )
        if variaveis is None:
            return
        self._gravar_percentuais_aba1(percentuais_novos)
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
        )
        self._marcar_sujo()
        self._registrar_historico("Alterar reparo da anomalia")
        self._recalcular()
        self._redesenhar_anomalias_orcamento()
        if hasattr(self, "tree_anomalias") and self.tree_anomalias.exists(item_id):
            self.tree_anomalias.selection_set(item_id)
            self.tree_anomalias.see(item_id)

    def _ao_focar_percentual(self, chave):
        self._pct_em_edicao[chave] = self.var_percentuais[chave].get()

    def _ao_sair_percentual(self, chave, widget):
        self._resolver_formula(widget, percentual=True)
        if (
            self._carregando
            or self._aplicando_historico
            or self._sincronizando_percentuais
        ):
            return
        atual = self.var_percentuais[chave].get()
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
        ligadas = self._anomalias_que_usam_percentual(chave)
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

    def _percentuais_pintura_das_anomalias(self) -> list[float]:
        valores = []
        for linha in self._anomalias_orcamento:
            if "pintura_fachada" not in self._chaves_percentuais_linha(linha):
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
        if self._pintura_fachada_manual:
            return
        valores = self._percentuais_pintura_das_anomalias()
        if not valores:
            return
        fmt = formatar_decimal_br(max(valores))
        var = self.var_percentuais["pintura_fachada"]
        atual = (var.get() or "").strip()
        if atual and self._percentuais_iguais(atual, fmt):
            return
        self._sincronizando_percentuais = True
        try:
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

    def _coletar_percentuais_faltantes(self, reparo) -> dict[str, str] | None:
        """Pergunta os percentuais da aba 1 que a fórmula usa e ainda estão vazios.

        None se o usuário cancelar. Os que a anomalia já declara são preenchidos
        depois com o percentual dela, então não entram nesta pergunta.
        """
        declarados = set(percentuais_aba1_validos((reparo or {}).get("percentuais_aba1")))
        declarados.discard("pintura_fachada")
        respostas: dict[str, str] = {}
        for chave in percentuais_dos_fatores(
            reparo, getattr(self, "_etapa_por_id", None)
        ):
            if chave in declarados or chave not in self.var_percentuais:
                continue
            if (self.var_percentuais[chave].get() or "").strip():
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

    def _gravar_percentuais_aba1(self, valores: dict[str, str]) -> None:
        if not valores:
            return
        self._sincronizando_percentuais = True
        try:
            for chave, valor in valores.items():
                var = self.var_percentuais.get(chave)
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

    def _preencher_grade(self):
        catalogo = self._composicoes_para_calculo()
        estado_atual = estado_do_combo(self.var_uf.get())
        bdi = self.orcamento.bdi_percent
        total = self._total_geral_calculado(bdi, catalogo, estado_atual)
        self._total_geral_ultimo = total
        self.var_total.set(
            f"Total geral (c/ BDI {_formatar_bdi(bdi)}%): {_formatar_moeda(total)}"
        )
        if not hasattr(self, "grade"):
            return

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
        self._mostrar_feedback("Orçamento atualizado na aba 3.", "green")

    def _salvar_em_customizados(self):
        messagebox.showinfo(
            "Área Comum",
            "Quando o orçamento estiver gerado, esta opção vai gravá-lo "
            "na lista de Orçamentos Customizados. Por enquanto o rascunho "
            "fica só no JSON local.",
            parent=self.winfo_toplevel(),
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
