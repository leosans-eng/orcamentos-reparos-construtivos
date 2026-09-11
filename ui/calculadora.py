"""Calculadora compacta flutuante (sempre no topo, arrastável)."""

from __future__ import annotations

import tkinter as tk

from ui.temas import _misturar, cores_tema, texto_contraste
from ui.widgets import (
    formatar_quantidade_edicao,
    parse_quantidade_expressao,
)

_instancia: CalculadoraFlutuante | None = None


class CalculadoraFlutuante(tk.Toplevel):
    """Janela pequena, always-on-top, arrastável pela barra de título."""

    def __init__(self, parent):
        super().__init__(parent)
        self.withdraw()
        self.overrideredirect(True)
        try:
            self.attributes("-topmost", True)
        except tk.TclError:
            pass
        self._cores = cores_tema(parent)
        self.configure(bg=self._cores.borda_suave)
        self.resizable(False, False)

        self._expressao = ""
        self._arrasto_x = 0
        self._arrasto_y = 0

        self._montar()
        self.protocol("WM_DELETE_WINDOW", self._fechar)
        self.bind("<Escape>", lambda _e: self._fechar())

        self.update_idletasks()
        self._posicionar_junto_ao_pai(parent)
        self.deiconify()
        self.lift()
        try:
            self.focus_force()
        except tk.TclError:
            pass

    def _montar(self):
        cores = self._cores
        borda = tk.Frame(self, bg=cores.borda_suave, padx=1, pady=1)
        borda.pack(fill="both", expand=True)

        painel = tk.Frame(borda, bg=cores.fundo, padx=8, pady=8)
        painel.pack(fill="both", expand=True)

        texto_faixa = texto_contraste(cores.faixa)
        barra = tk.Frame(painel, bg=cores.faixa, cursor="fleur")
        barra.pack(fill="x", pady=(0, 8))
        tk.Label(
            barra,
            text="Calculadora",
            bg=cores.faixa,
            fg=texto_faixa,
            font=("Arial", 9, "bold"),
            padx=8,
            pady=5,
            cursor="fleur",
        ).pack(side="left")
        tk.Button(
            barra,
            text="×",
            command=self._fechar,
            bg=cores.faixa,
            fg=texto_faixa,
            activebackground=cores.titulo_hover,
            activeforeground=texto_faixa,
            relief="flat",
            bd=0,
            padx=8,
            pady=2,
            cursor="hand2",
            font=("Arial", 11, "bold"),
        ).pack(side="right")

        for alvo in (barra, *barra.winfo_children()):
            if isinstance(alvo, tk.Button) and alvo.cget("text") == "×":
                continue
            alvo.bind("<ButtonPress-1>", self._iniciar_arrasto)
            alvo.bind("<B1-Motion>", self._arrastar)

        self.var_display = tk.StringVar(value="0")
        self.label_display = tk.Label(
            painel,
            textvariable=self.var_display,
            bg=cores.fundo_cartao,
            fg=cores.titulo,
            font=("Consolas", 15, "bold"),
            anchor="e",
            padx=10,
            pady=10,
            relief="solid",
            bd=1,
            highlightbackground=cores.borda_suave,
        )
        self.label_display.pack(fill="x", pady=(0, 8))

        teclado = tk.Frame(painel, bg=cores.fundo)
        teclado.pack()

        linhas = (
            ("C", "⌫", "(", ")"),
            ("7", "8", "9", "/"),
            ("4", "5", "6", "*"),
            ("1", "2", "3", "-"),
            ("0", ",", "=", "+"),
        )
        for r, linha in enumerate(linhas):
            for c, tecla in enumerate(linha):
                self._criar_tecla(teclado, tecla, r, c)

        for i in range(4):
            teclado.columnconfigure(i, weight=1)

        self.bind("<Key>", self._ao_tecla)

    def _criar_tecla(self, parent, tecla: str, row: int, col: int):
        bg, fg, active = self._cores_tecla(tecla)
        btn = tk.Button(
            parent,
            text=tecla,
            width=4,
            command=lambda t=tecla: self._pressionar(t),
            bg=bg,
            fg=fg,
            activebackground=active,
            activeforeground=fg,
            relief="flat",
            bd=0,
            padx=4,
            pady=6,
            cursor="hand2",
            font=("Arial", 10, "bold"),
            highlightthickness=0,
        )
        btn.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")

    def _cores_tecla(self, tecla: str) -> tuple[str, str, str]:
        cores = self._cores
        if tecla == "=":
            return cores.titulo, texto_contraste(cores.titulo), cores.titulo_hover
        if cores.escuro:
            if tecla == "C":
                return cores.fundo_cartao, cores.perigo, cores.fundo_hover
            if tecla in "+-*/()⌫":
                return cores.fundo_destaque, cores.titulo, cores.fundo_hover
            return cores.fundo_cartao, cores.texto, cores.fundo_hover
        if tecla == "C":
            bg = _misturar(cores.fundo, cores.perigo, 0.18)
            return bg, cores.perigo, _misturar(bg, cores.perigo, 0.22)
        if tecla in "+-*/()⌫":
            bg = _misturar(cores.fundo, cores.titulo, 0.32)
            return bg, cores.titulo, _misturar(bg, cores.titulo, 0.18)
        bg = _misturar(cores.fundo, cores.titulo, 0.18)
        return bg, cores.texto, _misturar(bg, cores.titulo, 0.12)

    def _posicionar_junto_ao_pai(self, parent):
        try:
            px = parent.winfo_rootx()
            py = parent.winfo_rooty()
            pw = parent.winfo_width()
        except tk.TclError:
            px, py, pw = 100, 100, 400
        largura = max(self.winfo_reqwidth(), 220)
        altura = max(self.winfo_reqheight(), 280)
        x = px + max(20, pw - largura - 40)
        y = py + 80
        self.geometry(f"{largura}x{altura}+{x}+{y}")

    def _iniciar_arrasto(self, event):
        self._arrasto_x = event.x_root - self.winfo_x()
        self._arrasto_y = event.y_root - self.winfo_y()

    def _arrastar(self, event):
        x = event.x_root - self._arrasto_x
        y = event.y_root - self._arrasto_y
        self.geometry(f"+{x}+{y}")

    def _atualizar_display(self):
        self.var_display.set(self._expressao or "0")

    def _pressionar(self, tecla: str):
        if tecla == "C":
            self._expressao = ""
        elif tecla == "⌫":
            self._expressao = self._expressao[:-1]
        elif tecla == "=":
            self._calcular()
            return
        else:
            if self._expressao in ("0", "Erro") and tecla not in "+-*/()":
                if tecla == ",":
                    self._expressao = "0,"
                else:
                    self._expressao = tecla
            elif self._expressao == "Erro":
                self._expressao = tecla if tecla not in "+-*/" else ""
            else:
                self._expressao += tecla
        self._atualizar_display()

    def _calcular(self):
        if not self._expressao or self._expressao == "Erro":
            return
        try:
            resultado = parse_quantidade_expressao(self._expressao)
            self._expressao = formatar_quantidade_edicao(resultado)
            self._atualizar_display()
        except ValueError:
            self._expressao = "Erro"
            self._atualizar_display()

    def _ao_tecla(self, event):
        tecla = event.keysym
        char = event.char or ""
        if tecla in ("Return", "KP_Enter", "Equal"):
            self._calcular()
            return "break"
        if tecla in ("Escape",):
            self._fechar()
            return "break"
        if tecla in ("BackSpace",):
            self._pressionar("⌫")
            return "break"
        if tecla in ("Delete",):
            self._pressionar("C")
            return "break"
        mapa = {
            "*": "*",
            "asterisk": "*",
            "plus": "+",
            "minus": "-",
            "slash": "/",
            "parenleft": "(",
            "parenright": ")",
            "comma": ",",
            "period": ",",
            "KP_Decimal": ",",
            "KP_Add": "+",
            "KP_Subtract": "-",
            "KP_Multiply": "*",
            "KP_Divide": "/",
        }
        if tecla in mapa:
            self._pressionar(mapa[tecla])
            return "break"
        if char.isdigit():
            self._pressionar(char)
            return "break"
        if char in "+-*/(),.":
            self._pressionar("," if char == "." else char)
            return "break"
        return None

    def _fechar(self):
        global _instancia
        if _instancia is self:
            _instancia = None
        try:
            self.destroy()
        except tk.TclError:
            pass

    def trazer_frente(self):
        try:
            self.attributes("-topmost", True)
            self.deiconify()
            self.lift()
            self.focus_force()
        except tk.TclError:
            pass


def abrir_calculadora(parent) -> CalculadoraFlutuante:
    """Abre a calculadora ou traz a instância existente para frente."""
    global _instancia
    if _instancia is not None:
        try:
            if _instancia.winfo_exists():
                _instancia.trazer_frente()
                return _instancia
        except tk.TclError:
            _instancia = None
    _instancia = CalculadoraFlutuante(parent)
    return _instancia


def fechar_calculadora() -> None:
    """Fecha a calculadora flutuante, se estiver aberta."""
    global _instancia
    janela = _instancia
    _instancia = None
    if janela is None:
        return
    try:
        if janela.winfo_exists():
            janela.destroy()
    except tk.TclError:
        pass
