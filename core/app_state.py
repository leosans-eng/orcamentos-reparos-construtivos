import json
import os
import threading
import tkinter as tk

from sinapi.atualizador_sinapi import (
    baixar_e_extrair,
    buscar_atualizacoes,
    limpar_versoes_antigas,
)
from sinapi.extrair_sinapi import processar_arquivo

from core.sinapi_loader import (
    BASE_DIR,
    carregar_sinapi_inicial,
    obter_estados_da_sinapi,
    recarregar_sinapi,
)

APP_VERSION = "0.9.9"

LARGURA_JANELA_PADRAO = 990
ALTURA_JANELA_PADRAO = 660
ALTURA_TREE_MIN = 11

RODAPE_CSV_SUMIR_APOS_MS = 3000
RODAPE_CSV_DESLIZE_INTERVALO_MS = 35
RODAPE_CSV_DESLIZE_PASSO_PX = 4

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
        self.sinapi, self.caminho_sinapi_carregado, self.sinapi_referencia_rotulo = (
            carregar_sinapi_inicial()
        )
        self.dados_json = self._carregar_dados_json()
        self._sinapi_callbacks = []

        self.janela = None
        self.frame_rodape = None
        self.label_rodape = None
        self.label_nome_csv_rodape = None
        self.status_sinapi = None

    def _carregar_dados_json(self):
        caminho = os.path.join(BASE_DIR, "vicios_construtivos.json")
        with open(caminho, "r", encoding="utf-8") as f:
            dados = json.load(f)
        if isinstance(dados, list):
            dados = dados[0]
        return dados

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
        base = f"Sistema ORC v{info['app']} · SINAPI referência {info['sinapi']}"
        extras = []
        if self.status_sinapi and self.status_sinapi.get():
            extras.append(self.status_sinapi.get())
        if extras:
            return f"{base} · {' · '.join(extras)}"
        return base

    def atualizar_rodape(self):
        if self.label_rodape and self.label_rodape.winfo_exists():
            self.label_rodape.config(text=self.texto_rodape_interface())

    def agendar_sumico_nome_csv_deslize_direita(self, label_csv):
        frame_rodape = self.frame_rodape

        def executar():
            if not label_csv.winfo_exists():
                return
            if label_csv.winfo_manager() != "pack":
                return
            label_csv.pack_forget()
            label_csv.place(relx=1.0, rely=0.5, anchor="e", x=-6, in_=frame_rodape)

            def deslizar():
                if not label_csv.winfo_exists():
                    return
                frame_rodape.update_idletasks()
                label_csv.update_idletasks()
                limite = frame_rodape.winfo_width()
                if label_csv.winfo_x() - frame_rodape.winfo_x() > limite + 8:
                    label_csv.destroy()
                    return
                info = label_csv.place_info()
                cur_x = int(float(info.get("x", 0)))
                label_csv.place(
                    relx=1.0,
                    rely=0.5,
                    anchor="e",
                    x=cur_x + RODAPE_CSV_DESLIZE_PASSO_PX,
                    in_=frame_rodape,
                )
                frame_rodape.after(
                    RODAPE_CSV_DESLIZE_INTERVALO_MS, deslizar
                )

            frame_rodape.after(25, deslizar)

        frame_rodape.after(RODAPE_CSV_SUMIR_APOS_MS, executar)

    def atualizar_label_csv_rodape(self):
        if self.caminho_sinapi_carregado:
            texto = (
                f"{os.path.basename(self.caminho_sinapi_carregado)} "
                f"⭠ Arquivo de base"
            )
        else:
            texto = "Nenhum arquivo SINAPI carregado"

        if (
            self.label_nome_csv_rodape is None
            or not self.label_nome_csv_rodape.winfo_exists()
        ):
            self.label_nome_csv_rodape = tk.Label(
                self.frame_rodape,
                text=texto,
                font=("Arial", 8, "bold"),
                fg="#C62828",
                anchor="e",
            )
            self.label_nome_csv_rodape.pack(side="right", anchor="e")
            self.agendar_sumico_nome_csv_deslize_direita(
                self.label_nome_csv_rodape
            )
        else:
            self.label_nome_csv_rodape.config(text=texto)

    def recarregar_sinapi_em_memoria(self):
        self.sinapi, self.caminho_sinapi_carregado, self.sinapi_referencia_rotulo = (
            recarregar_sinapi()
        )

    def obter_estados(self):
        return obter_estados_da_sinapi(self.sinapi)

    def iniciar_verificacao_sinapi(self):
        thread = threading.Thread(
            target=self._verificar_atualizacao_sinapi,
            daemon=True,
        )
        thread.start()

    def _verificar_atualizacao_sinapi(self):
        try:
            self.status_sinapi.set("SINAPI: verificando...")
            self.janela.after(0, self.atualizar_rodape)

            atualizacoes, aviso = buscar_atualizacoes()

            if aviso == "nao_encontrada":
                self.status_sinapi.set(
                    "SINAPI indisponível (servidor e pasta local)"
                )
                self.janela.after(0, self.atualizar_rodape)
                return

            if aviso == "servidor_indisponivel":
                if self.sinapi_referencia_rotulo != "BASE AUSENTE":
                    self.status_sinapi.set(
                        f"SINAPI local ({self.sinapi_referencia_rotulo})"
                    )
                else:
                    self.status_sinapi.set(
                        "SINAPI: servidor da Caixa indisponível"
                    )
                self.janela.after(0, self.atualizar_rodape)
                return

            if not atualizacoes:
                self.status_sinapi.set("SINAPI atualizada")
                self.janela.after(0, self.atualizar_rodape)
                return

            for ano, mes in atualizacoes:
                self.status_sinapi.set(f"SINAPI: baixando {mes:02d}/{ano}")
                self.janela.after(0, self.atualizar_rodape)

                caminho = baixar_e_extrair(ano, mes)

                self.status_sinapi.set(f"SINAPI: processando {mes:02d}/{ano}")
                self.janela.after(0, self.atualizar_rodape)

                processar_arquivo(caminho)

            limpar_versoes_antigas()
            self.recarregar_sinapi_em_memoria()
            self.janela.after(0, self._concluir_atualizacao_sinapi)

        except Exception as e:
            print("Erro atualização SINAPI:", e)
            self.status_sinapi.set("Erro atualização SINAPI")
            self.janela.after(0, self.atualizar_rodape)

    def _concluir_atualizacao_sinapi(self):
        from tkinter import messagebox

        self.notificar_sinapi_atualizada()

        if self.sinapi_referencia_rotulo == "BASE AUSENTE" or not self.obter_estados():
            self.status_sinapi.set("Erro ao carregar base SINAPI")
            self.atualizar_rodape()
            messagebox.showerror(
                "SINAPI",
                (
                    "O download foi concluído, mas a base não pôde ser "
                    "carregada na interface.\n\n"
                    "Verifique o arquivo em sinapi/sinapi_processado."
                ),
            )
            return

        self.status_sinapi.set(
            f"SINAPI atualizada para {self.sinapi_referencia_rotulo}"
        )
        self.atualizar_rodape()

        messagebox.showinfo(
            "SINAPI Atualizada",
            (
                "A base SINAPI foi atualizada com sucesso.\n\n"
                f"Nova referência: {self.sinapi_referencia_rotulo}\n\n"
                "O sistema já está pronto para uso."
            ),
        )
