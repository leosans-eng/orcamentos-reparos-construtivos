"""Recarga de catálogo da API sem bloquear a interface Tkinter."""

from __future__ import annotations

import threading
from collections.abc import Callable


class RecarregadorCatalogo:
    def __init__(
        self,
        widget,
        *,
        obter_cache: Callable[[], dict | None],
        carregar_rede: Callable[[], dict],
        ao_aplicar: Callable[[dict], None],
        ao_erro: Callable[[str, bool], None] | None = None,
        ao_inicio: Callable[[], None] | None = None,
        ao_fim: Callable[[], None] | None = None,
    ):
        self._widget = widget
        self._obter_cache = obter_cache
        self._carregar_rede = carregar_rede
        self._ao_aplicar = ao_aplicar
        self._ao_erro = ao_erro
        self._ao_inicio = ao_inicio
        self._ao_fim = ao_fim
        self._em_andamento = False

    def solicitar(self, *, forcar_rede: bool = False, avisar_erro: bool = True) -> None:
        if not forcar_rede:
            cache = self._obter_cache()
            if cache is not None:
                self._ao_aplicar(cache)

        if self._em_andamento:
            return
        self._em_andamento = True
        if self._ao_inicio is not None:
            self._ao_inicio()

        def trabalho():
            erro: str | None = None
            dados: dict | None = None
            try:
                dados = self._carregar_rede()
            except ValueError as exc:
                erro = str(exc)

            def concluir():
                self._em_andamento = False
                if erro is not None:
                    if self._ao_erro is not None:
                        self._ao_erro(erro, avisar_erro)
                elif dados is not None:
                    self._ao_aplicar(dados)
                if self._ao_fim is not None:
                    self._ao_fim()

            self._widget.after(0, concluir)

        threading.Thread(target=trabalho, daemon=True).start()

    @property
    def em_andamento(self) -> bool:
        return self._em_andamento


class RecarregadorLista:
    """Recarga de listas da API sem bloquear a interface Tkinter."""

    def __init__(
        self,
        widget,
        *,
        obter_cache: Callable[[], list | None],
        carregar_rede: Callable[[], list],
        ao_aplicar: Callable[[list], None],
        ao_erro: Callable[[str, bool], None] | None = None,
        ao_inicio: Callable[[], None] | None = None,
        ao_fim: Callable[[], None] | None = None,
    ):
        self._widget = widget
        self._obter_cache = obter_cache
        self._carregar_rede = carregar_rede
        self._ao_aplicar = ao_aplicar
        self._ao_erro = ao_erro
        self._ao_inicio = ao_inicio
        self._ao_fim = ao_fim
        self._em_andamento = False

    def solicitar(self, *, forcar_rede: bool = False, avisar_erro: bool = True) -> None:
        if not forcar_rede:
            cache = self._obter_cache()
            if cache is not None:
                self._ao_aplicar(cache)

        if self._em_andamento:
            return
        self._em_andamento = True
        if self._ao_inicio is not None:
            self._ao_inicio()

        def trabalho():
            erro: str | None = None
            dados: list | None = None
            try:
                dados = self._carregar_rede()
            except ValueError as exc:
                erro = str(exc)

            def concluir():
                self._em_andamento = False
                if erro is not None:
                    if self._ao_erro is not None:
                        self._ao_erro(erro, avisar_erro)
                elif dados is not None:
                    self._ao_aplicar(dados)
                if self._ao_fim is not None:
                    self._ao_fim()

            self._widget.after(0, concluir)

        threading.Thread(target=trabalho, daemon=True).start()

    @property
    def em_andamento(self) -> bool:
        return self._em_andamento
