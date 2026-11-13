import gc
import tkinter as tk

from app_paths import icon_path
from core.app_state import (
    ALTURA_JANELA_PADRAO,
    APP_VERSION,
    LARGURA_JANELA_PADRAO,
    AppContext,
)
from core.precarga_catalogos import iniciar_precarga_catalogos
from ui.area_privativa import criar_area_privativa
from ui.area_comum import AreaComumFrame
from ui.composicoes_proprias import ComposicoesPropriasFrame
from ui.consulta_sinapi import ConsultaSinapiFrame
from ui.etapas_predefinidas import EtapasPredefinidasFrame
from ui.hub import HubFrame
from ui.orcamento_customizado_modulo import OrcamentoCustomizadoModulo
from ui.dialogo_configuracoes import abrir_dialogo_configuracoes
from ui.dialogo_login import garantir_login
from ui.icones import criar_icone_svg
from ui.widgets import centralizar_janela_principal, vincular_tooltip
from ui.temas import aplicar_tema, cores_tema, limpar_listeners_tema, registrar_listener_tema
from tkinter import messagebox

TITULOS_JANELA = {
    "hub": "ORC — Orçamentos de Reparos Construtivos",
    "area_privativa": "ORC — Área Privativa",
    "area_comum": "ORC — Área Comum",
    "consulta_sinapi": "ORC — Consulta SINAPI",
    "orcamento_customizado": "ORC — Orçamento Customizado",
    "composicoes_proprias": "ORC — Composições Próprias",
    "etapas_predefinidas": "ORC — Etapas pré-definidas",
}


class OrcApp:
    def __init__(self, *, offline: bool = False):
        self.offline = offline
        self.ctx = AppContext()
        self._modulo_atual = None
        self._frames = {}
        self.pediu_logout = False
        self._after_sinapi = None

        self.janela = tk.Tk()
        self.janela.withdraw()
        self.ctx.janela = self.janela
        self.ctx.iniciar_carregamento_sinapi()
        aplicar_tema(self.janela)

        self.janela.title(TITULOS_JANELA["hub"])
        self.janela.minsize(940, 620)
        centralizar_janela_principal(
            self.janela, LARGURA_JANELA_PADRAO, ALTURA_JANELA_PADRAO
        )

        icone = icon_path()
        if icone is not None:
            self.janela.iconbitmap(icone)

        self.ctx.status_sinapi = tk.StringVar(value="SINAPI: verificando...")
        self.ctx.status_servidor_sinapi = tk.StringVar(value="—")
        self.ctx.http_servidor_sinapi = tk.StringVar(value="—")
        self.ctx.carregar_status_servidor_persistido()

        self._montar_rodape()

        self.area_conteudo = tk.Frame(self.janela)
        self.area_conteudo.pack(fill="both", expand=True)

        self._criar_hub()
        self._aplicar_chrome()
        limpar_listeners_tema()
        registrar_listener_tema(self._ao_mudar_tema)
        self.mostrar_modulo("hub")
        try:
            self.janela.deiconify()
            self.janela.lift()
        except tk.TclError:
            pass

        # Continua / conclui a checagem iniciada no login (ou inicia no offline).
        self._schedule_update_check()
        self._after_sinapi = self.janela.after(500, self._aguardar_sinapi_e_verificar)

    def _aguardar_sinapi_e_verificar(self):
        self._after_sinapi = None
        try:
            if self.janela is None or not self.janela.winfo_exists():
                return
        except tk.TclError:
            return
        if self.ctx.janela is None:
            return
        if self.ctx._sinapi_carregando:
            self._after_sinapi = self.janela.after(300, self._aguardar_sinapi_e_verificar)
            return
        self.ctx.iniciar_verificacao_sinapi()

    def _cancelar_afters_app(self):
        job = getattr(self, "_after_sinapi", None)
        if job is not None and self.janela is not None:
            try:
                self.janela.after_cancel(job)
            except (tk.TclError, ValueError):
                pass
        self._after_sinapi = None

    def _schedule_update_check(self):
        try:
            from atualizacao import iniciar_verificacao_atualizacao

            iniciar_verificacao_atualizacao(self.janela, APP_VERSION)
        except ImportError:
            pass

    def _montar_rodape(self):
        cores = cores_tema(self.janela)
        frame_rodape = tk.Frame(self.janela)
        self.ctx.frame_rodape = frame_rodape
        frame_rodape.pack(side="bottom", fill="x", padx=10, pady=(0, 6))

        # Quadradinho com a situação da SINAPI (verde, âmbar ou vermelho).
        indicador = tk.Frame(frame_rodape, width=8, height=8, bg=cores.texto_suave)
        indicador.pack(side="left", padx=(0, 6))
        self.ctx.indicador_sinapi_rodape = indicador

        label_rodape = tk.Label(
            frame_rodape,
            text=self.ctx.texto_rodape_interface(),
            font=("Arial", 8),
            fg=cores.texto_suave,
            bg=cores.fundo,
            anchor="w",
        )
        self.ctx.label_rodape = label_rodape
        label_rodape.pack(side="left", anchor="w")
        for widget in (indicador, label_rodape):
            vincular_tooltip(widget, lambda: self.ctx.dica_sinapi)
        # Clicar no rodapé também tira o foco de um cartão do Hub.
        for widget in (frame_rodape, indicador, label_rodape):
            widget.bind("<Button-1>", lambda _e: self.janela.focus_set(), add="+")
        self.ctx.atualizar_indicador_sinapi()

        self._refs_rodape: list = []
        slot_config = tk.Frame(frame_rodape, bg=cores.fundo)
        self.ctx.slot_configuracoes_rodape = slot_config
        slot_config.pack(side="right", anchor="e")
        self._montar_botao_configuracoes(slot_config, cores)

    def _montar_botao_configuracoes(self, parent, cores):
        icone = criar_icone_svg(
            parent,
            "settings-outline",
            altura=16,
            cor=cores.texto_suave,
        )
        self._refs_rodape.append(icone)
        btn = tk.Label(
            parent,
            image=icone,
            bg=cores.fundo,
            cursor="hand2",
            padx=4,
            pady=1,
        )
        btn.image = icone  # type: ignore[attr-defined]
        btn.pack(side="right", anchor="e")
        btn.bind("<Button-1>", lambda _e: self._abrir_configuracoes())
        vincular_tooltip(btn, "Configurações")
        self.ctx.btn_configuracoes_rodape = btn
        try:
            parent.lift()
        except tk.TclError:
            pass

    def _abrir_configuracoes(self):
        abrir_dialogo_configuracoes(self.janela, self.ctx)

    def _atualizar_botao_configuracoes(self, cores):
        btn = getattr(self.ctx, "btn_configuracoes_rodape", None)
        if btn is None:
            return
        try:
            if not btn.winfo_exists():
                return
        except tk.TclError:
            return
        self._refs_rodape.clear()
        icone = criar_icone_svg(
            btn,
            "settings-outline",
            altura=16,
            cor=cores.texto_suave,
        )
        self._refs_rodape.append(icone)
        try:
            btn.configure(image=icone, bg=cores.fundo)
            btn.image = icone  # type: ignore[attr-defined]
        except tk.TclError:
            pass

    def _ao_mudar_tema(self, _tema_id):
        from ui.calculadora import fechar_calculadora

        fechar_calculadora()
        self._aplicar_chrome()
        hub = self._frames.get("hub")
        if hub is not None:
            hub.atualizar_tema()
        atual = self._modulo_atual
        for nome in list(self._frames):
            if nome == "hub":
                continue
            frame = self._frames.pop(nome)
            try:
                frame.destroy()
            except tk.TclError:
                pass
        if atual and atual != "hub":
            self.mostrar_modulo(atual)

    def _aplicar_chrome(self):
        cores = cores_tema(self.janela)
        try:
            self.janela.configure(bg=cores.fundo)
        except tk.TclError:
            pass
        area = getattr(self, "area_conteudo", None)
        if area is not None:
            try:
                area.configure(bg=cores.fundo)
            except tk.TclError:
                pass
        rodape = getattr(self.ctx, "frame_rodape", None)
        if rodape is not None:
            try:
                rodape.configure(bg=cores.fundo)
            except tk.TclError:
                pass
        quadro = getattr(self.ctx, "slot_configuracoes_rodape", None)
        if quadro is not None:
            try:
                quadro.configure(bg=cores.fundo)
            except tk.TclError:
                pass
        label_rodape = getattr(self.ctx, "label_rodape", None)
        if label_rodape is not None:
            try:
                label_rodape.configure(bg=cores.fundo, fg=cores.texto_suave)
            except tk.TclError:
                pass
        self.ctx.atualizar_indicador_sinapi()
        self._atualizar_botao_configuracoes(cores)

    def _criar_hub(self):
        self._frames["hub"] = HubFrame(
            self.area_conteudo,
            self.ctx,
            on_selecionar_modulo=self._ao_selecionar_modulo_hub,
            on_logout=None if self.offline else self._logout,
            offline=self.offline,
        )

    def _logout(self):
        from atualizacao import reiniciar_coordenador_atualizacao
        from core.api_client import get_client
        from core.composicoes_proprias_storage import limpar_cache as limpar_cache_composicoes
        from core.etapas_predefinidas_storage import limpar_cache as limpar_cache_etapas
        from core.orcamento_storage import limpar_cache as limpar_cache_orcamentos

        print("[ORC] Logout — retornando à tela de login")
        self.pediu_logout = True
        limpar_listeners_tema()
        self._cancelar_afters_app()
        try:
            get_client().logout()
        except Exception:
            pass
        limpar_cache_composicoes()
        limpar_cache_etapas()
        limpar_cache_orcamentos()
        reiniciar_coordenador_atualizacao()
        self.ctx.desligar_ui()

        # Liberar PhotoImage/Variable na thread principal ANTES do destroy.
        for frame in list(self._frames.values()):
            refs = getattr(frame, "_refs_icones", None)
            if isinstance(refs, list):
                refs.clear()
            refs_botoes = getattr(frame, "_icones_botoes", None)
            if isinstance(refs_botoes, list):
                refs_botoes.clear()
        self._frames.clear()
        try:
            for filho in list(self.area_conteudo.winfo_children()):
                filho.destroy()
        except tk.TclError:
            pass
        gc.collect()
        try:
            self.janela.destroy()
        except tk.TclError:
            pass

    def _criar_modulo(self, nome):
        print(f"[ORC] Criando módulo: {nome}")
        if nome == "area_privativa":
            self._frames[nome] = criar_area_privativa(
                self.area_conteudo,
                self.ctx,
                on_voltar=lambda: self.mostrar_modulo("hub"),
            )
        elif nome == "consulta_sinapi":
            self._frames[nome] = ConsultaSinapiFrame(
                self.area_conteudo,
                self.ctx,
                on_voltar=lambda: self.mostrar_modulo("hub"),
            )
        elif nome == "orcamento_customizado":
            self._frames[nome] = OrcamentoCustomizadoModulo(
                self.area_conteudo,
                self.ctx,
                on_voltar=lambda: self.mostrar_modulo("hub"),
            )
        elif nome == "composicoes_proprias":
            self._frames[nome] = ComposicoesPropriasFrame(
                self.area_conteudo,
                self.ctx,
                on_voltar=lambda: self.mostrar_modulo("hub"),
            )
        elif nome == "etapas_predefinidas":
            self._frames[nome] = EtapasPredefinidasFrame(
                self.area_conteudo,
                self.ctx,
                on_voltar=lambda: self.mostrar_modulo("hub"),
            )
        elif nome == "area_comum":
            self._frames[nome] = AreaComumFrame(
                self.area_conteudo,
                self.ctx,
                on_voltar=lambda: self.mostrar_modulo("hub"),
                offline=self.offline,
            )

    def _ao_selecionar_modulo_hub(self, modulo):
        # O hub já oculta o cartão para quem não é admin; não consultar a API de novo
        # no clique (isso congelava a UI e, se a rede falhasse, negava o próprio admin).
        self.mostrar_modulo(modulo)

    def mostrar_modulo(self, nome):
        if self.pediu_logout:
            return
        try:
            if self.janela is None or not self.janela.winfo_exists():
                return
        except tk.TclError:
            return
        print(f"[ORC] Navegação → {TITULOS_JANELA.get(nome, nome)}")
        if (
            self._modulo_atual == "area_privativa"
            and "area_privativa" in self._frames
        ):
            self._frames["area_privativa"].desativar_scroll()

        modulos_expandidos = (
            "area_privativa",
            "area_comum",
            "consulta_sinapi",
            "orcamento_customizado",
            "composicoes_proprias",
            "etapas_predefinidas",
        )
        saindo_modulo_expandido = (
            self._modulo_atual in modulos_expandidos
            and nome not in modulos_expandidos
        )
        entrando_modulo_expandido = nome in modulos_expandidos
        modulo_anterior = self._modulo_atual
        cursor_anterior = None
        try:
            cursor_anterior = self.janela.cget("cursor")
            self.janela.config(cursor="watch")
            self.janela.update_idletasks()
        except tk.TclError:
            cursor_anterior = None

        try:
            # Monta o módulo com o hub ainda visível; só troca a tela depois.
            if nome not in self._frames:
                self._criar_modulo(nome)

            for frame in self._frames.values():
                frame.pack_forget()

            if entrando_modulo_expandido:
                try:
                    self.janela.state("zoomed")
                except tk.TclError:
                    self.janela.attributes("-zoomed", True)
            elif saindo_modulo_expandido:
                try:
                    self.janela.state("normal")
                except tk.TclError:
                    self.janela.attributes("-zoomed", False)
                centralizar_janela_principal(
                    self.janela, LARGURA_JANELA_PADRAO, ALTURA_JANELA_PADRAO
                )

            self._frames[nome].pack(fill="both", expand=True)
            self._modulo_atual = nome
            self.janela.title(TITULOS_JANELA.get(nome, TITULOS_JANELA["hub"]))

            if nome == "hub":
                centralizar_janela_principal(
                    self.janela, LARGURA_JANELA_PADRAO, ALTURA_JANELA_PADRAO
                )
            elif nome in (
                "area_privativa",
                "area_comum",
                "consulta_sinapi",
                "orcamento_customizado",
                "composicoes_proprias",
                "etapas_predefinidas",
            ):
                if nome == "area_privativa":
                    self._frames[nome].ativar_scroll()
                self._frames[nome].focar()
        except Exception as exc:
            print(f"[ORC] Falha ao abrir módulo {nome}: {exc}")
            if nome in self._frames and nome != "hub":
                try:
                    self._frames[nome].destroy()
                except tk.TclError:
                    pass
                self._frames.pop(nome, None)
            messagebox.showerror(
                "Serviço indisponível",
                str(exc)
                or "Não foi possível abrir este módulo.\n"
                "Verifique se a API e o banco de dados estão disponíveis.",
                parent=self.janela,
            )
            destino = "hub" if nome != "hub" else modulo_anterior or "hub"
            if destino == nome:
                destino = "hub"
            if destino in self._frames:
                self._frames[destino].pack(fill="both", expand=True)
                self._modulo_atual = destino
                self.janela.title(TITULOS_JANELA.get(destino, TITULOS_JANELA["hub"]))
                if destino == "hub":
                    try:
                        self.janela.state("normal")
                    except tk.TclError:
                        pass
                    centralizar_janela_principal(
                        self.janela, LARGURA_JANELA_PADRAO, ALTURA_JANELA_PADRAO
                    )
        finally:
            if cursor_anterior is not None:
                try:
                    self.janela.config(cursor=cursor_anterior)
                except tk.TclError:
                    pass

    def executar(self):
        self.janela.mainloop()


if __name__ == "__main__":
    while True:
        print("[ORC] Abrindo tela de login")
        _root_login = tk.Tk()
        _root_login.withdraw()
        try:
            logou = garantir_login(_root_login)
        except Exception as exc:
            print(f"[ORC] Falha na tela de login: {exc}")
            logou = False
        if not logou:
            print("[ORC] Login cancelado — encerrando")
            try:
                from atualizacao import reiniciar_coordenador_atualizacao

                reiniciar_coordenador_atualizacao()
            except ImportError:
                pass
            try:
                _root_login.destroy()
            except tk.TclError:
                pass
            gc.collect()
            raise SystemExit(0)
        try:
            from atualizacao import reiniciar_coordenador_atualizacao

            # Solta o poll do login antes de destruir a janela.
            reiniciar_coordenador_atualizacao()
        except ImportError:
            pass
        try:
            _root_login.destroy()
        except tk.TclError:
            pass
        gc.collect()
        print("[ORC] Login ok — iniciando hub")
        iniciar_precarga_catalogos()
        app = OrcApp()
        try:
            app.executar()
        except tk.TclError as exc:
            print(f"[ORC] Janela encerrada com TclError: {exc}")
        pediu_logout = bool(getattr(app, "pediu_logout", False))
        del app
        gc.collect()
        if not pediu_logout:
            print("[ORC] Aplicação encerrada")
            break
        print("[ORC] Sessão encerrada — novo ciclo de login")
