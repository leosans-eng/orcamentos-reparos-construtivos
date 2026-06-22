import os
import tkinter as tk

from app_paths import icon_path
from core.app_state import (
    ALTURA_JANELA_PADRAO,
    APP_VERSION,
    LARGURA_JANELA_PADRAO,
    AppContext,
)
from ui.area_privativa import criar_area_privativa
from ui.consulta_sinapi import ConsultaSinapiFrame
from ui.hub import HubFrame

TITULOS_JANELA = {
    "hub": "ORC — Orçamentos de Reparos Construtivos",
    "area_privativa": "ORC — Área Privativa",
    "consulta_sinapi": "ORC — Consulta SINAPI",
}


class OrcApp:
    def __init__(self):
        self.ctx = AppContext()
        self._modulo_atual = None
        self._frames = {}

        self.janela = tk.Tk()
        self.ctx.janela = self.janela

        self.janela.title(TITULOS_JANELA["hub"])
        self.janela.geometry(
            f"{LARGURA_JANELA_PADRAO}x{ALTURA_JANELA_PADRAO}+200+40"
        )
        self.janela.minsize(860, 520)

        icone = icon_path()
        if icone is not None:
            self.janela.iconbitmap(icone)

        self.ctx.status_sinapi = tk.StringVar(value="SINAPI: verificando...")

        self._montar_rodape()

        self.area_conteudo = tk.Frame(self.janela)
        self.area_conteudo.pack(fill="both", expand=True)

        self._criar_hub()
        self.mostrar_modulo("hub")

        self._schedule_update_check()
        self.janela.after(500, self.ctx.iniciar_verificacao_sinapi)

    def _schedule_update_check(self):
        try:
            from atualizacao import iniciar_verificacao_atualizacao

            iniciar_verificacao_atualizacao(self.janela, APP_VERSION)
        except ImportError:
            pass

    def _montar_rodape(self):
        self.ctx.frame_rodape = tk.Frame(self.janela)
        self.ctx.frame_rodape.pack(side="bottom", fill="x", padx=10, pady=(0, 6))

        self.ctx.label_rodape = tk.Label(
            self.ctx.frame_rodape,
            text=self.ctx.texto_rodape_interface(),
            font=("Arial", 8),
            fg="#555555",
            anchor="w",
        )
        self.ctx.label_rodape.pack(side="left", anchor="w")

        if self.ctx.caminho_sinapi_carregado:
            nome_csv = (
                f"{os.path.basename(self.ctx.caminho_sinapi_carregado)} "
                f"⭠ Arquivo de base"
            )
        else:
            nome_csv = "Nenhum arquivo SINAPI carregado"

        self.ctx.label_nome_csv_rodape = tk.Label(
            self.ctx.frame_rodape,
            text=nome_csv,
            font=("Arial", 8, "bold"),
            fg="#C62828",
            anchor="e",
        )
        self.ctx.label_nome_csv_rodape.pack(side="right", anchor="e")
        self.ctx.agendar_sumico_nome_csv_deslize_direita(
            self.ctx.label_nome_csv_rodape
        )

    def _criar_hub(self):
        self._frames["hub"] = HubFrame(
            self.area_conteudo,
            on_selecionar_modulo=self._ao_selecionar_modulo_hub,
        )

    def _criar_modulo(self, nome):
        if nome == "area_privativa":
            self._frames[nome] = criar_area_privativa(
                self.area_conteudo,
                self.ctx,
                on_voltar=lambda: self.mostrar_modulo("hub"),
            )
        elif nome == "consulta_sinapi":
            self._frames[nome] = ConsultaSinapiFrame(
                self.area_conteudo,
                on_voltar=lambda: self.mostrar_modulo("hub"),
            )

    def _ao_selecionar_modulo_hub(self, modulo):
        if modulo == "area_comum":
            return
        self.mostrar_modulo(modulo)

    def mostrar_modulo(self, nome):
        if (
            self._modulo_atual == "area_privativa"
            and "area_privativa" in self._frames
        ):
            self._frames["area_privativa"].desativar_scroll()

        for frame in self._frames.values():
            frame.pack_forget()

        if nome not in self._frames:
            self._criar_modulo(nome)

        self._frames[nome].pack(fill="both", expand=True)
        self._modulo_atual = nome
        self.janela.title(TITULOS_JANELA.get(nome, TITULOS_JANELA["hub"]))

        if nome == "area_privativa":
            self._frames[nome].ativar_scroll()
            self._frames[nome].focar()

    def executar(self):
        self.janela.mainloop()


if __name__ == "__main__":
    OrcApp().executar()
