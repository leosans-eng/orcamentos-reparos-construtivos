import tkinter as tk
from tkinter import ttk

from app_paths import asset_path
from ui.widgets import (
    COR_BORDA_PADRAO,
    COR_FUNDO_CARTAO,
    COR_TITULO_PADRAO,
    aplicar_hover_cartao,
    aplicar_icone_janela,
    centralizar_janela,
    preparar_toplevel,
)

LARGURA_CARTAO = 180
ALTURA_CARTAO = 268

MODELOS_PLANILHA = (
    ("modelo1.png", "Atualização (+ Word)"),
    ("modelo2.png", "Enviar ao Perito (Planilha com fórmulas)"),
    ("modelo3.png", "Parecer Inicial (+ Word)"),
    ("modelo4.png", "Orçamentos Customizados"),
)


def _carregar_imagem_modelo(caminho, largura_alvo=LARGURA_CARTAO - 28):
    imagem = tk.PhotoImage(file=str(caminho))
    if imagem.width() > largura_alvo:
        fator = max(1, round(imagem.width() / largura_alvo))
        imagem = imagem.subsample(fator, fator)
    return imagem


class DialogoSelecionarModeloPlanilha(tk.Toplevel):
    def __init__(self, parent, on_selecionar=None):
        super().__init__(parent)
        preparar_toplevel(self)
        self.on_selecionar = on_selecionar
        self._imagens = []

        self.title("Selecionar modelo")
        aplicar_icone_janela(self)
        self.configure(bg="#ececec")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        painel = tk.Frame(self, bg="#ececec", padx=20, pady=16)
        painel.pack(fill="both", expand=True)

        tk.Label(
            painel,
            text="Selecione o modelo da Planilha",
            font=("Arial", 11, "bold"),
            fg="#333333",
            bg="#ececec",
        ).pack(anchor="w", pady=(0, 14))

        grade = tk.Frame(painel, bg="#ececec")
        grade.pack(fill="x")
        for col in range(len(MODELOS_PLANILHA)):
            grade.columnconfigure(col, weight=1, uniform="modelo_planilha")

        for col, (arquivo, descricao) in enumerate(MODELOS_PLANILHA, start=1):
            self._criar_cartao_modelo(grade, col - 1, col, arquivo, descricao)

        botoes = ttk.Frame(painel)
        botoes.pack(fill="x", pady=(16, 0))
        ttk.Button(botoes, text="Cancelar", command=self.destroy, style="Delete.TButton").pack(
            side="right"
        )

        self.bind("<Escape>", lambda _e: self.destroy())
        self.update_idletasks()
        centralizar_janela(self, parent)

    def _criar_cartao_modelo(self, parent, coluna, numero, arquivo, descricao):
        cartao = tk.Frame(
            parent,
            width=LARGURA_CARTAO,
            height=ALTURA_CARTAO,
            bg=COR_FUNDO_CARTAO,
            highlightbackground=COR_BORDA_PADRAO,
            highlightthickness=2,
            cursor="hand2",
        )
        cartao.grid(row=0, column=coluna, padx=8, pady=4, sticky="n")
        cartao.grid_propagate(False)
        cartao.columnconfigure(0, weight=1)
        cartao.rowconfigure(1, weight=1)

        filhos = []

        caminho = asset_path("modelos", arquivo)
        if caminho is not None:
            imagem = _carregar_imagem_modelo(caminho)
            self._imagens.append(imagem)
            lbl_imagem = tk.Label(cartao, image=imagem, bg=COR_FUNDO_CARTAO)
        else:
            lbl_imagem = tk.Label(
                cartao,
                text="Imagem\nindisponível",
                font=("Arial", 8),
                fg="#999999",
                bg="#f0f0f0",
                width=18,
                height=7,
            )
        lbl_imagem.grid(row=0, column=0, pady=(10, 6))
        filhos.append(lbl_imagem)

        lbl_numero = tk.Label(
            cartao,
            text=f"Modelo {numero}",
            font=("Arial", 10, "bold"),
            fg=COR_TITULO_PADRAO,
            bg=COR_FUNDO_CARTAO,
        )
        lbl_numero.grid(row=1, column=0, pady=(0, 4))
        filhos.append(lbl_numero)

        lbl_desc = tk.Label(
            cartao,
            text=descricao,
            font=("Arial", 9),
            fg="#555555",
            bg=COR_FUNDO_CARTAO,
            wraplength=LARGURA_CARTAO - 24,
            justify="center",
        )
        lbl_desc.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="n")
        filhos.append(lbl_desc)

        def ao_clicar(_event=None, n=numero):
            if self.on_selecionar is not None:
                self.on_selecionar(n)
            self.destroy()

        cartao.bind("<Button-1>", ao_clicar)
        for filho in filhos:
            filho.bind("<Button-1>", ao_clicar)

        aplicar_hover_cartao(cartao, filhos)
