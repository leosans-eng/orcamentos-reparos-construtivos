"""Cadastro de anomalias da Área Comum (admin)."""

from __future__ import annotations

import json
import tkinter as tk
import unicodedata
from tkinter import messagebox, ttk

from core.area_comum import PERCENTUAIS_MODELO
from core.area_comum_anomalias import (
    CRITERIO_COBERTURA,
    CRITERIO_ESTRUTURA,
    CHAVE_PINTURA,
    ETAPAS_ORCAMENTO_FIXAS,
    NOMES_ETAPAS_FIXAS,
    OPERACAO_SOMAR,
    ORIGEM_ETAPA,
    ORIGEM_ITENS,
    ROTULOS_TIPO_CALCULO,
    ROTULOS_TITULO_ORCAMENTO,
    TITULO_PERSONALIZADO,
    TIPO_ITEM_CATALOGO_PROPRIA,
    TIPO_ITEM_CATALOGO_SINAPI,
    TIPOS_CALCULO,
    UNIDADES_COMUNS,
    carregar_catalogo,
    chave_titulo_orcamento,
    _definir_fundo_selador,
    itens_servicos_da_etapa,
    itens_sinapi_da_etapa,
    meta_etapa_fixa,
    normalizar_catalogo,
    normalizar_etapa_orcamento_fixa,
    normalizar_fatores,
    nova_anomalia,
    nova_etapa_orcamento_fixa,
    opcoes_do_criterio,
    recomendacao_vazia,
    novo_fator,
    novo_item_composicao_propria,
    novo_item_sinapi,
    novo_reparo,
    rotulo_fatores,
    rotulo_tipo_item_catalogo,
    rotulo_titulo_orcamento,
    salvar_catalogo,
    semear_etapas_orcamento_fixas,
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


def _ordem_alfabetica(nome: str) -> str:
    base = unicodedata.normalize("NFD", str(nome).casefold())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


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


def _rotulos_tipo_calculo() -> list[str]:
    return [f"{k} — {ROTULOS_TIPO_CALCULO.get(k, k)}" for k in TIPOS_CALCULO]


def _chave_tipo_calculo(texto: str) -> str:
    chave = str(texto or "").split(" — ", 1)[0].strip()
    return chave if chave in TIPOS_CALCULO else "fixo"


def _ajustar_janela_ao_conteudo(janela: tk.Toplevel) -> None:
    """Recalcula a altura da janela para caber o conteúdo (até o limite da tela)."""
    try:
        if not janela.winfo_exists():
            return
    except tk.TclError:
        return
    try:
        janela.geometry("")
        janela.update_idletasks()
        largura = min(max(int(janela.winfo_reqwidth()), 640), 860)
        altura_req = max(int(janela.winfo_reqheight()), 1)
        tela_h = int(janela.winfo_screenheight())
        altura = min(altura_req, max(280, tela_h - 80))
        janela.geometry(f"{largura}x{altura}")
        janela.update_idletasks()
    except tk.TclError:
        pass


class EditorFatoresCalculo(tk.Frame):
    """Lista de fatores combinados com × ou +."""

    def __init__(
        self,
        parent,
        *,
        fatores=None,
        multiplicador=1,
        bg=None,
        estilos=None,
        refs=None,
        on_mudou=None,
    ):
        from ui.temas import cores_tema

        cores = cores_tema(parent)
        if bg is None:
            bg = cores.fundo
        super().__init__(parent, bg=bg)
        self._cores = cores
        self._estilos = estilos
        self._refs = refs if refs is not None else []
        self._on_mudou = on_mudou
        self._linhas: list[dict] = []
        self._opcoes = _rotulos_tipo_calculo()
        self._silencioso = False

        cab = tk.Frame(self, bg=bg)
        cab.pack(fill="x")
        tk.Label(
            cab,
            text="Fatores",
            bg=bg,
            fg=cores.texto,
            anchor="w",
        ).pack(side="left")
        criar_botao_ttk_com_icone(
            cab,
            texto="Adicionar fator",
            nome_icone="add-circle-outline",
            command=lambda: self._adicionar(),
            estilo=(estilos.compacto_adicionar if estilos else "Add.Compact.TButton"),
            cor_icone=(estilos.icone_adicionar if estilos else cores.titulo),
            refs=self._refs,
        ).pack(side="right")

        self._lista = tk.Frame(self, bg=bg)
        self._lista.pack(fill="x", pady=(6, 0))
        self.var_resumo = tk.StringVar(value="")
        texto_mult = str(multiplicador if multiplicador not in (None, "") else 1)
        self.var_multiplicador = tk.StringVar(value=texto_mult.replace(".", ","))
        rodape = tk.Frame(self, bg=bg)
        rodape.pack(fill="x", pady=(8, 0))
        tk.Label(
            rodape,
            text="Multiplicar o resultado por",
            bg=bg,
            fg=cores.texto,
            anchor="w",
        ).pack(side="left")
        entrada_mult = ttk.Entry(rodape, textvariable=self.var_multiplicador, width=8)
        entrada_mult.pack(side="left", padx=(8, 0))
        self.var_multiplicador.trace_add("write", lambda *_a: self._atualizar_resumo())
        tk.Label(
            self,
            textvariable=self.var_resumo,
            bg=bg,
            fg=cores.texto_suave,
            anchor="w",
            justify="left",
            wraplength=760,
            font=("Segoe UI", 8),
        ).pack(fill="x", pady=(4, 0))

        iniciais = normalizar_fatores(fatores if fatores is not None else [novo_fator()])
        if not iniciais:
            iniciais = [novo_fator()]
        self._silencioso = True
        try:
            for fator in iniciais:
                self._adicionar(fator)
        finally:
            self._silencioso = False
        self._atualizar_resumo()
        self._avisar_mudanca()

    def _avisar_mudanca(self):
        if self._silencioso or self._on_mudou is None:
            return
        self.after_idle(self._on_mudou)

    def _adicionar(self, fator=None):
        fator = fator or novo_fator()
        fundo = self.cget("bg")
        bloco = tk.Frame(self._lista, bg=fundo)
        bloco.pack(fill="x", pady=2)
        linha = tk.Frame(bloco, bg=fundo)
        linha.pack(fill="x")

        tipo = str(fator.get("tipo_calculo") or "fixo")
        rotulo = f"{tipo} — {ROTULOS_TIPO_CALCULO.get(tipo, tipo)}"
        var_tipo = tk.StringVar(
            value=rotulo if rotulo in self._opcoes else self._opcoes[-1]
        )
        var_coef = tk.StringVar(
            value=str(fator.get("coeficiente", 1)).replace(".", ",")
        )
        var_juncao = tk.StringVar(
            value="+" if fator.get("operacao") == OPERACAO_SOMAR else "×"
        )
        var_pergunta = tk.StringVar(value=str(fator.get("pergunta") or ""))
        combo_juncao = ttk.Combobox(
            linha,
            textvariable=var_juncao,
            values=("×", "+"),
            width=3,
            state="readonly",
        )
        combo_juncao.bind("<<ComboboxSelected>>", lambda _e: self._atualizar_resumo())
        campo = CampoListaPesquisavel(
            linha,
            textvariable=var_tipo,
            on_escolher=lambda _v, alvo=bloco: self._ao_escolher_tipo(alvo),
            largura_minima_lista=420,
            altura_lista=10,
            bg=fundo,
        )
        campo.definir_opcoes(self._opcoes)
        campo.pack(side="left", fill="x", expand=True)
        tk.Label(linha, text="×", bg=fundo, fg=self._cores.texto).pack(
            side="left", padx=4
        )
        entrada = ttk.Entry(linha, textvariable=var_coef, width=8)
        entrada.pack(side="left")
        var_coef.trace_add("write", lambda *_a: self._atualizar_resumo())
        extra = tk.Frame(bloco, bg=fundo)
        tk.Label(
            extra, text="Pergunta", bg=fundo, fg=self._cores.texto_suave
        ).pack(side="left")
        ttk.Entry(extra, textvariable=var_pergunta).pack(
            side="left", fill="x", expand=True, padx=(6, 0)
        )
        var_pergunta.trace_add("write", lambda *_a: self._atualizar_resumo())
        criar_botao_ttk_com_icone(
            linha,
            texto="",
            nome_icone="remove-circle-outline",
            command=lambda: self._remover(registro),
            estilo=(
                self._estilos.compacto_excluir
                if self._estilos
                else "Delete.Compact.TButton"
            ),
            cor_icone=(
                self._estilos.icone_excluir if self._estilos else self._cores.titulo
            ),
            refs=self._refs,
        ).pack(side="left", padx=(4, 0))

        registro = {
            "frame": bloco,
            "var_tipo": var_tipo,
            "var_coef": var_coef,
            "var_juncao": var_juncao,
            "var_pergunta": var_pergunta,
            "combo_juncao": combo_juncao,
            "campo": campo,
            "extra": extra,
        }
        self._linhas.append(registro)
        self._mostrar_pergunta(registro)
        self._atualizar_juncoes()
        self._atualizar_resumo()
        self._avisar_mudanca()

    def _ao_escolher_tipo(self, bloco):
        for registro in self._linhas:
            if registro["frame"] is bloco:
                self._mostrar_pergunta(registro)
                break
        self._atualizar_resumo()

    def _mostrar_pergunta(self, registro):
        extra = registro["extra"]
        if _chave_tipo_calculo(registro["var_tipo"].get()) == "variavel":
            if not extra.winfo_ismapped():
                extra.pack(fill="x", pady=(2, 0))
        elif extra.winfo_ismapped():
            extra.pack_forget()

    def _atualizar_juncoes(self):
        for indice, registro in enumerate(self._linhas):
            combo = registro["combo_juncao"]
            if indice == 0:
                combo.pack_forget()
            elif not combo.winfo_ismapped():
                combo.pack(side="left", before=registro["campo"], padx=(0, 4))

    def _remover(self, registro):
        if len(self._linhas) <= 1:
            messagebox.showinfo(
                "Fatores",
                "Mantenha ao menos um fator.",
                parent=self.winfo_toplevel(),
            )
            return
        self._linhas.remove(registro)
        registro["frame"].destroy()
        self._atualizar_juncoes()
        self._atualizar_resumo()
        self._avisar_mudanca()

    def _atualizar_resumo(self):
        try:
            fatores = self.obter()
            multiplicador = self.obter_multiplicador()
        except ValueError:
            self.var_resumo.set("")
            return
        self.var_resumo.set(
            "Fórmula: "
            + rotulo_fatores({"fatores": fatores, "multiplicador": multiplicador})
        )

    def obter(self) -> list[dict]:
        fatores = []
        for indice, registro in enumerate(self._linhas):
            tipo = _chave_tipo_calculo(registro["var_tipo"].get())
            try:
                coef = _float_br(registro["var_coef"].get())
            except ValueError as exc:
                raise ValueError("Coeficiente inválido.") from exc
            operacao = (
                OPERACAO_SOMAR
                if indice and registro["var_juncao"].get() == "+"
                else "multiplicar"
            )
            fatores.append(
                novo_fator(
                    tipo_calculo=tipo,
                    coeficiente=coef,
                    operacao=operacao,
                    pergunta=registro["var_pergunta"].get(),
                )
            )
        return normalizar_fatores(fatores)

    def obter_multiplicador(self) -> float:
        texto = (self.var_multiplicador.get() or "").strip()
        if not texto:
            return 1.0
        try:
            return _float_br(texto)
        except ValueError as exc:
            raise ValueError("Multiplicador inválido.") from exc


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
        self.resizable(True, True)

        item = item or {}
        painel = tk.Frame(self, bg=fundo, padx=16, pady=14)
        painel.pack(fill="both", expand=True)

        self.var_codigo = tk.StringVar(value=str(item.get("codigo_sinapi", "")))
        self.var_unidade = tk.StringVar(value=str(item.get("unidade", "m²")))
        self._tipo_sinapi = str(item.get("tipo_sinapi") or "")

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

        self.editor_fatores = EditorFatoresCalculo(
            painel,
            fatores=normalizar_fatores(item),
            multiplicador=item.get("multiplicador", 1),
            bg=fundo,
            estilos=estilos,
            refs=self._refs_icones,
            on_mudou=lambda: _ajustar_janela_ao_conteudo(self),
        )
        self.editor_fatores.pack(fill="x", pady=(0, 4))

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
        self.after_idle(lambda: _ajustar_janela_ao_conteudo(self))
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

        def ao_escolher(codigo, _descricao, unidade, _custo, _quantidade, _estado, tipo_ic=""):
            if codigo:
                self.var_codigo.set(str(codigo).strip())
            if unidade:
                self.var_unidade.set(str(unidade).strip())
            self._tipo_sinapi = str(tipo_ic or "")

        DialogoBuscaSinapi(
            self,
            self.ctx,
            estado,
            ao_escolher,
            titulo="Buscar código SINAPI",
            mostrar_quantidade=False,
            texto_confirmar="Usar código",
            fechar_unico=True,
            consulta_inicial=self.var_codigo.get().strip(),
        )

    def _confirmar(self):
        codigo = self.var_codigo.get().strip()
        if not codigo:
            messagebox.showwarning("Item", "Informe o código SINAPI.", parent=self)
            return
        try:
            fatores = self.editor_fatores.obter()
            multiplicador = self.editor_fatores.obter_multiplicador()
        except ValueError:
            messagebox.showwarning("Item", "Coeficiente ou multiplicador inválido.", parent=self)
            return
        tipo_sinapi = self._tipo_sinapi
        sinapi = getattr(self.ctx, "sinapi", None) if self.ctx is not None else None
        if sinapi is not None:
            try:
                letra = str(sinapi.obter_tipo(codigo) or "").strip()
            except (AttributeError, TypeError, ValueError):
                letra = ""
            if letra:
                tipo_sinapi = letra
        item = novo_item_sinapi(
            codigo_sinapi=codigo,
            unidade=self.var_unidade.get().strip() or "un",
            fatores=fatores,
            multiplicador=multiplicador,
            tipo_sinapi=tipo_sinapi,
        )
        if self.on_confirmar:
            self.on_confirmar(item)
        self.destroy()


class DialogoCoefCalculoItem(tk.Toplevel):
    """Edita os fatores de cálculo de um item (SINAPI ou composição)."""

    def __init__(
        self,
        parent,
        item=None,
        on_confirmar=None,
        *,
        titulo="Editar quantitativo",
        pedir_troca=None,
    ):
        super().__init__(parent)
        preparar_toplevel(self)
        cores, estilos = aplicar_chrome_dialogo(self)
        fundo = cores.fundo
        self.on_confirmar = on_confirmar
        self._refs_icones: list = []
        item = item or {}
        self.title(titulo)
        aplicar_icone_janela(self)
        self.transient(parent)
        self.grab_set()
        self.resizable(True, True)

        painel = tk.Frame(self, bg=fundo, padx=16, pady=14)
        painel.pack(fill="both", expand=True)
        self._pedir_troca = pedir_troca
        self._composicao_trocada = None
        codigo = str(item.get("codigo") or "").strip()
        nome = (
            item.get("nome")
            or item.get("codigo_sinapi")
            or codigo
            or "Item"
        )
        texto_nome = f"{codigo} — {nome}" if codigo and nome != codigo else str(nome)
        linha_nome = tk.Frame(painel, bg=fundo)
        linha_nome.pack(fill="x", pady=(0, 8))
        self._rotulo_nome = tk.Label(
            linha_nome,
            text=texto_nome,
            bg=fundo,
            fg=cores.texto,
            anchor="w",
            wraplength=460,
            justify="left",
        )
        self._rotulo_nome.pack(side="left", fill="x", expand=True)
        if pedir_troca is not None:
            criar_botao_ttk_com_icone(
                linha_nome,
                texto="Trocar",
                nome_icone="search-outline",
                command=self._trocar_composicao,
                estilo=estilos.compacto,
                cor_icone=estilos.icone,
                refs=self._refs_icones,
            ).pack(side="right", padx=(8, 0))

        self.editor_fatores = EditorFatoresCalculo(
            painel,
            fatores=normalizar_fatores(item),
            multiplicador=item.get("multiplicador", 1),
            bg=fundo,
            estilos=estilos,
            refs=self._refs_icones,
            on_mudou=lambda: _ajustar_janela_ao_conteudo(self),
        )
        self.editor_fatores.pack(fill="x")

        botoes = ttk.Frame(painel)
        botoes.pack(fill="x", pady=(12, 0))
        criar_botao_cancelar(botoes, self.destroy).pack(side="right")
        criar_botao_ttk_com_icone(
            botoes,
            texto="Salvar",
            nome_icone="save-outline",
            command=self._confirmar,
            estilo=estilos.salvar,
            cor_icone=estilos.icone_salvar,
            refs=self._refs_icones,
        ).pack(side="right", padx=(0, 8))
        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        centralizar_janela(self, parent)
        self.after_idle(lambda: _ajustar_janela_ao_conteudo(self))

    def _trocar_composicao(self):
        if self._pedir_troca is None:
            return

        def ao_escolher(composicao, _quantidade=1.0):
            self._composicao_trocada = composicao
            codigo = str(composicao.get("codigo") or "").strip()
            nome = str(composicao.get("nome") or "Composição")
            texto = f"{codigo} — {nome}" if codigo else nome
            self._rotulo_nome.configure(text=texto)

        self._pedir_troca(self, ao_escolher)

    def _confirmar(self):
        try:
            fatores = self.editor_fatores.obter()
            multiplicador = self.editor_fatores.obter_multiplicador()
        except ValueError:
            messagebox.showwarning("Item", "Coeficiente ou multiplicador inválido.", parent=self)
            return
        if self.on_confirmar:
            payload = {"fatores": fatores, "multiplicador": multiplicador}
            if self._composicao_trocada:
                payload["composicao"] = self._composicao_trocada
            self.on_confirmar(payload)
        self.destroy()


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
        self._etapas_ui: dict[str, dict] = {}

        self._cores = cores
        self.title("Configurar — Área Comum")
        aplicar_icone_janela(self)
        self.transient(parent)
        self.grab_set()
        try:
            altura_tela = max(480, int(self.winfo_screenheight()) - 100)
        except tk.TclError:
            altura_tela = 560
        altura = min(640, altura_tela)
        self.geometry(f"1220x{altura}")
        self.minsize(1020, min(480, altura))

        painel = tk.Frame(self, bg=fundo, padx=12, pady=8)
        painel.pack(fill="both", expand=True)
        painel.columnconfigure(0, weight=1)
        painel.rowconfigure(1, weight=1)

        tk.Label(
            painel,
            text="Configuração da Área Comum",
            font=("Arial", 12, "bold"),
            fg=cores.titulo,
            bg=fundo,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", pady=(0, 4))

        self.notebook = ttk.Notebook(painel)
        self.notebook.grid(row=1, column=0, sticky="nsew")

        aba_anom = tk.Frame(self.notebook, bg=fundo)
        self.notebook.add(aba_anom, text="Anomalias")
        self._montar_aba_anomalias(aba_anom, cores, estilos, fundo)
        for meta in ETAPAS_ORCAMENTO_FIXAS:
            aba = tk.Frame(self.notebook, bg=fundo)
            self.notebook.add(aba, text=meta["rotulo"])
            self._montar_aba_etapa_fixa(aba, meta["chave"], cores, estilos, fundo)

        rodape = tk.Frame(painel, bg=fundo)
        rodape.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        criar_botao_fechar(
            rodape, command=self._fechar, texto="Fechar sem salvar"
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

        self.bind("<Escape>", self._fechar)
        self.protocol("WM_DELETE_WINDOW", self._fechar)
        self._popular_lista()
        for meta in ETAPAS_ORCAMENTO_FIXAS:
            self._redesenhar_etapa_fixa(meta["chave"])
        self._snapshot = self._serializar_estado()
        self.update_idletasks()
        centralizar_janela(self, parent, largura=1220, altura=altura)

    def _montar_aba_anomalias(self, aba, cores, estilos, fundo):
        aba.columnconfigure(1, weight=1)
        aba.rowconfigure(0, weight=1)

        esquerda = tk.Frame(aba, bg=fundo, padx=8, pady=6)
        esquerda.grid(row=0, column=0, sticky="ns")
        esquerda.rowconfigure(0, weight=1)

        self.lista = tk.Listbox(
            esquerda,
            width=32,
            height=16,
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
        botoes_lista.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
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

        direita = tk.Frame(aba, bg=fundo, padx=8, pady=6)
        direita.grid(row=0, column=1, sticky="nsew")
        direita.columnconfigure(0, weight=1)
        direita.columnconfigure(1, weight=1)
        direita.rowconfigure(4, weight=1)

        linha_reparos = tk.Frame(direita, bg=fundo)
        linha_reparos.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        tk.Label(linha_reparos, text="Reparo:", bg=fundo, fg=cores.texto).pack(side="left")
        self.combo_reparo = ttk.Combobox(linha_reparos, state="readonly", width=36)
        self.combo_reparo.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self.combo_reparo.bind("<<ComboboxSelected>>", self._ao_trocar_reparo)
        criar_botao_ttk_com_icone(
            linha_reparos,
            texto="Novo",
            nome_icone="add-circle-outline",
            command=self._novo_reparo,
            estilo=estilos.compacto_adicionar,
            cor_icone=estilos.icone_adicionar,
            refs=self._refs_icones,
        ).pack(side="left", padx=(6, 0))
        criar_botao_ttk_com_icone(
            linha_reparos,
            texto="Renomear",
            nome_icone="pencil",
            command=self._renomear_reparo,
            estilo=estilos.compacto_editar,
            cor_icone=estilos.icone_editar,
            refs=self._refs_icones,
        ).pack(side="left", padx=(4, 0))
        criar_botao_ttk_com_icone(
            linha_reparos,
            texto="Excluir",
            nome_icone="trash-outline",
            command=self._excluir_reparo,
            estilo=estilos.compacto_excluir,
            cor_icone=estilos.icone_excluir,
            refs=self._refs_icones,
        ).pack(side="left", padx=(4, 0))

        self.frame_recomendado = tk.LabelFrame(
            direita,
            text="Reparo recomendado",
            bg=fundo,
            fg=cores.texto,
            padx=6,
            pady=4,
        )
        self.frame_recomendado.grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(0, 4)
        )
        linha_criterio = tk.Frame(self.frame_recomendado, bg=fundo)
        linha_criterio.pack(fill="x")
        tk.Label(linha_criterio, text="Depende de:", bg=fundo, fg=cores.texto).pack(
            side="left"
        )
        self.var_criterio = tk.StringVar(value="nenhum")
        for valor, texto in (
            ("nenhum", "Não depende"),
            (CRITERIO_ESTRUTURA, "Tipo de estrutura"),
            (CRITERIO_COBERTURA, "Tipo de cobertura"),
        ):
            ttk.Radiobutton(
                linha_criterio,
                text=texto,
                value=valor,
                variable=self.var_criterio,
                command=self._ao_mudar_criterio,
            ).pack(side="left", padx=(10, 0))
        self.grade_recomendado = tk.Frame(self.frame_recomendado, bg=fundo)
        self.grade_recomendado.columnconfigure(1, weight=1)
        self.grade_recomendado.columnconfigure(3, weight=1)
        self._combos_recomendado: dict[str, ttk.Combobox] = {}

        origem = tk.LabelFrame(
            direita, text="Origem", bg=fundo, fg=cores.texto, padx=6, pady=4
        )
        origem.grid(row=2, column=0, sticky="nsew", padx=(0, 4), pady=(0, 4))
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
            text="B. Etapa pré-definida",
            value=ORIGEM_ETAPA,
            variable=self.var_origem,
            command=self._ao_mudar_origem,
        ).pack(anchor="w")
        self.frame_etapa = tk.Frame(origem, bg=fundo)
        linha_etapa = tk.Frame(self.frame_etapa, bg=fundo)
        linha_etapa.pack(fill="x", pady=(2, 0))
        self.var_etapa_nome = tk.StringVar(value="Nenhuma etapa selecionada")
        tk.Label(
            linha_etapa,
            textvariable=self.var_etapa_nome,
            bg=fundo,
            fg=cores.texto,
            anchor="w",
            wraplength=280,
            justify="left",
        ).pack(side="left", fill="x", expand=True)
        criar_botao_ttk_com_icone(
            linha_etapa,
            texto="Escolher",
            nome_icone="search-outline",
            command=self._escolher_etapa,
            estilo=estilos.compacto,
            cor_icone=estilos.icone,
            refs=self._refs_icones,
        ).pack(side="left", padx=(4, 0))

        frame_titulo = tk.LabelFrame(
            direita,
            text="Título no orçamento",
            bg=fundo,
            fg=cores.texto,
            padx=6,
            pady=4,
        )
        frame_titulo.grid(row=2, column=1, sticky="nsew", padx=(4, 0), pady=(0, 4))
        self.combo_titulo = ttk.Combobox(
            frame_titulo,
            state="readonly",
            values=[rotulo for _chave, rotulo in ROTULOS_TITULO_ORCAMENTO],
        )
        self.combo_titulo.pack(fill="x")
        self.combo_titulo.set(rotulo_titulo_orcamento(""))
        self.combo_titulo.bind("<<ComboboxSelected>>", self._ao_trocar_titulo)
        self.var_titulo_personalizado = tk.StringVar()
        self.entrada_titulo = ttk.Entry(
            frame_titulo, textvariable=self.var_titulo_personalizado
        )
        self.var_titulo_personalizado.trace_add("write", lambda *_a: self._aplicar_reparo())

        frame_pct = tk.LabelFrame(
            direita,
            text="Percentuais da aba 1 alterados por este reparo",
            bg=fundo,
            fg=cores.texto,
            padx=6,
            pady=4,
        )
        frame_pct.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        for col in range(3):
            frame_pct.columnconfigure(col, weight=1)
        self.var_pct_aba1 = {}
        for indice, (chave, rotulo, *_resto) in enumerate(PERCENTUAIS_MODELO):
            var = tk.BooleanVar(value=False)
            self.var_pct_aba1[chave] = var
            ttk.Checkbutton(
                frame_pct,
                text=rotulo,
                variable=var,
                command=self._aplicar_reparo,
            ).grid(
                row=indice // 3,
                column=indice % 3,
                sticky="w",
                padx=(0, 8),
                pady=0,
            )

        colunas = ("codigo", "unidade", "formula")
        self.tree = ttk.Treeview(direita, columns=colunas, show="headings", height=6)
        self.tree.heading("codigo", text="Código")
        self.tree.heading("unidade", text="Unid.")
        self.tree.heading("formula", text="Fórmula (fatores)")
        self.tree.column("codigo", width=72, minwidth=64, stretch=False, anchor="center")
        self.tree.column("unidade", width=64, minwidth=52, stretch=False, anchor="center")
        self.tree.column("formula", width=380, stretch=True, anchor="w")
        self.tree.grid(row=4, column=0, columnspan=2, sticky="nsew")
        self.tree.bind("<Double-1>", lambda _e: self._editar_item())

        botoes_itens = tk.Frame(direita, bg=fundo)
        botoes_itens.grid(row=5, column=0, columnspan=2, sticky="e", pady=(6, 0))
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
            texto="Adicionar composição PRÓPRIA",
            nome_icone="add-circle-outline",
            command=self._adicionar_composicao,
            estilo=estilos.compacto_adicionar,
            cor_icone=estilos.icone_adicionar,
            refs=self._refs_icones,
        ).pack(side="left", padx=(4, 0))
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

    def _montar_aba_etapa_fixa(self, aba, chave: str, cores, estilos, fundo):
        meta = meta_etapa_fixa(chave) or {}
        rotulo = meta.get("rotulo") or chave
        nome_padrao = NOMES_ETAPAS_FIXAS.get(chave) or chave
        aba.columnconfigure(0, weight=1)
        aba.rowconfigure(1, weight=1)

        linha_nome = tk.Frame(aba, bg=fundo)
        linha_nome.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 6))
        tk.Label(linha_nome, text="Título no orçamento:", bg=fundo, fg=cores.texto).pack(
            side="left"
        )
        var_nome = tk.StringVar(value=nome_padrao)
        ttk.Entry(linha_nome, textvariable=var_nome).pack(
            side="left", fill="x", expand=True, padx=(8, 0)
        )
        var_nome.trace_add(
            "write", lambda *_a, c=chave: self._aplicar_etapa_fixa(c)
        )
        criar_botao_ttk_com_icone(
            linha_nome,
            texto="Importar etapa",
            nome_icone="cloud-download-outline",
            command=lambda c=chave: self._importar_etapa_fixa(c),
            estilo=estilos.compacto,
            cor_icone=estilos.icone,
            refs=self._refs_icones,
        ).pack(side="left", padx=(8, 0))

        colunas = ["tipo", "codigo", "unidade", "formula"]
        if chave == CHAVE_PINTURA:
            colunas.append("selador")
        tree = ttk.Treeview(aba, columns=colunas, show="headings", height=10)
        tree.heading("tipo", text="Tipo")
        tree.heading("codigo", text="Código")
        tree.heading("unidade", text="Unid.")
        tree.heading("formula", text="Fórmula (fatores)")
        tree.column("tipo", width=168, minwidth=148, stretch=False, anchor="w")
        tree.column("codigo", width=72, minwidth=64, stretch=False, anchor="center")
        tree.column("unidade", width=64, minwidth=52, stretch=False, anchor="center")
        tree.column("formula", width=280, stretch=True, anchor="w")
        if chave == CHAVE_PINTURA:
            tree.heading("selador", text="Fundo selador")
            tree.column("selador", width=110, minwidth=96, stretch=False, anchor="center")
            tree.bind(
                "<Button-1>",
                lambda e, c=chave: self._ao_clique_fundo_selador(e, c),
            )
        tree.grid(row=1, column=0, sticky="nsew", padx=10)
        tree.bind(
            "<Double-1>",
            lambda e, c=chave: self._ao_duplo_item_etapa_fixa(e, c),
        )

        botoes = tk.Frame(aba, bg=fundo)
        botoes.grid(row=2, column=0, sticky="e", padx=10, pady=(6, 8))
        criar_botao_ttk_com_icone(
            botoes,
            texto="Adicionar item SINAPI",
            nome_icone="add-circle-outline",
            command=lambda c=chave: self._adicionar_item_etapa_sinapi(c),
            estilo=estilos.compacto_adicionar,
            cor_icone=estilos.icone_adicionar,
            refs=self._refs_icones,
        ).pack(side="left")
        criar_botao_ttk_com_icone(
            botoes,
            texto="Adicionar composição PRÓPRIA",
            nome_icone="add-circle-outline",
            command=lambda c=chave: self._adicionar_item_etapa_propria(c),
            estilo=estilos.compacto_adicionar,
            cor_icone=estilos.icone_adicionar,
            refs=self._refs_icones,
        ).pack(side="left", padx=(4, 0))
        criar_botao_ttk_com_icone(
            botoes,
            texto="Editar",
            nome_icone="pencil",
            command=lambda c=chave: self._editar_item_etapa_fixa(c),
            estilo=estilos.compacto_editar,
            cor_icone=estilos.icone_editar,
            refs=self._refs_icones,
        ).pack(side="left", padx=4)
        criar_botao_ttk_com_icone(
            botoes,
            texto="Remover item",
            nome_icone="remove-circle-outline",
            command=lambda c=chave: self._remover_item_etapa_fixa(c),
            estilo=estilos.compacto_excluir,
            cor_icone=estilos.icone_excluir,
            refs=self._refs_icones,
        ).pack(side="left")

        self._etapas_ui[chave] = {
            "var_nome": var_nome,
            "tree": tree,
            "nome_padrao": nome_padrao,
            "rotulo": rotulo,
        }

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
        nomes = sorted(self._anomalias().keys(), key=_ordem_alfabetica)
        for nome in nomes:
            self.lista.insert("end", nome)
        if not nomes:
            self._nome_atual = None
            self._reparo_atual_id = None
            self._redesenhar_reparo(None)
            self._redesenhar_recomendacao()
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
        self._redesenhar_recomendacao()

    def _nome_exibido_reparo(self, reparo, indice: int) -> str:
        return str(reparo.get("nome") or f"Reparo {indice + 1}")

    def _redesenhar_recomendacao(self):
        self._carregando = True
        try:
            for filho in self.grade_recomendado.winfo_children():
                filho.destroy()
            self._combos_recomendado = {}
            anomalia = (
                self._anomalias().get(self._nome_atual) if self._nome_atual else None
            )
            rec = (anomalia or {}).get("recomendacao") or recomendacao_vazia()
            criterio = str(rec.get("criterio") or "")
            if criterio not in (CRITERIO_ESTRUTURA, CRITERIO_COBERTURA):
                criterio = ""
            self.var_criterio.set(criterio or "nenhum")
            opcoes = opcoes_do_criterio(criterio)
            if not opcoes:
                self.grade_recomendado.pack_forget()
                return
            self.grade_recomendado.pack(fill="x", pady=(6, 0))
            reparos = self._reparos_atuais()
            nomes = [self._nome_exibido_reparo(r, i) for i, r in enumerate(reparos)]
            por_id = {str(r.get("id") or ""): nomes[i] for i, r in enumerate(reparos)}
            por_opcao = rec.get("por_opcao") or {}
            fundo = self.frame_recomendado.cget("bg")
            for indice, opcao in enumerate(opcoes):
                linha, coluna = divmod(indice, 2)
                rotulo = tk.Label(
                    self.grade_recomendado,
                    text=opcao,
                    bg=fundo,
                    fg=self._cores.texto,
                    anchor="w",
                )
                rotulo.grid(
                    row=linha, column=coluna * 2, sticky="w", padx=(0, 6), pady=2
                )
                combo = ttk.Combobox(
                    self.grade_recomendado,
                    state="readonly",
                    values=("—", *nomes),
                    width=28,
                )
                combo.grid(
                    row=linha, column=coluna * 2 + 1, sticky="ew", padx=(0, 12), pady=2
                )
                escolhido = por_id.get(str(por_opcao.get(opcao) or ""), "—")
                combo.set(escolhido if escolhido in ("—", *nomes) else "—")
                combo.bind(
                    "<<ComboboxSelected>>",
                    lambda _e, chave=opcao: self._ao_escolher_recomendado(chave),
                )
                self._combos_recomendado[opcao] = combo
        finally:
            self._carregando = False

    def _ao_mudar_criterio(self):
        if self._carregando or not self._nome_atual:
            return
        anomalia = self._anomalias()[self._nome_atual]
        rec = anomalia.setdefault("recomendacao", recomendacao_vazia())
        novo = self.var_criterio.get()
        if novo not in (CRITERIO_ESTRUTURA, CRITERIO_COBERTURA):
            novo = ""
        if rec.get("criterio") == novo:
            return
        rec["criterio"] = novo
        rec["por_opcao"] = {}
        self._redesenhar_recomendacao()

    def _ao_escolher_recomendado(self, opcao: str):
        if self._carregando or not self._nome_atual:
            return
        combo = self._combos_recomendado.get(opcao)
        if combo is None:
            return
        nome = combo.get()
        reparo_id = ""
        if nome and nome != "—":
            for indice, reparo in enumerate(self._reparos_atuais()):
                if self._nome_exibido_reparo(reparo, indice) == nome:
                    reparo_id = str(reparo.get("id") or "")
                    break
        rec = self._anomalias()[self._nome_atual].setdefault(
            "recomendacao", recomendacao_vazia()
        )
        por_opcao = rec.setdefault("por_opcao", {})
        if reparo_id:
            por_opcao[opcao] = reparo_id
        else:
            por_opcao.pop(opcao, None)

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
                self.combo_titulo.set(rotulo_titulo_orcamento(""))
                self.var_titulo_personalizado.set("")
                for var in self.var_pct_aba1.values():
                    var.set(False)
                self._mostrar_origem()
                self._mostrar_titulo_personalizado()
                return
            self._hidratar_itens_etapa_se_vazio(reparo)
            self.var_origem.set(reparo.get("origem") or ORIGEM_ITENS)
            nome_etapa = reparo.get("etapa_nome") or "Nenhuma etapa selecionada"
            self.var_etapa_nome.set(nome_etapa)
            self.combo_titulo.set(rotulo_titulo_orcamento(reparo.get("titulo_orcamento")))
            self.var_titulo_personalizado.set(reparo.get("titulo_personalizado") or "")
            selecionados = set(reparo.get("percentuais_aba1") or [])
            for chave, var in self.var_pct_aba1.items():
                var.set(chave in selecionados)
            for item in reparo.get("itens") or []:
                codigo = item.get("codigo_sinapi") or item.get("codigo") or ""
                formula = rotulo_fatores(item)
                self.tree.insert(
                    "",
                    "end",
                    iid=item.get("id"),
                    values=(
                        codigo,
                        item.get("unidade", ""),
                        formula,
                    ),
                )
            self._mostrar_origem()
            self._mostrar_titulo_personalizado()
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
        reparo = self._reparo_atual()
        if reparo and self.var_origem.get() == ORIGEM_ETAPA:
            if self._hidratar_itens_etapa_se_vazio(reparo):
                self._redesenhar_reparo(reparo)

    def _ao_trocar_titulo(self, _event=None):
        self._mostrar_titulo_personalizado()
        self._aplicar_reparo()

    def _mostrar_titulo_personalizado(self):
        fonte = chave_titulo_orcamento(self.combo_titulo.get())
        if fonte == TITULO_PERSONALIZADO:
            if not self.entrada_titulo.winfo_ismapped():
                self.entrada_titulo.pack(fill="x", pady=(6, 0))
        else:
            self.entrada_titulo.pack_forget()

    def _hidratar_itens_etapa_se_vazio(self, reparo) -> bool:
        if not reparo or reparo.get("origem") != ORIGEM_ETAPA:
            return False
        if reparo.get("itens"):
            return False
        etapa_id = str(reparo.get("etapa_predefinida_id") or "")
        if not etapa_id:
            return False
        etapa = next(
            (item for item in _listar_etapas() if str(item.get("id") or "") == etapa_id),
            None,
        )
        if not etapa:
            return False
        reparo["itens"] = itens_sinapi_da_etapa(
            etapa,
            tipo_calculo_padrao=reparo.get("tipo_calculo_etapa") or "fixo",
        )
        return True

    def _aplicar_reparo(self):
        if self._carregando:
            return
        reparo = self._reparo_atual()
        if not reparo or not self._nome_atual:
            return
        reparo["origem"] = self.var_origem.get()
        reparo["titulo_orcamento"] = chave_titulo_orcamento(self.combo_titulo.get())
        reparo["titulo_personalizado"] = self.var_titulo_personalizado.get().strip()
        reparo["percentuais_aba1"] = [
            chave for chave, var in self.var_pct_aba1.items() if var.get()
        ]
        for item in self._anomalias()[self._nome_atual]["reparos"]:
            if item.get("id") == reparo["id"]:
                item.update(reparo)
                break

    def _novo_reparo(self):
        if not self._nome_atual:
            return
        self._aplicar_reparo()
        nome = perguntar_texto(self, "Novo reparo", "Nome do reparo (ex.: Piso cerâmico):")
        if not nome or not nome.strip():
            return
        reparo = novo_reparo(nome=nome.strip())
        self._anomalias()[self._nome_atual].setdefault("reparos", []).append(reparo)
        self._reparo_atual_id = reparo["id"]
        self._atualizar_combo_reparos()
        self._redesenhar_reparo(reparo)
        self._redesenhar_recomendacao()

    def _renomear_reparo(self):
        if not self._nome_atual:
            return
        reparo = self._reparo_atual()
        if not reparo:
            return
        atual = str(reparo.get("nome") or "Reparo padrão")
        novo = perguntar_texto(
            self,
            "Renomear reparo",
            "Novo nome do reparo:",
            valor_inicial=atual,
        )
        if not novo or not str(novo).strip():
            return
        novo = str(novo).strip()
        if novo == atual:
            return
        duplicado = any(
            str(item.get("nome") or "").strip() == novo
            for item in self._reparos_atuais()
            if item.get("id") != reparo.get("id")
        )
        if duplicado:
            messagebox.showwarning(
                "Reparo",
                "Já existe um reparo com esse nome nesta anomalia.",
                parent=self,
            )
            return
        reparo["nome"] = novo
        self._atualizar_combo_reparos()
        self._redesenhar_recomendacao()

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
        removido = self._reparo_atual_id
        self._anomalias()[self._nome_atual]["reparos"] = [
            r for r in reparos if r.get("id") != removido
        ]
        rec = self._anomalias()[self._nome_atual].setdefault(
            "recomendacao", recomendacao_vazia()
        )
        rec["por_opcao"] = {
            opcao: reparo_id
            for opcao, reparo_id in (rec.get("por_opcao") or {}).items()
            if reparo_id != removido
        }
        self._reparo_atual_id = self._anomalias()[self._nome_atual]["reparos"][0]["id"]
        self._atualizar_combo_reparos()
        self._redesenhar_reparo(self._reparo_atual())
        self._redesenhar_recomendacao()

    def _escolher_etapa(self):
        self._aplicar_reparo()

        def ao_escolher(etapa):
            reparo = self._reparo_atual()
            if not reparo:
                return
            reparo["etapa_predefinida_id"] = etapa.get("id") or ""
            reparo["etapa_nome"] = etapa.get("nome") or ""
            reparo["origem"] = ORIGEM_ETAPA
            reparo["itens"] = itens_sinapi_da_etapa(
                etapa,
                itens_atuais=reparo.get("itens") or [],
                tipo_calculo_padrao=reparo.get("tipo_calculo_etapa") or "fixo",
            )
            self.var_origem.set(ORIGEM_ETAPA)
            self.var_etapa_nome.set(reparo["etapa_nome"])
            self._aplicar_reparo()
            self._redesenhar_reparo(reparo)

        DialogoSelecionarEtapaPredefinida(self, ao_escolher)

    def _adicionar_item(self):
        reparo = self._reparo_atual()
        if not reparo:
            return

        def ao_confirmar(item):
            item["da_etapa"] = False
            reparo.setdefault("itens", []).append(item)
            self._redesenhar_reparo(reparo)

        DialogoItemSinapiAreaComum(self, on_confirmar=ao_confirmar, ctx=self.ctx)

    def _adicionar_composicao(self):
        reparo = self._reparo_atual()
        if not reparo:
            return

        def ao_escolher(composicao, _quantidade=1.0):
            item = novo_item_composicao_propria(
                composicao_catalogo_id=composicao.get("id"),
                codigo=composicao.get("codigo"),
                nome=composicao.get("nome"),
                unidade=composicao.get("unidade") or "un",
                tipo_calculo="fixo",
                coeficiente=1,
                da_etapa=False,
            )
            reparo.setdefault("itens", []).append(item)
            self._redesenhar_reparo(reparo)

        self._pedir_composicao_propria(ao_escolher)

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
        if str(atual.get("tipo") or "") == TIPO_ITEM_CATALOGO_PROPRIA:
            self._editar_composicao_item(
                atual,
                ao_aplicar=lambda: self._redesenhar_reparo(reparo),
            )
            return

        def ao_confirmar(item):
            item["id"] = item_id
            item["da_etapa"] = bool(atual.get("da_etapa"))
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

    def _etapa_fixa(self, chave: str) -> dict:
        atual = normalizar_etapa_orcamento_fixa(self._dados.get(chave), chave)
        self._dados[chave] = atual
        return atual

    def _ui_etapa_fixa(self, chave: str) -> dict:
        return self._etapas_ui.get(chave) or {}

    def _aplicar_etapa_fixa(self, chave: str):
        if self._carregando:
            return
        ui = self._ui_etapa_fixa(chave)
        etapa = self._etapa_fixa(chave)
        nome_padrao = ui.get("nome_padrao") or NOMES_ETAPAS_FIXAS.get(chave) or chave
        var_nome = ui.get("var_nome")
        texto = var_nome.get() if var_nome is not None else ""
        etapa["nome"] = (texto or "").strip() or nome_padrao

    def _redesenhar_etapa_fixa(self, chave: str):
        ui = self._ui_etapa_fixa(chave)
        tree = ui.get("tree")
        var_nome = ui.get("var_nome")
        if tree is None or var_nome is None:
            return
        self._carregando = True
        try:
            semear_etapas_orcamento_fixas(self._dados)
            etapa = self._etapa_fixa(chave)
            nome_padrao = ui.get("nome_padrao") or NOMES_ETAPAS_FIXAS.get(chave) or chave
            var_nome.set(etapa.get("nome") or nome_padrao)
            tree.delete(*tree.get_children())
            sinapi = getattr(self.ctx, "sinapi", None) if self.ctx is not None else None
            for item in etapa.get("itens") or []:
                tipo = str(item.get("tipo") or TIPO_ITEM_CATALOGO_SINAPI)
                if tipo == TIPO_ITEM_CATALOGO_PROPRIA:
                    codigo = item.get("codigo") or ""
                else:
                    codigo = item.get("codigo_sinapi") or item.get("codigo") or ""
                valores = [
                    rotulo_tipo_item_catalogo(item, sinapi),
                    codigo,
                    item.get("unidade") or "",
                    rotulo_fatores(item),
                ]
                if chave == CHAVE_PINTURA:
                    valores.append("Sim" if item.get("fundo_selador") else "—")
                tree.insert("", "end", iid=item.get("id"), values=valores)
        finally:
            self._carregando = False

    def _importar_etapa_fixa(self, chave: str):
        self._aplicar_etapa_fixa(chave)
        nome_padrao = (
            self._ui_etapa_fixa(chave).get("nome_padrao")
            or NOMES_ETAPAS_FIXAS.get(chave)
            or chave
        )

        def ao_escolher(etapa_predef):
            etapa = self._etapa_fixa(chave)
            etapa["itens"] = itens_servicos_da_etapa(
                etapa_predef,
                itens_atuais=etapa.get("itens") or [],
                tipo_calculo_padrao="fixo",
            )
            if not (etapa.get("nome") or "").strip() or etapa.get("nome") == nome_padrao:
                etapa["nome"] = etapa_predef.get("nome") or nome_padrao
            self._redesenhar_etapa_fixa(chave)

        DialogoSelecionarEtapaPredefinida(self, ao_escolher)

    def _adicionar_item_etapa_sinapi(self, chave: str):
        etapa = self._etapa_fixa(chave)

        def ao_confirmar(item):
            item["da_etapa"] = False
            item["tipo"] = TIPO_ITEM_CATALOGO_SINAPI
            etapa.setdefault("itens", []).append(item)
            self._redesenhar_etapa_fixa(chave)

        DialogoItemSinapiAreaComum(self, on_confirmar=ao_confirmar, ctx=self.ctx)

    def _pedir_composicao_propria(
        self,
        ao_escolher,
        *,
        parent=None,
        titulo="Adicionar composição própria",
        texto_confirmar="Usar composição",
    ):
        from ui.orcamento_customizado import DialogoBuscaComposicaoPropria

        try:
            from core.composicoes_proprias_storage import listar as listar_composicoes

            catalogo = listar_composicoes()
        except (ValueError, OSError, TypeError):
            catalogo = []
        if not catalogo:
            messagebox.showinfo(
                "Composição própria",
                "Nenhuma composição cadastrada.",
                parent=parent or self,
            )
            return
        estados = self.ctx.obter_estados() if self.ctx is not None else []
        DialogoBuscaComposicaoPropria(
            parent or self,
            self.ctx,
            catalogo,
            estados[0] if estados else "",
            ao_escolher,
            mostrar_quantidade=False,
            titulo=titulo,
            texto_confirmar=texto_confirmar,
        )

    def _editar_composicao_item(self, atual, *, ao_aplicar):
        def ao_confirmar_calc(valores):
            fatores = normalizar_fatores(valores.get("fatores") or valores)
            atual["fatores"] = fatores
            atual["tipo_calculo"] = fatores[0]["tipo_calculo"]
            atual["coeficiente"] = fatores[0]["coeficiente"]
            atual["multiplicador"] = valores.get("multiplicador", 1)
            composicao = valores.get("composicao")
            if composicao:
                atual["composicao_catalogo_id"] = str(composicao.get("id") or "").strip()
                atual["codigo"] = str(composicao.get("codigo") or "").strip()
                atual["nome"] = str(composicao.get("nome") or "").strip()
                if composicao.get("unidade"):
                    atual["unidade"] = str(composicao.get("unidade")).strip()
            ao_aplicar()

        def pedir_troca(dialogo, ao_escolher):
            self._pedir_composicao_propria(
                ao_escolher,
                parent=dialogo,
                titulo="Trocar composição própria",
                texto_confirmar="Usar composição",
            )

        DialogoCoefCalculoItem(
            self,
            item=atual,
            on_confirmar=ao_confirmar_calc,
            titulo="Editar composição",
            pedir_troca=pedir_troca,
        )

    def _adicionar_item_etapa_propria(self, chave: str):
        etapa = self._etapa_fixa(chave)

        def ao_escolher(composicao, _quantidade=1.0):
            item = novo_item_composicao_propria(
                composicao_catalogo_id=composicao.get("id"),
                codigo=composicao.get("codigo"),
                nome=composicao.get("nome"),
                unidade=composicao.get("unidade") or "un",
                tipo_calculo="fixo",
                coeficiente=1,
                da_etapa=False,
            )
            etapa.setdefault("itens", []).append(item)
            self._redesenhar_etapa_fixa(chave)

        self._pedir_composicao_propria(ao_escolher)

    def _ao_clique_fundo_selador(self, event, chave: str):
        if chave != CHAVE_PINTURA:
            return
        tree = self._ui_etapa_fixa(chave).get("tree")
        if tree is None or tree.identify_region(event.x, event.y) != "cell":
            return
        if tree.identify_column(event.x) != "#5":
            return
        item_id = tree.identify_row(event.y)
        if not item_id:
            return
        etapa = self._etapa_fixa(chave)
        atual = next(
            (i for i in etapa.get("itens") or [] if i.get("id") == item_id), None
        )
        if atual is None:
            return
        _definir_fundo_selador(atual, not bool(atual.get("fundo_selador")))
        self._redesenhar_etapa_fixa(chave)
        if tree.exists(item_id):
            tree.selection_set(item_id)
            tree.focus(item_id)
        return "break"

    def _ao_duplo_item_etapa_fixa(self, event, chave: str):
        tree = self._ui_etapa_fixa(chave).get("tree")
        if (
            chave == CHAVE_PINTURA
            and tree is not None
            and tree.identify_column(event.x) == "#5"
        ):
            return "break"
        self._editar_item_etapa_fixa(chave)

    def _editar_item_etapa_fixa(self, chave: str):
        etapa = self._etapa_fixa(chave)
        tree = self._ui_etapa_fixa(chave).get("tree")
        if tree is None:
            return
        selecao = tree.selection()
        if not selecao:
            return
        item_id = selecao[0]
        atual = next(
            (i for i in etapa.get("itens") or [] if i.get("id") == item_id), None
        )
        if atual is None:
            return
        tipo = str(atual.get("tipo") or TIPO_ITEM_CATALOGO_SINAPI)
        if tipo == TIPO_ITEM_CATALOGO_PROPRIA:
            self._editar_composicao_item(
                atual,
                ao_aplicar=lambda: self._redesenhar_etapa_fixa(chave),
            )
            return

        def ao_confirmar(item):
            item["id"] = item_id
            item["da_etapa"] = bool(atual.get("da_etapa"))
            _definir_fundo_selador(item, atual.get("fundo_selador"))
            item["tipo"] = TIPO_ITEM_CATALOGO_SINAPI
            for i, existente in enumerate(etapa["itens"]):
                if existente.get("id") == item_id:
                    etapa["itens"][i] = item
                    break
            self._redesenhar_etapa_fixa(chave)

        DialogoItemSinapiAreaComum(
            self, item=atual, on_confirmar=ao_confirmar, ctx=self.ctx
        )

    def _remover_item_etapa_fixa(self, chave: str):
        etapa = self._etapa_fixa(chave)
        tree = self._ui_etapa_fixa(chave).get("tree")
        if tree is None:
            return
        selecao = tree.selection()
        if not selecao:
            return
        item_id = selecao[0]
        etapa["itens"] = [i for i in etapa.get("itens") or [] if i.get("id") != item_id]
        self._redesenhar_etapa_fixa(chave)

    def _serializar_estado(self) -> str:
        self._aplicar_reparo()
        for meta in ETAPAS_ORCAMENTO_FIXAS:
            self._aplicar_etapa_fixa(meta["chave"])
        return json.dumps(
            normalizar_catalogo(self._dados),
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )

    def _fechar(self, _event=None):
        if self._serializar_estado() != getattr(self, "_snapshot", ""):
            if not messagebox.askyesno(
                "Configurar",
                "Fechar sem salvar as alterações?",
                parent=self,
            ):
                return "break"
        self.destroy()
        return "break"

    def _salvar(self):
        self._aplicar_reparo()
        for meta in ETAPAS_ORCAMENTO_FIXAS:
            chave = meta["chave"]
            self._aplicar_etapa_fixa(chave)
            self._dados[chave] = normalizar_etapa_orcamento_fixa(
                self._dados.get(chave) or nova_etapa_orcamento_fixa(chave),
                chave,
            )
        try:
            salvar_catalogo(self._dados)
        except OSError as exc:
            messagebox.showerror("Salvar", f"Não foi possível gravar:\n{exc}", parent=self)
            return
        if self.on_salvo:
            self.on_salvo()
        self._snapshot = self._serializar_estado()
        messagebox.showinfo("Configurar", "Catálogo salvo.", parent=self)
