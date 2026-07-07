"""Tela de seleção de orçamentos customizados antes da edição."""

from datetime import datetime

import tkinter as tk
from tkinter import messagebox, ttk

from core.composicoes_proprias_storage import listar as listar_composicoes_catalogo
from core.importacao_i9 import importar_planilha_i9
from core.orcamento_storage import (
    adicionar_orcamento_importado,
    criar_orcamento,
    excluir_orcamento,
    listar_orcamentos_resumo,
    obter_orcamento_dict,
    renomear_orcamento,
)
from ui.dialogo_importar_i9 import DialogoImportarI9
from ui.icones import criar_botao_ttk_com_icone
from ui.widgets import (
    confirmar_exclusao_com_espera,
    criar_barra_modulo,
    perguntar_texto,
)


def _formatar_data_iso(iso_texto: str) -> str:
    if not iso_texto:
        return "—"
    try:
        texto = iso_texto.replace("Z", "+00:00")
        dt = datetime.fromisoformat(texto)
        return dt.astimezone().strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso_texto


class SelecaoOrcamentosCustomizadoFrame(tk.Frame):
    def __init__(self, parent, ctx, *, on_abrir, on_voltar):
        super().__init__(parent, bg="#ececec")
        self.ctx = ctx
        self.on_abrir = on_abrir
        self.on_voltar = on_voltar
        self._icones_botoes = []
        self._montar()

    def _texto_referencia(self):
        ref = self.ctx.sinapi_referencia_rotulo
        if ref == "BASE AUSENTE":
            return "Base não carregada"
        return f"Referência SINAPI: {ref}"

    def _montar(self):
        criar_barra_modulo(
            self,
            "Orçamento Customizado",
            self.on_voltar,
            texto_referencia=self._texto_referencia(),
        )

        conteudo = tk.Frame(self, bg="#ececec")
        conteudo.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        tk.Label(
            conteudo,
            text="Selecione um orçamento para editar ou crie um novo.",
            bg="#ececec",
            fg="#333333",
            font=("Arial", 10),
        ).pack(anchor="w", padx=4, pady=(0, 8))

        painel_lista = tk.LabelFrame(
            conteudo,
            text="Orçamentos salvos",
            bg="#ececec",
            padx=8,
            pady=8,
        )
        painel_lista.pack(fill="both", expand=True, padx=4)

        linha_botoes = tk.Frame(painel_lista, bg="#ececec")
        linha_botoes.pack(fill="x", pady=(0, 8))

        criar_botao_ttk_com_icone(
            linha_botoes,
            texto="Novo orçamento",
            nome_icone="add-circle-outline",
            command=self._novo_orcamento,
            estilo="Add.Compact.TButton",
            refs=self._icones_botoes,
        ).pack(side="left", padx=(0, 4))

        self.btn_abrir = ttk.Button(
            linha_botoes,
            text="Abrir orçamento",
            command=self._abrir_selecionado,
            style="Compact.TButton",
            state="disabled",
        )
        self.btn_abrir.pack(side="left", padx=(0, 4))

        ttk.Button(
            linha_botoes,
            text="Editar nome",
            command=self._renomear_selecionado,
            style="Edit.Compact.TButton",
        ).pack(side="left", padx=(0, 4))

        criar_botao_ttk_com_icone(
            linha_botoes,
            texto="Excluir",
            nome_icone="trash-outline",
            command=self._excluir_selecionado,
            estilo="Delete.Compact.TButton",
            refs=self._icones_botoes,
        ).pack(side="left", padx=(0, 4))

        criar_botao_ttk_com_icone(
            linha_botoes,
            texto="Importar i9",
            nome_icone="attach-outline",
            command=self._importar_i9,
            estilo="Compact.TButton",
            refs=self._icones_botoes,
        ).pack(side="left")

        self.var_busca = tk.StringVar()
        self.var_busca.trace_add("write", lambda *_a: self._atualizar_lista())
        linha_busca = tk.Frame(painel_lista, bg="#ececec")
        linha_busca.pack(fill="x", pady=(0, 6))
        tk.Label(linha_busca, text="Filtrar:", bg="#ececec").pack(side="left")
        ttk.Entry(linha_busca, textvariable=self.var_busca, width=36).pack(
            side="left", padx=(4, 0), fill="x", expand=True
        )

        container_tree = tk.Frame(painel_lista, bg="#ececec")
        container_tree.pack(fill="both", expand=True)

        colunas = ("nome", "criado_em", "atualizado_em", "etapas", "itens")
        self.tree = ttk.Treeview(
            container_tree, columns=colunas, show="headings", height=16
        )
        self.tree.heading("nome", text="Nome")
        self.tree.heading("criado_em", text="Criado em")
        self.tree.heading("atualizado_em", text="Atualizado em")
        self.tree.heading("etapas", text="Etapas")
        self.tree.heading("itens", text="Itens")
        self.tree.column("nome", width=280, stretch=True)
        self.tree.column("criado_em", width=130, anchor="center", stretch=False)
        self.tree.column("atualizado_em", width=130, anchor="center", stretch=False)
        self.tree.column("etapas", width=60, anchor="center", stretch=False)
        self.tree.column("itens", width=60, anchor="center", stretch=False)
        scroll = ttk.Scrollbar(container_tree, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self._ao_duplo_clique)
        self.tree.bind("<Return>", self._ao_duplo_clique)
        self.tree.bind("<<TreeviewSelect>>", self._ao_selecionar)

        self._atualizar_lista()

    def recarregar(self):
        self._atualizar_lista()

    def _orcamento_selecionado_id(self):
        selecao = self.tree.selection()
        if not selecao:
            return None
        return selecao[0]

    def _ao_selecionar(self, _event=None):
        tem_selecao = bool(self.tree.selection())
        estado = "normal" if tem_selecao else "disabled"
        self.btn_abrir.config(state=estado)

    def _ao_duplo_clique(self, _event=None):
        if self._orcamento_selecionado_id():
            self._abrir_selecionado()

    def _abrir_selecionado(self):
        orcamento_id = self._orcamento_selecionado_id()
        if not orcamento_id:
            messagebox.showinfo(
                "Orçamento",
                "Selecione um orçamento na lista.",
                parent=self.winfo_toplevel(),
            )
            return
        self.on_abrir(orcamento_id)

    def _atualizar_lista(self):
        filtro = self.var_busca.get().strip().lower()
        for item in self.tree.get_children():
            self.tree.delete(item)

        for resumo in listar_orcamentos_resumo():
            nome = resumo.get("nome", "")
            if filtro and filtro not in nome.lower():
                continue
            self.tree.insert(
                "",
                "end",
                iid=resumo["id"],
                values=(
                    nome,
                    _formatar_data_iso(resumo.get("criado_em", "")),
                    _formatar_data_iso(resumo.get("atualizado_em", "")),
                    resumo.get("grupos", 0),
                    resumo.get("itens", 0),
                ),
            )
        self._ao_selecionar()

    def _novo_orcamento(self):
        nome = perguntar_texto(
            self.winfo_toplevel(),
            "Novo orçamento",
            "Nome do novo orçamento:",
        )
        if not nome or not nome.strip():
            return
        novo_id = criar_orcamento(nome)
        self.on_abrir(novo_id)

    def _renomear_selecionado(self):
        orcamento_id = self._orcamento_selecionado_id()
        if not orcamento_id:
            messagebox.showinfo(
                "Orçamento",
                "Selecione um orçamento na lista.",
                parent=self.winfo_toplevel(),
            )
            return
        registro = obter_orcamento_dict(orcamento_id)
        nome_atual = registro.get("nome", "") if registro else ""
        nome = perguntar_texto(
            self.winfo_toplevel(),
            "Editar nome",
            "Novo nome do orçamento:",
            valor_inicial=nome_atual,
        )
        if not nome or not nome.strip():
            return
        try:
            renomear_orcamento(orcamento_id, nome)
            self._atualizar_lista()
            if self.tree.exists(orcamento_id):
                self.tree.selection_set(orcamento_id)
                self.tree.focus(orcamento_id)
        except ValueError as exc:
            messagebox.showwarning("Orçamento", str(exc), parent=self.winfo_toplevel())

    def _excluir_selecionado(self):
        orcamento_id = self._orcamento_selecionado_id()
        if not orcamento_id:
            messagebox.showinfo(
                "Orçamento",
                "Selecione um orçamento na lista.",
                parent=self.winfo_toplevel(),
            )
            return
        registro = obter_orcamento_dict(orcamento_id)
        nome = registro.get("nome", "Sem nome") if registro else "Sem nome"
        if not confirmar_exclusao_com_espera(
            self.winfo_toplevel(),
            "Excluir orçamento",
            f'Excluir o orçamento "{nome}"?\nEsta ação não pode ser desfeita.',
            "Excluir orçamento",
        ):
            return
        try:
            excluir_orcamento(orcamento_id)
            self._atualizar_lista()
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

            novo_id = adicionar_orcamento_importado(resultado.orcamento)

            resumo = (
                f'Orçamento "{resultado.orcamento.nome}" importado com sucesso.\n'
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
            self.on_abrir(novo_id)

        DialogoImportarI9(self.winfo_toplevel(), on_importar=ao_importar)
