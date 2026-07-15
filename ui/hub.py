import tkinter as tk
from tkinter import ttk

from core.api_client import get_client
from ui.dialogo_configuracoes import abrir_dialogo_configuracoes
from ui.icones import criar_icone_svg
from ui.widgets import (
    COR_BORDA_PADRAO,
    COR_FUNDO_CARTAO,
    COR_TITULO_PADRAO,
    aplicar_hover_cartao,
)

LARGURA_CARTAO = 240
ALTURA_CARTAO = 148
FONTE_TITULO_CARTAO = ("Arial", 12, "bold")
ALTURA_ICONE_CARTAO = 20


class HubFrame(tk.Frame):
    def __init__(self, parent, ctx, on_selecionar_modulo, on_logout=None):
        super().__init__(parent, bg="#ececec")
        self.ctx = ctx
        self.on_selecionar_modulo = on_selecionar_modulo
        self.on_logout = on_logout
        self._cache_icones = {}
        self._refs_icones = []
        self._montar()

    def _montar(self):
        container = tk.Frame(self, bg="#ececec")
        container.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(
            container,
            text="ORC",
            font=("Arial", 22, "bold"),
            fg="#006699",
            bg="#ececec",
        ).pack(pady=(0, 4))

        tk.Label(
            container,
            text="Orçamentos de Reparos Construtivos",
            font=("Arial", 11),
            fg="#444444",
            bg="#ececec",
        ).pack(pady=(0, 24))

        cartoes = tk.Frame(container, bg="#ececec")
        cartoes.pack()
        for col in range(3):
            cartoes.columnconfigure(col, weight=1, uniform="cartao_hub")

        self._criar_cartao(
            cartoes,
            titulo="Área Privativa",
            descricao="Orçamento de reparos em unidades autônomas",
            modulo="area_privativa",
            habilitado=True,
            coluna=0,
            linha=0,
            icone_titulo="construct-outline",
        )
        self._criar_cartao(
            cartoes,
            titulo="Área Comum",
            descricao="Orçamento de reparos em áreas comuns, com a opção de composições próprias",
            modulo="area_comum",
            habilitado=False,
            coluna=1,
            linha=0,
            aviso="Em breve",
            icone_titulo="construct-outline",
        )
        self._criar_cartao(
            cartoes,
            titulo="Consulta SINAPI",
            descricao="Pesquisar composições e preços da base",
            modulo="consulta_sinapi",
            habilitado=True,
            coluna=2,
            linha=0,
            icone_titulo="search-outline",
        )
        self._criar_cartao(
            cartoes,
            titulo="Orçamento\nCustomizado",
            descricao="Montar orçamento com Etapas e Itens personalizados",
            modulo="orcamento_customizado",
            habilitado=True,
            coluna=0,
            linha=1,
            icone_titulo="construct-outline",
        )
        self._criar_cartao(
            cartoes,
            titulo="Configurar\nComposições Próprias",
            descricao="Cadastre composições com insumos/composições SINAPI ou de mercado",
            modulo="composicoes_proprias",
            habilitado=True,
            coluna=1,
            linha=1,
            icone_titulo="cog-outline",
        )
        self._criar_cartao(
            cartoes,
            titulo="Configurar\nEtapas pré-definidas",
            descricao="Configure modelos de Etapas que já virão com itens SINAPI e composições próprias",
            modulo="etapas_predefinidas",
            habilitado=True,
            coluna=2,
            linha=1,
            icone_titulo="cog-outline",
        )

        self._montar_botoes_rodape()

    def _montar_botoes_rodape(self):
        icone_cfg = criar_icone_svg(
            self,
            "settings-outline",
            altura=16,
            cor="#006699",
        )
        self._refs_icones.append(icone_cfg)

        btn_cfg = ttk.Button(
            self,
            text="Configurações",
            image=icone_cfg,
            compound="left",
            command=self._abrir_configuracoes,
            style="Compact.TButton",
        )
        btn_cfg.place(relx=1.0, rely=1.0, anchor="se", x=-14, y=-10)

        if self.on_logout is not None:
            rodape_usuario = tk.Frame(self, bg="#ececec")
            rodape_usuario.place(relx=0.0, rely=1.0, anchor="sw", x=14, y=-10)

            icone_logout = criar_icone_svg(
                self,
                "log-out-outline",
                altura=16,
                cor="#c62828",
            )
            self._refs_icones.append(icone_logout)
            btn_logout = ttk.Button(
                rodape_usuario,
                text="Logout",
                image=icone_logout,
                compound="left",
                command=self._logout,
                style="Delete.Compact.TButton",
            )
            btn_logout.pack(side="left")

            icone_person = criar_icone_svg(
                self,
                "person",
                altura=16,
                cor="#555555",
            )
            self._refs_icones.append(icone_person)
            tk.Label(rodape_usuario, image=icone_person, bg="#ececec").pack(
                side="left", padx=(10, 4)
            )
            usuario = get_client().username or "—"
            tk.Label(
                rodape_usuario,
                text=usuario,
                font=("Arial", 9),
                fg="#555555",
                bg="#ececec",
            ).pack(side="left")

    def _abrir_configuracoes(self):
        janela = self.winfo_toplevel()
        abrir_dialogo_configuracoes(janela, self.ctx)

    def _logout(self):
        if self.on_logout is not None:
            self.on_logout()

    def _criar_cartao(
        self,
        parent,
        titulo,
        descricao,
        modulo,
        habilitado,
        coluna,
        linha=0,
        aviso=None,
        icone_titulo=None,
    ):
        largura = LARGURA_CARTAO
        altura = ALTURA_CARTAO
        cor_fundo = COR_FUNDO_CARTAO if habilitado else "#f0f0f0"
        cor_borda = COR_BORDA_PADRAO if habilitado else "#cccccc"
        cor_titulo = COR_TITULO_PADRAO if habilitado else "#999999"
        cor_texto = "#555555" if habilitado else "#aaaaaa"

        cartao = tk.Frame(
            parent,
            width=largura,
            height=altura,
            bg=cor_fundo,
            highlightbackground=cor_borda,
            highlightthickness=2,
            cursor="hand2" if habilitado else "arrow",
        )
        cartao.grid(row=linha, column=coluna, padx=12, pady=4, sticky="n")
        cartao.grid_propagate(False)
        cartao.rowconfigure(1, weight=1)
        cartao.columnconfigure(0, weight=1)

        filhos = []

        lbl_titulo = tk.Label(
            cartao,
            text=titulo,
            font=FONTE_TITULO_CARTAO,
            fg=cor_titulo,
            bg=cor_fundo,
            wraplength=largura - 28,
            justify="center",
        )
        lbl_titulo.grid(row=0, column=0, pady=(16, 4), sticky="n")
        filhos.append(lbl_titulo)

        lbl_desc = tk.Label(
            cartao,
            text=descricao,
            font=("Arial", 9),
            fg=cor_texto,
            bg=cor_fundo,
            wraplength=largura - 28,
            justify="center",
        )
        lbl_desc.grid(row=1, column=0, padx=14, sticky="n")
        filhos.append(lbl_desc)

        rodape = tk.Frame(cartao, bg=cor_fundo)
        rodape.grid(row=2, column=0, sticky="sew", padx=10, pady=(4, 10))
        filhos.append(rodape)

        texto_aviso = aviso if aviso else ""
        lbl_aviso = tk.Label(
            rodape,
            text=texto_aviso,
            font=("Arial", 8, "italic"),
            fg="#999999" if aviso else cor_fundo,
            bg=cor_fundo,
            height=1,
        )
        lbl_aviso.pack(side="left", fill="x", expand=True)
        filhos.append(lbl_aviso)

        if icone_titulo:
            icone = self._icone_cartao(icone_titulo, cor_titulo)
            lbl_icone = tk.Label(rodape, image=icone, bg=cor_fundo)
            lbl_icone.pack(side="right", padx=(6, 0))
            filhos.append(lbl_icone)

        if habilitado:
            def ao_clicar(_event=None, mod=modulo):
                self.on_selecionar_modulo(mod)

            cartao.bind("<Button-1>", ao_clicar)
            for filho in filhos:
                filho.bind("<Button-1>", ao_clicar)

            aplicar_hover_cartao(cartao, filhos)

    def _icone_cartao(self, nome: str, cor: str) -> tk.PhotoImage:
        chave = (nome, ALTURA_ICONE_CARTAO, cor)
        if chave not in self._cache_icones:
            self._cache_icones[chave] = criar_icone_svg(
                self,
                nome,
                altura=ALTURA_ICONE_CARTAO,
                cor=cor,
            )
        return self._cache_icones[chave]
