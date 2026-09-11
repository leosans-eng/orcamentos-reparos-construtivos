import os
import tkinter as tk
from tkinter import messagebox, ttk

from core.sinapi_busca import (
    TIPO_TODOS,
    VALORES_FILTRO_TIPO,
    nome_tipo_sinapi,
    obter_unidades_sinapi,
    pesquisar_sinapi,
    tipo_sinapi_para_filtro,
)
from core.sinapi_loader import obter_xlsx_sinapi_referencia_mais_recente
from ui.icones import carregar_png_icone, criar_label_icone
from ui.temas import cores_tema
from ui.widgets import (
    PLACEHOLDER_ESTADO,
    criar_barra_modulo,
    estado_do_combo,
    formatar_moeda_br,
    valores_combo_estado,
)

# Debounce proposital (ms): evita rebuscar a cada tecla enquanto o usuário digita.
DEBOUNCE_BUSCA_MS = 300
UNIDADE_TODAS = "Todas"


class ConsultaSinapiFrame(tk.Frame):
    def __init__(self, parent, ctx, on_voltar):
        cores = cores_tema(parent)
        super().__init__(parent, bg=cores.fundo)
        self._cores = cores
        self.ctx = ctx
        self.on_voltar = on_voltar
        self._job_busca = None
        self._ultima_largura_wrap = 0
        self._refs_icones = []
        self._montar()
        ctx.registrar_callback_sinapi(self._ao_atualizar_sinapi)

    def _montar(self):
        cores = self._cores
        fundo = cores.fundo
        self._icone_excel = None
        self.label_referencia = criar_barra_modulo(
            self,
            "Consulta SINAPI",
            self.on_voltar,
            texto_referencia=self._texto_referencia(),
            montar_acoes_antes_referencia=self._montar_botao_sinapi_cabecalho,
        )

        painel_busca = tk.LabelFrame(
            self,
            text="Pesquisar insumo ou composição",
            bg=fundo,
            fg=cores.texto,
            padx=10,
            pady=8,
        )
        painel_busca.pack(fill="x", padx=16, pady=(0, 8))

        linha_filtros = tk.Frame(painel_busca, bg=fundo)
        linha_filtros.pack(fill="x")

        tk.Label(linha_filtros, text="Estado:", bg=fundo, fg=cores.texto).grid(
            row=0, column=0, padx=(4, 6), pady=4, sticky="w"
        )

        estados = self.ctx.obter_estados()
        self.combo_estado = ttk.Combobox(
            linha_filtros,
            values=valores_combo_estado(estados),
            width=14,
            state="readonly",
        )
        self.combo_estado.grid(row=0, column=1, padx=4, pady=4, sticky="w")
        self.combo_estado.set(PLACEHOLDER_ESTADO)

        tk.Label(linha_filtros, text="Unidade:", bg=fundo, fg=cores.texto).grid(
            row=0, column=2, padx=(16, 6), pady=4, sticky="w"
        )

        self.combo_unidade = ttk.Combobox(
            linha_filtros,
            values=[UNIDADE_TODAS],
            width=10,
            state="readonly",
        )
        self.combo_unidade.grid(row=0, column=3, padx=4, pady=4, sticky="w")
        self.combo_unidade.set(UNIDADE_TODAS)

        tk.Label(linha_filtros, text="Tipo (I/C):", bg=fundo, fg=cores.texto).grid(
            row=0, column=4, padx=(16, 6), pady=4, sticky="w"
        )

        self.combo_tipo = ttk.Combobox(
            linha_filtros,
            values=list(VALORES_FILTRO_TIPO),
            width=12,
            state="readonly",
        )
        self.combo_tipo.grid(row=0, column=5, padx=4, pady=4, sticky="w")
        self.combo_tipo.set(TIPO_TODOS)

        criar_label_icone(
            linha_filtros,
            "funnel-outline",
            texto="Pesquisar:",
            bg=fundo,
            fg=cores.texto_suave,
            cor=cores.titulo,
            refs=self._refs_icones,
        ).grid(row=0, column=6, padx=(16, 6), pady=4, sticky="w")

        self.var_busca = tk.StringVar()
        self.entrada_busca = ttk.Entry(linha_filtros, textvariable=self.var_busca, width=40)
        self.entrada_busca.grid(row=0, column=7, padx=4, pady=4, sticky="ew")
        linha_filtros.columnconfigure(7, weight=1)

        self._atualizar_unidades()

        self.label_dica = tk.Label(
            painel_busca,
            text=(
                "Digite palavras do insumo/composição ou o código SINAPI. "
                "A unidade lista só as opções compatíveis com a busca atual. "
                "Acentos são opcionais e não é preciso digitar todas as palavras — ex.: “ceramica piso” ou “reboco parede”."
            ),
            font=("Arial", 8),
            fg=cores.texto_suave,
            bg=fundo,
            justify="left",
        )
        self.label_dica.pack(fill="x", anchor="w", padx=4, pady=(4, 0))

        self.label_status = tk.Label(
            self,
            text="Selecione o estado e digite para pesquisar.",
            font=("Arial", 9),
            fg=cores.texto_suave,
            bg=fundo,
            anchor="w",
        )
        self.label_status.pack(fill="x", padx=18, pady=(0, 4))

        painel_resultados = tk.LabelFrame(
            self,
            text="Resultados",
            bg=fundo,
            fg=cores.texto,
            padx=8,
            pady=6,
        )
        painel_resultados.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        colunas = ("codigo", "tipo_ic", "descricao", "unidade", "custo")
        self.tree = ttk.Treeview(
            painel_resultados,
            columns=colunas,
            show="headings",
            height=14,
        )
        self.tree.heading("codigo", text="Código")
        self.tree.heading("tipo_ic", text="I/C")
        self.tree.heading("descricao", text="Descrição")
        self.tree.heading("unidade", text="Unid.")
        self.tree.heading("custo", text="Custo unit. (R$)")

        self.tree.column("codigo", width=60, minwidth=50, stretch=False, anchor="center")
        self.tree.column("tipo_ic", width=40, minwidth=36, stretch=False, anchor="center")
        self.tree.column("descricao", width=500, minwidth=200, stretch=True)
        self.tree.column("unidade", width=60, minwidth=50, stretch=False, anchor="center")
        self.tree.column("custo", width=110, minwidth=90, stretch=False, anchor="e")

        scroll_y = ttk.Scrollbar(painel_resultados, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scroll_y.pack(side="right", fill="y")

        barra = cores.fundo_barra
        painel_detalhe = tk.Frame(
            self,
            bg=barra,
            highlightbackground=cores.borda_suave,
            highlightthickness=1,
        )
        painel_detalhe.pack(fill="x", padx=16, pady=(0, 10))

        self.label_detalhe = tk.Label(
            painel_detalhe,
            text="Selecione um item na lista para ver os detalhes.",
            font=("Arial", 9),
            fg=cores.texto,
            bg=barra,
            justify="left",
            anchor="w",
            padx=10,
            pady=8,
        )
        self.label_detalhe.pack(fill="x")

        self.bind("<Configure>", self._ao_redimensionar)
        self.var_busca.trace_add("write", self._ao_digitar)
        self.combo_estado.bind("<<ComboboxSelected>>", self._ao_mudar_estado)
        self.combo_unidade.bind("<<ComboboxSelected>>", lambda _e: self._executar_busca())
        self.combo_tipo.bind("<<ComboboxSelected>>", lambda _e: self._executar_busca())
        self.tree.bind("<<TreeviewSelect>>", self._ao_selecionar_item)

        if self.ctx.sinapi.empty:
            self.label_status.config(
                text="Base SINAPI indisponível. Aguarde a atualização ou verifique sinapi/sinapi_processado.",
                fg=cores.perigo,
            )

    def _texto_referencia(self):
        ref = self.ctx.sinapi_referencia_rotulo
        if ref == "BASE AUSENTE":
            return "Base não carregada"
        return f"Referência SINAPI: {ref}"

    def _cor_status(self, mensagem, *, vazio=False):
        cores = self._cores
        texto = (mensagem or "").lower()
        if "indisponível" in texto or "nenhum item" in texto:
            return cores.perigo
        if vazio:
            return "#ffb74d" if cores.escuro else "#a67c00"
        return cores.texto_suave

    def _montar_botao_sinapi_cabecalho(self, parent):
        cores = self._cores
        kwargs_botao = {
            "text": "Abrir SINAPI Completa",
            "command": self._abrir_sinapi_real,
            "bg": cores.fundo,
            "activebackground": cores.fundo_hover,
            "relief": "flat",
            "bd": 0,
            "padx": 4,
            "pady": 0,
            "cursor": "hand2",
            "font": ("Arial", 9),
            "fg": cores.texto,
            "activeforeground": cores.texto,
            "highlightthickness": 0,
        }
        try:
            self._icone_excel = carregar_png_icone(self, "excel24.png")
            kwargs_botao["image"] = self._icone_excel
            kwargs_botao["compound"] = "left"
        except (FileNotFoundError, OSError, tk.TclError):
            pass
        tk.Button(parent, **kwargs_botao).pack(side="right", padx=(0, 10))

    def _abrir_sinapi_real(self):
        caminho = obter_xlsx_sinapi_referencia_mais_recente()
        if caminho is None or not caminho.is_file():
            messagebox.showwarning(
                "SINAPI Real",
                (
                    "Nenhum arquivo Excel da SINAPI foi encontrado em "
                    "sinapi/sinapi_referencia.\n\n"
                    "Aguarde a atualização automática ou verifique a pasta."
                ),
                parent=self.winfo_toplevel(),
            )
            return
        try:
            os.startfile(str(caminho))
        except OSError as exc:
            messagebox.showerror(
                "SINAPI Real",
                f"Não foi possível abrir o arquivo:\n{caminho}\n\n{exc}",
                parent=self.winfo_toplevel(),
            )

    def _ao_redimensionar(self, event=None):
        if event is not None and event.widget is not self:
            return
        self.ajustar_layout()

    def ajustar_layout(self):
        self.update_idletasks()
        largura = self.winfo_width()
        if largura < 200:
            return
        if largura == self._ultima_largura_wrap:
            return
        self._ultima_largura_wrap = largura
        # Margem horizontal dos painéis (padx 16) + padding interno
        wrap = max(280, largura - 56)
        self.label_dica.config(wraplength=wrap)
        self.label_detalhe.config(wraplength=wrap)

    def _unidade_selecionada(self):
        valor = self.combo_unidade.get().strip()
        return None if not valor or valor == UNIDADE_TODAS else valor

    def _tipo_selecionado(self):
        return tipo_sinapi_para_filtro(self.combo_tipo.get())

    def _aplicar_unidades(self, unidades):
        valores = [UNIDADE_TODAS] + list(unidades)
        atual = self.combo_unidade.get().strip()
        self.combo_unidade["values"] = valores
        if atual in valores:
            self.combo_unidade.set(atual)
        else:
            self.combo_unidade.set(UNIDADE_TODAS)

    def _atualizar_unidades(self, consulta=None):
        estado = estado_do_combo(self.combo_estado.get())
        if consulta is None:
            consulta = self.var_busca.get() if hasattr(self, "var_busca") else ""
        texto = consulta
        if texto and texto.strip():
            unidades = obter_unidades_sinapi(self.ctx.sinapi, estado or None, texto)
        else:
            unidades = obter_unidades_sinapi(self.ctx.sinapi, estado or None)
        self._aplicar_unidades(unidades)

    def _ao_mudar_estado(self, _event=None):
        self._atualizar_unidades()
        self._executar_busca()

    def _ao_atualizar_sinapi(self):
        estados = self.ctx.obter_estados()
        self.combo_estado["values"] = valores_combo_estado(estados)
        if self.combo_estado.get() not in self.combo_estado["values"]:
            self.combo_estado.set(PLACEHOLDER_ESTADO)
        self._atualizar_unidades()
        if self.label_referencia is not None:
            self.label_referencia.config(text=self._texto_referencia())
        if self.var_busca.get().strip():
            self._executar_busca()

    def _ao_digitar(self, *_args):
        if self._job_busca is not None:
            self.after_cancel(self._job_busca)
        self._job_busca = self.after(DEBOUNCE_BUSCA_MS, self._executar_busca)

    def _executar_busca(self):
        if self._job_busca is not None:
            self.after_cancel(self._job_busca)
            self._job_busca = None

        estado = estado_do_combo(self.combo_estado.get())
        consulta = self.var_busca.get()
        unidade = self._unidade_selecionada()

        if not estado:
            self.label_status.config(
                text="Selecione um estado antes de pesquisar.",
                fg=self._cores.perigo,
            )
            return

        resultados, mensagem, unidades = pesquisar_sinapi(
            self.ctx.sinapi,
            estado,
            consulta,
            unidade=unidade,
            tipo=self._tipo_selecionado(),
        )
        self._aplicar_unidades(unidades)
        self._preencher_resultados(resultados)
        self.label_status.config(text=mensagem, fg=self._cor_status(mensagem, vazio=resultados.empty))

    def _preencher_resultados(self, df):
        self.tree.delete(*self.tree.get_children())
        for _, linha in df.iterrows():
            custo = linha.get("custo", 0)
            custo_fmt = formatar_moeda_br(custo)

            self.tree.insert(
                "",
                "end",
                values=(
                    str(linha.get("codigo", "")),
                    str(linha.get("tipo", "")).strip().upper()[:1] or "—",
                    str(linha.get("descricao", "")),
                    str(linha.get("unidade", "")),
                    custo_fmt,
                ),
            )
        self.label_detalhe.config(text="Selecione um item na lista para ver os detalhes.")

    def _ao_selecionar_item(self, _event=None):
        selecionado = self.tree.selection()
        if not selecionado:
            return
        valores = self.tree.item(selecionado[0], "values")
        if len(valores) < 5:
            return
        codigo, tipo_ic, descricao, unidade, custo = valores
        estado = estado_do_combo(self.combo_estado.get())
        tipo_rotulo = nome_tipo_sinapi(tipo_ic) or tipo_ic
        self.label_detalhe.config(
            text=(
                f"Código: {codigo}  ·  {tipo_rotulo}  ·  Estado: {estado}  ·  "
                f"Unidade: {unidade}  ·  Custo: {custo}\n{descricao}"
            ),
        )

    def focar(self):
        self.entrada_busca.focus_set()
        self.after_idle(self.ajustar_layout)
