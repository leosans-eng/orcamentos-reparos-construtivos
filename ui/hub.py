import tkinter as tk

from ui.widgets import (
    COR_BORDA_PADRAO,
    COR_FUNDO_CARTAO,
    COR_TITULO_PADRAO,
    aplicar_hover_cartao,
)


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
            descricao="Orçamento de reparos em áreas comuns do edifício",
            modulo="area_comum",
            habilitado=False,
            coluna=1,
            aviso="Em breve",
        )
        self._criar_cartao(
            cartoes,
            titulo="Consulta SINAPI",
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
        largura = 220
        altura = 130
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
        cartao.grid(row=0, column=coluna, padx=12, pady=4)
        cartao.grid_propagate(False)

        filhos = []

        lbl_titulo = tk.Label(
            cartao,
            text=titulo,
            font=("Arial", 12, "bold"),
            fg=cor_titulo,
            bg=cor_fundo,
        )
        lbl_titulo.pack(pady=(18, 6))
        filhos.append(lbl_titulo)

        lbl_desc = tk.Label(
            cartao,
            text=descricao,
            font=("Arial", 9),
            fg=cor_texto,
            bg=cor_fundo,
            wraplength=largura - 24,
            justify="center",
        )
        lbl_desc.pack(padx=12)
        filhos.append(lbl_desc)

        if aviso:
            lbl_aviso = tk.Label(
                cartao,
                text=aviso,
                font=("Arial", 8, "italic"),
                fg="#999999",
                bg=cor_fundo,
            )
            lbl_aviso.pack(pady=(8, 0))
            filhos.append(lbl_aviso)

        if habilitado:
            def ao_clicar(_event=None, mod=modulo):
                self.on_selecionar_modulo(mod)

            cartao.bind("<Button-1>", ao_clicar)
            for filho in filhos:
                filho.bind("<Button-1>", ao_clicar)

            aplicar_hover_cartao(cartao, filhos)
