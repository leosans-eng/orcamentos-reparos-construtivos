import gc
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk

from core.api_client import reiniciar_cliente
from core.api_config import URL_PADRAO, carregar_config, salvar_config
from core.api_exceptions import ApiError
from ui.icones import IndicadorAmpulheta, criar_botao_ttk_com_icone
from ui.widgets import (
    COR_BORDA_PADRAO,
    COR_FUNDO_CARTAO,
    COR_TITULO_PADRAO,
    aplicar_icone_janela,
    centralizar_janela,
    configurar_estilos_ttk,
)

COR_FUNDO = "#e8eef1"
COR_FAIXA = "#006699"
COR_ROTULO = "#555555"
COR_ERRO = "#c62828"
COR_STATUS = "#006699"
LARGURA_JANELA = 420
WRAP_ERRO = LARGURA_JANELA - 64


class DialogoLogin:
    """Login montado na janela raiz (Tk) para aparecer na barra de tarefas."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.resultado = False
        self._refs_icones: list = []
        self._after_topmost = None
        self._concluido = tk.BooleanVar(master=root, value=False)
        self._conectando = False
        self._btn_entrar = None
        self._btn_sair = None
        self._ampulheta = None
        self._slot_amp = None
        self._fila_login: queue.Queue = queue.Queue()
        self._after_login = None

        configurar_estilos_ttk(root)

        config = carregar_config()
        root.title("ORC — Login")
        aplicar_icone_janela(root)
        root.configure(bg=COR_FUNDO)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self._cancelar)

        for filho in list(root.winfo_children()):
            try:
                filho.destroy()
            except tk.TclError:
                pass

        raiz = tk.Frame(root, bg=COR_FUNDO)
        raiz.pack(fill="both", expand=True)

        faixa = tk.Frame(raiz, bg=COR_FAIXA, height=6)
        faixa.pack(fill="x")
        faixa.pack_propagate(False)

        painel = tk.Frame(raiz, bg=COR_FUNDO, padx=28, pady=20)
        painel.pack(fill="both", expand=True)
        painel.columnconfigure(0, weight=1)

        cabecalho = tk.Frame(painel, bg=COR_FUNDO)
        cabecalho.pack(fill="x", pady=(4, 18))

        tk.Label(
            cabecalho,
            text="ORC",
            font=("Segoe UI", 26, "bold"),
            fg=COR_TITULO_PADRAO,
            bg=COR_FUNDO,
        ).pack(anchor="center")
        tk.Label(
            cabecalho,
            text="Orçamentos de Reparos Construtivos",
            font=("Segoe UI", 10),
            fg="#5a6a72",
            bg=COR_FUNDO,
        ).pack(anchor="center", pady=(2, 0))

        cartao = tk.Frame(
            painel,
            bg=COR_FUNDO_CARTAO,
            highlightbackground=COR_BORDA_PADRAO,
            highlightthickness=2,
        )
        cartao.pack(fill="x")
        inner = tk.Frame(cartao, bg=COR_FUNDO_CARTAO, padx=20, pady=18)
        inner.pack(fill="x")
        inner.columnconfigure(0, weight=1)

        # master=root: evita Variable órfã após destruir o Tk do login.
        self.var_usuario = tk.StringVar(master=root, value=config.get("usuario", ""))
        self.var_senha = tk.StringVar(master=root, value=config.get("senha", ""))
        self.var_salvar_usuario = tk.BooleanVar(
            master=root, value=bool(config.get("salvar_usuario"))
        )
        self.var_salvar_senha = tk.BooleanVar(
            master=root, value=bool(config.get("salvar_senha"))
        )

        self._campo(inner, "Usuário", self.var_usuario, linha=0)
        entrada_senha = self._campo(
            inner,
            "Senha",
            self.var_senha,
            linha=2,
            mostrar="•",
        )
        entrada_senha.bind("<Return>", lambda _e: self._entrar())

        opcoes = tk.Frame(inner, bg=COR_FUNDO_CARTAO)
        opcoes.grid(row=4, column=0, sticky="w", pady=(12, 0))

        chk_usuario = tk.Checkbutton(
            opcoes,
            text="Salvar usuário",
            variable=self.var_salvar_usuario,
            command=self._ao_alterar_salvar_usuario,
            bg=COR_FUNDO_CARTAO,
            activebackground=COR_FUNDO_CARTAO,
            fg=COR_ROTULO,
            activeforeground=COR_ROTULO,
            selectcolor="#ffffff",
            font=("Segoe UI", 9),
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
            selectcolor="#ffffff",
            font=("Segoe UI", 9),
            anchor="w",
        )
        chk_senha.pack(anchor="w", pady=(2, 0))

        status = tk.Frame(painel, bg=COR_FUNDO, height=56)
        status.pack(fill="x", pady=(14, 10))
        status.pack_propagate(False)

        self._slot_amp = tk.Frame(status, bg=COR_FUNDO, width=30, height=28)
        self._slot_amp.pack(side="left", padx=(0, 8))
        self._slot_amp.pack_propagate(False)

        self._lbl_erro = tk.Label(
            status,
            text="",
            font=("Segoe UI", 9),
            fg=COR_ERRO,
            bg=COR_FUNDO,
            wraplength=WRAP_ERRO - 38,
            justify="left",
            anchor="w",
        )
        self._lbl_erro.pack(side="left", fill="both", expand=True)

        botoes = ttk.Frame(painel)
        botoes.pack(fill="x", pady=(4, 0))
        self._btn_sair = criar_botao_ttk_com_icone(
            botoes,
            texto="Sair",
            nome_icone="log-out-outline",
            command=self._cancelar,
            estilo="Delete.TButton",
            refs=self._refs_icones,
        )
        self._btn_sair.pack(side="right")
        self._btn_entrar = criar_botao_ttk_com_icone(
            botoes,
            texto="Entrar",
            nome_icone="log-in-outline",
            command=self._entrar,
            estilo="Add.TButton",
            refs=self._refs_icones,
        )
        self._btn_entrar.pack(side="right", padx=(0, 8))

        root.bind("<Escape>", lambda _e: self._cancelar())
        root.update_idletasks()
        altura = max(root.winfo_reqheight(), 400)
        root.minsize(LARGURA_JANELA, altura)
        root.maxsize(LARGURA_JANELA, 900)
        root.geometry(f"{LARGURA_JANELA}x{altura}")
        centralizar_janela(root)
        self._trazer_para_frente()

        if self.var_usuario.get().strip() and not self.var_senha.get():
            entrada_senha.focus_set()
        elif not self.var_usuario.get().strip():
            root.focus_set()

    def esperar(self) -> bool:
        self.root.wait_variable(self._concluido)
        return self.resultado

    def limpar(self) -> None:
        """Libera imagens/agendamentos com o Tk ainda vivo (antes do destroy)."""
        self._cancelar_agendamentos()
        if self._ampulheta is not None:
            try:
                self._ampulheta.liberar()
            except tk.TclError:
                pass
            try:
                self._ampulheta.destroy()
            except tk.TclError:
                pass
            self._ampulheta = None
        self._refs_icones.clear()
        self._btn_entrar = None
        self._btn_sair = None

    def _trazer_para_frente(self):
        root = self.root
        try:
            root.deiconify()
            root.lift()
            root.focus_force()
            if sys.platform == "win32":
                root.attributes("-topmost", True)
                self._after_topmost = root.after(300, self._liberar_topmost)
        except tk.TclError:
            pass

    def _liberar_topmost(self):
        self._after_topmost = None
        try:
            self.root.attributes("-topmost", False)
        except tk.TclError:
            pass

    def _cancelar_agendamentos(self):
        for atributo in ("_after_topmost", "_after_login"):
            after_id = getattr(self, atributo, None)
            if after_id is None:
                continue
            try:
                self.root.after_cancel(after_id)
            except (tk.TclError, ValueError):
                pass
            setattr(self, atributo, None)

    def _campo(self, parent, rotulo, variavel, *, linha, mostrar=None):
        tk.Label(
            parent,
            text=rotulo,
            bg=COR_FUNDO_CARTAO,
            fg=COR_ROTULO,
            font=("Segoe UI", 9),
        ).grid(row=linha, column=0, sticky="w", pady=(0 if linha == 0 else 10, 4))
        kwargs = {"textvariable": variavel}
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

    def _definir_botoes_habilitados(self, habilitado: bool):
        # "Sair" segue ativo durante a conexão para o usuário poder desistir.
        if self._btn_entrar is None:
            return
        try:
            self._btn_entrar.configure(state="normal" if habilitado else "disabled")
        except tk.TclError:
            pass

    def _garantir_ampulheta(self):
        if self._ampulheta is not None or self._slot_amp is None:
            return
        self._ampulheta = IndicadorAmpulheta(
            self._slot_amp,
            altura=22,
            cor=COR_STATUS,
            bg=COR_FUNDO,
            refs=self._refs_icones,
        )

    def _mostrar_status(self, texto: str, *, erro: bool = False, carregando: bool = False):
        self._lbl_erro.config(
            text=texto,
            fg=COR_ERRO if erro else COR_STATUS,
        )
        if carregando:
            self._garantir_ampulheta()
            if self._ampulheta is not None:
                self._ampulheta.iniciar()
            return
        if self._ampulheta is not None:
            self._ampulheta.parar()

    def _persistir_credenciais(self, usuario: str, senha: str) -> None:
        salvar_config(
            URL_PADRAO,
            salvar_usuario=bool(self.var_salvar_usuario.get()),
            salvar_senha=bool(self.var_salvar_senha.get()),
            usuario=usuario,
            senha=senha,
        )

    def _falha_login(self, mensagem: str):
        self._conectando = False
        self._definir_botoes_habilitados(True)
        self._mostrar_status(mensagem, erro=True)

    def _sucesso_login(self, usuario: str, senha: str):
        self._persistir_credenciais(usuario, senha)
        self._finalizar(True)

    def _consultar_resultado_login(self):
        """Poll na thread da UI: Tk não pode ser tocado pela thread de rede."""
        self._after_login = None
        try:
            status, dado = self._fila_login.get_nowait()
        except queue.Empty:
            if self._conectando:
                try:
                    self._after_login = self.root.after(
                        120, self._consultar_resultado_login
                    )
                except tk.TclError:
                    pass
            return

        if status == "ok":
            usuario, senha = dado
            self._sucesso_login(usuario, senha)
        else:
            self._falha_login(dado)

    def _finalizar(self, resultado: bool):
        self._cancelar_agendamentos()
        if self._ampulheta is not None:
            try:
                self._ampulheta.parar()
            except tk.TclError:
                pass
        self.resultado = resultado
        self._concluido.set(True)

    def _cancelar(self):
        # Fechar a janela deve funcionar mesmo com a rede pendurada;
        # o resultado tardio da thread é descartado com o poll cancelado.
        self._finalizar(False)

    def _entrar(self):
        if self._conectando:
            return
        usuario = self.var_usuario.get().strip()
        senha = self.var_senha.get()
        if not usuario:
            self._mostrar_status("Informe o usuário.", erro=True)
            return
        if not senha:
            self._mostrar_status("Informe a senha.", erro=True)
            return

        self._conectando = True
        self._definir_botoes_habilitados(False)
        self._mostrar_status("Conectando…", carregando=True)

        def trabalho():
            try:
                cliente = reiniciar_cliente(base_url=URL_PADRAO)
                cliente.verificar_saude()
                cliente.login(usuario, senha)
            except ApiError as exc:
                self._fila_login.put(("erro", exc.mensagem))
                return
            except Exception as exc:
                self._fila_login.put(("erro", str(exc)))
                return
            self._fila_login.put(("ok", (usuario, senha)))

        threading.Thread(target=trabalho, daemon=True).start()
        try:
            self._after_login = self.root.after(120, self._consultar_resultado_login)
        except tk.TclError:
            self._conectando = False


def garantir_login(parent: tk.Tk) -> bool:
    print("[ORC] Tela: Login")
    dialogo = DialogoLogin(parent)
    try:
        from atualizacao import iniciar_verificacao_atualizacao
        from core.app_state import APP_VERSION

        iniciar_verificacao_atualizacao(parent, APP_VERSION)
    except ImportError:
        pass
    try:
        ok = dialogo.esperar()
    finally:
        dialogo.limpar()
        gc.collect()
    if ok:
        print("[ORC] Login autenticado")
    else:
        print("[ORC] Login não concluído")
    return ok
