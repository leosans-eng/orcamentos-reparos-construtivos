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
FONTE_CATEGORIA = ("Segoe UI", 11, "bold")
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
        faixa = tk.Frame(self, bg=COR_TITULO_PADRAO, height=6)
        faixa.pack(fill="x")
        faixa.pack_propagate(False)

        # Área expansível: em tela cheia o conteúdo permanece centralizado e com respiro.
        area = tk.Frame(self, bg="#ececec")
        area.pack(fill="both", expand=True, padx=24, pady=(16, 48))

        container = tk.Frame(area, bg="#ececec")
        container.place(relx=0.5, rely=0.45, anchor="center")

        tk.Label(
            container,
            text="ORC",
            font=("Segoe UI", 22, "bold"),
            fg="#006699",
            bg="#ececec",
        ).pack(pady=(0, 4))

        tk.Label(
            container,
            text="Orçamentos de Reparos Construtivos",
            font=("Segoe UI", 11),
            fg="#444444",
            bg="#ececec",
        ).pack(pady=(0, 20))

        destaque = tk.Frame(
            container,
            bg="#e2eef3",
            highlightbackground="#b7cdd8",
            highlightthickness=1,
        )
        destaque.pack(fill="x", pady=(0, 22), padx=0)
        interno = tk.Frame(destaque, bg="#e2eef3")
        interno.pack(fill="x", padx=14, pady=(10, 12))
        self._montar_secao(
            interno,
            "Orçamentos",
            [
                {
                    "titulo": "Orçamento\nCustomizado",
                    "descricao": "Montar orçamento com Etapas e Itens personalizados",
                    "modulo": "orcamento_customizado",
                    "habilitado": True,
                    "icone_titulo": "construct-outline",
                },
                {
                    "titulo": "Área Privativa",
                    "descricao": "Orçamento de reparos em unidades autônomas",
                    "modulo": "area_privativa",
                    "habilitado": True,
                    "icone_titulo": "construct-outline",
                },
                {
                    "titulo": "Área Comum",
                    "descricao": (
                        "Orçamento de reparos em áreas comuns, "
                        "com a opção de composições próprias"
                    ),
                    "modulo": "area_comum",
                    "habilitado": False,
                    "aviso": "Em breve",
                    "icone_titulo": "construct-outline",
                },
            ],
            pady_abaixo=0,
            cor_fundo="#e2eef3",
        )

        inferior = tk.Frame(container, bg="#ececec")
        inferior.pack(fill="x")
        inferior.columnconfigure(0, weight=1)
        inferior.columnconfigure(1, weight=0)

        cadastros = tk.Frame(inferior, bg="#ececec")
        cadastros.grid(row=0, column=0, sticky="nw", padx=(0, 28))
        self._montar_secao(
            cadastros,
            "Configurar cadastros",
            [
                {
                    "titulo": "Configurar\nComposições Próprias",
                    "descricao": (
                        "Cadastre composições com insumos/composições "
                        "SINAPI ou de mercado"
                    ),
                    "modulo": "composicoes_proprias",
                    "habilitado": True,
                    "icone_titulo": "cog-outline",
                },
                {
                    "titulo": "Configurar\nEtapas pré-definidas",
                    "descricao": (
                        "Configure modelos de Etapas que já virão com "
                        "itens SINAPI e composições próprias"
                    ),
                    "modulo": "etapas_predefinidas",
                    "habilitado": True,
                    "icone_titulo": "cog-outline",
                },
            ],
            pady_abaixo=0,
        )

        consulta = tk.Frame(inferior, bg="#ececec")
        consulta.grid(row=0, column=1, sticky="nw")
        self._montar_secao(
            consulta,
            "Consulta",
            [
                {
                    "titulo": "Consulta SINAPI",
                    "descricao": "Pesquisar composições e preços da base",
                    "modulo": "consulta_sinapi",
                    "habilitado": True,
                    "icone_titulo": "search-outline",
                },
            ],
            pady_abaixo=0,
        )

        self._montar_botoes_rodape()

    def _montar_secao(
        self, parent, titulo, cartoes, *, pady_abaixo=16, cor_fundo="#ececec"
    ):
        secao = tk.Frame(parent, bg=cor_fundo)
        secao.pack(fill="x", pady=(0, pady_abaixo))

        cabecalho = tk.Frame(secao, bg=cor_fundo)
        cabecalho.pack(fill="x", pady=(0, 8))
        tk.Label(
            cabecalho,
            text=titulo,
            font=FONTE_CATEGORIA,
            fg="#006699",
            bg=cor_fundo,
            anchor="w",
        ).pack(side="left")
        tk.Frame(cabecalho, bg="#c5d6de", height=1).pack(
            side="left", fill="x", expand=True, padx=(10, 0), pady=6
        )

        grade = tk.Frame(secao, bg=cor_fundo)
        grade.pack(anchor="w")
        for col in range(len(cartoes)):
            grade.columnconfigure(col, weight=0)

        for indice, cartao in enumerate(cartoes):
            self._criar_cartao(
                grade,
                titulo=cartao["titulo"],
                descricao=cartao["descricao"],
                modulo=cartao["modulo"],
                habilitado=cartao.get("habilitado", True),
                coluna=indice,
                linha=0,
                aviso=cartao.get("aviso"),
                icone_titulo=cartao.get("icone_titulo"),
            )
        return secao

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
                font=("Segoe UI", 9),
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
        cartao.grid(row=linha, column=coluna, padx=(0, 12), pady=4, sticky="n")
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
