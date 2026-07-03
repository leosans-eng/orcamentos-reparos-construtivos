import tkinter as tk
from tkinter import messagebox, ttk

from core.composicoes_proprias_storage import listar as listar_composicoes_catalogo
from core.etapas_predefinidas import (
    TIPO_ITEM_PROPRIA,
    TIPO_ITEM_SINAPI,
    novo_item_propria_template,
    novo_item_sinapi_template,
)
from core.etapas_predefinidas_storage import (
    atualizar,
    carregar,
    criar,
    excluir,
    listar,
    obter_cache_catalogo,
    obter_por_id,
)
from ui.icones import (
    criar_botao_inserir_prominente,
    criar_botao_ttk_com_icone,
    criar_botao_ttk_so_icone,
)
from ui.orcamento_customizado import DialogoBuscaComposicaoPropria, DialogoBuscaSinapi
from ui.recarga_catalogo import RecarregadorCatalogo
from ui.widgets import (
    aplicar_icone_janela,
    centralizar_janela,
    confirmar_exclusao_com_espera,
    criar_barra_modulo,
    vincular_tooltip,
)


class DialogoNovaEtapaPredefinida(tk.Toplevel):
    def __init__(self, parent, on_confirmar):
        super().__init__(parent)
        self.on_confirmar = on_confirmar
        self.title("Nova etapa pré-definida")
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
        ).pack(fill="x", pady=(0, 8))

        self.var_nome = tk.StringVar()
        entrada = ttk.Entry(painel, textvariable=self.var_nome, width=44)
        entrada.pack(fill="x", pady=(0, 12))
        entrada.focus_set()

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

    def _confirmar(self):
        nome = self.var_nome.get().strip()
        if not nome:
            messagebox.showwarning(
                "Nova etapa",
                "Informe o nome da etapa.",
                parent=self,
            )
            return
        if self.on_confirmar(nome):
            self.destroy()


class EtapasPredefinidasFrame(tk.Frame):
    def __init__(self, parent, ctx, on_voltar):
        super().__init__(parent, bg="#ececec")
        self.ctx = ctx
        self.on_voltar = on_voltar
        self._dados = {"versao": 1, "etapas": []}
        self._etapa_editando_id = None
        self._icones_botoes = []
        self._atualizando_lista = False
        self._suprimir_selecao = False
        self._recarregador = RecarregadorCatalogo(
            self,
            obter_cache=obter_cache_catalogo,
            carregar_rede=carregar,
            ao_aplicar=self._aplicar_dados_catalogo,
            ao_erro=self._ao_erro_recarga_catalogo,
        )
        self._montar()
        ctx.registrar_callback_sinapi(self._ao_atualizar_sinapi)

    def _texto_referencia(self):
        ref = self.ctx.sinapi_referencia_rotulo
        if ref == "BASE AUSENTE":
            return "Base não carregada"
        return f"Referência SINAPI: {ref}"

    def _montar_botao_recarregar_cabecalho(self, parent):
        btn = criar_botao_ttk_so_icone(
            parent,
            nome_icone="sync-outline",
            command=self.recarregar_catalogo,
            estilo="Compact.TButton",
            cor_icone="#006699",
            refs=self._icones_botoes,
        )
        btn.pack(side="left", padx=(0, 8))
        vincular_tooltip(btn, "Atualizar página")

    def _ao_erro_recarga_catalogo(self, mensagem: str, avisar_erro: bool):
        if avisar_erro:
            messagebox.showwarning(
                "Recarregar",
                mensagem,
                parent=self.winfo_toplevel(),
            )

    def _aplicar_dados_catalogo(self, dados: dict):
        self._dados = dados
        self._atualizar_lista_etapas()

    def recarregar_catalogo(self, *, forcar_rede: bool = True):
        self._recarregador.solicitar(forcar_rede=forcar_rede, avisar_erro=True)

    def _liberar_supressao_selecao(self):
        self._suprimir_selecao = False

    def _montar(self):
        self.label_referencia = criar_barra_modulo(
            self,
            "Etapas pré-definidas",
            self.on_voltar,
            texto_referencia=self._texto_referencia(),
            montar_acoes_apos_titulo=self._montar_botao_recarregar_cabecalho,
        )

        conteudo = tk.Frame(self, bg="#ececec")
        conteudo.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        painel = tk.PanedWindow(conteudo, orient=tk.HORIZONTAL, sashwidth=6, bg="#cccccc")
        painel.pack(fill="both", expand=True)

        esquerda = tk.LabelFrame(
            painel, text="Etapas cadastradas", bg="#ececec", padx=6, pady=6
        )
        painel.add(esquerda, minsize=320)

        self.var_busca = tk.StringVar()
        self.var_busca.trace_add("write", lambda *_a: self._atualizar_lista_etapas())
        linha_busca = tk.Frame(esquerda, bg="#ececec")
        linha_busca.pack(fill="x", pady=(0, 6))
        tk.Label(linha_busca, text="Filtrar:", bg="#ececec").pack(side="left")
        ttk.Entry(linha_busca, textvariable=self.var_busca, width=28).pack(
            side="left", padx=(4, 0), fill="x", expand=True
        )

        container_tree = tk.Frame(esquerda, bg="#ececec")
        container_tree.pack(fill="both", expand=True)

        colunas_etapas = ("nome", "itens")
        self.tree_etapas = ttk.Treeview(
            container_tree, columns=colunas_etapas, show="headings", height=14
        )
        self.tree_etapas.heading("nome", text="Nome")
        self.tree_etapas.heading("itens", text="Itens")
        self.tree_etapas.column("nome", width=220, stretch=True)
        self.tree_etapas.column("itens", width=56, anchor="center", stretch=False)
        scroll_etapas = ttk.Scrollbar(
            container_tree, orient="vertical", command=self.tree_etapas.yview
        )
        self.tree_etapas.configure(yscrollcommand=scroll_etapas.set)
        self.tree_etapas.pack(side="left", fill="both", expand=True)
        scroll_etapas.pack(side="right", fill="y")
        self.tree_etapas.bind("<<TreeviewSelect>>", self._ao_selecionar_etapa)

        linha_bt_etapas = tk.Frame(esquerda, bg="#ececec")
        linha_bt_etapas.pack(fill="x", pady=(6, 0))
        criar_botao_ttk_com_icone(
            linha_bt_etapas,
            texto="Nova etapa",
            nome_icone="add-circle-outline",
            command=self._nova_etapa,
            estilo="Add.Compact.TButton",
            refs=self._icones_botoes,
        ).pack(side="left", padx=(0, 4))
        criar_botao_ttk_com_icone(
            linha_bt_etapas,
            texto="Excluir",
            nome_icone="trash-outline",
            command=self._excluir_etapa,
            estilo="Delete.Compact.TButton",
            refs=self._icones_botoes,
        ).pack(side="left")

        direita = tk.LabelFrame(painel, text="Edição da etapa", bg="#ececec", padx=8, pady=8)
        painel.add(direita, minsize=420)

        form = tk.Frame(direita, bg="#ececec")
        form.pack(fill="x", pady=(0, 8))

        self.var_nome = tk.StringVar()
        linha_nome = tk.Frame(form, bg="#ececec")
        linha_nome.pack(fill="x", pady=2)
        tk.Label(linha_nome, text="Nome:", width=10, anchor="w", bg="#ececec").pack(side="left")
        ttk.Entry(linha_nome, textvariable=self.var_nome, width=48).pack(
            side="left", fill="x", expand=True
        )

        criar_botao_ttk_com_icone(
            form,
            texto="Salvar alterações",
            nome_icone="save-outline",
            command=self._salvar_etapa,
            estilo="Save.TButton",
            refs=self._icones_botoes,
        ).pack(anchor="e", pady=(6, 0))

        painel_itens = tk.LabelFrame(
            direita, text="Itens da etapa", bg="#ececec", padx=6, pady=6
        )
        painel_itens.pack(fill="both", expand=True)

        colunas = ("codigo", "descricao", "unidade", "tipo")
        self.tree_itens = ttk.Treeview(
            painel_itens, columns=colunas, show="headings", height=10
        )
        self.tree_itens.heading("codigo", text="Código")
        self.tree_itens.heading("descricao", text="Descrição")
        self.tree_itens.heading("unidade", text="Unid.")
        self.tree_itens.heading("tipo", text="Tipo")
        self.tree_itens.column("codigo", width=56, anchor="center", stretch=False)
        self.tree_itens.column("descricao", width=220, stretch=True)
        self.tree_itens.column("unidade", width=48, anchor="center", stretch=False)
        self.tree_itens.column("tipo", width=130, anchor="center", stretch=False)
        scroll_itens = ttk.Scrollbar(
            painel_itens, orient="vertical", command=self.tree_itens.yview
        )
        self.tree_itens.configure(yscrollcommand=scroll_itens.set)
        self.tree_itens.pack(side="left", fill="both", expand=True)
        scroll_itens.pack(side="right", fill="y")

        linha_bt_itens = tk.Frame(direita, bg="#ececec")
        linha_bt_itens.pack(fill="x", pady=(8, 0))
        criar_botao_inserir_prominente(
            linha_bt_itens,
            texto="Adicionar item SINAPI",
            command=self._adicionar_sinapi,
            refs=self._icones_botoes,
        ).pack(side="left", padx=(0, 4))
        criar_botao_inserir_prominente(
            linha_bt_itens,
            texto="Adicionar composição própria",
            command=self._adicionar_propria,
            refs=self._icones_botoes,
        ).pack(side="left", padx=(0, 4))
        criar_botao_ttk_com_icone(
            linha_bt_itens,
            texto="Remover item",
            nome_icone="remove-circle-outline",
            command=self._remover_item,
            estilo="Delete.Compact.TButton",
            refs=self._icones_botoes,
        ).pack(side="left")

        tk.Label(
            direita,
            text="Os itens serão inseridos com quantidade 1 ao usar o modelo no orçamento.",
            font=("Arial", 8),
            fg="#666666",
            bg="#ececec",
            anchor="w",
        ).pack(fill="x", pady=(8, 0))

    def _ao_atualizar_sinapi(self):
        if self.label_referencia is not None:
            self.label_referencia.config(text=self._texto_referencia())

    def _filtrar_etapas(self):
        texto = self.var_busca.get().strip().lower()
        etapas = listar(self._dados)
        if not texto:
            return etapas
        return [e for e in etapas if texto in str(e.get("nome", "")).lower()]

    def _atualizar_lista_etapas(self):
        self._suprimir_selecao = True
        self._atualizando_lista = True
        try:
            selecionado = self._etapa_editando_id
            self.tree_etapas.delete(*self.tree_etapas.get_children())
            primeiro_id = None
            for etapa in self._filtrar_etapas():
                etapa_id = etapa["id"]
                if primeiro_id is None:
                    primeiro_id = etapa_id
                self.tree_etapas.insert(
                    "",
                    "end",
                    iid=etapa_id,
                    values=(etapa.get("nome", ""), len(etapa.get("itens", []))),
                )
            if selecionado and self.tree_etapas.exists(selecionado):
                self.tree_etapas.selection_set(selecionado)
                self.tree_etapas.focus(selecionado)
                self._carregar_etapa_na_edicao(selecionado)
            elif primeiro_id:
                self.tree_etapas.selection_set(primeiro_id)
                self._carregar_etapa_na_edicao(primeiro_id)
            else:
                self._etapa_editando_id = None
                self.var_nome.set("")
                self._atualizar_itens()
        finally:
            self._atualizando_lista = False
            self.after_idle(self._liberar_supressao_selecao)

    def _ao_selecionar_etapa(self, _event=None):
        if self._atualizando_lista or self._suprimir_selecao:
            return
        selecionado = self.tree_etapas.selection()
        if not selecionado:
            return
        self._carregar_etapa_na_edicao(selecionado[0])

    def _carregar_etapa_na_edicao(self, etapa_id):
        etapa = obter_por_id(etapa_id, self._dados)
        if etapa is None:
            return
        self._etapa_editando_id = etapa_id
        self.var_nome.set(etapa.get("nome", ""))
        self._atualizar_itens()

    def _etapa_em_edicao(self):
        if not self._etapa_editando_id:
            return None
        return obter_por_id(self._etapa_editando_id, self._dados)

    def _atualizar_itens(self):
        self.tree_itens.delete(*self.tree_itens.get_children())
        etapa = self._etapa_em_edicao()
        if etapa is None:
            return
        for item in etapa.get("itens", []):
            tipo = item.get("tipo", "")
            if tipo == TIPO_ITEM_SINAPI:
                rotulo_tipo = "SINAPI"
                descricao = item.get("descricao", "")
            else:
                rotulo_tipo = "Composição própria"
                descricao = item.get("nome", "")
            self.tree_itens.insert(
                "",
                "end",
                iid=item["id"],
                values=(
                    item.get("codigo", ""),
                    descricao,
                    item.get("unidade", ""),
                    rotulo_tipo,
                ),
            )

    def _nova_etapa(self):
        def ao_confirmar(nome):
            try:
                novo_id = criar(nome, dados=self._dados)
            except ValueError as exc:
                messagebox.showwarning(
                    "Nova etapa", str(exc), parent=self.winfo_toplevel()
                )
                return False
            self._dados = carregar()
            self._etapa_editando_id = novo_id
            self._atualizar_lista_etapas()
            if self.tree_etapas.exists(novo_id):
                self.tree_etapas.selection_set(novo_id)
                self.tree_etapas.focus(novo_id)
            return True

        DialogoNovaEtapaPredefinida(self.winfo_toplevel(), ao_confirmar)

    def _salvar_etapa(self):
        etapa = self._etapa_em_edicao()
        if etapa is None:
            messagebox.showinfo(
                "Salvar",
                "Selecione uma etapa para editar.",
                parent=self.winfo_toplevel(),
            )
            return
        etapa["nome"] = self.var_nome.get().strip()
        try:
            atualizar(etapa, self._dados)
        except ValueError as exc:
            messagebox.showwarning("Salvar", str(exc), parent=self.winfo_toplevel())
            if "Recarregue" in str(exc):
                self.recarregar_catalogo()
            return
        self._dados = carregar()
        self._atualizar_lista_etapas()

    def _excluir_etapa(self):
        etapa = self._etapa_em_edicao()
        if etapa is None:
            messagebox.showinfo(
                "Excluir",
                "Selecione uma etapa.",
                parent=self.winfo_toplevel(),
            )
            return
        if not confirmar_exclusao_com_espera(
            self.winfo_toplevel(),
            "Excluir etapa",
            f"Excluir a etapa \"{etapa.get('nome')}\"?",
            "Excluir etapa",
        ):
            return
        try:
            excluir(etapa["id"], self._dados)
        except ValueError as exc:
            messagebox.showwarning("Excluir", str(exc), parent=self.winfo_toplevel())
            return
        self._dados = carregar()
        self._etapa_editando_id = None
        self.var_nome.set("")
        self._atualizar_lista_etapas()

    def _adicionar_sinapi(self):
        etapa = self._etapa_em_edicao()
        if etapa is None:
            messagebox.showinfo(
                "Item SINAPI",
                "Selecione ou crie uma etapa primeiro.",
                parent=self.winfo_toplevel(),
            )
            return

        def ao_escolher(codigo, descricao, unidade, _custo, _quantidade, _estado, tipo_sinapi=""):
            item = novo_item_sinapi_template(
                codigo, descricao, unidade, tipo_sinapi
            )
            etapa.setdefault("itens", []).append(item)
            try:
                atualizar(etapa, self._dados)
            except ValueError as exc:
                messagebox.showwarning("Item", str(exc), parent=self.winfo_toplevel())
                return
            self._dados = carregar()
            self._atualizar_lista_etapas()

        DialogoBuscaSinapi(
            self.winfo_toplevel(),
            self.ctx,
            "SP",
            ao_escolher,
            titulo="Adicionar item SINAPI",
            mostrar_quantidade=False,
            texto_confirmar="Adicionar",
            fechar_unico=True,
        )

    def _adicionar_propria(self):
        etapa = self._etapa_em_edicao()
        if etapa is None:
            messagebox.showinfo(
                "Composição própria",
                "Selecione ou crie uma etapa primeiro.",
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

        def ao_escolher(comp, _quantidade):
            item = novo_item_propria_template(
                comp.get("id", ""),
                comp.get("codigo", ""),
                comp.get("nome", ""),
                comp.get("unidade", ""),
            )
            etapa.setdefault("itens", []).append(item)
            try:
                atualizar(etapa, self._dados)
            except ValueError as exc:
                messagebox.showwarning("Item", str(exc), parent=self.winfo_toplevel())
                return
            self._dados = carregar()
            self._atualizar_lista_etapas()

        DialogoBuscaComposicaoPropria(
            self.winfo_toplevel(),
            self.ctx,
            catalogo,
            "",
            ao_escolher,
            mostrar_quantidade=False,
        )

    def _remover_item(self):
        etapa = self._etapa_em_edicao()
        if etapa is None:
            return
        selecionado = self.tree_itens.selection()
        if not selecionado:
            messagebox.showinfo(
                "Remover item",
                "Selecione um item na lista.",
                parent=self.winfo_toplevel(),
            )
            return
        item_id = selecionado[0]
        etapa["itens"] = [
            item for item in etapa.get("itens", []) if item.get("id") != item_id
        ]
        try:
            atualizar(etapa, self._dados)
        except ValueError as exc:
            messagebox.showwarning("Remover", str(exc), parent=self.winfo_toplevel())
            return
        self._dados = carregar()
        self._atualizar_lista_etapas()

    def focar(self):
        self.recarregar_catalogo(forcar_rede=False)
