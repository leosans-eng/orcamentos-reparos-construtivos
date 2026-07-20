"""Calculadora compacta flutuante (sempre no topo, arrastável)."""

from __future__ import annotations

import tkinter as tk

from ui.widgets import (
    formatar_quantidade_edicao,
    parse_quantidade_expressao,
)

# Paleta alinhada ao ORC
_COR_FUNDO = "#e8f2f7"
_COR_PAINEL = "#f5fafc"
_COR_BARRA = "#006699"
_COR_BARRA_TEXTO = "#ffffff"
_COR_DISPLAY = "#ffffff"
_COR_DISPLAY_TEXTO = "#006699"
_COR_BORDA = "#8eb8cc"
_COR_BOTAO = "#d6ebf5"
_COR_BOTAO_ATIVO = "#b8d9ea"
_COR_BOTAO_TEXTO = "#004d73"
_COR_BOTAO_OP = "#c5e0ef"
_COR_BOTAO_IGUAL = "#006699"
_COR_BOTAO_IGUAL_TEXTO = "#ffffff"
_COR_BOTAO_LIMPAR = "#e8a0a0"
_COR_BOTAO_LIMPAR_ATIVO = "#d98080"

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
        self.configure(bg=_COR_BORDA)
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
        borda = tk.Frame(self, bg=_COR_BORDA, padx=1, pady=1)
        borda.pack(fill="both", expand=True)

        painel = tk.Frame(borda, bg=_COR_FUNDO, padx=8, pady=8)
        painel.pack(fill="both", expand=True)

        barra = tk.Frame(painel, bg=_COR_BARRA, cursor="fleur")
        barra.pack(fill="x", pady=(0, 8))
        tk.Label(
            barra,
            text="Calculadora",
            bg=_COR_BARRA,
            fg=_COR_BARRA_TEXTO,
            font=("Arial", 9, "bold"),
            padx=8,
            pady=5,
            cursor="fleur",
        ).pack(side="left")
        tk.Button(
            barra,
            text="×",
            command=self._fechar,
            bg=_COR_BARRA,
            fg=_COR_BARRA_TEXTO,
            activebackground="#005580",
            activeforeground=_COR_BARRA_TEXTO,
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
            bg=_COR_DISPLAY,
            fg=_COR_DISPLAY_TEXTO,
            font=("Consolas", 15, "bold"),
            anchor="e",
            padx=10,
            pady=10,
            relief="solid",
            bd=1,
            highlightbackground=_COR_BORDA,
        )
        self.label_display.pack(fill="x", pady=(0, 8))

        teclado = tk.Frame(painel, bg=_COR_FUNDO)
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
        if tecla == "=":
            bg, fg, active = _COR_BOTAO_IGUAL, _COR_BOTAO_IGUAL_TEXTO, "#005580"
        elif tecla == "C":
            bg, fg, active = _COR_BOTAO_LIMPAR, "#5c2020", _COR_BOTAO_LIMPAR_ATIVO
        elif tecla in "+-*/()⌫":
            bg, fg, active = _COR_BOTAO_OP, _COR_BOTAO_TEXTO, _COR_BOTAO_ATIVO
        else:
            bg, fg, active = _COR_BOTAO, _COR_BOTAO_TEXTO, _COR_BOTAO_ATIVO

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
