"""Estrutura otimizada da base SINAPI: catálogo + preços por estado."""

from __future__ import annotations

from typing import cast

import pandas as pd

COLUNAS_BUSCA = ("codigo", "descricao", "unidade", "tipo", "estado", "custo")


class SinapiBase:
    """Catálogo único por código e tabela de preços por (código, estado)."""

    def __init__(self, catalogo: pd.DataFrame, precos: pd.DataFrame):
        self.catalogo = self._normalizar_catalogo(catalogo)
        self.precos = self._normalizar_precos(precos)
        self._cache_por_estado: dict[str, pd.DataFrame] = {}
        # Índices montados na primeira consulta. A base não muda depois de
        # criada (uma SINAPI nova gera outro objeto), então podem ser reaproveitados.
        self._estados: list[str] | None = None
        self._estados_por_codigo: dict[str, list[str]] | None = None
        self._posicao_por_estado: dict[str, dict[str, int]] = {}
        self._tipo_por_codigo: dict[str, str] | None = None

    @property
    def empty(self) -> bool:
        return self.catalogo.empty or self.precos.empty

    @classmethod
    def vazio(cls) -> SinapiBase:
        return cls(
            pd.DataFrame(columns=["codigo", "descricao", "unidade", "tipo"]),
            pd.DataFrame(columns=["codigo", "estado", "custo"]),
        )

    @staticmethod
    def _normalizar_catalogo(catalogo: pd.DataFrame) -> pd.DataFrame:
        if catalogo.empty:
            return pd.DataFrame(columns=["codigo", "descricao", "unidade", "tipo"])
        df = catalogo.copy()
        df.columns = df.columns.str.strip().str.lower()
        df["codigo"] = df["codigo"].astype(str).str.strip()
        if "tipo" not in df.columns:
            df["tipo"] = ""
        df["tipo"] = df["tipo"].astype(str).str.strip().str.upper().str[:1]
        return df.drop_duplicates("codigo", keep="first").reset_index(drop=True)

    @staticmethod
    def _normalizar_precos(precos: pd.DataFrame) -> pd.DataFrame:
        if precos.empty:
            return pd.DataFrame(columns=["codigo", "estado", "custo"])
        df = precos.copy()
        df.columns = df.columns.str.strip().str.lower()
        df["codigo"] = df["codigo"].astype(str).str.strip()
        df["estado"] = df["estado"].astype(str).str.strip()
        return df.reset_index(drop=True)

    def estados(self) -> list[str]:
        if self.precos.empty:
            return []
        if self._estados is None:
            # "estado" já foi limpo em _normalizar_precos.
            self._estados = sorted(self.precos["estado"].dropna().unique().tolist())
        return list(self._estados)

    def estados_do_codigo(self, codigo: str) -> list[str]:
        """UFs em que o código tem preço. Monta o índice na primeira chamada."""
        if self._estados_por_codigo is None:
            agrupado: dict[str, set[str]] = {}
            for cod, uf in zip(
                self.precos["codigo"].tolist(), self.precos["estado"].tolist()
            ):
                agrupado.setdefault(cod, set()).add(uf)
            self._estados_por_codigo = {
                cod: sorted(ufs) for cod, ufs in agrupado.items()
            }
        return list(self._estados_por_codigo.get(str(codigo).strip(), ()))

    def obter_tipo(self, codigo: str) -> str:
        codigo = str(codigo).strip()
        if not codigo or self.catalogo.empty:
            return ""
        if self._tipo_por_codigo is None:
            # O catálogo não tem códigos repetidos (drop_duplicates acima).
            self._tipo_por_codigo = dict(
                zip(
                    self.catalogo["codigo"].tolist(),
                    self.catalogo["tipo"].astype(str).tolist(),
                )
            )
        return self._tipo_por_codigo.get(codigo, "").strip().upper()[:1]

    def dataframe_estado(self, estado: str) -> pd.DataFrame:
        estado = str(estado or "").strip()
        if not estado:
            return pd.DataFrame(columns=list(COLUNAS_BUSCA))
        if estado in self._cache_por_estado:
            return self._cache_por_estado[estado]

        precos_estado = self.precos[self.precos["estado"] == estado]
        if precos_estado.empty:
            vazio = pd.DataFrame(columns=list(COLUNAS_BUSCA))
            self._cache_por_estado[estado] = vazio
            return vazio

        merged = pd.DataFrame(precos_estado.merge(self.catalogo, on="codigo", how="left"))
        merged["estado"] = estado
        colunas = [c for c in COLUNAS_BUSCA if c in merged.columns]
        frame = cast(pd.DataFrame, merged[colunas].copy())
        self._cache_por_estado[estado] = frame
        return frame

    def obter_linha(self, codigo: str, estado: str):
        estado = str(estado or "").strip()
        codigo = str(codigo).strip()
        if not codigo or not estado:
            return None
        df = self.dataframe_estado(estado)
        posicoes = self._posicao_por_estado.get(estado)
        if posicoes is None:
            # Antes: df[df["codigo"] == codigo] percorria a tabela inteira a
            # cada busca. Agora é uma consulta num dicionário código -> linha.
            posicoes = {}
            if "codigo" in df.columns:
                for pos, cod in enumerate(df["codigo"].tolist()):
                    posicoes.setdefault(cod, pos)  # primeira ocorrência, como iloc[0]
            self._posicao_por_estado[estado] = posicoes
        pos = posicoes.get(codigo)
        if pos is None:
            return None
        return df.iloc[pos]
