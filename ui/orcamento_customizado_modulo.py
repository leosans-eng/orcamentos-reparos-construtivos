"""Módulo Orçamento Customizado: seleção de orçamento e edição."""

import tkinter as tk

from ui.orcamento_customizado import OrcamentoCustomizadoFrame
from ui.selecao_orcamentos_customizado import SelecaoOrcamentosCustomizadoFrame


class OrcamentoCustomizadoModulo(tk.Frame):
    def __init__(self, parent, ctx, on_voltar):
        super().__init__(parent, bg="#ececec")
        self.ctx = ctx
        self._on_voltar_hub = on_voltar
        self._frame_editor = None
        self._orcamento_aberto_id = None

        self._frame_selecao = SelecaoOrcamentosCustomizadoFrame(
            self,
            ctx,
            on_abrir=self._abrir_editor,
            on_voltar=self._on_voltar_hub,
        )
        self._frame_selecao.pack(fill="both", expand=True)

    def focar(self):
        self._mostrar_selecao()

    def _mostrar_selecao(self):
        if self._frame_editor is not None:
            self._frame_editor.pack_forget()
            self._frame_editor.destroy()
            self._frame_editor = None
            self._orcamento_aberto_id = None
        self._frame_selecao.pack(fill="both", expand=True)
        self._frame_selecao.recarregar()

    def _abrir_editor(self, orcamento_id):
        self._orcamento_aberto_id = orcamento_id
        self._frame_selecao.pack_forget()

        if self._frame_editor is None:
            self._frame_editor = OrcamentoCustomizadoFrame(
                self,
                self.ctx,
                on_voltar=self._mostrar_selecao,
                orcamento_id=orcamento_id,
            )
        else:
            self._frame_editor.definir_orcamento(orcamento_id)

        self._frame_editor.pack(fill="both", expand=True)
