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
        return sorted(self.precos["estado"].dropna().astype(str).str.strip().unique().tolist())

    def obter_tipo(self, codigo: str) -> str:
        codigo = str(codigo).strip()
        if not codigo or self.catalogo.empty:
            return ""
        linhas = self.catalogo[self.catalogo["codigo"] == codigo]
        if linhas.empty:
            return ""
        return str(linhas.iloc[0].get("tipo", "")).strip().upper()[:1]

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
        linhas = df[df["codigo"] == codigo]
        if linhas.empty:
            return None
        return linhas.iloc[0]
