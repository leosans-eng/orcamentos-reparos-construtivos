import ctypes
import gc
import queue
import sys
import threading
import time
import tkinter as tk
import traceback
from tkinter import font as tkfont
from tkinter import ttk

from core.api_client import OrcApiClient, reiniciar_cliente
from core.api_config import URL_PADRAO, carregar_config, limpar_sessao, salvar_config
from core.api_exceptions import ApiError, ApiIndisponivelError
from ui.icones import IndicadorAmpulheta, criar_botao_ttk_com_icone, definir_estado_botao_icone
from ui.temas import aplicar_tema, cores_tema, estilos_botao
from ui.widgets import (
    aplicar_icone_janela,
    centralizar_janela,
)

LARGURA_JANELA = 420
WRAP_ERRO = LARGURA_JANELA - 64

# Depois desse tempo sem resposta, a mensagem "Entrando…" muda para avisar
# que o servidor está lento (o limite do pedido é de 12 s, em api_client).
SEGUNDOS_AVISO_DEMORA = 5
# Com o servidor fora, o indicador do rodapé tenta de novo nesse intervalo.
SEGUNDOS_NOVA_CHECAGEM = 10
# Por quanto tempo o rodapé fica de olho na busca de atualização.
SEGUNDOS_ESPERA_ATUALIZACAO = 60

MSG_ERRO_INESPERADO = (
    "Algo deu errado ao entrar. Tente de novo; se continuar, contate o suporte."
)


def _caps_lock_ligado() -> bool:
    if sys.platform != "win32":
        return False
    try:
        return bool(ctypes.windll.user32.GetKeyState(0x14) & 1)  # 0x14 = Caps Lock
    except (AttributeError, OSError):
        return False


class DialogoLogin:
    """Login montado na janela raiz (Tk) para aparecer na barra de tarefas."""

    def __init__(self, root: tk.Tk, app_version: str = ""):
        self.root = root
        self.resultado = False
        self._refs_icones: list = []
        self._after_topmost = None
        self._after_login = None
        self._after_rodape = None
        self._concluido = tk.BooleanVar(master=root, value=False)
        self._conectando = False
        self._inicio_login = 0.0
        self._avisou_demora = False
        self._btn_entrar = None
        self._btn_sair = None
        self._ampulheta = None
        self._slot_amp = None
        self._fila_login: queue.Queue = queue.Queue()
        # Protege a decisão "cancelou ou não" entre a tela e a thread de rede.
        self._lock_login = threading.Lock()
        self._cancelado = False

        self._app_version = app_version
        self._fila_servidor: queue.Queue = queue.Queue()
        self._checando_servidor = False
        self._servidor_online: bool | None = None
        self._ultima_checagem = 0.0
        self._inicio_tela = time.monotonic()
        self._versao_nova_mostrada = False

        try:
            root.withdraw()
        except tk.TclError:
            pass

        aplicar_tema(root)
        cores = cores_tema(root)
        self._cores = cores
        self._cor_ok = "#66bb6a" if cores.escuro else "#2e7d32"
        self._cor_aviso = "#ffb74d" if cores.escuro else "#b26a00"

        config = carregar_config()
        root.title("ORC — Login")
        aplicar_icone_janela(root)
        root.configure(bg=cores.fundo)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self._cancelar)

        for filho in list(root.winfo_children()):
            try:
                filho.destroy()
            except tk.TclError:
                pass

        raiz = tk.Frame(root, bg=cores.fundo)
        raiz.pack(fill="both", expand=True)

        faixa = tk.Frame(raiz, bg=cores.faixa, height=6)
        faixa.pack(fill="x")
        faixa.pack_propagate(False)

        self._montar_rodape(raiz)

        painel = tk.Frame(raiz, bg=cores.fundo, padx=28, pady=20)
        painel.pack(fill="both", expand=True)
        painel.columnconfigure(0, weight=1)

        cabecalho = tk.Frame(painel, bg=cores.fundo)
        cabecalho.pack(fill="x", pady=(4, 18))

        tk.Label(
            cabecalho,
            text="ORC",
            font=("Segoe UI", 26, "bold"),
            fg=cores.titulo,
            bg=cores.fundo,
        ).pack(anchor="center")
        tk.Label(
            cabecalho,
            text="Orçamentos de Reparos Construtivos",
            font=("Segoe UI", 10),
            fg=cores.texto_suave,
            bg=cores.fundo,
        ).pack(anchor="center", pady=(2, 0))

        cartao = tk.Frame(
            painel,
            bg=cores.fundo_cartao,
            highlightbackground=cores.borda,
            highlightthickness=2,
        )
        cartao.pack(fill="x")
        inner = tk.Frame(cartao, bg=cores.fundo_cartao, padx=20, pady=18)
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

        _lbl_usuario, self._entrada_usuario = self._campo(
            inner, "Usuário", self.var_usuario, linha=0
        )
        _lbl_senha, self._entrada_senha = self._campo(
            inner, "Senha", self.var_senha, linha=2, mostrar="•"
        )
        self.var_mostrar_senha = tk.BooleanVar(master=root, value=False)

        linha_senha = tk.Frame(inner, bg=cores.fundo_cartao)
        linha_senha.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        ttk.Checkbutton(
            linha_senha,
            text="Mostrar senha",
            variable=self.var_mostrar_senha,
            command=self._ao_mostrar_senha,
            style="Cartao.TCheckbutton",
        ).pack(side="left")
        self._lbl_caps = tk.Label(
            linha_senha,
            text="",
            font=("Segoe UI", 9, "bold"),
            fg=self._cor_aviso,
            bg=cores.fundo_cartao,
        )
        self._lbl_caps.pack(side="right")

        opcoes = tk.Frame(inner, bg=cores.fundo_cartao)
        opcoes.grid(row=5, column=0, sticky="w", pady=(12, 0))

        ttk.Checkbutton(
            opcoes,
            text="Lembrar meu usuário",
            variable=self.var_salvar_usuario,
            command=self._ao_alterar_salvar_usuario,
            style="Cartao.TCheckbutton",
        ).pack(anchor="w")
        ttk.Checkbutton(
            opcoes,
            text="Lembrar minha senha",
            variable=self.var_salvar_senha,
            command=self._ao_alterar_salvar_senha,
            style="Cartao.TCheckbutton",
        ).pack(anchor="w", pady=(2, 0))

        status = tk.Frame(painel, bg=cores.fundo, height=56)
        status.pack(fill="x", pady=(14, 10))
        status.pack_propagate(False)

        self._slot_amp = tk.Frame(status, bg=cores.fundo, width=30, height=28)
        self._slot_amp.pack(side="left", padx=(0, 8))
        self._slot_amp.pack_propagate(False)

        self._lbl_erro = tk.Label(
            status,
            text="",
            font=("Segoe UI", 9),
            fg=cores.perigo,
            bg=cores.fundo,
            wraplength=WRAP_ERRO - 38,
            justify="left",
            anchor="w",
        )
        self._lbl_erro.pack(side="left", fill="both", expand=True)

        botoes = tk.Frame(painel, bg=cores.fundo)
        botoes.pack(fill="x", pady=(4, 0))
        estilos = estilos_botao(root)
        self._btn_sair = criar_botao_ttk_com_icone(
            botoes,
            texto="Sair",
            nome_icone="log-out-outline",
            command=self._cancelar,
            estilo=estilos.excluir,
            cor_icone=estilos.icone_excluir,
            refs=self._refs_icones,
        )
        self._btn_sair.pack(side="right")
        self._btn_entrar = criar_botao_ttk_com_icone(
            botoes,
            texto="Entrar",
            nome_icone="log-in-outline",
            command=self._entrar,
            estilo=estilos.adicionar,
            cor_icone=estilos.icone_adicionar,
            refs=self._refs_icones,
        )
        self._btn_entrar.pack(side="right", padx=(0, 8))

        # Enter entra de qualquer ponto da tela; no campo Usuário, pula para a
        # Senha; com o foco em "Sair", sai.
        root.bind("<Return>", lambda _e: self._entrar())
        root.bind("<Escape>", lambda _e: self._cancelar())
        self._entrada_usuario.bind("<Return>", self._ir_para_senha)
        self._btn_sair.bind("<Return>", lambda _e: (self._cancelar(), "break")[1])
        for evento in ("<KeyRelease>", "<FocusIn>"):
            self._entrada_senha.bind(evento, self._atualizar_caps, add="+")
        self._entrada_senha.bind("<FocusOut>", lambda _e: self._lbl_caps.config(text=""), add="+")

        root.update_idletasks()
        altura = max(root.winfo_reqheight(), 400)
        root.minsize(LARGURA_JANELA, altura)
        root.maxsize(LARGURA_JANELA, 900)
        centralizar_janela(root, largura=LARGURA_JANELA, altura=altura)
        self._trazer_para_frente()

        if not self.var_usuario.get().strip():
            self._entrada_usuario.focus_set()
        elif not self.var_senha.get():
            self._entrada_senha.focus_set()
        else:
            # Tudo lembrado: basta apertar Enter.
            self._btn_entrar.focus_set()

        self._verificar_servidor()
        self._agendar_rodape()

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

    # ------------------------------------------------------------------ montagem

    def _campo(self, parent, rotulo, variavel, *, linha, mostrar=None):
        cores = self._cores
        lbl = tk.Label(
            parent,
            text=rotulo,
            bg=cores.fundo_cartao,
            fg=cores.texto_suave,
            font=("Segoe UI", 9),
        )
        lbl.grid(row=linha, column=0, sticky="w", pady=(0 if linha == 0 else 10, 4))
        kwargs = {"textvariable": variavel}
        if mostrar is not None:
            kwargs["show"] = mostrar
        entrada = ttk.Entry(parent, **kwargs)
        entrada.grid(row=linha + 1, column=0, sticky="ew")
        return lbl, entrada

    def _montar_rodape(self, parent) -> None:
        cores = self._cores
        rodape = tk.Frame(parent, bg=cores.fundo, padx=28, pady=8)
        rodape.pack(side="bottom", fill="x")
        tk.Frame(parent, bg=cores.borda_suave, height=1).pack(side="bottom", fill="x")

        self._quadrado_servidor = tk.Frame(rodape, width=8, height=8, bg=cores.texto_suave)
        self._quadrado_servidor.pack(side="left", padx=(0, 6))
        self._lbl_servidor = tk.Label(
            rodape,
            text="Verificando o servidor…",
            font=("Segoe UI", 8),
            fg=cores.texto_suave,
            bg=cores.fundo,
        )
        self._lbl_servidor.pack(side="left")

        texto_versao = f"Versão {self._app_version}" if self._app_version else ""
        self._lbl_versao = tk.Label(
            rodape,
            text=texto_versao,
            font=("Segoe UI", 8),
            fg=cores.texto_suave,
            bg=cores.fundo,
        )
        self._lbl_versao.pack(side="right")
        self._lbl_versao.bind("<Button-1>", lambda _e: self._abrir_atualizacao())

    # ------------------------------------------------------------------ janela

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
        for atributo in ("_after_topmost", "_after_login", "_after_rodape"):
            after_id = getattr(self, atributo, None)
            if after_id is None:
                continue
            try:
                self.root.after_cancel(after_id)
            except (tk.TclError, ValueError):
                pass
            setattr(self, atributo, None)

    # ------------------------------------------------------------------ campos

    def _ir_para_senha(self, _evento=None):
        self._entrada_senha.focus_set()
        self._entrada_senha.icursor("end")
        return "break"

    def _atualizar_caps(self, _evento=None):
        try:
            com_foco = self.root.focus_get() is self._entrada_senha
        except (tk.TclError, KeyError):
            com_foco = False
        ligado = com_foco and _caps_lock_ligado()
        self._lbl_caps.config(text="Caps Lock ativado" if ligado else "")

    def _ao_mostrar_senha(self):
        try:
            self._entrada_senha.configure(show="" if self.var_mostrar_senha.get() else "•")
        except tk.TclError:
            pass

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
            if habilitado:
                definir_estado_botao_icone(self._btn_entrar, "normal")
                return
            # Não usar state=disabled nem o ícone cinza: o ttk clareia o SVG
            # e o deixa embaçado enquanto "Entrando…".
            icone = getattr(self._btn_entrar, "_orc_img_normal", None)
            kwargs = {"state": "normal", "command": lambda: None}
            if icone is not None:
                kwargs["image"] = icone
            self._btn_entrar.configure(**kwargs)
        except tk.TclError:
            pass

    def _garantir_ampulheta(self):
        if self._ampulheta is not None or self._slot_amp is None:
            return
        self._ampulheta = IndicadorAmpulheta(
            self._slot_amp,
            altura=22,
            cor=self._cores.titulo,
            bg=self._cores.fundo,
            refs=self._refs_icones,
        )

    def _mostrar_status(self, texto: str, *, erro: bool = False, carregando: bool = False):
        self._lbl_erro.config(
            text=texto,
            fg=self._cores.perigo if erro else self._cores.titulo,
        )
        if carregando:
            self._garantir_ampulheta()
            if self._ampulheta is not None:
                self._ampulheta.iniciar()
            return
        if self._ampulheta is not None:
            self._ampulheta.parar()

    # ------------------------------------------------------------------ rodapé

    def _mostrar_servidor(self, online: bool | None):
        self._servidor_online = online
        cores = self._cores
        if online is None:
            cor, texto = cores.texto_suave, "Verificando o servidor…"
        elif online:
            cor, texto = self._cor_ok, "Servidor online"
        else:
            cor, texto = cores.perigo, "Sem conexão com o servidor"
        try:
            self._quadrado_servidor.config(bg=cor)
            self._lbl_servidor.config(text=texto)
        except tk.TclError:
            pass

    def _verificar_servidor(self):
        if self._checando_servidor:
            return
        self._checando_servidor = True
        self._ultima_checagem = time.monotonic()
        fila = self._fila_servidor

        def trabalho():
            try:
                online = OrcApiClient(URL_PADRAO, access_token="").health()
            except Exception:
                online = False
            fila.put(online)

        threading.Thread(target=trabalho, daemon=True).start()

    def _agendar_rodape(self):
        try:
            self._after_rodape = self.root.after(300, self._tick_rodape)
        except tk.TclError:
            self._after_rodape = None

    def _tick_rodape(self):
        """Poll na thread da UI: resultado do servidor e aviso de versão nova."""
        self._after_rodape = None
        try:
            online = self._fila_servidor.get_nowait()
        except queue.Empty:
            pass
        else:
            self._checando_servidor = False
            self._mostrar_servidor(online)

        agora = time.monotonic()
        if (
            self._servidor_online is False
            and not self._checando_servidor
            and agora - self._ultima_checagem >= SEGUNDOS_NOVA_CHECAGEM
        ):
            self._verificar_servidor()

        if (
            not self._versao_nova_mostrada
            and agora - self._inicio_tela < SEGUNDOS_ESPERA_ATUALIZACAO
        ):
            self._checar_versao_nova()

        self._agendar_rodape()

    def _checar_versao_nova(self):
        try:
            from atualizacao import versao_nova_encontrada
        except ImportError:
            self._versao_nova_mostrada = True
            return
        nova = versao_nova_encontrada()
        if not nova:
            return
        self._versao_nova_mostrada = True
        fonte_link = tkfont.Font(root=self.root, family="Segoe UI", size=8, underline=True)
        try:
            self._lbl_versao.config(
                text=f"Atualizar para a versão {nova}",
                font=fonte_link,
                fg=self._cores.titulo,
                cursor="hand2",
            )
        except tk.TclError:
            pass

    def _abrir_atualizacao(self):
        # Só funciona depois que o link aparece (há versão nova encontrada).
        if not self._versao_nova_mostrada:
            return
        try:
            from atualizacao import reabrir_aviso_atualizacao
        except ImportError:
            return
        reabrir_aviso_atualizacao(self.root)

    # ------------------------------------------------------------------ login

    def _persistir_credenciais(self, usuario: str, senha: str) -> None:
        try:
            salvar_config(
                URL_PADRAO,
                salvar_usuario=bool(self.var_salvar_usuario.get()),
                salvar_senha=bool(self.var_salvar_senha.get()),
                usuario=usuario,
                senha=senha,
            )
        except OSError as exc:
            # Não impede a entrada; só não lembra os dados desta vez.
            print(f"[ORC] Não foi possível salvar as preferências de login: {exc}")

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
            if not self._conectando:
                return
            demorou = time.monotonic() - self._inicio_login >= SEGUNDOS_AVISO_DEMORA
            if demorou and not self._avisou_demora:
                self._avisou_demora = True
                self._lbl_erro.config(text="O servidor está demorando para responder…")
            try:
                self._after_login = self.root.after(120, self._consultar_resultado_login)
            except tk.TclError:
                pass
            return

        if status == "ok":
            usuario, senha = dado
            self._sucesso_login(usuario, senha)
            return
        if status == "sem_conexao":
            self._mostrar_servidor(False)
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
        # Fechar a janela deve funcionar mesmo com a rede pendurada.
        with self._lock_login:
            self._cancelado = True
            try:
                status, _dado = self._fila_login.get_nowait()
            except queue.Empty:
                status = None
        if status == "ok":
            # O login terminou um instante antes do cancelamento: não deixa
            # a sessão gravada no disco para quem desistiu de entrar.
            limpar_sessao()
        self._finalizar(False)

    def _entrar(self):
        if self._conectando or self._concluido.get():
            return
        usuario = self.var_usuario.get().strip()
        senha = self.var_senha.get()
        if not usuario:
            self._mostrar_status("Informe o usuário.", erro=True)
            self._entrada_usuario.focus_set()
            return
        if not senha:
            self._mostrar_status("Informe a senha.", erro=True)
            self._entrada_senha.focus_set()
            return

        self._conectando = True
        self._inicio_login = time.monotonic()
        self._avisou_demora = False
        self._definir_botoes_habilitados(False)
        self._mostrar_status("Entrando…", carregando=True)

        def trabalho():
            try:
                cliente = reiniciar_cliente(base_url=URL_PADRAO)
                cliente.login(usuario, senha)
                resultado = ("ok", (usuario, senha))
            except ApiIndisponivelError as exc:
                resultado = ("sem_conexao", exc.mensagem)
            except ApiError as exc:
                resultado = ("erro", exc.mensagem)
            except Exception:
                traceback.print_exc()
                resultado = ("erro", MSG_ERRO_INESPERADO)
            with self._lock_login:
                if self._cancelado:
                    if resultado[0] == "ok":
                        limpar_sessao()
                    return
                self._fila_login.put(resultado)

        threading.Thread(target=trabalho, daemon=True).start()
        try:
            self._after_login = self.root.after(120, self._consultar_resultado_login)
        except tk.TclError:
            self._conectando = False


def garantir_login(parent: tk.Tk) -> bool:
    print("[ORC] Tela: Login")
    try:
        from core.app_state import APP_VERSION
    except ImportError:
        APP_VERSION = ""
    dialogo = DialogoLogin(parent, app_version=APP_VERSION)
    try:
        from atualizacao import iniciar_verificacao_atualizacao

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
