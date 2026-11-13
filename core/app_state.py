import json
import queue
import threading
import tkinter as tk
from typing import Any, Callable

from sinapi.atualizador_sinapi import (
    baixar_e_extrair,
    buscar_atualizacoes,
    carregar_status,
    limpar_versoes_antigas,
    salvar_status,
)
from sinapi.extrair_sinapi import processar_arquivo

from app_paths import anomalias_area_privativa_path

from core.sinapi_loader import (
    carregar_sinapi_inicial,
    obter_estados_da_sinapi,
    recarregar_sinapi,
)
from core.sinapi_base import SinapiBase

APP_VERSION = "1.5.2"

LARGURA_JANELA_PADRAO = 1080
ALTURA_JANELA_PADRAO = 720
ALTURA_TREE_MIN = 11

INTERVALO_FILA_UI_MS = 80

NOMES_GRUPOS_REPARO = {
    "reparo_pisos_ceramicos": "Reparo de Pisos Cerâmicos",
    "reparo_azulejos": "Reparo de Azulejos",
    "reparo_trincas": "Intervenção de fissuras e trincas",
    "reparo_esquadrias": "Reparo de infiltrações por esquadrias",
    "reparo_umidade_teto": "Reparo de umidade no teto",
    "reparo_umidade_parede": "Reparo de umidade na parede",
    "reparo_dr": "Instalação de Dispositivo DR",
}


class AppContext:
    def __init__(self):
        self.sinapi = SinapiBase.vazio()
        self.caminho_sinapi_carregado = None
        self.sinapi_referencia_rotulo = "Carregando..."
        self.dados_json = self._carregar_dados_json()
        self._sinapi_callbacks: list[Callable[[], Any]] = []

        self.janela: tk.Tk | None = None
        self.frame_rodape: tk.Frame | None = None
        self.label_rodape: tk.Label | None = None
        self.indicador_sinapi_rodape: tk.Frame | None = None
        self.dica_sinapi = ""
        self.slot_configuracoes_rodape: tk.Frame | None = None
        self.btn_configuracoes_rodape: tk.Label | None = None
        self.status_sinapi: tk.StringVar | None = None
        self.status_servidor_sinapi: tk.StringVar | None = None
        self.http_servidor_sinapi: tk.StringVar | None = None
        self._sinapi_verificando = False
        self._sinapi_carregando = False
        self._after_jobs: list[tuple[tk.Misc, str]] = []
        self._fila_ui: queue.Queue = queue.Queue()
        self._consumindo_fila_ui = False

    def _agendar_after(self, widget: tk.Misc, delay_ms: int, callback) -> str | None:
        """Agenda after e guarda o id para cancelar no logout."""
        registro: list = []

        def executar_e_remover():
            # Remove o próprio id antes de rodar: a lista não pode crescer
            # indefinidamente em animações que se reagendam.
            if registro:
                try:
                    self._after_jobs.remove(registro[0])
                except ValueError:
                    pass
            callback()

        try:
            if not widget.winfo_exists():
                return None
            job = widget.after(delay_ms, executar_e_remover)
        except (tk.TclError, RuntimeError):
            return None
        registro.append((widget, job))
        self._after_jobs.append(registro[0])
        return job

    def _cancelar_afters(self) -> None:
        jobs = list(self._after_jobs)
        self._after_jobs.clear()
        for widget, job in jobs:
            try:
                if widget.winfo_exists():
                    widget.after_cancel(job)
            except (tk.TclError, RuntimeError, ValueError):
                pass

    def iniciar_consumo_fila_ui(self) -> None:
        """Liga o laço que aplica os recados das threads. Só na thread principal."""
        if self._consumindo_fila_ui:
            return
        if self.janela is None:
            return
        self._consumindo_fila_ui = True
        self._consumir_fila_ui()

    def _consumir_fila_ui(self) -> None:
        janela = self.janela
        try:
            if janela is None or not janela.winfo_exists():
                self._consumindo_fila_ui = False
                return
        except tk.TclError:
            self._consumindo_fila_ui = False
            return

        while True:
            try:
                callback = self._fila_ui.get_nowait()
            except queue.Empty:
                break
            try:
                callback()
            except tk.TclError:
                pass
            except Exception as exc:
                print("Erro ao aplicar atualização de interface:", exc)

        if self._agendar_after(janela, INTERVALO_FILA_UI_MS, self._consumir_fila_ui) is None:
            self._consumindo_fila_ui = False

    def _agendar_na_janela(self, callback) -> None:
        """Encaminha trabalho para a interface a partir de qualquer thread.

        Tk só pode ser tocado pela thread principal; por isso a thread de fundo
        apenas deposita o recado na fila, e quem o executa é o laço de consumo.
        """
        if self.janela is None:
            return
        if threading.current_thread() is threading.main_thread():
            self._agendar_after(self.janela, 0, callback)
            return
        self._fila_ui.put(callback)

    def _descartar_fila_ui(self) -> None:
        while True:
            try:
                self._fila_ui.get_nowait()
            except queue.Empty:
                return

    def desligar_ui(self) -> None:
        """Evita callbacks Tk após destroy da janela (logout / reinício)."""
        self._cancelar_afters()
        self._consumindo_fila_ui = False
        self._descartar_fila_ui()
        self.janela = None
        self.frame_rodape = None
        self.label_rodape = None
        self.indicador_sinapi_rodape = None
        self.slot_configuracoes_rodape = None
        self.btn_configuracoes_rodape = None
        self.status_sinapi = None
        self.status_servidor_sinapi = None
        self.http_servidor_sinapi = None
        self._sinapi_callbacks.clear()

    def iniciar_carregamento_sinapi(self) -> None:
        if self._sinapi_carregando:
            return
        self.iniciar_consumo_fila_ui()
        self._sinapi_carregando = True
        threading.Thread(
            target=self._carregar_sinapi_inicial_background,
            daemon=True,
        ).start()

    def _carregar_sinapi_inicial_background(self) -> None:
        try:
            resultado = carregar_sinapi_inicial()
        except Exception as exc:
            print("Erro ao carregar SINAPI local:", exc)
            resultado = (SinapiBase.vazio(), None, "BASE AUSENTE")

        def aplicar():
            self._sinapi_carregando = False
            (
                self.sinapi,
                self.caminho_sinapi_carregado,
                self.sinapi_referencia_rotulo,
            ) = resultado
            self.notificar_sinapi_atualizada()

        self._agendar_na_janela(aplicar)

    def _carregar_dados_json(self):
        with open(anomalias_area_privativa_path(), "r", encoding="utf-8") as f:
            dados = json.load(f)
        if isinstance(dados, list):
            dados = dados[0]
        return dados

    def recarregar_dados_json(self):
        self.dados_json = self._carregar_dados_json()
        return self.dados_json

    def registrar_callback_sinapi(self, callback):
        self._sinapi_callbacks.append(callback)

    def notificar_sinapi_atualizada(self):
        self.atualizar_rodape()
        for callback in self._sinapi_callbacks:
            callback()

    def informacoes_versao(self):
        return {
            "app": APP_VERSION,
            "sinapi": self.sinapi_referencia_rotulo,
        }

    def texto_rodape_interface(self):
        info = self.informacoes_versao()
        base = f"Sistema ORC v{info['app']} · Referência SINAPI: {info['sinapi']}"
        extras = []
        if self.status_sinapi and self.status_sinapi.get():
            extras.append(self.status_sinapi.get())
        if extras:
            return f"{base} · {' · '.join(extras)}"
        return base

    def atualizar_rodape(self):
        if self.label_rodape and self.label_rodape.winfo_exists():
            self.label_rodape.config(text=self.texto_rodape_interface())
        self.atualizar_indicador_sinapi()

    def estado_sinapi(self) -> tuple[str, str]:
        """Resume a situação da base SINAPI para o quadradinho do rodapé.

        Devolve (estado, explicação), onde estado é "ok", "andamento",
        "atencao" ou "erro".
        """
        texto = (self.status_sinapi.get() if self.status_sinapi else "") or ""
        minusculo = texto.lower()
        if self.sinapi_referencia_rotulo == "BASE AUSENTE" or "erro" in minusculo:
            return "erro", "Não foi possível carregar a base SINAPI."
        if "indisponível (servidor e pasta local)" in minusculo:
            return "erro", "A base SINAPI não foi encontrada no site da Caixa nem neste computador."
        if self._sinapi_carregando or any(
            palavra in minusculo for palavra in ("verificando", "baixando", "processando")
        ):
            return "andamento", "Carregando ou verificando a base SINAPI…"
        if "sinapi local" in minusculo or "servidor da caixa" in minusculo:
            return (
                "atencao",
                "O site da Caixa não respondeu. Usando a base salva neste computador, "
                "que pode não ser a mais recente.",
            )
        if "atualizada" in minusculo:
            return "ok", "A base SINAPI está atualizada."
        return "andamento", "Verificando a base SINAPI…"

    def atualizar_indicador_sinapi(self) -> None:
        quadrado = self.indicador_sinapi_rodape
        if quadrado is None:
            return
        try:
            if not quadrado.winfo_exists():
                return
            from ui.temas import cores_tema

            cores = cores_tema(quadrado)
            estado, explicacao = self.estado_sinapi()
            cor = {
                "ok": "#66bb6a" if cores.escuro else "#2e7d32",
                "andamento": "#ffb74d" if cores.escuro else "#e09100",
                "atencao": "#ffb74d" if cores.escuro else "#e09100",
                "erro": cores.perigo,
            }[estado]
            quadrado.configure(bg=cor)
            self.dica_sinapi = explicacao
        except tk.TclError:
            pass

    def recarregar_sinapi_em_memoria(self):
        self.sinapi, self.caminho_sinapi_carregado, self.sinapi_referencia_rotulo = (
            recarregar_sinapi()
        )

    def obter_estados(self):
        return obter_estados_da_sinapi(self.sinapi)

    def aplicar_status_servidor(self, status: str, http_codigo: str = "—"):
        if self.status_servidor_sinapi is not None:
            self.status_servidor_sinapi.set(status)
        if self.http_servidor_sinapi is not None:
            self.http_servidor_sinapi.set(http_codigo or "—")

    def carregar_status_servidor_persistido(self):
        dados = carregar_status()
        status = dados.get("status_servidor")
        http = dados.get("http_codigo", "—")
        if not status:
            if self.sinapi_referencia_rotulo == "BASE AUSENTE":
                status = "Crítico"
            else:
                status = "—"
        self.aplicar_status_servidor(str(status), str(http))

    def _definir_status_sinapi(self, texto: str) -> None:
        def aplicar():
            if self.status_sinapi is not None:
                self.status_sinapi.set(texto)
            self.atualizar_rodape()

        self._agendar_na_janela(aplicar)

    def iniciar_verificacao_sinapi(self, *, silencioso: bool = False):
        if self._sinapi_carregando:
            return False
        if self._sinapi_verificando:
            return False
        self.iniciar_consumo_fila_ui()
        self._sinapi_verificando = True
        thread = threading.Thread(
            target=self._verificar_atualizacao_sinapi,
            args=(silencioso,),
            daemon=True,
        )
        thread.start()
        return True

    def _verificar_atualizacao_sinapi(self, silencioso: bool = False):
        janela = self.janela
        if janela is None or self.status_sinapi is None:
            self._sinapi_verificando = False
            return

        try:
            self._agendar_na_janela(
                lambda: self.aplicar_status_servidor("Verificando...", "—")
            )
            self._definir_status_sinapi("SINAPI: verificando...")

            atualizacoes, aviso, info_status = buscar_atualizacoes()
            if not atualizacoes:
                self._agendar_na_janela(
                    lambda: self.aplicar_status_servidor(
                        info_status.get("status_servidor", "—"),
                        info_status.get("http_codigo", "—"),
                    )
                )

            if aviso == "nao_encontrada":
                self._definir_status_sinapi(
                    "SINAPI indisponível (servidor e pasta local)"
                )
                return

            if aviso == "servidor_indisponivel":
                if self.sinapi_referencia_rotulo != "BASE AUSENTE":
                    self._definir_status_sinapi(
                        f"SINAPI local ({self.sinapi_referencia_rotulo})"
                    )
                else:
                    self._definir_status_sinapi(
                        "SINAPI: servidor da Caixa indisponível"
                    )
                return

            if not atualizacoes:
                self._definir_status_sinapi("SINAPI atualizada")
                return

            for ano, mes in atualizacoes:
                self._definir_status_sinapi(f"SINAPI: baixando {mes:02d}/{ano}")

                caminho = baixar_e_extrair(ano, mes)

                self._definir_status_sinapi(f"SINAPI: processando {mes:02d}/{ano}")

                processar_arquivo(caminho)

            limpar_versoes_antigas()
            self.recarregar_sinapi_em_memoria()
            self._agendar_na_janela(
                lambda h=info_status.get("http_codigo", "—"): self._concluir_atualizacao_sinapi(
                    silencioso, h
                )
            )

        except Exception as e:
            print("Erro atualização SINAPI:", e)
            self._definir_status_sinapi("Erro atualização SINAPI")
            self._agendar_na_janela(
                lambda: self.aplicar_status_servidor("Erro", "—")
            )
        finally:
            self._sinapi_verificando = False

    def _concluir_atualizacao_sinapi(self, silencioso: bool = False, http_codigo: str = "—"):
        from tkinter import messagebox

        status = self.status_sinapi
        if status is None:
            return

        self.notificar_sinapi_atualizada()

        if self.sinapi_referencia_rotulo == "BASE AUSENTE" or not self.obter_estados():
            status.set("Erro ao carregar base SINAPI")
            self.aplicar_status_servidor("Crítico", "—")
            self.atualizar_rodape()
            if not silencioso:
                messagebox.showerror(
                    "SINAPI",
                    (
                        "O download foi concluído, mas a base não pôde ser "
                        "carregada na interface.\n\n"
                        "Verifique o arquivo em sinapi/sinapi_processado."
                    ),
                )
            return

        self.aplicar_status_servidor("Atualizado", http_codigo)
        salvar_status({
            **carregar_status(),
            "status_servidor": "Atualizado",
        })
        status.set(
            f"SINAPI atualizada para {self.sinapi_referencia_rotulo}"
        )
        self.atualizar_rodape()

        if silencioso:
            return

        messagebox.showinfo(
            "SINAPI Atualizada",
            (
                "A base SINAPI foi atualizada com sucesso.\n\n"
                f"Nova referência: {self.sinapi_referencia_rotulo}\n\n"
                "O sistema já está pronto para uso."
            ),
        )
