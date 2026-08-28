"""Janela para cadastrar e editar anomalias de vicios_construtivos.json."""

from __future__ import annotations

import tkinter as tk
from copy import deepcopy
from tkinter import messagebox, ttk

from core.app_state import NOMES_GRUPOS_REPARO
from core.vicios_storage import (
    COMODOS_AREA_PRIVATIVA,
    ROTULOS_TIPO_CALCULO,
    TIPOS_CALCULO,
    UNIDADES_COMUNS,
    nova_anomalia,
    nova_etapa,
    salvar_vicios,
)
from ui.icones import criar_botao_ttk_com_icone
from ui.widgets import (
    aplicar_icone_janela,
    centralizar_janela,
    criar_botao_fechar,
    focar_entrada_apos_exibir,
    perguntar_texto,
    preparar_toplevel,
)


def _float_br(texto: str) -> float:
    return float(str(texto).strip().replace(",", "."))


class DialogoEtapaAnomalia(tk.Toplevel):
    def __init__(self, parent, etapa=None, on_confirmar=None, ctx=None):
        super().__init__(parent)
        preparar_toplevel(self)
        self.on_confirmar = on_confirmar
        self.ctx = ctx
        self._refs_icones: list = []
        self.title("Etapa da anomalia" if etapa else "Nova etapa")
        aplicar_icone_janela(self)
        self.configure(bg="#ececec")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        etapa = etapa or {}
        painel = tk.Frame(self, bg="#ececec", padx=16, pady=14)
        painel.pack(fill="both", expand=True)

        self.var_codigo = tk.StringVar(value=str(etapa.get("codigo_sinapi", "")))
        self.var_unidade = tk.StringVar(value=str(etapa.get("unidade", "m²")))
        self.var_coef = tk.StringVar(value=str(etapa.get("coeficiente", 1)).replace(".", ","))
        self.var_grupo = tk.StringVar(value=str(etapa.get("grupo_planilha", "")))

        linha_codigo = tk.Frame(painel, bg="#ececec")
        linha_codigo.pack(fill="x", pady=3)
        tk.Label(linha_codigo, text="Código SINAPI:", width=22, anchor="w", bg="#ececec").pack(
            side="left"
        )
        entrada_codigo = ttk.Entry(linha_codigo, textvariable=self.var_codigo, width=18)
        entrada_codigo.pack(side="left")
        if ctx is not None:
            criar_botao_ttk_com_icone(
                linha_codigo,
                texto="Buscar",
                nome_icone="search-outline",
                command=self._buscar_sinapi,
                refs=self._refs_icones,
            ).pack(side="left", padx=(8, 0))

        self._campo(painel, "Unidade:", self.var_unidade, valores=UNIDADES_COMUNS)
        valores_tipo = [f"{k} — {ROTULOS_TIPO_CALCULO.get(k, k)}" for k in TIPOS_CALCULO]
        atual_tipo = str(etapa.get("tipo_calculo", "area_piso"))
        rotulo_tipo = f"{atual_tipo} — {ROTULOS_TIPO_CALCULO.get(atual_tipo, atual_tipo)}"
        self.var_tipo_exibicao = tk.StringVar(
            value=rotulo_tipo if rotulo_tipo in valores_tipo else valores_tipo[0]
        )
        self._campo(painel, "Tipo de cálculo:", self.var_tipo_exibicao, valores=valores_tipo)
        self._campo(painel, "Coeficiente:", self.var_coef)
        self._campo(
            painel,
            "Grupo da planilha:",
            self.var_grupo,
            valores=["", "repintura"],
        )

        botoes = ttk.Frame(painel)
        botoes.pack(fill="x", pady=(12, 0))
        ttk.Button(botoes, text="Cancelar", command=self.destroy, style="Delete.TButton").pack(
            side="right", padx=(6, 0)
        )
        ttk.Button(botoes, text="Salvar etapa", command=self._confirmar, style="Add.TButton").pack(
            side="right"
        )

        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        centralizar_janela(self, parent)
        focar_entrada_apos_exibir(entrada_codigo)

    def _campo(self, parent, rotulo, var, valores=None):
        linha = tk.Frame(parent, bg="#ececec")
        linha.pack(fill="x", pady=3)
        tk.Label(linha, text=rotulo, width=22, anchor="w", bg="#ececec").pack(side="left")
        if valores is None:
            ttk.Entry(linha, textvariable=var, width=36).pack(side="left", fill="x", expand=True)
            return
        combo = ttk.Combobox(linha, textvariable=var, values=list(valores), width=34)
        combo.pack(side="left", fill="x", expand=True)

    def _buscar_sinapi(self):
        from ui.orcamento_customizado import DialogoBuscaSinapi

        estado = ""
        if self.ctx is not None:
            estados = self.ctx.obter_estados()
            estado = estados[0] if estados else ""

        def ao_escolher(codigo, descricao, unidade, _custo, _quantidade, _estado, _tipo_ic=""):
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
            messagebox.showwarning("Etapa", "Informe o código SINAPI.", parent=self)
            return
        try:
            coeficiente = _float_br(self.var_coef.get())
        except ValueError:
            messagebox.showwarning("Etapa", "Coeficiente inválido.", parent=self)
            return
        tipo_exib = self.var_tipo_exibicao.get().strip()
        tipo = tipo_exib.split(" — ", 1)[0].strip() or "area_piso"
        if tipo not in TIPOS_CALCULO:
            tipo = "area_piso"
        etapa = nova_etapa(
            codigo_sinapi=codigo,
            unidade=self.var_unidade.get().strip() or "un",
            tipo_calculo=tipo,
            coeficiente=coeficiente,
            grupo_planilha=self.var_grupo.get().strip(),
        )
        if self.on_confirmar:
            self.on_confirmar(etapa)
        self.destroy()


class DialogoConfigAnomalias(tk.Toplevel):
    def __init__(self, parent, ctx, on_salvo=None):
        super().__init__(parent)
        preparar_toplevel(self)
        self.ctx = ctx
        self.on_salvo = on_salvo
        self._refs_icones: list = []
        self._nome_atual: str | None = None
        self._carregando = False
        self._dados = deepcopy(ctx.dados_json)
        self._dados.setdefault("anomalias", {})

        self.title("Configurar anomalias")
        aplicar_icone_janela(self)
        self.configure(bg="#ececec")
        self.transient(parent)
        self.grab_set()
        self.geometry("980x640")
        self.minsize(820, 540)

        painel = tk.Frame(self, bg="#ececec", padx=14, pady=12)
        painel.pack(fill="both", expand=True)
        painel.columnconfigure(1, weight=1)
        painel.rowconfigure(1, weight=1)

        tk.Label(
            painel,
            text="Anomalias cadastradas",
            font=("Arial", 12, "bold"),
            fg="#006699",
            bg="#ececec",
            anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        esquerda = tk.Frame(painel, bg="#ececec")
        esquerda.grid(row=1, column=0, sticky="ns", padx=(0, 10))
        esquerda.rowconfigure(0, weight=1)

        self.lista = tk.Listbox(esquerda, width=42, height=22, exportselection=False)
        self.lista.grid(row=0, column=0, sticky="ns")
        scroll_lista = ttk.Scrollbar(esquerda, orient="vertical", command=self.lista.yview)
        scroll_lista.grid(row=0, column=1, sticky="ns")
        self.lista.configure(yscrollcommand=scroll_lista.set)
        self.lista.bind("<<ListboxSelect>>", self._ao_selecionar)

        botoes_lista = tk.Frame(esquerda, bg="#ececec")
        botoes_lista.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        criar_botao_ttk_com_icone(
            botoes_lista,
            texto="Nova",
            nome_icone="add-circle-outline",
            command=self._nova,
            estilo="Add.Compact.TButton",
            refs=self._refs_icones,
        ).pack(side="left")
        criar_botao_ttk_com_icone(
            botoes_lista,
            texto="Renomear",
            nome_icone="pencil",
            command=self._renomear,
            refs=self._refs_icones,
        ).pack(side="left", padx=4)
        criar_botao_ttk_com_icone(
            botoes_lista,
            texto="Excluir",
            nome_icone="trash-outline",
            command=self._excluir,
            estilo="Delete.Compact.TButton",
            refs=self._refs_icones,
        ).pack(side="left")

        direita = tk.LabelFrame(painel, text="Detalhes", bg="#ececec", padx=10, pady=8)
        direita.grid(row=1, column=1, sticky="nsew")
        direita.columnconfigure(1, weight=1)
        direita.rowconfigure(4, weight=1)

        tk.Label(direita, text="Nome:", bg="#ececec").grid(row=0, column=0, sticky="w", pady=3)
        self.var_nome = tk.StringVar()
        ttk.Entry(direita, textvariable=self.var_nome, state="readonly").grid(
            row=0, column=1, sticky="ew", pady=3
        )

        tk.Label(direita, text="Grupo de reparo:", bg="#ececec").grid(
            row=1, column=0, sticky="nw", pady=3
        )
        grupos = sorted(set(NOMES_GRUPOS_REPARO.keys()) | {"repintura"})
        self.var_grupo = tk.StringVar()
        self.combo_grupo = ttk.Combobox(direita, textvariable=self.var_grupo, values=grupos)
        self.combo_grupo.grid(row=1, column=1, sticky="ew", pady=3)
        self.combo_grupo.bind("<<ComboboxSelected>>", lambda _e: self._aplicar_formulario())
        self.combo_grupo.bind("<FocusOut>", lambda _e: self._aplicar_formulario())

        frame_comodos = tk.LabelFrame(
            direita,
            text="Cômodos em que a anomalia pode ser aplicada",
            bg="#ececec",
            padx=6,
            pady=4,
        )
        frame_comodos.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 4))
        frame_comodos.columnconfigure(0, weight=1)
        frame_comodos.columnconfigure(1, weight=1)
        self._vars_comodos = {}
        for indice, comodo in enumerate(COMODOS_AREA_PRIVATIVA):
            var = tk.BooleanVar(value=True)
            chk = tk.Checkbutton(
                frame_comodos,
                text=comodo,
                variable=var,
                bg="#ececec",
                activebackground="#ececec",
                anchor="w",
                command=self._aplicar_formulario,
            )
            chk.grid(row=indice // 2, column=indice % 2, sticky="w", padx=(0, 8), pady=0)
            self._vars_comodos[comodo] = var

        tk.Label(direita, text="Etapas SINAPI", bg="#ececec", font=("Arial", 10, "bold")).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(10, 4)
        )

        colunas = ("codigo", "unidade", "tipo", "coef", "grupo")
        self.tree = ttk.Treeview(direita, columns=colunas, show="headings", height=8)
        self.tree.heading("codigo", text="Código")
        self.tree.heading("unidade", text="Unid.")
        self.tree.heading("tipo", text="Cálculo")
        self.tree.heading("coef", text="Coef.")
        self.tree.heading("grupo", text="Grupo planilha")
        self.tree.column("codigo", width=90, anchor="center")
        self.tree.column("unidade", width=60, anchor="center")
        self.tree.column("tipo", width=160, anchor="w")
        self.tree.column("coef", width=70, anchor="e")
        self.tree.column("grupo", width=110, anchor="w")
        self.tree.grid(row=4, column=0, columnspan=2, sticky="nsew")
        self.tree.bind("<Double-1>", lambda _e: self._editar_etapa())

        botoes_etapas = tk.Frame(direita, bg="#ececec")
        botoes_etapas.grid(row=5, column=0, columnspan=2, sticky="e", pady=(8, 0))
        criar_botao_ttk_com_icone(
            botoes_etapas,
            texto="Adicionar etapa",
            nome_icone="add-circle-outline",
            command=self._adicionar_etapa,
            estilo="Add.Compact.TButton",
            refs=self._refs_icones,
        ).pack(side="left")
        criar_botao_ttk_com_icone(
            botoes_etapas,
            texto="Editar",
            nome_icone="pencil",
            command=self._editar_etapa,
            refs=self._refs_icones,
        ).pack(side="left", padx=4)
        criar_botao_ttk_com_icone(
            botoes_etapas,
            texto="Remover etapa",
            nome_icone="remove-circle-outline",
            command=self._remover_etapa,
            estilo="Delete.Compact.TButton",
            refs=self._refs_icones,
        ).pack(side="left")

        rodape = tk.Frame(painel, bg="#ececec")
        rodape.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        criar_botao_fechar(
            rodape, command=self.destroy, texto="Fechar sem salvar"
        ).pack(side="right", padx=(6, 0))
        criar_botao_ttk_com_icone(
            rodape,
            texto="Salvar no JSON",
            nome_icone="save-outline",
            command=self._salvar,
            estilo="Save.TButton",
            refs=self._refs_icones,
        ).pack(side="right")

        self.bind("<Escape>", lambda _e: self.destroy())
        self._popular_lista()
        self.update_idletasks()
        centralizar_janela(self, parent)

    def _anomalias(self) -> dict:
        return self._dados.setdefault("anomalias", {})

    def _popular_lista(self, selecionar: str | None = None):
        self.lista.delete(0, "end")
        nomes = list(self._anomalias().keys())
        for nome in nomes:
            self.lista.insert("end", nome)
        if not nomes:
            self._nome_atual = None
            self.var_nome.set("")
            self.var_grupo.set("")
            self._definir_comodos_permitidos(list(COMODOS_AREA_PRIVATIVA))
            self._redesenhar_etapas([])
            return
        alvo = selecionar if selecionar in nomes else nomes[0]
        indice = nomes.index(alvo)
        self.lista.selection_clear(0, "end")
        self.lista.selection_set(indice)
        self.lista.see(indice)
        self._carregar_anomalia(alvo)

    def _ao_selecionar(self, _event=None):
        self._aplicar_formulario()
        selecao = self.lista.curselection()
        if not selecao:
            return
        self._carregar_anomalia(self.lista.get(selecao[0]))

    def _carregar_anomalia(self, nome: str):
        dados = self._anomalias().get(nome) or nova_anomalia(nome)
        self._carregando = True
        try:
            self._nome_atual = nome
            self.var_nome.set(nome)
            self.var_grupo.set(str(dados.get("grupo_reparo", "")))
            self._definir_comodos_permitidos(dados.get("comodos_permitidos"))
            self._redesenhar_etapas(dados.get("etapas") or [])
        finally:
            self._carregando = False

    def _redesenhar_etapas(self, etapas):
        self.tree.delete(*self.tree.get_children())
        for etapa in etapas:
            tipo = str(etapa.get("tipo_calculo", ""))
            self.tree.insert(
                "",
                "end",
                values=(
                    etapa.get("codigo_sinapi", ""),
                    etapa.get("unidade", ""),
                    ROTULOS_TIPO_CALCULO.get(tipo, tipo),
                    str(etapa.get("coeficiente", "")).replace(".", ","),
                    etapa.get("grupo_planilha", ""),
                ),
            )

    def _etapas_atuais(self) -> list[dict]:
        if not self._nome_atual:
            return []
        return list(self._anomalias().get(self._nome_atual, {}).get("etapas") or [])

    def _definir_comodos_permitidos(self, permitidos):
        if permitidos is None:
            nomes = set(COMODOS_AREA_PRIVATIVA)
        else:
            nomes = {str(item) for item in permitidos}
        for comodo, var in self._vars_comodos.items():
            var.set(comodo in nomes)

    def _comodos_marcados(self) -> list[str]:
        return [
            comodo
            for comodo, var in self._vars_comodos.items()
            if var.get()
        ]

    def _aplicar_formulario(self):
        if self._carregando:
            return
        if not self._nome_atual or self._nome_atual not in self._anomalias():
            return
        self._anomalias()[self._nome_atual]["grupo_reparo"] = self.var_grupo.get().strip()
        self._anomalias()[self._nome_atual]["comodos_permitidos"] = self._comodos_marcados()

    def _nova(self):
        self._aplicar_formulario()
        nome = perguntar_texto(self, "Nova anomalia", "Nome da anomalia:")
        if not nome:
            return
        nome = nome.strip()
        if not nome:
            return
        if nome in self._anomalias():
            messagebox.showwarning("Anomalia", "Já existe uma anomalia com esse nome.", parent=self)
            return
        self._anomalias()[nome] = nova_anomalia(nome)
        self._popular_lista(nome)

    def _renomear(self):
        self._aplicar_formulario()
        if not self._nome_atual:
            return
        nome = perguntar_texto(
            self,
            "Renomear anomalia",
            "Novo nome:",
            valor_inicial=self._nome_atual,
        )
        if not nome:
            return
        nome = nome.strip()
        if not nome or nome == self._nome_atual:
            return
        if nome in self._anomalias():
            messagebox.showwarning("Anomalia", "Já existe uma anomalia com esse nome.", parent=self)
            return
        antigo = self._nome_atual
        self._anomalias()[nome] = self._anomalias().pop(antigo)
        self._popular_lista(nome)

    def _excluir(self):
        self._aplicar_formulario()
        if not self._nome_atual:
            return
        if not messagebox.askyesno(
            "Excluir anomalia",
            f"Excluir a anomalia '{self._nome_atual}'?",
            parent=self,
        ):
            return
        self._anomalias().pop(self._nome_atual, None)
        self._nome_atual = None
        self._popular_lista()

    def _adicionar_etapa(self):
        if not self._nome_atual:
            messagebox.showinfo("Anomalia", "Selecione ou crie uma anomalia primeiro.", parent=self)
            return

        def ao_confirmar(etapa):
            etapas = self._etapas_atuais()
            etapas.append(etapa)
            self._anomalias()[self._nome_atual]["etapas"] = etapas
            self._redesenhar_etapas(etapas)

        DialogoEtapaAnomalia(self, on_confirmar=ao_confirmar, ctx=self.ctx)

    def _editar_etapa(self):
        if not self._nome_atual:
            return
        item = self.tree.selection()
        if not item:
            messagebox.showinfo("Etapa", "Selecione uma etapa para editar.", parent=self)
            return
        indice = self.tree.index(item[0])
        etapas = self._etapas_atuais()
        if indice >= len(etapas):
            return

        def ao_confirmar(etapa):
            atuais = self._etapas_atuais()
            atuais[indice] = etapa
            self._anomalias()[self._nome_atual]["etapas"] = atuais
            self._redesenhar_etapas(atuais)

        DialogoEtapaAnomalia(self, etapa=etapas[indice], on_confirmar=ao_confirmar, ctx=self.ctx)

    def _remover_etapa(self):
        if not self._nome_atual:
            return
        item = self.tree.selection()
        if not item:
            messagebox.showinfo("Etapa", "Selecione uma etapa para remover.", parent=self)
            return
        indice = self.tree.index(item[0])
        etapas = self._etapas_atuais()
        if 0 <= indice < len(etapas):
            del etapas[indice]
            self._anomalias()[self._nome_atual]["etapas"] = etapas
            self._redesenhar_etapas(etapas)

    def _salvar(self):
        self._aplicar_formulario()
        if self._nome_atual and not self._comodos_marcados():
            messagebox.showwarning(
                "Cômodos permitidos",
                "Selecione ao menos um cômodo em que a anomalia possa ser aplicada.",
                parent=self,
            )
            return
        try:
            caminho = salvar_vicios(self._dados)
            self.ctx.recarregar_dados_json()
        except OSError as exc:
            messagebox.showerror("Salvar anomalias", str(exc), parent=self)
            return
        if self.on_salvo:
            self.on_salvo()
        messagebox.showinfo(
            "Anomalias",
            f"Alterações salvas em:\n{caminho}",
            parent=self,
        )
