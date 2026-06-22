import tkinter as tk

from ui.widgets import criar_botao_voltar


class ConsultaSinapiFrame(tk.Frame):
    def __init__(self, parent, on_voltar):
        super().__init__(parent, bg="#ececec")
        self.on_voltar = on_voltar
        self._montar()

    def _montar(self):
        barra = tk.Frame(self, bg="#ececec")
        barra.pack(fill="x", padx=10, pady=(8, 0))
        criar_botao_voltar(barra, self.on_voltar, bg_parent="#ececec").pack(side="left")

        centro = tk.Frame(self, bg="#ececec")
        centro.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(
            centro,
            text="Consulta SINAPI",
            font=("Arial", 16, "bold"),
            fg="#006699",
            bg="#ececec",
        ).pack(pady=(0, 8))

        tk.Label(
            centro,
            text=(
                "Módulo em desenvolvimento.\n"
                "Em breve você poderá pesquisar\n"
                "composições e preços da base SINAPI."
            ),
            font=("Arial", 10),
            fg="#666666",
            bg="#ececec",
            justify="center",
        ).pack()
