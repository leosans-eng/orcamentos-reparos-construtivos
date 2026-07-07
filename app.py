import os
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
from ui.composicoes_proprias import ComposicoesPropriasFrame
from ui.consulta_sinapi import ConsultaSinapiFrame
from ui.etapas_predefinidas import EtapasPredefinidasFrame
from ui.hub import HubFrame
from ui.orcamento_customizado_modulo import OrcamentoCustomizadoModulo
from ui.dialogo_login import garantir_login
from ui.widgets import centralizar_janela_principal, configurar_estilos_ttk

TITULOS_JANELA = {
    "hub": "ORC — Orçamentos de Reparos Construtivos",
    "area_privativa": "ORC — Área Privativa",
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

        self.janela = tk.Tk()
        self.ctx.janela = self.janela
        self.ctx.iniciar_carregamento_sinapi()
        configurar_estilos_ttk(self.janela)

        self.janela.title(TITULOS_JANELA["hub"])
        self.janela.minsize(860, 520)
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
        frame_rodape = tk.Frame(self.janela)
        self.ctx.frame_rodape = frame_rodape
        frame_rodape.pack(side="bottom", fill="x", padx=10, pady=(0, 6))

        label_rodape = tk.Label(
            frame_rodape,
            text=self.ctx.texto_rodape_interface(),
            font=("Arial", 8),
            fg="#555555",
            anchor="w",
        )
        self.ctx.label_rodape = label_rodape
        label_rodape.pack(side="left", anchor="w")

        if self.ctx.caminho_sinapi_carregado:
            nome_csv = (
                f"{os.path.basename(self.ctx.caminho_sinapi_carregado)} "
                f"⭠ Arquivo de base"
            )
        else:
            nome_csv = "Nenhum arquivo SINAPI carregado"

        self.ctx.label_nome_csv_rodape = tk.Label(
            frame_rodape,
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
            self.ctx,
            on_selecionar_modulo=self._ao_selecionar_modulo_hub,
            on_logout=None if self.offline else self._logout,
        )

    def _logout(self):
        from core.api_client import get_client
        from core.composicoes_proprias_storage import limpar_cache as limpar_cache_composicoes
        from core.etapas_predefinidas_storage import limpar_cache as limpar_cache_etapas
        from core.orcamento_storage import limpar_cache as limpar_cache_orcamentos

        get_client().logout()
        limpar_cache_composicoes()
        limpar_cache_etapas()
        limpar_cache_orcamentos()
        self.pediu_logout = True
        self.janela.destroy()

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

        modulos_expandidos = (
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

        for frame in self._frames.values():
            frame.pack_forget()

        if nome not in self._frames:
            self._criar_modulo(nome)

        self._frames[nome].pack(fill="both", expand=True)
        self._modulo_atual = nome
        self.janela.title(TITULOS_JANELA.get(nome, TITULOS_JANELA["hub"]))

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

        if nome == "hub":
            centralizar_janela_principal(
                self.janela, LARGURA_JANELA_PADRAO, ALTURA_JANELA_PADRAO
            )
        elif nome == "area_privativa":
            self._frames[nome].ativar_scroll()
            self._frames[nome].focar()
        elif nome in (
            "consulta_sinapi",
            "orcamento_customizado",
            "composicoes_proprias",
            "etapas_predefinidas",
        ):
            self._frames[nome].focar()

    def executar(self):
        self.janela.mainloop()


if __name__ == "__main__":
    while True:
        if not garantir_login():
            raise SystemExit(0)
        iniciar_precarga_catalogos()
        app = OrcApp()
        app.executar()
        if not app.pediu_logout:
            break
