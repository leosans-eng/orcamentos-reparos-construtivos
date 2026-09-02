import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import math
import os
import threading
import unicodedata
from copy import deepcopy
from datetime import datetime

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Border, Side, Font, PatternFill

from app_paths import asset_path
from core.app_state import ALTURA_TREE_MIN, NOMES_GRUPOS_REPARO
from core.idebras_client import (
    IdebrasClient,
    IdebrasError,
    formatar_decimal_br,
    localizar_conjunto_parecer,
    medidas_para_orcamento,
    normalizar_ambiente,
)
from core.municipios_br import resolver_uf_conjunto
from core.sinapi_busca import obter_item_sinapi
from core.ui_prefs import definir_pref, obter_pref
from core.vicios_storage import COMODOS_AREA_PRIVATIVA, comodos_permitidos_anomalia, nomes_anomalias
from ui.dialogo_admin_usuarios import usuario_atual_eh_admin
from ui.dialogo_ambientes_planta import DialogoAmbientesPlanta
from ui.dialogo_config_anomalias import DialogoConfigAnomalias
from ui.dialogo_importar_autor_idebras import DialogoImportarAutorIdebras
from ui.dialogo_previa_anomalia import DialogoPreviaAnomalia
from ui.icones import (
    IndicadorAmpulheta,
    criar_botao_ttk_com_icone,
    criar_botao_ttk_so_icone,
    criar_icone_svg,
    definir_estado_botao_icone,
)
from ui.widgets import (
    CampoListaPesquisavel,
    criar_barra_modulo,
    formatar_moeda_br,
    perguntar_escolha,
    vincular_tooltip,
)


def criar_area_privativa(parent, ctx, on_voltar):
    """Monta o modulo de orcamento para area privativa."""
    root = parent.winfo_toplevel()
    lista_anomalias = []
    _feedback_timer = None
    _refs_icones = []
    _job_recalculo = None
    _historico_undo = []
    _historico_redo = []
    _snapshot_base = None
    _aplicando_historico = False
    _binds_historico = []

    wrapper = tk.Frame(parent, bg="#ececec")
    wrapper._refs_icones = _refs_icones

    criar_barra_modulo(wrapper, "Área Privativa", on_voltar)

    corpo = tk.Frame(wrapper, bg="#ececec")
    corpo.pack(fill="both", expand=True, padx=12, pady=(0, 8))
    corpo.columnconfigure(0, weight=1)
    corpo.rowconfigure(1, weight=1)

    # ---------------------------- #
    # FRAME DADOS DO ORÇAMENTO     #
    # ---------------------------- #
    frame_dados = tk.LabelFrame(
        corpo, text="1. Dados do orçamento", bg="#ececec", padx=8, pady=6
    )
    frame_dados.grid(row=0, column=0, sticky="ew", pady=(0, 6))

    linha_topo = tk.Frame(frame_dados, bg="#ececec")
    linha_topo.pack(fill="x")

    bloco_autor = tk.Frame(linha_topo, bg="#ececec")
    bloco_autor.pack(side="left", fill="x", expand=True)
    bloco_valores = tk.Frame(linha_topo, bg="#ececec")
    bloco_valores.pack(side="left", fill="x", expand=True, padx=(12, 0))

    tk.Label(bloco_autor, text="Autor(a):", bg="#ececec").pack(side="left")

    var_proprietario = tk.StringVar()

    def forcar_maiusculo(*args):
        texto = var_proprietario.get()
        var_proprietario.set(texto.upper())

    var_proprietario.trace_add("write", forcar_maiusculo)

    entrada_proprietario = tk.Entry(bloco_autor, textvariable=var_proprietario)
    entrada_proprietario.pack(side="left", fill="x", expand=True, padx=(6, 6))

    ctrl_idebras = {
        "cliente": None,
        "obter_conjuntos": lambda: [],
        "selecionar_conjunto": lambda _nome: None,
    }

    def abrir_importar_autor():
        cliente = ctrl_idebras.get("cliente")
        conjuntos = list((ctrl_idebras.get("obter_conjuntos") or (lambda: []))())
        if cliente is None or not conjuntos:
            mostrar_feedback("Aguarde a conexão com o Idebras.", "orange")
            return

        def ao_importar(parecer):
            var_proprietario.set(parecer.nome)
            conjunto = localizar_conjunto_parecer(conjuntos, parecer)
            selecionar = ctrl_idebras.get("selecionar_conjunto")
            if conjunto is not None and selecionar:
                selecionar(conjunto.nome)
                mostrar_feedback(
                    f"Autor importado: {parecer.nome}.",
                    "green",
                )
            else:
                mostrar_feedback(
                    f"Autor importado: {parecer.nome}. "
                    "O conjunto não foi localizado automaticamente.",
                    "orange",
                    temporario=False,
                )

        DialogoImportarAutorIdebras(
            root,
            cliente=cliente,
            conjuntos=conjuntos,
            on_importar=ao_importar,
            refs_icones=_refs_icones,
        )

    btn_importar_autor = criar_botao_ttk_so_icone(
        bloco_autor,
        nome_icone="cloud-download-outline",
        command=abrir_importar_autor,
        refs=_refs_icones,
    )
    btn_importar_autor.pack(side="left")
    vincular_tooltip(btn_importar_autor, "Importar autor do Idebras")

    tk.Label(bloco_valores, text="Estado:", bg="#ececec").pack(side="left")

    estados = ctx.obter_estados()

    combo_estado = ttk.Combobox(bloco_valores, values=estados, width=8, state="readonly")
    combo_estado.pack(side="left", padx=(6, 16))

    def estado_alterado(event=None):
        atualizar_valores()
        registrar_historico("Alterar estado")

    combo_estado.bind("<<ComboboxSelected>>", estado_alterado)

    def obter_estado():

        estado = combo_estado.get()

        if estado == "":
            mostrar_feedback("Selecione um Estado.", "red")
            raise ValueError

        return estado

    def linha_sinapi_codigo(codigo, estado):
        return obter_item_sinapi(ctx.sinapi, str(codigo).strip(), estado)

    tk.Label(bloco_valores, text="Aluguel (R$):", bg="#ececec").pack(side="left")
    entrada_aluguel = tk.Entry(bloco_valores, width=10)
    entrada_aluguel.pack(side="left", padx=(6, 16))
    entrada_aluguel.insert(0, "1000")

    tk.Label(bloco_valores, text="BDI (%):", bg="#ececec").pack(side="left")
    entrada_bdi = ttk.Entry(bloco_valores, width=8)
    entrada_bdi.pack(side="left", padx=(6, 0))
    entrada_bdi.insert(0, "30,45")

    var_acompanhamento = tk.BooleanVar(value=True)
    var_eventuais = tk.BooleanVar(value=False)
    checks_opcoes = []

    def _montar_checks_orcamento(parent):
        bloco = tk.Frame(parent, bg="#ececec")
        chk_acompanhamento = tk.Checkbutton(
            bloco,
            text="Acompanhamento técnico",
            variable=var_acompanhamento,
            bg="#ececec",
            activebackground="#ececec",
        )
        chk_acompanhamento.pack(side="left")
        chk_eventuais = tk.Checkbutton(
            bloco,
            text="Eventuais (10%)",
            variable=var_eventuais,
            bg="#ececec",
            activebackground="#ececec",
        )
        chk_eventuais.pack(side="left", padx=(16, 0))
        checks_opcoes.extend([chk_acompanhamento, chk_eventuais])
        return bloco

    bloco_checks_topo = _montar_checks_orcamento(bloco_valores)
    bloco_checks_topo.pack(side="left", padx=(16, 0))

    linha_opcoes = tk.Frame(frame_dados, bg="#ececec")
    bloco_checks_baixo = _montar_checks_orcamento(linha_opcoes)
    bloco_checks_baixo.pack(side="left")
    _checks_na_segunda_linha = {"ativo": False}

    def _mostrar_checks_primeira_linha():
        if linha_opcoes.winfo_manager():
            linha_opcoes.pack_forget()
        if not bloco_checks_topo.winfo_manager():
            bloco_checks_topo.pack(side="left", padx=(16, 0))
        _checks_na_segunda_linha["ativo"] = False

    def _mostrar_checks_segunda_linha():
        if bloco_checks_topo.winfo_manager():
            bloco_checks_topo.pack_forget()
        if not linha_opcoes.winfo_manager():
            linha_opcoes.pack(fill="x", pady=(8, 0), after=linha_topo)
        _checks_na_segunda_linha["ativo"] = True

    def _reflow_linha_dados(event=None):
        if event is not None and event.widget is not frame_dados:
            return
        largura = frame_dados.winfo_width()
        if largura <= 1:
            return
        margem = 16
        histerese = 48
        if not _checks_na_segunda_linha["ativo"]:
            if linha_topo.winfo_reqwidth() > largura - margem:
                _mostrar_checks_segunda_linha()
            elif not bloco_checks_topo.winfo_manager():
                _mostrar_checks_primeira_linha()
            return
        extra = bloco_checks_baixo.winfo_reqwidth() + 16
        if linha_topo.winfo_reqwidth() + extra + histerese <= largura - margem:
            _mostrar_checks_primeira_linha()
            return
        if not linha_opcoes.winfo_manager():
            _mostrar_checks_segunda_linha()

    frame_dados.bind("<Configure>", _reflow_linha_dados)

    frame_idebras_host = tk.Frame(frame_dados, bg="#ececec")
    frame_idebras_host.pack(fill="x", pady=(8, 0))

    # ---------------------------- #
    # COLUNAS PRINCIPAIS           #
    # ---------------------------- #
    painel_colunas = tk.PanedWindow(
        corpo,
        orient=tk.HORIZONTAL,
        sashwidth=6,
        sashrelief="flat",
        showhandle=False,
        bd=0,
        bg="#ececec",
        opaqueresize=True,
    )
    painel_colunas.grid(row=1, column=0, sticky="nsew", pady=(0, 0))

    frame_metragem = tk.LabelFrame(
        painel_colunas, text="2. Metragem dos cômodos", bg="#ececec", padx=8, pady=6
    )

    frame_tabela = tk.Frame(frame_metragem, bg="#ececec")
    frame_tabela.pack(fill="both", expand=True)

    tk.Label(
        frame_tabela, text="Cômodo", font=("Arial", 9, "bold"), bg="#ececec", anchor="w"
    ).grid(row=0, column=0, sticky="ew", padx=2, pady=(0, 4))
    tk.Label(
        frame_tabela, text="Piso (m²)", font=("Arial", 9, "bold"), bg="#ececec"
    ).grid(row=0, column=1, padx=2, pady=(0, 4))
    tk.Label(
        frame_tabela,
        text="Rev. Arg.\n(m²)",
        font=("Arial", 9, "bold"),
        bg="#ececec",
        justify="center",
    ).grid(row=0, column=2, padx=2, pady=(0, 4))
    tk.Label(
        frame_tabela,
        text="Rev. Cer.\n(m²)",
        font=("Arial", 9, "bold"),
        bg="#ececec",
        justify="center",
    ).grid(row=0, column=3, padx=2, pady=(0, 4))
    frame_tabela.columnconfigure(0, weight=1)

    lista_comodos = list(COMODOS_AREA_PRIVATIVA)

    comodos_area_molhada = [
        "Banheiro",
        "Cozinha",
        "Área de Serviço",
    ]

    comodos_area_seca = [
        "Sala",
        "Dormitório 1",
        "Dormitório 2",
        "Circulação",
    ]

    comodos_com_rev_cer = set(comodos_area_molhada) | {
        "Área Externa",
        "Varanda",
    }

    comodos = {}

    for i, c in enumerate(lista_comodos, start=1):

        tk.Label(frame_tabela, text=c, bg="#ececec", anchor="w").grid(
            row=i, column=0, sticky="ew", padx=2, pady=2
        )

        entrada_piso = tk.Entry(frame_tabela, width=9, justify="right")
        entrada_piso.grid(row=i, column=1, padx=2, pady=2)

        entrada_rev_arg = tk.Entry(frame_tabela, width=9, justify="right")
        entrada_rev_arg.grid(row=i, column=2, padx=2, pady=2)

        if c in comodos_com_rev_cer:
            entrada_rev_cer = tk.Entry(frame_tabela, width=9, justify="right")
        else:
            entrada_rev_cer = tk.Entry(frame_tabela, width=9, justify="right", state="disabled")

        entrada_rev_cer.grid(row=i, column=3, padx=2, pady=2)

        comodos[c] = {
            "piso": entrada_piso,
            "rev_arg": entrada_rev_arg,
            "rev_cer": entrada_rev_cer
        }

    def limpar_campos_metragem():
        for campos in comodos.values():
            for entrada in campos.values():
                if str(entrada.cget("state")) == "disabled":
                    continue
                entrada.delete(0, "end")

    def limpar_metragens():
        limpar_campos_metragem()
        atualizar_valores()
        registrar_historico("Limpar metragens")
        mostrar_feedback("Metragens dos cômodos limpas.", "orange")

    def ao_trocar_conjunto_limpar_metragens():
        limpar_campos_metragem()
        atualizar_valores()
        registrar_historico("Limpar metragens ao trocar conjunto")

    botoes_metragem = tk.Frame(frame_metragem, bg="#ececec")
    botoes_metragem.pack(fill="x", pady=(6, 0))
    criar_botao_ttk_com_icone(
        botoes_metragem,
        texto="Limpar",
        nome_icone="sweeper-cleaning-icon",
        command=limpar_metragens,
        estilo="Compact.TButton",
        refs=_refs_icones,
    ).pack(side="left")

    def preencher_metragens(medidas):
        limpar_campos_metragem()
        preenchidos = []
        for comodo, valores in medidas.items():
            if comodo not in comodos:
                continue
            for chave in ("piso", "rev_arg", "rev_cer"):
                entrada = comodos[comodo][chave]
                if str(entrada.cget("state")) == "disabled":
                    continue
                entrada.delete(0, "end")
                entrada.insert(0, formatar_decimal_br(valores.get(chave, 0)))
            preenchidos.append(comodo)
        atualizar_valores()
        registrar_historico("Preencher metragens da planta")
        if preenchidos:
            mostrar_feedback(
                f"Metragens preenchidas: {', '.join(preenchidos)}.",
                "green",
            )
        else:
            mostrar_feedback("Nenhum cômodo da planta corresponde à tabela.", "orange")

    # ---------------------------- #
    # FRAME SELEÇÃO DE ANOMALIA    #
    # ---------------------------- #
    frame_anomalia = tk.LabelFrame(
        painel_colunas, text="3. Selecionar anomalia", bg="#ececec", padx=8, pady=6
    )

    def obter_vicios():
        nomes = nomes_anomalias(ctx.dados_json)
        return sorted(nomes, key=lambda nome: (normalizar_ambiente(nome), nome))

    frame_combo_anomalia = tk.Frame(frame_anomalia, bg="#ececec")
    frame_combo_anomalia.pack(fill="x", padx=6, pady=5)

    var_vicio = tk.StringVar()
    campo_vicio = CampoListaPesquisavel(
        frame_combo_anomalia,
        textvariable=var_vicio,
        normalizar=normalizar_ambiente,
        on_escolher=lambda _nome: atualizar_checkboxes_por_vicio(),
        altura_lista=16,
        largura_minima_lista=420,
        bg="#ececec",
    )
    campo_vicio.pack(side="left", fill="x", expand=True)
    campo_vicio.definir_opcoes(obter_vicios())
    campo_vicio.entrada.bind(
        "<KeyRelease>", lambda _e: atualizar_checkboxes_por_vicio(), add="+"
    )

    # ---------------------------- #
    # CHECKBOXES DE CÔMODOS        #
    # ---------------------------- #
    tk.Label(
        frame_anomalia, text="Cômodos afetados:", bg="#ececec", anchor="w"
    ).pack(fill="x", padx=6, pady=(4, 0))

    frame_check = tk.Frame(frame_anomalia, bg="#ececec")
    frame_check.pack(fill="x", padx=6, pady=4)

    linhas = [
        ["Sala", "Banheiro"],
        ["Circulação", "Cozinha"],
        ["Dormitório 1", "Área de Serviço"],
        ["Dormitório 2", "Área Externa"],
        ["Varanda", "Residência Inteira"],
    ]

    checkbox_comodos = {}

    for r, linha in enumerate(linhas):

        for c, comodo in enumerate(linha):

            var = tk.BooleanVar()

            chk = tk.Checkbutton(
                frame_check,
                text=comodo,
                variable=var,
                bg="#ececec",
                activebackground="#ececec",
                anchor="w",
            )
            chk.grid(row=r, column=c, sticky="w", padx=(0, 12), pady=1)

            checkbox_comodos[comodo] = {
                "var": var,
                "widget": chk
            }
    frame_check.columnconfigure(0, weight=1)
    frame_check.columnconfigure(1, weight=1)

    def anomalia_escolhida(*, completar=False):
        nome = var_vicio.get().strip()
        valores = obter_vicios()
        if nome in valores:
            return nome
        chave = normalizar_ambiente(nome)
        if not chave:
            return ""
        matches = [item for item in valores if chave in normalizar_ambiente(item)]
        if len(matches) == 1:
            if completar:
                var_vicio.set(matches[0])
            return matches[0]
        return ""

    def atualizar_checkboxes_por_vicio(event=None):

        vicio_selecionado = anomalia_escolhida()
        dados_vicio = ctx.dados_json.get("anomalias", {}).get(vicio_selecionado, {})
        permitidos = set(comodos_permitidos_anomalia(dados_vicio, lista_comodos))

        for comodo, dados in checkbox_comodos.items():

            var = dados["var"]
            chk = dados["widget"]

            if vicio_selecionado and comodo not in permitidos:
                var.set(False)
                chk.config(state="disabled")
            else:
                chk.config(state="normal")

    def atualizar_lista_vicios():
        atual = var_vicio.get()
        valores = obter_vicios()
        campo_vicio.definir_opcoes(valores)
        if atual in valores:
            var_vicio.set(atual)
        elif atual:
            var_vicio.set("")
        atualizar_checkboxes_por_vicio()

    def abrir_config_anomalias():
        DialogoConfigAnomalias(root, ctx, on_salvo=atualizar_lista_vicios)

    if usuario_atual_eh_admin():
        criar_botao_ttk_com_icone(
            frame_combo_anomalia,
            texto="Configurar",
            nome_icone="cog-outline",
            command=abrir_config_anomalias,
            refs=_refs_icones,
        ).pack(side="left", padx=(6, 0))

    frame_btn_adicionar = tk.Frame(frame_anomalia, bg="#ececec")
    frame_btn_adicionar.pack(fill="x", padx=6, pady=(8, 4))

    # ---------------------------- #
    # FEEDBACK VISUAL              #
    # ---------------------------- #

    def mostrar_feedback(mensagem, cor="red", temporario=True):

        nonlocal _feedback_timer

        feedback_label.config(text=mensagem, fg=cor)

        if _feedback_timer is not None:
            root.after_cancel(_feedback_timer)

        if temporario:
            _feedback_timer = root.after(
                3000,
                lambda: feedback_label.config(text="")
        )

    # ---------------------------- #
    # LISTA DE ANOMALIAS           #
    # ---------------------------- #
    frame_lista = tk.LabelFrame(
        painel_colunas, text="4. Anomalias adicionadas", bg="#ececec", padx=8, pady=6
    )
    frame_lista.rowconfigure(0, weight=1)
    frame_lista.columnconfigure(0, weight=1)

    min_metragem, min_anomalia, min_lista = 200, 200, 260
    painel_colunas.add(frame_metragem, minsize=min_metragem, stretch="never", width=240)
    painel_colunas.add(frame_anomalia, minsize=min_anomalia, stretch="never", width=240)
    painel_colunas.add(frame_lista, minsize=min_lista, stretch="always", width=720)

    _fracoes_colunas = {
        "vals": list(obter_pref("area_privativa_colunas", [0.20, 0.20, 0.60]))
    }
    _arrastando_colunas = {"ok": False}
    _job_aplicar_colunas = {"id": None}

    def _sashes_das_fracoes(largura, fracoes):
        sash0 = int(round(largura * fracoes[0]))
        sash1 = int(round(largura * (fracoes[0] + fracoes[1])))
        sash0 = max(min_metragem, sash0)
        sash1 = max(sash0 + min_anomalia, sash1)
        sash1 = min(sash1, largura - min_lista)
        sash0 = min(sash0, sash1 - min_anomalia)
        sash0 = max(min_metragem, sash0)
        return sash0, sash1

    def _fracoes_das_sashes(largura):
        c0 = painel_colunas.sash_coord(0)[0]
        c1 = painel_colunas.sash_coord(1)[0]
        f0 = max(c0, 1) / largura
        f1 = max(c1 - c0, 1) / largura
        f2 = max(1.0 - f0 - f1, 0.05)
        total = f0 + f1 + f2
        return [round(f0 / total, 4), round(f1 / total, 4), round(f2 / total, 4)]

    def _aplicar_colunas():
        if _arrastando_colunas["ok"]:
            return
        largura = painel_colunas.winfo_width()
        if largura < 500:
            return
        alvo0, alvo1 = _sashes_das_fracoes(largura, _fracoes_colunas["vals"])
        try:
            atual0 = painel_colunas.sash_coord(0)[0]
            atual1 = painel_colunas.sash_coord(1)[0]
            if abs(atual0 - alvo0) < 3 and abs(atual1 - alvo1) < 3:
                return
            painel_colunas.sash_place(0, alvo0, 1)
            painel_colunas.sash_place(1, alvo1, 1)
        except tk.TclError:
            return

    def _agendar_aplicar_colunas(_event=None):
        if _event is not None and _event.widget is not painel_colunas:
            return
        if _arrastando_colunas["ok"]:
            return
        if _job_aplicar_colunas["id"] is not None:
            return
        def _rodar():
            _job_aplicar_colunas["id"] = None
            _aplicar_colunas()
        _job_aplicar_colunas["id"] = painel_colunas.after_idle(_rodar)

    def _sash_foi_clicado(event) -> bool:
        try:
            ident = painel_colunas.identify(event.x, event.y)
        except tk.TclError:
            return False
        if not ident:
            return False
        tipo = ident[0] if isinstance(ident, (tuple, list)) else ident
        return str(tipo).lower() == "sash"

    def _ao_pressionar_colunas(event):
        if _sash_foi_clicado(event):
            _arrastando_colunas["ok"] = True

    def _ao_mover_colunas(_event=None):
        _arrastando_colunas["ok"] = True

    def _ao_soltar_colunas(_event=None):
        if not _arrastando_colunas["ok"]:
            return
        _arrastando_colunas["ok"] = False
        try:
            largura = painel_colunas.winfo_width()
            if largura >= 500:
                atuais = _fracoes_das_sashes(largura)
                alvo0, alvo1 = _sashes_das_fracoes(largura, _fracoes_colunas["vals"])
                atual0 = painel_colunas.sash_coord(0)[0]
                atual1 = painel_colunas.sash_coord(1)[0]
                if abs(atual0 - alvo0) >= 8 or abs(atual1 - alvo1) >= 8:
                    _fracoes_colunas["vals"] = atuais
                    definir_pref("area_privativa_colunas", _fracoes_colunas["vals"])
        except (tk.TclError, OSError):
            pass
        _agendar_aplicar_colunas()

    painel_colunas.bind("<ButtonPress-1>", _ao_pressionar_colunas)
    painel_colunas.bind("<B1-Motion>", _ao_mover_colunas)
    painel_colunas.bind("<ButtonRelease-1>", _ao_soltar_colunas)
    painel_colunas.bind("<Configure>", _agendar_aplicar_colunas)
    painel_colunas.after(50, _aplicar_colunas)

    lista_anomalias = []

    frame_listbox = tk.Frame(frame_lista)
    frame_listbox.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

    tree_anomalias = ttk.Treeview(
        frame_listbox,
        columns=("subtotal"),
        show="tree headings",
        height=ALTURA_TREE_MIN
    )

    tree_anomalias.heading("#0", text="Anomalia")
    tree_anomalias.heading("subtotal", text="Subtotal")

    tree_anomalias.column("#0", width=350, minwidth=200, stretch=True)
    tree_anomalias.column("subtotal", width=100, minwidth=90, stretch=False, anchor="e")

    icone_previa = criar_icone_svg(
        tree_anomalias, "search-outline", altura=14, cor="#006699"
    )
    _refs_icones.append(icone_previa)

    def ajustar_altura_treeview(event=None):
        frame_listbox.update_idletasks()
        altura = frame_listbox.winfo_height()
        if altura < 40:
            return
        linhas = max(ALTURA_TREE_MIN, (altura - 28) // 20)
        tree_anomalias.configure(height=linhas)

    frame_listbox.bind("<Configure>", ajustar_altura_treeview)

    tree_anomalias.pack(side="left", fill="both", expand=True)

    scroll_lista = ttk.Scrollbar(
        frame_listbox,
        orient="vertical",
        command=tree_anomalias.yview
    )

    tree_anomalias.configure(yscrollcommand=scroll_lista.set)

    scroll_lista.pack(side="right", fill="y")

    def ao_tecla_delete(_event=None):
        if tree_anomalias.selection():
            remover_anomalia()
        return "break"

    tree_anomalias.bind("<Delete>", ao_tecla_delete)

    # ---------------------------- #
    # FUNÇÃO ADICIONAR ANOMALIA    #
    # ---------------------------- #
    def adicionar_anomalia():

        vicio = anomalia_escolhida(completar=True)

        if not vicio:
            mostrar_feedback("Selecione uma anomalia.", "red")
            return

        if vicio not in ctx.dados_json.get("anomalias", {}):
            mostrar_feedback(
                "Anomalia não encontrada no cadastro.",
                "red",
            )
            return

        comodos_afetados = [
            c for c in lista_comodos if checkbox_comodos[c]["var"].get()
        ]

        if not comodos_afetados:
            mostrar_feedback("Selecione ao menos um cômodo.", "red")
            return

        zerados = []
        for comodo in comodos_afetados:
            campos = comodos[comodo]
            tem_medida = False
            for chave in ("piso", "rev_arg", "rev_cer"):
                entrada = campos[chave]
                if str(entrada.cget("state")) == "disabled":
                    continue
                bruto = entrada.get().strip().replace(",", ".")
                try:
                    if bruto and float(bruto) > 0:
                        tem_medida = True
                        break
                except ValueError:
                    if entrada.get().strip():
                        tem_medida = True
                        break
            if not tem_medida:
                zerados.append(comodo)
        if zerados:
            lista_zerados = ", ".join(zerados)
            if not messagebox.askyesno(
                "Metragem zerada",
                "O(s) cômodo(s) a seguir estão com metragem zerada:\n\n"
                f"{lista_zerados}\n\n"
                "Deseja adicionar a anomalia mesmo assim?",
                parent=root,
            ):
                return

        # procurar se a anomalia já foi adicionada
        for item in lista_anomalias:

            if item["vicio"] == vicio:

                novos = []

                for c in comodos_afetados:

                    if c not in item["comodos"]:
                        item["comodos"].append(c)
                        novos.append(c)

                if novos:

                    atualizar_tree()
                    registrar_historico("Adicionar cômodo à anomalia")

                    mostrar_feedback(
                        f"Cômodo(s) adicionado(s): {', '.join(novos)}",
                        "orange"
                    )

                else:

                    mostrar_feedback(
                        "Esta anomalia já está cadastrada nesse(s) cômodo(s).",
                        "orange red"
                    )

                for dados in checkbox_comodos.values():
                    dados["var"].set(False)

                return

        # criar nova anomalia
        item = {
            "vicio": vicio,
            "comodos": comodos_afetados
        }

        lista_anomalias.append(item)

        atualizar_tree()

        for dados in checkbox_comodos.values():
            dados["var"].set(False)

        mostrar_feedback("Anomalia adicionada com sucesso.", "green")
        registrar_historico("Adicionar anomalia")

    def atualizar_tree():

        tree_anomalias.delete(*tree_anomalias.get_children())

        for item in lista_anomalias:

            subtotal = calcular_subtotal_anomalia(item)

            subtotal_str = f"R$ {subtotal:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

            pai = tree_anomalias.insert(
                "",
                "end",
                text=item["vicio"],
                image=icone_previa,
                values=(subtotal_str,),
                open=True
            )

            for comodo in item["comodos"]:

                tree_anomalias.insert(
                    pai,
                    "end",
                    text=comodo,
                    values=("",)
                )

        atualizar_total_rodape()


    def aplicar_sinapi_na_interface():

        estados_disponiveis = ctx.obter_estados()

        combo_estado["values"] = estados_disponiveis

        if estados_disponiveis:
            estado_atual = combo_estado.get().strip()

        else:
            combo_estado.set("")

        ctx.atualizar_label_csv_rodape()
        ctx.atualizar_rodape()

        if lista_anomalias:
            atualizar_valores()
        else:
            atualizar_total_rodape()


    # FUNÇÃO REMOVER ANOMALIA      #
    # ---------------------------- #
    def remover_anomalia():

        selecionado = tree_anomalias.selection()

        if not selecionado:
            mostrar_feedback("Selecione uma anomalia para remover.", "red")
            return

        item_id = selecionado[0]

        pai = tree_anomalias.parent(item_id)

        # SE SELECIONAR APENAS A ANOMALIA
        if pai == "":

            indice = tree_anomalias.index(item_id)
            del lista_anomalias[indice]
            atualizar_tree()
            registrar_historico("Remover anomalia")
            mostrar_feedback("Anomalia removida.", "orange red")

        # SE SELECIONAR UM CÔMODO
        else:

            indice_anomalia = tree_anomalias.index(pai)
            comodo = tree_anomalias.item(item_id)["text"]
            lista_anomalias[indice_anomalia]["comodos"].remove(comodo)

            # PARA TIRAR A ANOMALIA CASO NÃO SOBRE NENHUM CÔMODO
            if not lista_anomalias[indice_anomalia]["comodos"]:
                del lista_anomalias[indice_anomalia]

            atualizar_tree()
            registrar_historico("Remover cômodo")
            mostrar_feedback(f"Cômodo removido: {comodo}", "orange")

    def remover_todas_anomalias():

        if not lista_anomalias:
            mostrar_feedback("Não há anomalias para remover.", "orange")
            return

        lista_anomalias.clear()
        atualizar_tree()
        registrar_historico("Remover todas as anomalias")
        mostrar_feedback("Todas as anomalias foram removidas.", "orange red")

    # ---------------------------- #
    # BOTÕES                       #
    # ---------------------------- #
    criar_botao_ttk_com_icone(
        frame_btn_adicionar,
        texto="Adicionar anomalia",
        nome_icone="add-circle-outline",
        command=adicionar_anomalia,
        estilo="Add.TButton",
        refs=_refs_icones,
    ).pack(fill="x")

    botoes_lista = tk.Frame(frame_lista, bg="#ececec")
    botoes_lista.grid(row=1, column=0, sticky="ew", pady=(8, 0))
    criar_botao_ttk_com_icone(
        botoes_lista,
        texto="Remover selecionada",
        nome_icone="remove-circle-outline",
        command=remover_anomalia,
        estilo="Delete.Compact.TButton",
        refs=_refs_icones,
    ).pack(side="left")
    criar_botao_ttk_com_icone(
        botoes_lista,
        texto="Remover todas",
        nome_icone="trash-outline",
        command=remover_todas_anomalias,
        estilo="Delete.Compact.TButton",
        refs=_refs_icones,
    ).pack(side="left", padx=(6, 0))

    # ---------------------------- #
    # RODAPÉ: FEEDBACK + GERAR     #
    # ---------------------------- #
    frame_rodape_modulo = tk.Frame(
        corpo, bg="#f5fafc", highlightbackground="#cccccc", highlightthickness=1
    )
    frame_rodape_modulo.grid(row=2, column=0, sticky="ew", pady=(8, 0))

    linha_rodape = tk.Frame(frame_rodape_modulo, bg="#f5fafc")
    linha_rodape.pack(fill="x")

    container_historico = tk.Frame(linha_rodape, bg="#f5fafc")
    container_historico.pack(side="left", padx=10, pady=6)

    btn_desfazer = criar_botao_ttk_so_icone(
        container_historico,
        nome_icone="caret-back-outline",
        command=lambda: desfazer(),
        refs=_refs_icones,
    )
    btn_desfazer.pack(side="left", padx=(0, 4))
    vincular_tooltip(btn_desfazer, "Desfazer (Ctrl+Z)")
    definir_estado_botao_icone(btn_desfazer, "disabled")

    btn_refazer = criar_botao_ttk_so_icone(
        container_historico,
        nome_icone="caret-forward-outline",
        command=lambda: refazer(),
        refs=_refs_icones,
    )
    btn_refazer.pack(side="left", padx=(0, 10))
    vincular_tooltip(btn_refazer, "Refazer (Ctrl+Y)")
    definir_estado_botao_icone(btn_refazer, "disabled")

    feedback_label = tk.Label(
        linha_rodape,
        text="",
        font=("Arial", 10, "bold"),
        fg="#a67c00",
        bg="#f5fafc",
        anchor="w",
    )
    feedback_label.pack(side="left", fill="x", expand=True, padx=(0, 12))

    container_total = tk.Frame(linha_rodape, bg="#f5fafc")
    container_total.pack(side="right", padx=10, pady=6)

    var_total = tk.StringVar(value="Total geral: R$ 0,00")
    label_total = tk.Label(
        container_total,
        textvariable=var_total,
        font=("Arial", 11, "bold"),
        fg="#006699",
        bg="#f5fafc",
        anchor="e",
    )

    # ---------------------------- #
    # FUNÇÃO CALCULAR QUANTIDADE   #
    # ---------------------------- #
    def ler_float(entry):

        valor = entry.get().strip()

        if valor == "":
            return 0

        valor = valor.replace(",", ".")

        try:
            return float(valor)
        except ValueError as exc:
            raise ValueError from exc

    def ler_float_seguro(entry):
        try:
            return ler_float(entry)
        except ValueError:
            return 0

    def calcular_quantidade(etapa, medidas):

        tipo = etapa["tipo_calculo"]

        if tipo == "area_piso":
            return medidas["piso"] * etapa.get("coeficiente", 1)

        if tipo == "area_rev_arg":
            return medidas["rev_arg"] * etapa.get("coeficiente", 1)

        if tipo == "area_rev_cer":
            return medidas["rev_cer"] * etapa.get("coeficiente", 1)

        if tipo == "perimetro":
            return math.sqrt(medidas["piso"]) * 4 * etapa.get("coeficiente", 1)

        if tipo == "por_comodo":
            return etapa["coeficiente"]

        if tipo == "fixo":
            return etapa["coeficiente"]

        return 0

    def calcular_subtotal_anomalia(item):

        total = 0

        nome_anomalia = item["vicio"]
        dados_anomalia = ctx.dados_json.get("anomalias", {}).get(nome_anomalia)
        if not dados_anomalia:
            return 0
        etapas = dados_anomalia.get("etapas", [])

        for comodo in item["comodos"]:

            piso = ler_float_seguro(comodos[comodo]["piso"])
            arg = ler_float_seguro(comodos[comodo]["rev_arg"])

            if comodos[comodo]["rev_cer"].cget("state") != "disabled":
                cer = ler_float_seguro(comodos[comodo]["rev_cer"])
            else:
                cer = 0

            medidas = {
                "piso": piso,
                "rev_arg": arg,
                "rev_cer": cer
            }

            for etapa in etapas:

                quantidade = calcular_quantidade(etapa, medidas)

                codigo = str(etapa["codigo_sinapi"])

                estado = combo_estado.get()

                linha_sinapi = linha_sinapi_codigo(codigo, estado)
                if linha_sinapi is not None:
                    valor = linha_sinapi.get("custo", 0)
                else:
                    valor = 0

                total += quantidade * valor

        return total

    def medidas_do_comodo(comodo):
        piso = ler_float_seguro(comodos[comodo]["piso"])
        arg = ler_float_seguro(comodos[comodo]["rev_arg"])
        if comodos[comodo]["rev_cer"].cget("state") != "disabled":
            cer = ler_float_seguro(comodos[comodo]["rev_cer"])
        else:
            cer = 0
        return {"piso": piso, "rev_arg": arg, "rev_cer": cer}

    def montar_linhas_previa(item):
        linhas = []
        nome_anomalia = item["vicio"]
        dados_anomalia = ctx.dados_json.get("anomalias", {}).get(nome_anomalia) or {}
        etapas = dados_anomalia.get("etapas") or []
        estado = combo_estado.get().strip()
        repintura_executada = set()
        for comodo in item["comodos"]:
            medidas = medidas_do_comodo(comodo)
            for etapa in etapas:
                quantidade = calcular_quantidade(etapa, medidas)
                codigo = str(etapa.get("codigo_sinapi", "")).strip()
                grupo_planilha = etapa.get("grupo_planilha", "")
                if grupo_planilha == "repintura":
                    chave = (comodo, codigo)
                    if chave in repintura_executada:
                        continue
                    repintura_executada.add(chave)
                linha_sinapi = linha_sinapi_codigo(codigo, estado) if estado else None
                if linha_sinapi is not None:
                    descricao = linha_sinapi.get("descricao", "")
                    valor = linha_sinapi.get("custo", 0)
                else:
                    descricao = (
                        "Selecione um Estado"
                        if not estado
                        else "Código não encontrado"
                    )
                    valor = 0
                linhas.append({
                    "comodo": comodo,
                    "codigo": codigo,
                    "descricao": descricao,
                    "unidade": etapa.get("unidade", ""),
                    "quantidade": quantidade,
                    "valor_unit": valor,
                    "total": quantidade * valor,
                    "grupo": grupo_planilha,
                })
        return linhas

    def abrir_previa_anomalia(item):
        if not item:
            return
        DialogoPreviaAnomalia(
            root,
            nome_anomalia=item["vicio"],
            comodos=list(item.get("comodos") or []),
            estado=combo_estado.get().strip(),
            linhas=montar_linhas_previa(item),
            subtotal=calcular_subtotal_anomalia(item),
        )

    def ao_clicar_previa(event):
        row = tree_anomalias.identify_row(event.y)
        if not row or tree_anomalias.parent(row):
            return
        elemento = str(tree_anomalias.identify_element(event.x, event.y) or "")
        if "image" not in elemento.lower():
            return
        indice = tree_anomalias.index(row)
        if 0 <= indice < len(lista_anomalias):
            abrir_previa_anomalia(lista_anomalias[indice])

    def ao_mover_lista(event):
        row = tree_anomalias.identify_row(event.y)
        elemento = str(tree_anomalias.identify_element(event.x, event.y) or "")
        if row and not tree_anomalias.parent(row) and "image" in elemento.lower():
            tree_anomalias.configure(cursor="hand2")
        else:
            tree_anomalias.configure(cursor="")

    tree_anomalias.bind("<ButtonRelease-1>", ao_clicar_previa)
    tree_anomalias.bind("<Motion>", ao_mover_lista)

    def calcular_total_geral():
        total_itens = 0.0
        for item in lista_anomalias:
            total_itens += calcular_subtotal_anomalia(item)

        itens_gerais = ctx.dados_json.get("itens_gerais", {})
        estado = combo_estado.get().strip()
        for chave, item in itens_gerais.items():
            incluir = False
            if item.get("tipo") == "automatico":
                incluir = True
            elif item.get("tipo") == "checkbox":
                if chave == "acompanhamento_tecnico" and var_acompanhamento.get():
                    incluir = True
            if not incluir:
                continue
            for etapa in item.get("etapas", []):
                quantidade = calcular_quantidade(etapa, {})
                linha_sinapi = linha_sinapi_codigo(str(etapa["codigo_sinapi"]), estado)
                valor = linha_sinapi.get("custo", 0) if linha_sinapi is not None else 0
                total_itens += quantidade * valor

        try:
            bdi = ler_float_seguro(entrada_bdi) / 100
        except Exception:
            bdi = 0
        valor_bdi = total_itens * bdi
        valor_eventuais = (total_itens + valor_bdi) * 0.10 if var_eventuais.get() else 0
        aluguel = ler_float_seguro(entrada_aluguel)
        return total_itens + valor_bdi + valor_eventuais + aluguel

    def atualizar_total_rodape():
        var_total.set(f"Total geral: {formatar_moeda_br(calcular_total_geral())}")

    def atualizar_valores(_event=None):
        atualizar_tree()

    def agendar_recalculo(_event=None):
        nonlocal _job_recalculo
        if _job_recalculo is not None:
            try:
                root.after_cancel(_job_recalculo)
            except tk.TclError:
                pass

        def _tick():
            atualizar_valores()
            registrar_historico("Editar metragem, BDI ou aluguel", coalescer=True)

        _job_recalculo = root.after(180, _tick)

    # ---------------- #
    # NOME DE ARQUIVOS #
    # ---------------- #
    def nome_arquivo(texto):

        texto = texto.strip()

        if not texto:
            return "sem_proprietario"

        caracteres_invalidos = '<>:"/\\|?*'

        for caractere in caracteres_invalidos:
            texto = texto.replace(caractere, "_")

        texto = "_".join(texto.split())

        return texto[:80]

    def normalizar_texto(texto):
        if texto is None:
            return ""
        texto = str(texto).strip()
        texto = unicodedata.normalize("NFKD", texto)
        texto = "".join(c for c in texto if not unicodedata.combining(c))
        return texto.upper()

    # ------------------- #
    # ORDEM DO ORÇAMENTO  #
    # ------------------- #
    def definir_ordem(anomalia):
        nome = normalizar_texto(anomalia)

        if "ACOMPANHAMENTO" in nome:
            return 1

        if "PISOS" in nome or "AZULEJOS" in nome:
            return 2

        if "ENTULHO" in nome or "LIMPEZA" in nome:
            return 4

        return 3

    # ---------------------------- #
    # GERAR ORÇAMENTO              #
    # ---------------------------- #
    def gerar_orcamento():

        # para diagnosticar bugs
        print("LISTA_ANOMALIAS:", lista_anomalias)

        if not lista_anomalias:
            mostrar_feedback(
                "Adicione ao menos uma anomalia para gerar o orçamento.",
                "red"
            )
            return

        linhas = []

        # controle para evitar duplicação de repintura por cômodo/código
        repintura_executada = set() # (comodo, codigo_sinapi)

        # Para ANOMALIAS selecionadas

        for item in lista_anomalias:
            if not isinstance(item, dict):
                print("Item inválido na lista:", item)
                continue

            nome_anomalia = item["vicio"]
            comodos_afetados = item["comodos"]
            dados_anomalia = ctx.dados_json.get("anomalias", {}).get(nome_anomalia)
            if not dados_anomalia:
                mostrar_feedback(
                    f"Anomalia não encontrada no cadastro: {nome_anomalia}",
                    "red",
                )
                return
            grupo_reparo = dados_anomalia.get("grupo_reparo", nome_anomalia)
            etapas = dados_anomalia["etapas"]

            for comodo in comodos_afetados:
                try:
                    piso = ler_float(comodos[comodo]["piso"])
                    arg = ler_float(comodos[comodo]["rev_arg"])

                    if comodos[comodo]["rev_cer"].cget("state") != "disabled":
                        cer = ler_float(comodos[comodo]["rev_cer"])
                    else:
                        cer = 0

                except Exception as e:
                    print("ERRO:", e)
                    mostrar_feedback(
                        f"Erro ao ler medidas do cômodo {comodo}",
                        "red"
                    )

                    return

                medidas = {
                    "piso": piso,
                    "rev_arg": arg,
                    "rev_cer": cer
                }

                for ordem, etapa in enumerate(etapas):

                    quantidade = calcular_quantidade(etapa, medidas)

                    codigo = str(etapa["codigo_sinapi"])
                    grupo_planilha = etapa.get("grupo_planilha", "")
                    # Se for repintura, só adiciona se não foi feita para este cômodo/código
                    if grupo_planilha == "repintura":
                        chave_repintura = (comodo, codigo)
                        if chave_repintura in repintura_executada:
                            continue
                        repintura_executada.add(chave_repintura)

                    estado = obter_estado()

                    linha_sinapi = linha_sinapi_codigo(codigo, estado)
                    if linha_sinapi is not None:
                        descricao = linha_sinapi.get("descricao", "")
                        valor = linha_sinapi.get("custo", 0)
                    else:
                        descricao = "Código não encontrado"
                        valor = 0

                    total = quantidade * valor

                    linhas.append({
                        "Anomalia": grupo_reparo,
                        "Grupo Planilha": grupo_planilha,
                        "Ordem": ordem,
                        "Código SINAPI": codigo,
                        "Descrição do item": descricao,
                        "Unid.": etapa["unidade"],
                        "Qtd.": round(quantidade, 2),
                        "Valor Unit.": valor,
                        "Total s/ BDI": round(total, 2)
                    })

        # Para ITENS GERAIS que irão em todos os orçamentos

        itens_gerais = ctx.dados_json.get("itens_gerais", {})

        for chave, item in itens_gerais.items():

            incluir = False

            if item.get("tipo") == "automatico":
                incluir = True

            elif item.get("tipo") == "checkbox":
                if chave == "acompanhamento_tecnico" and var_acompanhamento.get():
                    incluir = True

            if not incluir:
                continue

            for ordem, etapa in enumerate(item["etapas"]):

                quantidade = calcular_quantidade(etapa, {})

                codigo = str(etapa["codigo_sinapi"])
                estado = obter_estado()

                linha_sinapi = linha_sinapi_codigo(codigo, estado)
                if linha_sinapi is not None:
                    descricao = linha_sinapi.get("descricao", "")
                    valor = linha_sinapi.get("custo", 0)
                else:
                    descricao = "Código não encontrado"
                    valor = 0

                total = quantidade * valor

                linhas.append({
                    "Anomalia": item["descricao"],
                    "Grupo Planilha": "",
                    "Ordem": ordem,
                    "Código SINAPI": codigo,
                    "Descrição do item": descricao,
                    "Unid.": etapa["unidade"],
                    "Qtd.": round(quantidade, 2),
                    "Valor Unit.": valor,
                    "Total s/ BDI": round(total, 2)
                })

        # Criação do DataFrame 
        df = pd.DataFrame(linhas)

        df = df.groupby(
            ["Anomalia", "Grupo Planilha","Código SINAPI", "Descrição do item", "Unid.", "Valor Unit."],
            as_index=False,
            sort=False
        ).agg({
            "Qtd.": "sum",
            "Total s/ BDI": "sum"
        })

        def ordem_grupo_planilha(grupo):
            if grupo == "repintura":
                return 2
            return 0

        df["Ordem_Execucao"] = df["Anomalia"].apply(definir_ordem)
        df["Ordem_Grupo"]    = df["Grupo Planilha"].apply(ordem_grupo_planilha)

        total_sem_repintura = df[df["Grupo Planilha"] != "repintura"]["Total s/ BDI"].sum()
        total_repintura     = df[df["Grupo Planilha"] == "repintura"]["Total s/ BDI"].sum()

        total_geral = total_sem_repintura + total_repintura

        df = df.sort_values(["Ordem_Execucao", "Ordem_Grupo"])

        linhas_final = []

        # itera na ordem já definida pelo sort_values
        for _, linha_df in df.iterrows():

            anomalia     = linha_df["Anomalia"]
            grupo        = linha_df["Grupo Planilha"]

            # cabeçalho da seção — só insere quando encontra a primeira linha dela
            secao_atual = ("repintura" if grupo == "repintura" else anomalia)

            if not linhas_final or linhas_final[-1].get("_secao") != secao_atual:

                if grupo == "repintura":
                    titulo_secao   = "REPINTURA APÓS INTERVENÇÕES"
                    subtotal_secao = df[df["Grupo Planilha"] == "repintura"]["Total s/ BDI"].sum()
                else:
                    titulo_secao   = NOMES_GRUPOS_REPARO.get(anomalia, anomalia).upper()
                    subtotal_secao = df[
                        (df["Anomalia"] == anomalia) &
                        (df["Grupo Planilha"] != "repintura")
                    ]["Total s/ BDI"].sum()

                linhas_final.append({
                    "_secao":            secao_atual,
                    "Código SINAPI":     "",
                    "Descrição do item": titulo_secao,
                    "Unid.": "", "Qtd.": "", "Valor Unit.": "",
                    "Total s/ BDI":      subtotal_secao
                })

            linhas_final.append({
                "_secao":            secao_atual,
                "Código SINAPI":     linha_df["Código SINAPI"],
                "Descrição do item": linha_df["Descrição do item"],
                "Unid.":             linha_df["Unid."],
                "Qtd.":              linha_df["Qtd."],
                "Valor Unit.":       linha_df["Valor Unit."],
                "Total s/ BDI":      linha_df["Total s/ BDI"]
            })

        df = pd.DataFrame(linhas_final).drop(columns=["_secao"])

        df["Total s/ BDI"] = pd.to_numeric(df["Total s/ BDI"], errors="coerce").fillna(0)

        linha_total = pd.DataFrame([{
            "Código SINAPI": "",
            "Descrição do item": "Total sem BDI",
            "Unid.": "",
            "Qtd.": "",
            "Valor Unit.": "",
            "Total s/ BDI": round(total_geral, 2)
        }])

        df = pd.concat([df, linha_total], ignore_index=True)

        # ------------ #
        # CALCULAR BDI #
        # ------------ #
        bdi_str = entrada_bdi.get().replace(",", ".")

        try:
            bdi = float(bdi_str) / 100
        except:
            mostrar_feedback("BDI inválido.", "red")
            return

        valor_bdi = total_geral * bdi

        linha_bdi = pd.DataFrame([{
            "Código SINAPI": "",
            "Descrição do item": f"Total do BDI ({entrada_bdi.get()}%)",
            "Unid.": "",
            "Qtd.": "",
            "Valor Unit.": "",
            "Total s/ BDI": round(valor_bdi, 2)
        }])

        df = pd.concat([df, linha_bdi], ignore_index=True)

        # --------- #
        # EVENTUAIS #
        # --------- #
        base_eventuais = total_geral + valor_bdi
        valor_eventuais = base_eventuais * 0.10 if var_eventuais.get() else 0

        if var_eventuais.get():
            linha_eventuais = pd.DataFrame([{
                "Código SINAPI": "",
                "Descrição do item": "Eventuais (10%)",
                "Unid.": "",
                "Qtd.": "",
                "Valor Unit.": "",
                "Total s/ BDI": round(valor_eventuais, 2)
            }])

            df = pd.concat([df, linha_eventuais], ignore_index=True)

        # ------- #
        # ALUGUEL #
        # ------- #
        aluguel_str = entrada_aluguel.get().replace(",", ".")

        try:
            aluguel = float(aluguel_str)
        except:
            mostrar_feedback("Valor de aluguel inválido.", "red")
            return

        linha_aluguel = pd.DataFrame([{
            "Código SINAPI": "",
            "Descrição do item": "Aluguel (1 mês)",
            "Unid.": "",
            "Qtd.": "",
            "Valor Unit.": "",
            "Total s/ BDI": round(aluguel, 2)
        }])

        df = pd.concat([df, linha_aluguel], ignore_index=True)

        # ----------- #
        # TOTAL FINAL #
        # ----------- #
        total_final = total_geral + valor_bdi + valor_eventuais + aluguel

        linha_total_final = pd.DataFrame([{
            "Código SINAPI": "",
            "Descrição do item": "TOTAL GERAL",
            "Unid.": "",
            "Qtd.": "",
            "Valor Unit.": "",
            "Total s/ BDI": round(total_final, 2)
        }])

        df = pd.concat([df, linha_total_final], ignore_index=True)

        df = df[["Código SINAPI", "Descrição do item", "Unid.", "Qtd.", "Valor Unit.", "Total s/ BDI"]]

        nome_proprietario = nome_arquivo(entrada_proprietario.get())
        nome_base = f"orcamento_reparos_{nome_proprietario}_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.xlsx"

        pasta_downloads = os.path.join(os.path.expanduser("~"), "Downloads")

        if not os.path.isdir(pasta_downloads):
            pasta_downloads = os.getcwd()

        arquivo = filedialog.asksaveasfilename(
            title="Salvar orçamento como:",
            initialdir=pasta_downloads,
            initialfile=nome_base,
            defaultextension=".xlsx",
            filetypes=[("Planilha Excel", "*.xlsx")]
        )

        if not arquivo:
            mostrar_feedback("Geração de orçamento cancelada.", "orange", temporario=False)
            return

        try:
            df.to_excel(arquivo, index=False)
        except PermissionError:
            mostrar_feedback(
                "Feche a planilha antes de gerar novamente.",
                "red",
                temporario=False
            )
            return

        mostrar_feedback("Orçamento gerado com sucesso!", "dark green", temporario=False)

    # ---------------------------- #
    # FORMATAR PLANILHA            #
    # ---------------------------- #
        wb = load_workbook(arquivo)
        ws = wb.active

        fonte_cabecalho = Font(bold=True)

        fundo_cabecalho = PatternFill(
            start_color="006699",
            end_color="006699",
            fill_type="solid"
        )

        fundo_anomalia = PatternFill(
            start_color='D0CECE',
            end_color='D0CECE',
            fill_type='solid'
        )

        fundo_totais = PatternFill(
            start_color="F2F2F2",
            end_color="F2F2F2",
            fill_type="solid"
        )

        fundo_total_final = PatternFill(
            start_color="006699",
            end_color="006699",
            fill_type="solid"
        )

        borda = Border(
            left=Side(style="thin"),
            right=Side(style="thin"),
            top=Side(style="thin"),
            bottom=Side(style="thin")
        )

        for row in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=6):
            for cell in row:
                cell.border = borda

        # Linha de título logo acima do cabeçalho original
        ws.insert_rows(1)
        nome_titulo = entrada_proprietario.get().strip() or ""
        ws.merge_cells("A1:F1")
        titulo_base = "ORÇAMENTO DE REPAROS DE VÍCIOS CONSTRUTIVOS"
        ws["A1"] = (
            f"{titulo_base} - {nome_titulo.upper()}" if nome_titulo else titulo_base
        )
        ws.row_dimensions[1].height = 24.75

        for row in ws.iter_rows(min_row=3, max_row=ws.max_row, min_col=5, max_col=6):
            for cell in row:
                cell.number_format = 'R$ #,##0.00'

        # larguras das colunas
        ws.column_dimensions["A"].width = 7.24
        ws.column_dimensions["B"].width = 70
        ws.column_dimensions["C"].width = 5.96

        # largura da coluna de Qtd.
        max_length = 0

        for col in ["D"]:

            for cell in ws[col]:

                if cell.value is not None:

                    comprimento = len(str(cell.value))

                    if comprimento > max_length:
                        max_length = comprimento

        ws.column_dimensions["D"].width = max_length + 1

        # largura da coluna de Total s/ BDI
        max_length = 0

        for col in ["F"]:

            for cell in ws[col]:

                if cell.value is not None:

                    comprimento = len(str(cell.value))

                    if comprimento > max_length:
                        max_length = comprimento

        ws.column_dimensions["F"].width = max_length

        # centralizar e quebrar texto do cabeçalho
        # título (linha 1)
        ws["A1"].font = Font(bold=True, size=12, color="FFFFFF")
        ws["A1"].fill = fundo_cabecalho
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        # cabeçalho da tabela (linha 2)
        for cell in ws[2]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = fundo_cabecalho
            cell.alignment = Alignment(
                horizontal="center",
                vertical="center",
                wrap_text=True
            )

        colunas_centro = ["A", "C", "D", "E", "F"]

        for col in colunas_centro:

            for cell in ws[col]:

                cell.alignment = Alignment(
                    horizontal="center",
                    vertical="center",
                    wrap_text=True
                )

        for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=6):

            for cell in row:

                cell.alignment = Alignment(
                    horizontal=cell.alignment.horizontal if cell.alignment else "center",
                    vertical="center",
                    wrap_text=True
                )
        for row in ws.iter_rows(min_row=3, max_row=ws.max_row):

            codigo = row[0].value
            descricao = row[1].value

            # --------------------------- #
            # TOTAL SEM BDI, BDI, ALUGUEL #
            # --------------------------- #
            descricao_norm = normalizar_texto(descricao)

            if descricao_norm and (
                descricao_norm == "TOTAL SEM BDI" or
                descricao_norm.startswith("TOTAL DO BDI") or
                descricao_norm.startswith("EVENTUAIS") or
                descricao_norm == "ALUGUEL (1 MES)"
            ):
                linha_idx = row[0].row
                descricao_formatada = str(descricao).strip()

                if descricao_norm == "TOTAL SEM BDI":
                    descricao_formatada = "Total sem BDI"
                elif descricao_norm == "ALUGUEL (1 MES)":
                    descricao_formatada = "Aluguel (1 mês)"
                elif descricao_norm.startswith("TOTAL DO BDI"):
                    descricao_formatada = f"Total do BDI ({entrada_bdi.get()}%)"

                # O texto original está na coluna B. Após mesclar, precisa ficar em A
                ws.cell(row=linha_idx, column=1, value=descricao_formatada)
                for col_idx in range(2, 6):
                    ws.cell(row=linha_idx, column=col_idx, value=None)

                # Mesclar rótulo em A:E, como no modelo de referência.
                ws.merge_cells(start_row=linha_idx, start_column=1, end_row=linha_idx, end_column=5)

                for col_idx in range(1, 7):
                    cell = ws.cell(row=linha_idx, column=col_idx)
                    cell.fill = fundo_totais
                    cell.font = Font(bold=True, size=11)
                    cell.alignment = Alignment(
                        horizontal="right" if col_idx == 1 else "center",
                        vertical="center",
                        wrap_text=True
                    )

            # ----------- #
            # TOTAL FINAL #
            # ----------- #
            elif descricao == "TOTAL GERAL":
                linha_idx = row[0].row
                descricao_formatada = "Total do Orçamento"

                ws.cell(row=linha_idx, column=1, value=descricao_formatada)
                for col_idx in range(2, 6):
                    ws.cell(row=linha_idx, column=col_idx, value=None)

                ws.merge_cells(start_row=linha_idx, start_column=1, end_row=linha_idx, end_column=5)

                for col_idx in range(1, 7):
                    cell = ws.cell(row=linha_idx, column=col_idx)
                    cell.fill = fundo_total_final
                    cell.font = Font(bold=True, size=12, color="FFFFFF")
                    cell.alignment = Alignment(
                        horizontal="right" if col_idx == 1 else "center",
                        vertical="center",
                        wrap_text=True
                    )

            # --------------------- #
            # SUBTÍTULO DE ANOMALIA #
            # --------------------- #
            elif (codigo in ("", None)) and descricao not in ("", None):

                for cell in row:
                    cell.fill = fundo_anomalia
                    cell.font = Font(bold=True, size=12)

    # Pintar a mensagem de 'Código não encontrado' em vermelho
            descricao = str(row[1].value)

            if "Código não encontrado" in descricao:
                for cell in row:
                    cell.font = Font(
                    name=cell.font.name,
                    size=cell.font.size,
                    bold=cell.font.bold,
                    italic=cell.font.italic,
                    color="FF0000"
                    )

        # ------------------ #
        # RODAPÉ DA PLANILHA #
        # ------------------ #
        linha_nota_sinapi = ws.max_row + 1
        estado_planilha = combo_estado.get().strip()
        sufixo_referencia = (
            f"{estado_planilha} {ctx.sinapi_referencia_rotulo}"
            if estado_planilha
            else ctx.sinapi_referencia_rotulo
        )
        texto_nota = f"Base de preços: SINAPI — referência: {sufixo_referencia}"
        ws.merge_cells(
            start_row=linha_nota_sinapi, start_column=1,
            end_row=linha_nota_sinapi, end_column=6,
        )
        celula_nota = ws.cell(row=linha_nota_sinapi, column=1, value=texto_nota)
        celula_nota.font = Font(size=9, italic=True, color="444444")
        celula_nota.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

        wb.save(arquivo)
        os.startfile(arquivo)

    # ---------------------------- #
    # BOTÃO GERAR ORÇAMENTO        #
    # ---------------------------- #
    wrapper._icone_excel_export = None
    wrapper._icone_word_parecer = None
    kwargs_botao_word = {
        "text": "Parecer de atualização",
        "state": "disabled",
        "font": ("Arial", 10, "bold"),
        "fg": "#000000",
        "disabledforeground": "#9e9e9e",
        "bg": "#f5fafc",
        "activebackground": "#f5fafc",
        "relief": "flat",
        "bd": 0,
        "padx": 2,
        "pady": 0,
        "highlightthickness": 0,
        "takefocus": 0,
    }
    caminho_icone_word = asset_path("icons", "microsoft-word-24.png")
    if caminho_icone_word is not None:
        wrapper._icone_word_parecer = tk.PhotoImage(file=str(caminho_icone_word))
        kwargs_botao_word["image"] = wrapper._icone_word_parecer
        kwargs_botao_word["compound"] = "right"
    host_parecer = tk.Frame(container_total, bg="#f5fafc")
    host_parecer.pack(side="left", padx=(0, 12))
    btn_parecer = tk.Button(host_parecer, **kwargs_botao_word)
    btn_parecer.pack()
    vincular_tooltip(
        host_parecer,
        "Em breve: gerar Parecer de Atualização de Orçamento.",
    )

    kwargs_botao_excel = {
        "text": "Gerar orçamento",
        "command": gerar_orcamento,
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
        wrapper._icone_excel_export = tk.PhotoImage(file=str(caminho_icone_excel))
        kwargs_botao_excel["image"] = wrapper._icone_excel_export
        kwargs_botao_excel["compound"] = "right"
    tk.Button(container_total, **kwargs_botao_excel).pack(
        side="left", padx=(0, 16)
    )
    label_total.pack(side="left")

    def ao_opcao_orcamento(_event=None):
        atualizar_valores()
        registrar_historico("Alterar opções do orçamento")

    for chk in checks_opcoes:
        chk.config(command=ao_opcao_orcamento)
    entrada_bdi.bind("<KeyRelease>", agendar_recalculo)
    entrada_bdi.bind("<FocusOut>", atualizar_valores)
    entrada_aluguel.bind("<KeyRelease>", agendar_recalculo)
    entrada_aluguel.bind("<FocusOut>", atualizar_valores)
    for campos in comodos.values():
        for entrada in campos.values():
            entrada.bind("<KeyRelease>", agendar_recalculo)
            entrada.bind("<FocusOut>", atualizar_valores)

    HISTORICO_MAX = 40

    def capturar_snapshot():
        metragens = {}
        for nome, campos in comodos.items():
            metragens[nome] = {
                chave: campos[chave].get()
                for chave in ("piso", "rev_arg", "rev_cer")
            }
        return {
            "anomalias": deepcopy(lista_anomalias),
            "metragens": metragens,
            "bdi": entrada_bdi.get(),
            "aluguel": entrada_aluguel.get(),
            "acompanhamento": bool(var_acompanhamento.get()),
            "eventuais": bool(var_eventuais.get()),
            "estado": combo_estado.get(),
        }

    def aplicar_snapshot(snap):
        nonlocal _aplicando_historico
        _aplicando_historico = True
        try:
            lista_anomalias.clear()
            lista_anomalias.extend(deepcopy(snap.get("anomalias") or []))
            for nome, valores in (snap.get("metragens") or {}).items():
                if nome not in comodos:
                    continue
                for chave, valor in valores.items():
                    entrada = comodos[nome][chave]
                    if str(entrada.cget("state")) == "disabled":
                        continue
                    entrada.delete(0, "end")
                    entrada.insert(0, valor)
            entrada_bdi.delete(0, "end")
            entrada_bdi.insert(0, snap.get("bdi", ""))
            entrada_aluguel.delete(0, "end")
            entrada_aluguel.insert(0, snap.get("aluguel", ""))
            var_acompanhamento.set(bool(snap.get("acompanhamento")))
            var_eventuais.set(bool(snap.get("eventuais")))
            estado = str(snap.get("estado") or "")
            if estado:
                combo_estado.set(estado)
            atualizar_valores()
        finally:
            _aplicando_historico = False

    def atualizar_botoes_historico():
        definir_estado_botao_icone(
            btn_desfazer, "normal" if _historico_undo else "disabled"
        )
        definir_estado_botao_icone(
            btn_refazer, "normal" if _historico_redo else "disabled"
        )

    def registrar_historico(descricao, *, coalescer=False):
        nonlocal _snapshot_base
        if _aplicando_historico:
            return
        depois = capturar_snapshot()
        antes = _snapshot_base if _snapshot_base is not None else depois
        if antes == depois:
            _snapshot_base = depois
            return
        if (
            coalescer
            and _historico_undo
            and _historico_undo[-1]["descricao"] == descricao
        ):
            _historico_undo[-1]["depois"] = depois
        else:
            _historico_undo.append(
                {"antes": antes, "depois": depois, "descricao": descricao}
            )
            if len(_historico_undo) > HISTORICO_MAX:
                del _historico_undo[0 : len(_historico_undo) - HISTORICO_MAX]
        _historico_redo.clear()
        _snapshot_base = depois
        atualizar_botoes_historico()

    def desfazer():
        nonlocal _snapshot_base
        if not _historico_undo or _aplicando_historico:
            return
        entrada = _historico_undo.pop()
        _historico_redo.append(entrada)
        aplicar_snapshot(entrada["antes"])
        _snapshot_base = capturar_snapshot()
        atualizar_botoes_historico()
        mostrar_feedback(f"Desfeita — {entrada['descricao']}", "orange")

    def refazer():
        nonlocal _snapshot_base
        if not _historico_redo or _aplicando_historico:
            return
        entrada = _historico_redo.pop()
        _historico_undo.append(entrada)
        aplicar_snapshot(entrada["depois"])
        _snapshot_base = capturar_snapshot()
        atualizar_botoes_historico()
        mostrar_feedback(f"Refeita — {entrada['descricao']}", "green")

    def widget_do_modulo(widget):
        atual = widget
        while atual is not None:
            if atual is wrapper:
                return True
            try:
                atual = atual.master
            except (tk.TclError, AttributeError):
                return False
        return False

    def ao_tecla_desfazer(event):
        if not widget_do_modulo(event.widget):
            return
        desfazer()
        return "break"

    def ao_tecla_refazer(event):
        if not widget_do_modulo(event.widget):
            return
        refazer()
        return "break"

    def desvincular_atalhos(_event=None):
        if _event is not None and _event.widget is not wrapper:
            return
        for widget, sequencia, func_id in _binds_historico:
            try:
                widget.unbind(sequencia, func_id)
            except tk.TclError:
                pass
        _binds_historico.clear()

    for sequencia, callback in (
        ("<Control-z>", ao_tecla_desfazer),
        ("<Control-Z>", ao_tecla_desfazer),
        ("<Control-y>", ao_tecla_refazer),
        ("<Control-Y>", ao_tecla_refazer),
        ("<Control-Shift-z>", ao_tecla_refazer),
        ("<Control-Shift-Z>", ao_tecla_refazer),
    ):
        func_id = root.bind(sequencia, callback, add="+")
        _binds_historico.append((root, sequencia, func_id))
    wrapper.bind("<Destroy>", desvincular_atalhos)

    _snapshot_base = capturar_snapshot()
    atualizar_botoes_historico()

    ctx.registrar_callback_sinapi(aplicar_sinapi_na_interface)
    aplicar_sinapi_na_interface()
    atualizar_total_rodape()

    def ao_conjunto_idebras(nome_conjunto):
        resultado = resolver_uf_conjunto(nome_conjunto)
        valores = list(combo_estado["values"] or [])
        if resultado.uf:
            if resultado.uf not in valores:
                mostrar_feedback(
                    f"Estado {resultado.uf} identificado, mas não há SINAPI para essa UF.",
                    "orange",
                    temporario=False,
                )
                return
            if combo_estado.get().strip() != resultado.uf:
                combo_estado.set(resultado.uf)
                atualizar_valores()
                registrar_historico("Definir estado pelo conjunto")
                mostrar_feedback(
                    f"Estado definido a partir do conjunto: {resultado.uf}.",
                    "green",
                )
            return
        if resultado.motivo == "ambigua":
            cidade = str(resultado.cidade or "").title()
            ufs = sorted(resultado.ufs_possiveis)
            escolhido = perguntar_escolha(
                root,
                "Selecionar estado",
                f"A cidade '{cidade}' existe em mais de um estado.\n"
                "Qual é o estado deste conjunto?",
                ufs,
            )
            if escolhido and escolhido in valores:
                combo_estado.set(escolhido)
                atualizar_valores()
                registrar_historico("Definir estado pelo conjunto")
                mostrar_feedback(
                    f"Estado definido: {escolhido}.",
                    "green",
                )
            elif escolhido:
                mostrar_feedback(
                    f"Estado {escolhido} identificado, mas não há SINAPI para essa UF.",
                    "orange",
                    temporario=False,
                )
            else:
                mostrar_feedback(
                    f"Selecione o Estado de '{cidade}' ({', '.join(ufs)}).",
                    "orange",
                    temporario=False,
                )
            return
        if resultado.cidade:
            mostrar_feedback(
                f"Cidade '{resultado.cidade}' não reconhecida para preencher o Estado. "
                "Selecione o Estado e informe o suporte/administrador.",
                "orange",
                temporario=False,
            )

    ctrl_idebras.update(
        _montar_painel_idebras(
            frame_idebras_host,
            root,
            preencher_metragens,
            _refs_icones,
            on_conjunto=ao_conjunto_idebras,
            on_limpar_metragens=ao_trocar_conjunto_limpar_metragens,
        )
    )

    def ativar_scroll():
        return None

    def desativar_scroll():
        return None

    wrapper.aplicar_sinapi = aplicar_sinapi_na_interface
    wrapper.ativar_scroll = ativar_scroll
    wrapper.desativar_scroll = desativar_scroll
    wrapper.focar = lambda: entrada_proprietario.focus()
    root.after_idle(_reflow_linha_dados)

    return wrapper


def _montar_painel_idebras(
    host, root, preencher_metragens, refs_icones, on_conjunto=None, on_limpar_metragens=None
):
    """Painel de conjunto/planta do Idebras, preenchido de forma assíncrona."""
    cliente = IdebrasClient()
    conjuntos = []
    plantas = []
    conjunto_por_nome = {}
    conjunto_carregado_id = None

    frame = tk.Frame(host, bg="#ececec")
    frame.pack(fill="x")
    frame.columnconfigure(1, weight=1)
    frame.columnconfigure(3, weight=1)

    var_status = tk.StringVar(value="Conectando ao Idebras...")
    var_conjunto = tk.StringVar()
    var_planta = tk.StringVar()

    tk.Label(frame, text="Conjunto:", bg="#ececec").grid(row=0, column=0, padx=(0, 4), sticky="w")
    campo_conjunto = CampoListaPesquisavel(
        frame,
        textvariable=var_conjunto,
        normalizar=normalizar_ambiente,
        altura_lista=12,
        largura_minima_lista=420,
        bg="#ececec",
    )
    campo_conjunto.grid(row=0, column=1, padx=(0, 10), sticky="ew")

    tk.Label(frame, text="Planta:", bg="#ececec").grid(row=0, column=2, padx=(0, 4), sticky="w")
    combo_planta = ttk.Combobox(frame, textvariable=var_planta, state="readonly")
    combo_planta.grid(row=0, column=3, sticky="ew")

    linha_status = tk.Frame(frame, bg="#ececec")
    linha_status.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 0))
    linha_status.columnconfigure(0, weight=1)

    tk.Label(
        linha_status,
        textvariable=var_status,
        fg="#555555",
        bg="#ececec",
        anchor="w",
    ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

    slot_ampulheta = tk.Frame(linha_status, bg="#ececec", width=30, height=26)
    slot_ampulheta.grid(row=0, column=1, padx=(0, 8), sticky="e")
    slot_ampulheta.pack_propagate(False)
    ampulheta = IndicadorAmpulheta(
        slot_ampulheta,
        altura=24,
        cor="#006699",
        bg="#ececec",
        refs=refs_icones,
    )

    btn_visualizar = criar_botao_ttk_com_icone(
        linha_status,
        texto="Visualizar ambientes",
        nome_icone="search-outline",
        command=lambda: None,
        refs=refs_icones,
    )
    btn_visualizar.grid(row=0, column=2, sticky="e")

    btn_preencher = criar_botao_ttk_com_icone(
        linha_status,
        texto="Preencher metragens",
        nome_icone="color-wand-outline",
        command=lambda: None,
        refs=refs_icones,
    )
    btn_preencher.grid(row=0, column=3, sticky="e", padx=(6, 0))
    vincular_tooltip(
        btn_preencher,
        "Preencher metragens da planta nos cômodos",
    )

    def na_ui(fn):
        try:
            if root.winfo_exists():
                root.after(0, fn)
        except tk.TclError:
            pass

    def atualizar_combo_conjuntos():
        campo_conjunto.definir_opcoes([c.nome for c in conjuntos])

    def conjunto_selecionado():
        nome = var_conjunto.get().strip()
        encontrado = conjunto_por_nome.get(nome)
        if encontrado is not None:
            return encontrado
        chave = normalizar_ambiente(nome)
        if not chave:
            return None
        matches = [c for c in conjuntos if chave in normalizar_ambiente(c.nome)]
        if len(matches) == 1:
            var_conjunto.set(matches[0].nome)
            return matches[0]
        return None

    def planta_selecionada():
        nome = var_planta.get()
        for planta in plantas:
            rotulo = _rotulo_planta(planta)
            if rotulo == nome:
                return planta
        return plantas[0] if plantas else None

    def ao_escolher_conjunto(_event=None):
        nonlocal conjunto_carregado_id
        conjunto = conjunto_selecionado()
        if conjunto is None:
            return
        if var_conjunto.get() != conjunto.nome:
            var_conjunto.set(conjunto.nome)
        if on_conjunto is not None:
            on_conjunto(conjunto.nome)
        if conjunto.id == conjunto_carregado_id and plantas:
            return
        if on_limpar_metragens is not None and conjunto.id != conjunto_carregado_id:
            on_limpar_metragens()
        conjunto_carregado_id = conjunto.id
        var_status.set(f"Buscando plantas de {conjunto.nome}...")
        var_planta.set("")
        combo_planta["values"] = []

        def trabalho():
            try:
                encontradas = cliente.pesquisar_plantas(conjunto.id)
            except IdebrasError as exc:
                msg = str(exc)
                na_ui(lambda m=msg: var_status.set(m))
                return
            except Exception as exc:
                msg = f"Erro ao buscar plantas: {exc}"
                na_ui(lambda m=msg: var_status.set(m))
                return

            def aplicar():
                nonlocal plantas
                plantas = encontradas
                combo_planta["values"] = [_rotulo_planta(p) for p in plantas]
                if plantas:
                    var_planta.set(_rotulo_planta(plantas[0]))
                    var_status.set(
                        f"{len(plantas)} planta(s) encontrada(s) para {conjunto.nome}."
                    )
                else:
                    var_status.set("Nenhuma planta cadastrada para este conjunto.")

            na_ui(aplicar)

        threading.Thread(target=trabalho, daemon=True).start()

    def iniciar_carregamento(mensagem):
        var_status.set(mensagem)
        ampulheta.iniciar()
        definir_estado_botao_icone(btn_visualizar, "disabled")
        definir_estado_botao_icone(btn_preencher, "disabled")

    def parar_carregamento():
        ampulheta.parar()
        definir_estado_botao_icone(btn_visualizar, "normal")
        definir_estado_botao_icone(btn_preencher, "normal")

    def carregar_ambientes(ao_sucesso, mensagem):
        conjunto = conjunto_selecionado()
        planta = planta_selecionada()
        if conjunto is None:
            var_status.set("Digite ou selecione um conjunto.")
            return
        if on_conjunto is not None:
            on_conjunto(conjunto.nome)
        if planta is None and var_planta.get().strip():
            var_status.set("Selecione uma planta.")
            return
        if planta is not None and not planta.event_target_ambientes:
            var_status.set("Esta planta não possui ambientes para visualizar.")
            return
        iniciar_carregamento(mensagem)

        def trabalho():
            try:
                encontradas = cliente.pesquisar_plantas(conjunto.id)
                if not encontradas:
                    na_ui(lambda: (
                        parar_carregamento(),
                        var_status.set("Nenhuma planta cadastrada para este conjunto."),
                    ))
                    return
                if planta is not None:
                    planta_atual = next(
                        (p for p in encontradas if p.nome == planta.nome),
                        encontradas[0],
                    )
                else:
                    planta_atual = encontradas[0]
                if not planta_atual.event_target_ambientes:
                    na_ui(lambda: (
                        parar_carregamento(),
                        var_status.set("Esta planta não possui ambientes para visualizar."),
                    ))
                    return
                ambientes = cliente.obter_ambientes(planta_atual.event_target_ambientes)
            except IdebrasError as exc:
                msg = str(exc)
                na_ui(lambda m=msg: (parar_carregamento(), var_status.set(m)))
                return
            except Exception as exc:
                msg = f"Erro ao carregar ambientes: {exc}"
                na_ui(lambda m=msg: (parar_carregamento(), var_status.set(m)))
                return

            def concluir():
                parar_carregamento()
                ao_sucesso(conjunto, planta_atual, ambientes)

            na_ui(concluir)

        threading.Thread(target=trabalho, daemon=True).start()

    def visualizar_ambientes():
        def abrir(conjunto, planta_atual, ambientes):
            if not ambientes:
                var_status.set("A planta não possui ambientes cadastrados.")
                return
            DialogoAmbientesPlanta(
                root,
                conjunto_nome=conjunto.nome,
                planta=planta_atual,
                ambientes=ambientes,
                on_aplicar=preencher_metragens,
            )
            var_status.set(
                f"{len(ambientes)} ambiente(s) carregados de {planta_atual.nome}."
            )

        carregar_ambientes(abrir, "Carregando ambientes da planta...")

    def preencher_metragens_planta():
        def aplicar(conjunto, planta_atual, ambientes):
            if not ambientes:
                var_status.set("A planta não possui ambientes cadastrados.")
                return
            preencher_metragens(medidas_para_orcamento(ambientes))
            mapeados = sum(1 for amb in ambientes if amb.comodo_orc)
            var_status.set(
                f"Metragens preenchidas a partir de {planta_atual.nome} "
                f"({mapeados} cômodo(s) mapeado(s))."
            )

        carregar_ambientes(aplicar, "Preenchendo metragens da planta...")

    def selecionar_conjunto(nome):
        if not nome:
            return
        var_conjunto.set(nome)
        ao_escolher_conjunto()

    btn_visualizar.configure(command=visualizar_ambientes)
    btn_visualizar._orc_command = visualizar_ambientes
    btn_preencher.configure(command=preencher_metragens_planta)
    btn_preencher._orc_command = preencher_metragens_planta
    campo_conjunto.on_escolher = lambda _nome: ao_escolher_conjunto()

    def conectar():
        def trabalho():
            try:
                carregados = cliente.listar_conjuntos()
            except IdebrasError as exc:
                msg = str(exc)
                na_ui(lambda m=msg: var_status.set(m))
                return
            except Exception as exc:
                msg = f"Erro Idebras: {exc}"
                na_ui(lambda m=msg: var_status.set(m))
                return

            def aplicar():
                nonlocal conjuntos, conjunto_por_nome
                conjuntos = carregados
                conjunto_por_nome = {c.nome: c for c in conjuntos}
                atualizar_combo_conjuntos()
                var_status.set(
                    f"Conectado no Idebras · {len(conjuntos)} conjuntos."
                )

            na_ui(aplicar)

        threading.Thread(target=trabalho, daemon=True).start()

    conectar()
    return {
        "cliente": cliente,
        "obter_conjuntos": lambda: conjuntos,
        "selecionar_conjunto": selecionar_conjunto,
    }


def _rotulo_planta(planta):
    partes = [planta.nome]
    if planta.area_total:
        partes.append(f"{planta.area_total} m²")
    if planta.metodo_construtivo:
        partes.append(planta.metodo_construtivo)
    return " · ".join(partes)
