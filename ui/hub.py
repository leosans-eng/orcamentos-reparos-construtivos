import tkinter as tk
import tkinter.font as tkfont

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


class HubFrame(tk.Frame):
    def __init__(self, parent, on_selecionar_modulo):
        super().__init__(parent, bg="#ececec")
        self.on_selecionar_modulo = on_selecionar_modulo
        self._cache_icones = {}
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
            titulo="Orçamento Customizado",
            descricao="Montar orçamento com Etapas e Itens personalizados",
            modulo="orcamento_customizado",
            habilitado=True,
            coluna=0,
            linha=1,
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

        if icone_titulo:
            filhos.extend(
                self._montar_titulo_com_icone(
                    cartao, titulo, cor_fundo, cor_titulo, icone_titulo
                )
            )
        else:
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

    def _icone_svg(self, nome: str, cor: str) -> tk.PhotoImage:
        fonte_titulo = tkfont.Font(font=FONTE_TITULO_CARTAO)
        altura = fonte_titulo.metrics("ascent") + fonte_titulo.metrics("descent")
        chave = (nome, altura, cor)
        if chave not in self._cache_icones:
            self._cache_icones[chave] = criar_icone_svg(
                self,
                nome,
                altura=altura,
                cor=cor,
            )
        return self._cache_icones[chave]

    def _montar_titulo_com_icone(
        self, cartao, titulo, cor_fundo, cor_titulo, nome_icone
    ):
        filhos = []
        texto_primeira_linha = titulo.split("\n", 1)[0].strip()
        fonte_titulo = tkfont.Font(font=FONTE_TITULO_CARTAO)

        titulo_container = tk.Frame(cartao, bg=cor_fundo)
        titulo_container.grid(row=0, column=0, padx=14, pady=(16, 2), sticky="ew")
        filhos.append(titulo_container)

        icone = self._icone_svg(nome_icone, cor_titulo)
        largura_icone = icone.width() + 4

        lbl_titulo = tk.Label(
            titulo_container,
            text=titulo,
            font=FONTE_TITULO_CARTAO,
            fg=cor_titulo,
            bg=cor_fundo,
            justify="center",
            wraplength=LARGURA_CARTAO - 28,
        )
        lbl_titulo.pack(anchor="center")
        filhos.append(lbl_titulo)

        lbl_icone = tk.Label(titulo_container, image=icone, bg=cor_fundo)
        filhos.append(lbl_icone)

        def posicionar_icone(_event=None):
            lbl_titulo.update_idletasks()
            largura_primeira_linha = fonte_titulo.measure(texto_primeira_linha)
            x_titulo = lbl_titulo.winfo_x()
            y_titulo = lbl_titulo.winfo_y()
            largura_titulo = lbl_titulo.winfo_width()
            x_icone = (
                x_titulo
                + (largura_titulo - largura_primeira_linha) // 2
                - largura_icone
            )
            lbl_icone.place(x=max(0, x_icone), y=y_titulo, anchor="nw")

        lbl_titulo.bind("<Configure>", posicionar_icone, add="+")
        titulo_container.after_idle(posicionar_icone)

        return filhos
