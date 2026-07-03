import tkinter as tk
from tkinter import ttk

from core.api_client import reiniciar_cliente
from core.api_config import carregar_config, salvar_config
from core.api_exceptions import ApiError, ApiIndisponivelError
from ui.widgets import aplicar_icone_janela, centralizar_janela, preparar_toplevel

URL_PADRAO = "http://localhost:8000"


class DialogoLogin(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        preparar_toplevel(self)
        self.resultado = False

        config = carregar_config()
        self.title("ORC — Login")
        aplicar_icone_janela(self)
        self.configure(bg="#ececec")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        painel = tk.Frame(self, bg="#ececec", padx=20, pady=16)
        painel.pack(fill="both", expand=True)

        tk.Label(
            painel,
            text="Conectar ao servidor",
            font=("Arial", 12, "bold"),
            fg="#333333",
            bg="#ececec",
        ).pack(anchor="w", pady=(0, 4))

        tk.Label(
            painel,
            text="Composições e etapas pré-definidas são compartilhadas pela API.",
            font=("Arial", 9),
            fg="#555555",
            bg="#ececec",
            wraplength=360,
            justify="left",
        ).pack(anchor="w", pady=(0, 14))

        form = tk.Frame(painel, bg="#ffffff", highlightbackground="#cccccc", highlightthickness=1)
        form.pack(fill="x", pady=(0, 12))
        inner = tk.Frame(form, bg="#ffffff", padx=14, pady=12)
        inner.pack(fill="x")

        tk.Label(inner, text="URL da API", bg="#ffffff", fg="#555555", font=("Arial", 9)).grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        self.var_url = tk.StringVar(value=config.get("base_url", URL_PADRAO))
        ttk.Entry(inner, textvariable=self.var_url, width=42).grid(row=1, column=0, sticky="ew", pady=(0, 10))
        inner.columnconfigure(0, weight=1)

        tk.Label(inner, text="Usuário", bg="#ffffff", fg="#555555", font=("Arial", 9)).grid(
            row=2, column=0, sticky="w", pady=(0, 4)
        )
        self.var_usuario = tk.StringVar()
        ttk.Entry(inner, textvariable=self.var_usuario, width=28).grid(row=3, column=0, sticky="w", pady=(0, 10))

        tk.Label(inner, text="Senha", bg="#ffffff", fg="#555555", font=("Arial", 9)).grid(
            row=4, column=0, sticky="w", pady=(0, 4)
        )
        self.var_senha = tk.StringVar()
        entrada_senha = ttk.Entry(inner, textvariable=self.var_senha, width=28, show="•")
        entrada_senha.grid(row=5, column=0, sticky="w")
        entrada_senha.bind("<Return>", lambda _e: self._entrar())

        self._lbl_erro = tk.Label(
            painel,
            text="",
            font=("Arial", 9),
            fg="#c62828",
            bg="#ececec",
            wraplength=360,
            justify="left",
        )
        self._lbl_erro.pack(anchor="w", pady=(0, 8))

        botoes = ttk.Frame(painel)
        botoes.pack(fill="x")
        ttk.Button(botoes, text="Sair", command=self._cancelar, style="Delete.TButton").pack(side="right")
        ttk.Button(botoes, text="Entrar", command=self._entrar).pack(side="right", padx=(0, 8))

        self.bind("<Escape>", lambda _e: self._cancelar())
        self.protocol("WM_DELETE_WINDOW", self._cancelar)
        self.update_idletasks()
        centralizar_janela(self, parent)

    def _cancelar(self):
        self.resultado = False
        self.destroy()

    def _entrar(self):
        url = self.var_url.get().strip().rstrip("/") or URL_PADRAO
        usuario = self.var_usuario.get().strip()
        senha = self.var_senha.get()
        if not usuario:
            self._lbl_erro.config(text="Informe o usuário.")
            return
        if not senha:
            self._lbl_erro.config(text="Informe a senha.")
            return

        salvar_config(url)
        cliente = reiniciar_cliente(base_url=url)
        try:
            if not cliente.health():
                raise ApiIndisponivelError(
                    f"A API em {url} não respondeu. Verifique se o servidor está em execução."
                )
            cliente.login(usuario, senha)
        except ApiError as exc:
            self._lbl_erro.config(text=exc.mensagem)
            return

        self.resultado = True
        self.destroy()


def garantir_login(parent) -> bool:
    dialogo = DialogoLogin(parent)
    parent.wait_window(dialogo)
    return dialogo.resultado
