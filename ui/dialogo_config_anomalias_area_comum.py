"""Cadastro de anomalias da Área Comum (admin)."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from core.area_comum_anomalias import (
    ORIGEM_ETAPA,
    ORIGEM_ITENS,
    ROTULOS_TIPO_CALCULO,
    TIPOS_CALCULO,
    UNIDADES_COMUNS,
    carregar_catalogo,
    nova_anomalia,
    novo_item_sinapi,
    novo_reparo,
    salvar_catalogo,
)
from ui.icones import criar_botao_ttk_com_icone
from ui.temas import aplicar_chrome_dialogo, texto_contraste
from ui.widgets import (
    CampoListaPesquisavel,
    aplicar_icone_janela,
    centralizar_janela,
    criar_botao_cancelar,
    criar_botao_fechar,
    focar_entrada_apos_exibir,
    perguntar_texto,
    preparar_toplevel,
)


def _float_br(texto: str) -> float:
    return float(str(texto).strip().replace(",", "."))


def _listar_etapas() -> list[dict]:
    try:
        from core.etapas_predefinidas_storage import (
            carregar,
            listar,
            obter_cache_catalogo,
        )

        if obter_cache_catalogo() is None:
            carregar()
        return listar()
    except (ValueError, OSError):
        return []


class DialogoItemSinapiAreaComum(tk.Toplevel):
    def __init__(self, parent, item=None, on_confirmar=None, ctx=None):
        super().__init__(parent)
        preparar_toplevel(self)
        cores, estilos = aplicar_chrome_dialogo(self)
        fundo = cores.fundo
        self.on_confirmar = on_confirmar
        self.ctx = ctx
        self._refs_icones: list = []
        self.title("Item SINAPI" if item else "Novo item SINAPI")
        aplicar_icone_janela(self)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        item = item or {}
        painel = tk.Frame(self, bg=fundo, padx=16, pady=14)
        painel.pack(fill="x")

        self.var_codigo = tk.StringVar(value=str(item.get("codigo_sinapi", "")))
        self.var_unidade = tk.StringVar(value=str(item.get("unidade", "m²")))
        self.var_coef = tk.StringVar(
            value=str(item.get("coeficiente", 1)).replace(".", ",")
        )

        linha_codigo = tk.Frame(painel, bg=fundo)
        linha_codigo.pack(fill="x", pady=3)
        tk.Label(
            linha_codigo,
            text="Código SINAPI:",
            width=22,
            anchor="w",
            bg=fundo,
            fg=cores.texto,
        ).pack(side="left")
        entrada_codigo = ttk.Entry(linha_codigo, textvariable=self.var_codigo, width=18)
        entrada_codigo.pack(side="left")
        if ctx is not None:
            criar_botao_ttk_com_icone(
                linha_codigo,
                texto="Buscar",
                nome_icone="search-outline",
                command=self._buscar_sinapi,
                estilo=estilos.compacto,
                cor_icone=estilos.icone,
                refs=self._refs_icones,
            ).pack(side="left", padx=(8, 0))

        self._campo(painel, "Unidade:", self.var_unidade, valores=UNIDADES_COMUNS)
        valores_tipo = [f"{k} — {ROTULOS_TIPO_CALCULO.get(k, k)}" for k in TIPOS_CALCULO]
        atual_tipo = str(item.get("tipo_calculo", "area_fachada_total"))
        rotulo_tipo = f"{atual_tipo} — {ROTULOS_TIPO_CALCULO.get(atual_tipo, atual_tipo)}"
        self.var_tipo_exibicao = tk.StringVar(
            value=rotulo_tipo if rotulo_tipo in valores_tipo else valores_tipo[0]
        )
        self._campo(painel, "Tipo de cálculo:", self.var_tipo_exibicao, valores=valores_tipo)
        self._campo(painel, "Coeficiente:", self.var_coef)

        botoes = ttk.Frame(painel)
        botoes.pack(fill="x", pady=(12, 0))
        criar_botao_cancelar(botoes, self.destroy).pack(side="right")
        criar_botao_ttk_com_icone(
            botoes,
            texto="Salvar item",
            nome_icone="save-outline",
            command=self._confirmar,
            estilo=estilos.salvar,
            cor_icone=estilos.icone_salvar,
            refs=self._refs_icones,
        ).pack(side="right", padx=(0, 8))

        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        centralizar_janela(self, parent)
        focar_entrada_apos_exibir(entrada_codigo)

    def _campo(self, parent, rotulo, var, valores=None):
        cores = self._cores
        fundo = cores.fundo
        linha = tk.Frame(parent, bg=fundo)
        linha.pack(fill="x", pady=3)
        tk.Label(
            linha, text=rotulo, width=22, anchor="w", bg=fundo, fg=cores.texto
        ).pack(side="left")
        if valores is None:
            ttk.Entry(linha, textvariable=var, width=42).pack(side="left", fill="x", expand=True)
            return
        combo = ttk.Combobox(linha, textvariable=var, values=list(valores), width=40)
        combo.pack(side="left", fill="x", expand=True)

    def _buscar_sinapi(self):
        from ui.orcamento_customizado import DialogoBuscaSinapi

        estado = ""
        if self.ctx is not None:
            estados = self.ctx.obter_estados()
            estado = estados[0] if estados else ""

        def ao_escolher(codigo, _descricao, unidade, _custo, _quantidade, _estado, _tipo_ic=""):
            if codigo:
                self.var_codigo.set(str(codigo).strip())
            if unidade:
                self.var_unidade.set(str(unidade).strip())

        DialogoBuscaSinapi(
            self,
            self.ctx,
            estado,
            ao_escolher,
            titulo="Buscar código SINAPI",
            mostrar_quantidade=False,
            texto_confirmar="Usar código",
            fechar_unico=True,
        )

    def _confirmar(self):
        codigo = self.var_codigo.get().strip()
        if not codigo:
            messagebox.showwarning("Item", "Informe o código SINAPI.", parent=self)
            return
        try:
            coeficiente = _float_br(self.var_coef.get())
        except ValueError:
            messagebox.showwarning("Item", "Coeficiente inválido.", parent=self)
            return
        tipo_exib = self.var_tipo_exibicao.get().strip()
        tipo = tipo_exib.split(" — ", 1)[0].strip() or "fixo"
        if tipo not in TIPOS_CALCULO:
            tipo = "fixo"
        item = novo_item_sinapi(
            codigo_sinapi=codigo,
            unidade=self.var_unidade.get().strip() or "un",
            tipo_calculo=tipo,
            coeficiente=coeficiente,
        )
        if self.on_confirmar:
            self.on_confirmar(item)
        self.destroy()


def _rotulos_tipo_calculo() -> list[str]:
    return [f"{k} — {ROTULOS_TIPO_CALCULO.get(k, k)}" for k in TIPOS_CALCULO]


def _chave_tipo_calculo(texto: str) -> str:
    chave = str(texto or "").split(" — ", 1)[0].strip()
    return chave if chave in TIPOS_CALCULO else "fixo"


class DialogoSelecionarEtapaPredefinida(tk.Toplevel):
    def __init__(self, parent, on_escolher):
        super().__init__(parent)
        preparar_toplevel(self)
        cores, _estilos = aplicar_chrome_dialogo(self)
        fundo = cores.fundo
        self.on_escolher = on_escolher
        self._etapas = _listar_etapas()
        self._visiveis: list[dict] = list(self._etapas)
        self.title("Selecionar etapa pré-definida")
        aplicar_icone_janela(self)
        self.transient(parent)
        self.grab_set()
        self.geometry("760x560")
        self.minsize(560, 420)

        painel = tk.Frame(self, bg=fundo, padx=14, pady=12)
        painel.pack(fill="both", expand=True)
        painel.rowconfigure(2, weight=1)
        painel.columnconfigure(0, weight=1)

        tk.Label(
            painel,
            text="Etapas cadastradas no ORC:",
            bg=fundo,
            fg=cores.texto,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 6))

        self.var_filtro = tk.StringVar()
        entrada_filtro = ttk.Entry(painel, textvariable=self.var_filtro)
        entrada_filtro.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.var_filtro.trace_add("write", lambda *_a: self._filtrar())

        bloco_lista = tk.Frame(painel, bg=fundo)
        bloco_lista.grid(row=2, column=0, sticky="nsew")
        bloco_lista.rowconfigure(0, weight=1)
        bloco_lista.columnconfigure(0, weight=1)
        self.lista = tk.Listbox(
            bloco_lista,
            exportselection=False,
            bg=cores.fundo_cartao,
            fg=cores.texto,
            selectbackground=cores.titulo,
            selectforeground=texto_contraste(cores.titulo),
            font=("Segoe UI", 10),
        )
        self.lista.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(bloco_lista, orient="vertical", command=self.lista.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.lista.configure(yscrollcommand=scroll.set)
        self.lista.bind("<Double-1>", lambda _e: self._confirmar())
        self.lista.bind("<Return>", lambda _e: self._confirmar())

        botoes = tk.Frame(painel, bg=fundo)
        botoes.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        criar_botao_cancelar(botoes, self.destroy).pack(side="right")
        ttk.Button(
            botoes, text="Usar etapa", command=self._confirmar, style="Add.TButton"
        ).pack(side="right", padx=(0, 8))
        self.bind("<Escape>", lambda _e: self.destroy())
        self._popular()
        self.update_idletasks()
        centralizar_janela(self, parent)
        focar_entrada_apos_exibir(entrada_filtro)

    def _popular(self):
        consulta = (self.var_filtro.get() or "").casefold().strip()
        self.lista.delete(0, "end")
        self._visiveis = []
        for etapa in self._etapas:
            nome = etapa.get("nome") or "(sem nome)"
            if consulta and consulta not in str(nome).casefold():
                continue
            self._visiveis.append(etapa)
            self.lista.insert("end", nome)
        if self._visiveis:
            self.lista.selection_set(0)
            self.lista.see(0)

    def _filtrar(self):
        self._popular()

    def _confirmar(self):
        selecao = self.lista.curselection()
        if not selecao:
            messagebox.showwarning("Etapa", "Selecione uma etapa.", parent=self)
            return
        etapa = self._visiveis[selecao[0]]
        if self.on_escolher:
            self.on_escolher(etapa)
        self.destroy()


class DialogoConfigAnomaliasAreaComum(tk.Toplevel):
    def __init__(self, parent, ctx, on_salvo=None):
        super().__init__(parent)
        preparar_toplevel(self)
        cores, estilos = aplicar_chrome_dialogo(self)
        fundo = cores.fundo
        self.ctx = ctx
        self.on_salvo = on_salvo
        self._refs_icones: list = []
        self._nome_atual: str | None = None
        self._reparo_atual_id: str | None = None
        self._carregando = False
        self._dados = carregar_catalogo()

        self.title("Configurar anomalias — Área Comum")
        aplicar_icone_janela(self)
        self.transient(parent)
        self.grab_set()
        self.geometry("1040x680")
        self.minsize(860, 560)

        painel = tk.Frame(self, bg=fundo, padx=14, pady=12)
        painel.pack(fill="both", expand=True)
        painel.columnconfigure(1, weight=1)
        painel.rowconfigure(1, weight=1)

        tk.Label(
            painel,
            text="Anomalias da Área Comum",
            font=("Arial", 12, "bold"),
            fg=cores.titulo,
            bg=fundo,
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        esquerda = tk.Frame(painel, bg=fundo)
        esquerda.grid(row=1, column=0, sticky="ns", padx=(0, 10))
        esquerda.rowconfigure(0, weight=1)

        self.lista = tk.Listbox(
            esquerda,
            width=38,
            height=22,
            exportselection=False,
            bg=cores.fundo_cartao,
            fg=cores.texto,
            selectbackground=cores.titulo,
            selectforeground=texto_contraste(cores.titulo),
            highlightbackground=cores.borda_suave,
            highlightthickness=1,
            relief="flat",
        )
        self.lista.grid(row=0, column=0, sticky="ns")
        scroll_lista = ttk.Scrollbar(esquerda, orient="vertical", command=self.lista.yview)
        scroll_lista.grid(row=0, column=1, sticky="ns")
        self.lista.configure(yscrollcommand=scroll_lista.set)
        self.lista.bind("<<ListboxSelect>>", self._ao_selecionar)

        botoes_lista = tk.Frame(esquerda, bg=fundo)
        botoes_lista.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        criar_botao_ttk_com_icone(
            botoes_lista,
            texto="Nova",
            nome_icone="add-circle-outline",
            command=self._nova,
            estilo=estilos.compacto_adicionar,
            cor_icone=estilos.icone_adicionar,
            refs=self._refs_icones,
        ).pack(side="left")
        criar_botao_ttk_com_icone(
            botoes_lista,
            texto="Renomear",
            nome_icone="pencil",
            command=self._renomear,
            estilo=estilos.compacto,
            cor_icone=estilos.icone_editar,
            refs=self._refs_icones,
        ).pack(side="left", padx=4)
        criar_botao_ttk_com_icone(
            botoes_lista,
            texto="Excluir",
            nome_icone="trash-outline",
            command=self._excluir,
            estilo=estilos.compacto_excluir,
            cor_icone=estilos.icone_excluir,
            refs=self._refs_icones,
        ).pack(side="left")

        direita = tk.LabelFrame(
            painel, text="Reparos desta anomalia", bg=fundo, fg=cores.texto, padx=10, pady=8
        )
        direita.grid(row=1, column=1, sticky="nsew")
        direita.columnconfigure(0, weight=1)
        direita.rowconfigure(3, weight=1)

        tk.Label(
            direita,
            text=(
                "Cada anomalia pode ter mais de um reparo (ex.: sistemas construtivos "
                "diferentes). O reparo usa itens SINAPI ou uma etapa pré-definida."
            ),
            bg=fundo,
            fg=cores.texto_suave,
            wraplength=620,
            justify="left",
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 8))

        linha_reparos = tk.Frame(direita, bg=fundo)
        linha_reparos.grid(row=1, column=0, sticky="ew")
        self.combo_reparo = ttk.Combobox(linha_reparos, state="readonly", width=42)
        self.combo_reparo.pack(side="left", fill="x", expand=True)
        self.combo_reparo.bind("<<ComboboxSelected>>", self._ao_trocar_reparo)
        criar_botao_ttk_com_icone(
            linha_reparos,
            texto="Novo reparo",
            nome_icone="add-circle-outline",
            command=self._novo_reparo,
            estilo=estilos.compacto_adicionar,
            cor_icone=estilos.icone_adicionar,
            refs=self._refs_icones,
        ).pack(side="left", padx=(8, 0))
        criar_botao_ttk_com_icone(
            linha_reparos,
            texto="Excluir reparo",
            nome_icone="trash-outline",
            command=self._excluir_reparo,
            estilo=estilos.compacto_excluir,
            cor_icone=estilos.icone_excluir,
            refs=self._refs_icones,
        ).pack(side="left", padx=(4, 0))

        origem = tk.LabelFrame(
            direita, text="Origem do reparo", bg=fundo, fg=cores.texto, padx=8, pady=6
        )
        origem.grid(row=2, column=0, sticky="ew", pady=(8, 6))
        self.var_origem = tk.StringVar(value=ORIGEM_ITENS)
        ttk.Radiobutton(
            origem,
            text="A. Itens SINAPI",
            value=ORIGEM_ITENS,
            variable=self.var_origem,
            command=self._ao_mudar_origem,
        ).pack(anchor="w")
        ttk.Radiobutton(
            origem,
            text="B. Etapa pré-definida já cadastrada",
            value=ORIGEM_ETAPA,
            variable=self.var_origem,
            command=self._ao_mudar_origem,
        ).pack(anchor="w")

        self.frame_etapa = tk.Frame(origem, bg=fundo)
        linha_etapa = tk.Frame(self.frame_etapa, bg=fundo)
        linha_etapa.pack(fill="x")
        self.var_etapa_nome = tk.StringVar(value="Nenhuma etapa selecionada")
        tk.Label(
            linha_etapa,
            textvariable=self.var_etapa_nome,
            bg=fundo,
            fg=cores.texto,
            anchor="w",
        ).pack(side="left", fill="x", expand=True)
        criar_botao_ttk_com_icone(
            linha_etapa,
            texto="Escolher etapa",
            nome_icone="search-outline",
            command=self._escolher_etapa,
            estilo=estilos.compacto,
            cor_icone=estilos.icone,
            refs=self._refs_icones,
        ).pack(side="left", padx=(8, 0))
        tk.Label(
            self.frame_etapa,
            text="Quantitativo da etapa:",
            bg=fundo,
            fg=cores.texto,
            anchor="w",
        ).pack(fill="x", pady=(8, 2))
        self.var_tipo_etapa = tk.StringVar()
        self.campo_tipo_etapa = CampoListaPesquisavel(
            self.frame_etapa,
            textvariable=self.var_tipo_etapa,
            on_escolher=lambda _v: self._aplicar_reparo(),
            largura_minima_lista=420,
            altura_lista=10,
            bg=fundo,
        )
        self.campo_tipo_etapa.definir_opcoes(_rotulos_tipo_calculo())
        self.campo_tipo_etapa.pack(fill="x")
        valores_tipo = _rotulos_tipo_calculo()
        self.var_tipo_etapa.set(valores_tipo[-1] if valores_tipo else "")

        colunas = ("codigo", "unidade", "tipo", "coef")
        self.tree = ttk.Treeview(direita, columns=colunas, show="headings", height=10)
        self.tree.heading("codigo", text="Código")
        self.tree.heading("unidade", text="Unid.")
        self.tree.heading("tipo", text="Cálculo")
        self.tree.heading("coef", text="Coef.")
        self.tree.column("codigo", width=100, anchor="center")
        self.tree.column("unidade", width=60, anchor="center")
        self.tree.column("tipo", width=280, anchor="w")
        self.tree.column("coef", width=70, anchor="e")
        self.tree.grid(row=3, column=0, sticky="nsew")
        self.tree.bind("<Double-1>", lambda _e: self._editar_item())

        botoes_itens = tk.Frame(direita, bg=fundo)
        botoes_itens.grid(row=4, column=0, sticky="e", pady=(8, 0))
        criar_botao_ttk_com_icone(
            botoes_itens,
            texto="Adicionar item SINAPI",
            nome_icone="add-circle-outline",
            command=self._adicionar_item,
            estilo=estilos.compacto_adicionar,
            cor_icone=estilos.icone_adicionar,
            refs=self._refs_icones,
        ).pack(side="left")
        criar_botao_ttk_com_icone(
            botoes_itens,
            texto="Editar",
            nome_icone="pencil",
            command=self._editar_item,
            estilo=estilos.compacto_editar,
            cor_icone=estilos.icone_editar,
            refs=self._refs_icones,
        ).pack(side="left", padx=4)
        criar_botao_ttk_com_icone(
            botoes_itens,
            texto="Remover item",
            nome_icone="remove-circle-outline",
            command=self._remover_item,
            estilo=estilos.compacto_excluir,
            cor_icone=estilos.icone_excluir,
            refs=self._refs_icones,
        ).pack(side="left")

        rodape = tk.Frame(painel, bg=fundo)
        rodape.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        criar_botao_fechar(
            rodape, command=self.destroy, texto="Fechar sem salvar"
        ).pack(side="right", padx=(6, 0))
        criar_botao_ttk_com_icone(
            rodape,
            texto="Salvar no JSON",
            nome_icone="save-outline",
            command=self._salvar,
            estilo=estilos.salvar,
            cor_icone=estilos.icone_salvar,
            refs=self._refs_icones,
        ).pack(side="right")

        self.bind("<Escape>", lambda _e: self.destroy())
        self._popular_lista()
        self.update_idletasks()
        centralizar_janela(self, parent)

    def _anomalias(self) -> dict:
        return self._dados.setdefault("anomalias", {})

    def _reparos_atuais(self) -> list[dict]:
        if not self._nome_atual:
            return []
        return list(self._anomalias().get(self._nome_atual, {}).get("reparos") or [])

    def _reparo_atual(self) -> dict | None:
        for reparo in self._reparos_atuais():
            if reparo.get("id") == self._reparo_atual_id:
                return reparo
        return None

    def _popular_lista(self, selecionar: str | None = None):
        self.lista.delete(0, "end")
        nomes = list(self._anomalias().keys())
        for nome in nomes:
            self.lista.insert("end", nome)
        if not nomes:
            self._nome_atual = None
            self._reparo_atual_id = None
            self._redesenhar_reparo(None)
            return
        alvo = selecionar if selecionar in nomes else nomes[0]
        indice = nomes.index(alvo)
        self.lista.selection_clear(0, "end")
        self.lista.selection_set(indice)
        self.lista.see(indice)
        self._carregar_anomalia(alvo)

    def _ao_selecionar(self, _event=None):
        self._aplicar_reparo()
        selecao = self.lista.curselection()
        if not selecao:
            return
        self._carregar_anomalia(self.lista.get(selecao[0]))

    def _carregar_anomalia(self, nome: str):
        dados = self._anomalias().get(nome) or nova_anomalia(nome)
        self._anomalias()[nome] = dados
        self._nome_atual = nome
        reparos = dados.get("reparos") or []
        self._reparo_atual_id = reparos[0]["id"] if reparos else None
        self._atualizar_combo_reparos()
        self._redesenhar_reparo(self._reparo_atual())

    def _atualizar_combo_reparos(self):
        reparos = self._reparos_atuais()
        nomes = [r.get("nome") or "Reparo" for r in reparos]
        self.combo_reparo["values"] = nomes
        atual = 0
        for i, reparo in enumerate(reparos):
            if reparo.get("id") == self._reparo_atual_id:
                atual = i
                break
        if nomes:
            self.combo_reparo.current(atual)
            self._reparo_atual_id = reparos[atual]["id"]
        else:
            self.combo_reparo.set("")

    def _ao_trocar_reparo(self, _event=None):
        self._aplicar_reparo()
        indice = self.combo_reparo.current()
        reparos = self._reparos_atuais()
        if 0 <= indice < len(reparos):
            self._reparo_atual_id = reparos[indice]["id"]
            self._redesenhar_reparo(reparos[indice])

    def _redesenhar_reparo(self, reparo):
        self._carregando = True
        try:
            self.tree.delete(*self.tree.get_children())
            if not reparo:
                self.var_origem.set(ORIGEM_ITENS)
                self.var_etapa_nome.set("Nenhuma etapa selecionada")
                self._mostrar_origem()
                return
            self.var_origem.set(reparo.get("origem") or ORIGEM_ITENS)
            nome_etapa = reparo.get("etapa_nome") or "Nenhuma etapa selecionada"
            self.var_etapa_nome.set(nome_etapa)
            tipo = reparo.get("tipo_calculo_etapa") or "fixo"
            self.var_tipo_etapa.set(f"{tipo} — {ROTULOS_TIPO_CALCULO.get(tipo, tipo)}")
            for item in reparo.get("itens") or []:
                tipo_i = str(item.get("tipo_calculo", ""))
                self.tree.insert(
                    "",
                    "end",
                    iid=item.get("id"),
                    values=(
                        item.get("codigo_sinapi", ""),
                        item.get("unidade", ""),
                        ROTULOS_TIPO_CALCULO.get(tipo_i, tipo_i),
                        str(item.get("coeficiente", "")).replace(".", ","),
                    ),
                )
            self._mostrar_origem()
        finally:
            self._carregando = False

    def _mostrar_origem(self):
        if self.var_origem.get() == ORIGEM_ETAPA:
            self.frame_etapa.pack(fill="x", pady=(6, 0))
        else:
            self.frame_etapa.pack_forget()

    def _ao_mudar_origem(self):
        self._mostrar_origem()
        self._aplicar_reparo()

    def _aplicar_reparo(self):
        if self._carregando:
            return
        reparo = self._reparo_atual()
        if not reparo or not self._nome_atual:
            return
        reparo["origem"] = self.var_origem.get()
        tipo = _chave_tipo_calculo(self.var_tipo_etapa.get())
        reparo["tipo_calculo_etapa"] = tipo
        for item in self._anomalias()[self._nome_atual]["reparos"]:
            if item.get("id") == reparo["id"]:
                item.update(reparo)
                break

    def _novo_reparo(self):
        if not self._nome_atual:
            return
        nome = perguntar_texto(self, "Novo reparo", "Nome do reparo (ex.: Piso cerâmico):")
        if not nome or not nome.strip():
            return
        reparo = novo_reparo(nome=nome.strip())
        self._anomalias()[self._nome_atual].setdefault("reparos", []).append(reparo)
        self._reparo_atual_id = reparo["id"]
        self._atualizar_combo_reparos()
        self._redesenhar_reparo(reparo)

    def _excluir_reparo(self):
        if not self._nome_atual:
            return
        reparos = self._reparos_atuais()
        if len(reparos) <= 1:
            messagebox.showinfo(
                "Reparo",
                "A anomalia precisa de pelo menos um reparo.",
                parent=self,
            )
            return
        self._anomalias()[self._nome_atual]["reparos"] = [
            r for r in reparos if r.get("id") != self._reparo_atual_id
        ]
        self._reparo_atual_id = self._anomalias()[self._nome_atual]["reparos"][0]["id"]
        self._atualizar_combo_reparos()
        self._redesenhar_reparo(self._reparo_atual())

    def _escolher_etapa(self):
        def ao_escolher(etapa):
            reparo = self._reparo_atual()
            if not reparo:
                return
            reparo["etapa_predefinida_id"] = etapa.get("id") or ""
            reparo["etapa_nome"] = etapa.get("nome") or ""
            reparo["origem"] = ORIGEM_ETAPA
            self.var_origem.set(ORIGEM_ETAPA)
            self.var_etapa_nome.set(reparo["etapa_nome"])
            self._aplicar_reparo()
            self._mostrar_origem()

        DialogoSelecionarEtapaPredefinida(self, ao_escolher)

    def _adicionar_item(self):
        reparo = self._reparo_atual()
        if not reparo:
            return
        if reparo.get("origem") == ORIGEM_ETAPA:
            if not messagebox.askyesno(
                "Item SINAPI",
                "Este reparo está como etapa pré-definida. "
                "Trocar para itens SINAPI?",
                parent=self,
            ):
                return
            reparo["origem"] = ORIGEM_ITENS
            self.var_origem.set(ORIGEM_ITENS)
            self._mostrar_origem()

        def ao_confirmar(item):
            reparo.setdefault("itens", []).append(item)
            self._redesenhar_reparo(reparo)

        DialogoItemSinapiAreaComum(self, on_confirmar=ao_confirmar, ctx=self.ctx)

    def _editar_item(self):
        reparo = self._reparo_atual()
        if not reparo:
            return
        selecao = self.tree.selection()
        if not selecao:
            return
        item_id = selecao[0]
        atual = next((i for i in reparo.get("itens") or [] if i.get("id") == item_id), None)
        if atual is None:
            return

        def ao_confirmar(item):
            item["id"] = item_id
            for i, existente in enumerate(reparo["itens"]):
                if existente.get("id") == item_id:
                    reparo["itens"][i] = item
                    break
            self._redesenhar_reparo(reparo)

        DialogoItemSinapiAreaComum(self, item=atual, on_confirmar=ao_confirmar, ctx=self.ctx)

    def _remover_item(self):
        reparo = self._reparo_atual()
        if not reparo:
            return
        selecao = self.tree.selection()
        if not selecao:
            return
        item_id = selecao[0]
        reparo["itens"] = [i for i in reparo.get("itens") or [] if i.get("id") != item_id]
        self._redesenhar_reparo(reparo)

    def _nova(self):
        self._aplicar_reparo()
        nome = perguntar_texto(self, "Nova anomalia", "Nome da anomalia:")
        if not nome or not str(nome).strip():
            return
        nome = str(nome).strip()
        if nome in self._anomalias():
            messagebox.showwarning("Anomalia", "Já existe uma anomalia com esse nome.", parent=self)
            return
        self._anomalias()[nome] = nova_anomalia(nome)
        self._popular_lista(selecionar=nome)

    def _renomear(self):
        if not self._nome_atual:
            return
        novo = perguntar_texto(
            self, "Renomear", "Novo nome da anomalia:", valor_inicial=self._nome_atual
        )
        if not novo or not str(novo).strip():
            return
        novo = str(novo).strip()
        if novo == self._nome_atual:
            return
        if novo in self._anomalias():
            messagebox.showwarning("Anomalia", "Já existe uma anomalia com esse nome.", parent=self)
            return
        self._anomalias()[novo] = self._anomalias().pop(self._nome_atual)
        self._popular_lista(selecionar=novo)

    def _excluir(self):
        if not self._nome_atual:
            return
        if not messagebox.askyesno(
            "Excluir",
            f"Excluir a anomalia '{self._nome_atual}'?",
            parent=self,
        ):
            return
        self._anomalias().pop(self._nome_atual, None)
        self._popular_lista()

    def _salvar(self):
        self._aplicar_reparo()
        try:
            salvar_catalogo(self._dados)
        except OSError as exc:
            messagebox.showerror("Salvar", f"Não foi possível gravar:\n{exc}", parent=self)
            return
        if self.on_salvo:
            self.on_salvo()
        messagebox.showinfo("Anomalias", "Catálogo salvo.", parent=self)
        self.destroy()
