"""Pesquisa autores em pareceres finalizados do Idebras."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

from core.idebras_client import (
    ConjuntoIdebras,
    IdebrasClient,
    IdebrasError,
    ParecerFinalizado,
    normalizar_ambiente,
)
from ui.icones import (
    IndicadorAmpulheta,
    criar_botao_ttk_com_icone,
    definir_estado_botao_icone,
)
from ui.widgets import (
    CampoListaPesquisavel,
    aplicar_icone_janela,
    centralizar_janela,
    criar_botao_fechar,
    focar_entrada_apos_exibir,
    preparar_toplevel,
)


class DialogoImportarAutorIdebras(tk.Toplevel):
    def __init__(
        self,
        parent,
        *,
        cliente: IdebrasClient,
        conjuntos: list[ConjuntoIdebras],
        on_importar,
        refs_icones: list | None = None,
    ):
        super().__init__(parent)
        preparar_toplevel(self)
        self.cliente = cliente
        self.conjuntos = list(conjuntos or [])
        self._conjunto_por_nome = {c.nome: c for c in self.conjuntos}
        self.on_importar = on_importar
        self._refs_icones = refs_icones if refs_icones is not None else []
        self._pareceres: list[ParecerFinalizado] = []
        self._por_iid: dict[str, ParecerFinalizado] = {}
        self._ocupado = False

        self.title("Importar autor do Idebras")
        aplicar_icone_janela(self)
        self.configure(bg="#ececec")
        self.transient(parent)
        self.grab_set()
        self.geometry("920x520")
        self.minsize(720, 400)

        painel = tk.Frame(self, bg="#ececec", padx=16, pady=14)
        painel.pack(fill="both", expand=True)
        painel.columnconfigure(0, weight=1)
        painel.rowconfigure(3, weight=1)

        tk.Label(
            painel,
            text="Importar autor do Idebras",
            font=("Arial", 12, "bold"),
            fg="#006699",
            bg="#ececec",
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            painel,
            text="Pesquise pelo nome do cliente e/ou pelo conjunto. "
            "Ao selecionar um autor, o conjunto e a planta são carregados.",
            font=("Arial", 9),
            fg="#555555",
            bg="#ececec",
            anchor="w",
            wraplength=860,
            justify="left",
        ).grid(row=1, column=0, sticky="ew", pady=(2, 10))

        filtros = tk.Frame(painel, bg="#ececec")
        filtros.grid(row=2, column=0, sticky="ew")
        filtros.columnconfigure(1, weight=3)
        filtros.columnconfigure(3, weight=4)

        self.var_nome = tk.StringVar()
        self.var_conjunto = tk.StringVar()
        self.var_status = tk.StringVar(
            value="Informe o nome e/ou o conjunto e clique em Pesquisar."
        )

        tk.Label(filtros, text="Nome Cliente:", bg="#ececec").grid(
            row=0, column=0, sticky="w", padx=(0, 6)
        )
        self.entrada_nome = ttk.Entry(filtros, textvariable=self.var_nome)
        self.entrada_nome.grid(row=0, column=1, sticky="ew")
        self.entrada_nome.bind("<Return>", lambda _e: self._pesquisar())

        tk.Label(filtros, text="Conjunto:", bg="#ececec").grid(
            row=0, column=2, sticky="w", padx=(12, 6)
        )
        self.campo_conjunto = CampoListaPesquisavel(
            filtros,
            textvariable=self.var_conjunto,
            normalizar=normalizar_ambiente,
            altura_lista=14,
            largura_minima_lista=480,
            bg="#ececec",
        )
        self.campo_conjunto.definir_opcoes([c.nome for c in self.conjuntos])
        self.campo_conjunto.grid(row=0, column=3, sticky="ew")

        self.btn_pesquisar = criar_botao_ttk_com_icone(
            filtros,
            texto="Pesquisar",
            nome_icone="search-outline",
            command=self._pesquisar,
            refs=self._refs_icones,
        )
        self.btn_pesquisar.grid(row=0, column=4, padx=(10, 0))

        colunas = ("autor", "conjunto", "cidade_uf", "endereco")
        tree_frame = tk.Frame(painel, bg="#ececec")
        tree_frame.grid(row=3, column=0, sticky="nsew", pady=(12, 0))
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            tree_frame, columns=colunas, show="headings", height=12
        )
        self.tree.heading("autor", text="Autor")
        self.tree.heading("conjunto", text="Conjunto")
        self.tree.heading("cidade_uf", text="Cidade/UF")
        self.tree.heading("endereco", text="Endereço")
        self.tree.column("autor", width=240, anchor="w")
        self.tree.column("conjunto", width=260, anchor="w")
        self.tree.column("cidade_uf", width=140, anchor="w")
        self.tree.column("endereco", width=220, anchor="w")
        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<Double-1>", lambda _e: self._confirmar())
        self.tree.bind("<Return>", lambda _e: self._confirmar())
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._atualizar_botao_importar())

        rodape = tk.Frame(painel, bg="#ececec")
        rodape.grid(row=4, column=0, sticky="ew", pady=(10, 0))
        rodape.columnconfigure(0, weight=1)

        tk.Label(
            rodape,
            textvariable=self.var_status,
            font=("Arial", 9),
            fg="#555555",
            bg="#ececec",
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        slot = tk.Frame(rodape, bg="#ececec", width=30, height=26)
        slot.grid(row=0, column=1, padx=(0, 8), sticky="e")
        slot.pack_propagate(False)
        self.ampulheta = IndicadorAmpulheta(
            slot, altura=24, cor="#006699", bg="#ececec", refs=self._refs_icones
        )

        criar_botao_fechar(rodape, command=self.destroy).grid(
            row=0, column=3, sticky="e", padx=(6, 0)
        )
        self.btn_importar = criar_botao_ttk_com_icone(
            rodape,
            texto="Importar",
            nome_icone="cloud-download-outline",
            command=self._confirmar,
            estilo="Add.TButton",
            refs=self._refs_icones,
        )
        self.btn_importar.grid(row=0, column=2, sticky="e")
        definir_estado_botao_icone(self.btn_importar, "disabled")

        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        centralizar_janela(self, parent)
        focar_entrada_apos_exibir(self.entrada_nome)

    def _na_ui(self, fn):
        try:
            if self.winfo_exists():
                self.after(0, fn)
        except tk.TclError:
            pass

    def _conjunto_id_atual(self) -> str | None:
        nome = self.var_conjunto.get().strip()
        if not nome:
            return ""
        encontrado = self._conjunto_por_nome.get(nome)
        if encontrado is not None:
            return encontrado.id
        chave = normalizar_ambiente(nome)
        matches = [c for c in self.conjuntos if chave in normalizar_ambiente(c.nome)]
        if len(matches) == 1:
            self.var_conjunto.set(matches[0].nome)
            return matches[0].id
        if len(matches) > 1:
            self.var_status.set(
                "Há vários conjuntos com esse texto. Selecione um na lista."
            )
            return None
        self.var_status.set(
            "Conjunto não encontrado. Selecione um da lista ou deixe em branco."
        )
        return None

    def _pesquisar(self):
        if self._ocupado:
            return
        nome = self.var_nome.get().strip()
        conjunto_id = self._conjunto_id_atual()
        if conjunto_id is None:
            return
        if not nome and not conjunto_id:
            self.var_status.set("Informe o nome do cliente e/ou selecione um conjunto.")
            return
        self._ocupado = True
        self.var_status.set("Pesquisando pareceres finalizados...")
        self.ampulheta.iniciar()
        definir_estado_botao_icone(self.btn_pesquisar, "disabled")
        definir_estado_botao_icone(self.btn_importar, "disabled")

        def trabalho():
            try:
                resultado = self.cliente.pesquisar_pareceres_finalizados(
                    nome_cliente=nome,
                    conjunto_id=conjunto_id,
                )
            except IdebrasError as exc:
                msg = str(exc)
                self._na_ui(lambda m=msg: self._fim_pesquisa_erro(m))
                return
            except Exception as exc:
                msg = f"Erro ao pesquisar autores: {exc}"
                self._na_ui(lambda m=msg: self._fim_pesquisa_erro(m))
                return
            self._na_ui(lambda r=resultado: self._fim_pesquisa_ok(r))

        threading.Thread(target=trabalho, daemon=True).start()

    def _liberar_pesquisa(self):
        self._ocupado = False
        self.ampulheta.parar()
        definir_estado_botao_icone(self.btn_pesquisar, "normal")
        self._atualizar_botao_importar()

    def _fim_pesquisa_erro(self, mensagem: str):
        self._liberar_pesquisa()
        self.var_status.set(mensagem)

    def _fim_pesquisa_ok(self, resultado):
        self._liberar_pesquisa()
        self._pareceres = list(resultado.pareceres)
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._por_iid.clear()
        for parecer in self._pareceres:
            iid = self.tree.insert(
                "",
                "end",
                values=(
                    parecer.nome,
                    parecer.conjunto,
                    parecer.cidade_uf,
                    parecer.endereco,
                ),
            )
            self._por_iid[iid] = parecer
        mostrados = len(self._pareceres)
        total = resultado.total or mostrados
        if mostrados == 0:
            self.var_status.set("Nenhum autor encontrado para essa pesquisa.")
            return
        if total > mostrados:
            self.var_status.set(
                f"Mostrando {mostrados} de {total} autor(es). "
                "Refine o nome ou o conjunto se necessário."
            )
        else:
            self.var_status.set(f"{mostrados} autor(es) encontrado(s).")
        primeiro = self.tree.get_children()
        if primeiro:
            self.tree.selection_set(primeiro[0])
            self.tree.focus(primeiro[0])
            self.tree.see(primeiro[0])
        self._atualizar_botao_importar()

    def _parecer_selecionado(self) -> ParecerFinalizado | None:
        selecao = self.tree.selection()
        if not selecao:
            return None
        return self._por_iid.get(selecao[0])

    def _atualizar_botao_importar(self):
        if self._ocupado:
            definir_estado_botao_icone(self.btn_importar, "disabled")
            return
        estado = "normal" if self._parecer_selecionado() else "disabled"
        definir_estado_botao_icone(self.btn_importar, estado)

    def _confirmar(self):
        if self._ocupado:
            return
        parecer = self._parecer_selecionado()
        if parecer is None:
            self.var_status.set("Selecione um autor na lista.")
            return
        self.on_importar(parecer)
        self.destroy()
