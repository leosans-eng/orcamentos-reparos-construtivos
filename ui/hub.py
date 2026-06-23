import tkinter as tk

from ui.widgets import (
    COR_BORDA_PADRAO,
    COR_FUNDO_CARTAO,
    COR_TITULO_PADRAO,
    aplicar_hover_cartao,
)

LARGURA_CARTAO = 240
ALTURA_CARTAO = 148


class HubFrame(tk.Frame):
    def __init__(self, parent, on_selecionar_modulo):
        super().__init__(parent, bg="#ececec")
        self.on_selecionar_modulo = on_selecionar_modulo
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
        )
        self._criar_cartao(
            cartoes,
            titulo="Área Comum",
            descricao="Orçamento de reparos em áreas comuns, com a opção de composições próprias",
            modulo="area_comum",
            habilitado=False,
            coluna=1,
            aviso="Em breve",
        )
        self._criar_cartao(
            cartoes,
            titulo="Consulta SINAPI 🔍",
            descricao="Pesquisar composições e preços da base",
            modulo="consulta_sinapi",
            habilitado=True,
            coluna=2,
        )

    def _criar_cartao(
        self,
        parent,
        titulo,
        descricao,
        modulo,
        habilitado,
        coluna,
        aviso=None,
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
        cartao.grid(row=0, column=coluna, padx=12, pady=4, sticky="n")
        cartao.grid_propagate(False)
        cartao.rowconfigure(1, weight=1)
        cartao.columnconfigure(0, weight=1)

        filhos = []

        lbl_titulo = tk.Label(
            cartao,
            text=titulo,
            font=("Arial", 12, "bold"),
            fg=cor_titulo,
            bg=cor_fundo,
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

        texto_aviso = aviso if aviso else ""
        lbl_aviso = tk.Label(
            cartao,
            text=texto_aviso,
            font=("Arial", 8, "italic"),
            fg="#999999" if aviso else cor_fundo,
            bg=cor_fundo,
            height=1,
        )
        lbl_aviso.grid(row=2, column=0, pady=(4, 12), sticky="s")
        filhos.append(lbl_aviso)

        if habilitado:
            def ao_clicar(_event=None, mod=modulo):
                self.on_selecionar_modulo(mod)

            cartao.bind("<Button-1>", ao_clicar)
            for filho in filhos:
                filho.bind("<Button-1>", ao_clicar)

            aplicar_hover_cartao(cartao, filhos)
