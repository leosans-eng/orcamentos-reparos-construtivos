"""Módulo Orçamento Customizado: seleção de orçamento e edição."""

import tkinter as tk
from tkinter import messagebox

from ui.temas import cores_tema
from ui.orcamento_customizado import OrcamentoCustomizadoFrame
from ui.selecao_orcamentos_customizado import SelecaoOrcamentosCustomizadoFrame


class OrcamentoCustomizadoModulo(tk.Frame):
    def __init__(self, parent, ctx, on_voltar):
        cores = cores_tema(parent)
        super().__init__(parent, bg=cores.fundo)
        self.ctx = ctx
        self._on_voltar_hub = on_voltar
        self._frame_editor = None
        self._orcamento_aberto_id = None
        self._abrindo_editor = False

        self._frame_selecao = SelecaoOrcamentosCustomizadoFrame(
            self,
            ctx,
            on_abrir=self._abrir_editor,
            on_voltar=self._on_voltar_hub,
        )
        self._frame_selecao.pack(fill="both", expand=True)

    def focar(self):
        if self._abrindo_editor:
            return
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
        if self._abrindo_editor:
            return
        self._abrindo_editor = True
        self._orcamento_aberto_id = orcamento_id
        try:
            self._frame_selecao.pack_forget()
        except tk.TclError:
            self._abrindo_editor = False
            return

        try:
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
        except Exception as exc:
            self._restaurar_selecao_apos_falha(exc)
        finally:
            self._abrindo_editor = False

    def _restaurar_selecao_apos_falha(self, exc):
        print(f"[ORC] Falha ao abrir orçamento: {exc}")
        if self._frame_editor is not None:
            try:
                self._frame_editor.destroy()
            except tk.TclError:
                pass
            self._frame_editor = None
        self._orcamento_aberto_id = None
        try:
            for filho in list(self.winfo_children()):
                if filho is not self._frame_selecao:
                    filho.destroy()
        except tk.TclError:
            pass
        try:
            self._frame_selecao.pack(fill="both", expand=True)
        except tk.TclError:
            return
        parent = self.winfo_toplevel()
        if isinstance(exc, ValueError):
            messagebox.showwarning(
                "Orçamento",
                str(exc)
                or "Não foi possível abrir o orçamento.\n"
                "Verifique se a API e o banco de dados estão disponíveis.",
                parent=parent,
            )
            return
        messagebox.showerror(
            "Orçamento",
            "Não foi possível abrir o orçamento.\nTente novamente.",
            parent=parent,
        )
