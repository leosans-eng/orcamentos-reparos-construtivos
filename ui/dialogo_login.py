import sys
import tkinter as tk
from tkinter import ttk

from core.api_client import reiniciar_cliente
from core.api_config import carregar_config, salvar_config
from core.api_exceptions import ApiError, ApiIndisponivelError
from ui.icones import criar_botao_ttk_com_icone
from ui.widgets import (
    COR_BORDA_PADRAO,
    COR_FUNDO_CARTAO,
    COR_TITULO_PADRAO,
    aplicar_icone_janela,
    centralizar_janela,
    configurar_estilos_ttk,
    preparar_toplevel,
)

URL_PADRAO = "http://localhost:8000"
COR_FUNDO = "#ececec"
COR_ROTULO = "#555555"
COR_ERRO = "#c62828"


class DialogoLogin(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        preparar_toplevel(self)
        configurar_estilos_ttk(self)
        self.resultado = False
        self._refs_icones: list = []

        config = carregar_config()
        self.title("ORC — Login")
        aplicar_icone_janela(self)
        self.configure(bg=COR_FUNDO)
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)

        painel = tk.Frame(self, bg=COR_FUNDO, padx=28, pady=22)
        painel.pack(fill="both", expand=True)

        cartao = tk.Frame(
            painel,
            bg=COR_FUNDO_CARTAO,
            highlightbackground=COR_BORDA_PADRAO,
            highlightthickness=2,
        )
        cartao.pack(fill="x")
        inner = tk.Frame(cartao, bg=COR_FUNDO_CARTAO, padx=18, pady=16)
        inner.pack(fill="x")
        inner.columnconfigure(0, weight=1)

        self.var_url = tk.StringVar(value=config.get("base_url", URL_PADRAO))
        self.var_usuario = tk.StringVar(value=config.get("usuario", ""))
        self.var_senha = tk.StringVar(value=config.get("senha", ""))
        self.var_salvar_usuario = tk.BooleanVar(value=bool(config.get("salvar_usuario")))
        self.var_salvar_senha = tk.BooleanVar(value=bool(config.get("salvar_senha")))

        self._campo(inner, "URL da API:", self.var_url, linha=0, largura=40)
        self._campo(inner, "Usuário:", self.var_usuario, linha=2, largura=28)
        entrada_senha = self._campo(
            inner,
            "Senha:",
            self.var_senha,
            linha=4,
            largura=28,
            mostrar="•",
        )
        entrada_senha.bind("<Return>", lambda _e: self._entrar())

        opcoes = tk.Frame(inner, bg=COR_FUNDO_CARTAO)
        opcoes.grid(row=6, column=0, sticky="w", pady=(10, 0))

        chk_usuario = tk.Checkbutton(
            opcoes,
            text="Salvar usuário",
            variable=self.var_salvar_usuario,
            command=self._ao_alterar_salvar_usuario,
            bg=COR_FUNDO_CARTAO,
            activebackground=COR_FUNDO_CARTAO,
            fg=COR_ROTULO,
            activeforeground=COR_ROTULO,
            selectcolor=COR_FUNDO_CARTAO,
            font=("Arial", 9),
            anchor="w",
        )
        chk_usuario.pack(anchor="w")

        chk_senha = tk.Checkbutton(
            opcoes,
            text="Salvar senha",
            variable=self.var_salvar_senha,
            command=self._ao_alterar_salvar_senha,
            bg=COR_FUNDO_CARTAO,
            activebackground=COR_FUNDO_CARTAO,
            fg=COR_ROTULO,
            activeforeground=COR_ROTULO,
            selectcolor=COR_FUNDO_CARTAO,
            font=("Arial", 9),
            anchor="w",
        )
        chk_senha.pack(anchor="w", pady=(2, 0))

        self._lbl_erro = tk.Label(
            painel,
            text="",
            font=("Arial", 9),
            fg=COR_ERRO,
            bg=COR_FUNDO,
            wraplength=380,
            justify="center",
            height=2,
        )
        self._lbl_erro.pack(fill="x", pady=(12, 8))

        botoes = ttk.Frame(painel)
        botoes.pack(fill="x")
        criar_botao_ttk_com_icone(
            botoes,
            texto="Sair",
            nome_icone="log-out-outline",
            command=self._cancelar,
            estilo="Delete.TButton",
            refs=self._refs_icones,
        ).pack(side="right")
        criar_botao_ttk_com_icone(
            botoes,
            texto="Entrar",
            nome_icone="log-in-outline",
            command=self._entrar,
            estilo="Add.TButton",
            refs=self._refs_icones,
        ).pack(side="right", padx=(0, 8))

        self.bind("<Escape>", lambda _e: self._cancelar())
        self.protocol("WM_DELETE_WINDOW", self._cancelar)
        self.update_idletasks()
        centralizar_janela(self, parent)
        self._trazer_para_frente()

        if self.var_usuario.get().strip() and not self.var_senha.get():
            entrada_senha.focus_set()
        elif not self.var_usuario.get().strip():
            self.focus_set()

    def _trazer_para_frente(self):
        self.lift()
        self.focus_force()
        if sys.platform == "win32":
            try:
                self.attributes("-topmost", True)
                self._after_topmost = self.after(300, self._liberar_topmost)
            except tk.TclError:
                pass

    def _liberar_topmost(self):
        self._after_topmost = None
        try:
            self.attributes("-topmost", False)
        except tk.TclError:
            pass

    def _cancelar_agendamentos(self):
        after_id = getattr(self, "_after_topmost", None)
        if after_id is not None:
            try:
                self.after_cancel(after_id)
            except tk.TclError:
                pass
            self._after_topmost = None

    def _campo(self, parent, rotulo, variavel, *, linha, largura, mostrar=None):
        tk.Label(
            parent,
            text=rotulo,
            bg=COR_FUNDO_CARTAO,
            fg=COR_ROTULO,
            font=("Arial", 9),
        ).grid(row=linha, column=0, sticky="w", pady=(0 if linha == 0 else 8, 4))
        kwargs = {"textvariable": variavel, "width": largura}
        if mostrar is not None:
            kwargs["show"] = mostrar
        entrada = ttk.Entry(parent, **kwargs)
        entrada.grid(row=linha + 1, column=0, sticky="ew")
        return entrada

    def _ao_alterar_salvar_usuario(self):
        if not self.var_salvar_usuario.get():
            self.var_salvar_senha.set(False)

    def _ao_alterar_salvar_senha(self):
        if self.var_salvar_senha.get():
            self.var_salvar_usuario.set(True)

    def _cancelar(self):
        self._cancelar_agendamentos()
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

        self._lbl_erro.config(text="Conectando…", fg=COR_TITULO_PADRAO)
        self.update_idletasks()

        salvar_config(
            url,
            salvar_usuario=self.var_salvar_usuario.get(),
            salvar_senha=self.var_salvar_senha.get(),
            usuario=usuario,
            senha=senha,
        )
        cliente = reiniciar_cliente(base_url=url)
        try:
            if not cliente.health():
                raise ApiIndisponivelError(
                    f"A API em {url} não respondeu.\n"
                    "Verifique se o servidor está em execução e se a URL está correta."
                )
            cliente.login(usuario, senha)
        except ApiError as exc:
            self._lbl_erro.config(text=exc.mensagem, fg=COR_ERRO)
            return

        self.resultado = True
        self._cancelar_agendamentos()
        self.destroy()


def garantir_login(parent) -> bool:
    print("[ORC] Tela: Login")
    dialogo = DialogoLogin(parent)
    try:
        from atualizacao import iniciar_verificacao_atualizacao
        from core.app_state import APP_VERSION

        # Começa no login; se o usuário entrar antes, o hub reutiliza o resultado.
        iniciar_verificacao_atualizacao(dialogo, APP_VERSION)
    except ImportError:
        pass
    parent.wait_window(dialogo)
    if dialogo.resultado:
        print("[ORC] Login autenticado")
    else:
        print("[ORC] Login não concluído")
    return dialogo.resultado
