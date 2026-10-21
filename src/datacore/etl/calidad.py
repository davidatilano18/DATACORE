"""Registro de hallazgos de calidad y utilidades de normalización.

Un hallazgo describe qué regla se disparó sobre qué registro y qué se hizo:
- corregido: el valor se arregló y el registro se carga;
- rechazado: el registro no se carga;
- marcado:   se carga tal cual (o con NULL) pero queda señalado.
"""

import re
import unicodedata

import pandas as pd

COLUMNAS = ["tabla", "clave", "regla", "severidad", "accion", "valor_original", "valor_final"]

ESTADOS = ["Aguascalientes", "Ciudad de México", "Guanajuato", "Jalisco", "Michoacán", "Nuevo León",
           "Puebla", "Querétaro", "San Luis Potosí"]
# Alias frecuentes de captura, ya normalizados con `clave_texto`.
ALIAS_ESTADO = {"QRO": "Querétaro", "CDMX": "Ciudad de México", "DF": "Ciudad de México",
                "CD DE MEXICO": "Ciudad de México", "MEXICO CITY": "Ciudad de México",
                "JAL": "Jalisco", "NL": "Nuevo León", "GTO": "Guanajuato", "SLP": "San Luis Potosí",
                "PUE": "Puebla", "AGS": "Aguascalientes", "MICH": "Michoacán"}

PATRON_EMAIL = re.compile(r"^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$")


class Hallazgos:
    def __init__(self):
        self._partes: list[pd.DataFrame] = []

    def agregar(self, tabla: str, regla: str, claves, accion: str, originales=None, finales=None,
                severidad: str | None = None) -> None:
        claves = pd.Series(claves).astype(str).to_numpy()
        if len(claves) == 0:
            return
        n = len(claves)
        self._partes.append(pd.DataFrame({
            "tabla": tabla, "clave": claves, "regla": regla,
            "severidad": severidad or ("error" if accion == "rechazado" else "advertencia"),
            "accion": accion,
            "valor_original": _texto(originales, n),
            "valor_final": _texto(finales, n),
        }))

    def to_frame(self) -> pd.DataFrame:
        if not self._partes:
            return pd.DataFrame(columns=COLUMNAS)
        return pd.concat(self._partes, ignore_index=True)


def _texto(valores, n):
    if valores is None:
        return [None] * n
    s = pd.Series(valores).reset_index(drop=True)
    return s.where(s.notna(), None).map(lambda v: None if v is None else str(v)).to_numpy()


def sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def clave_texto(serie: pd.Series) -> pd.Series:
    """Forma canónica para comparar textos: sin acentos, mayúsculas, sin puntuación ni espacios extra."""
    s = serie.fillna("").map(sin_acentos).str.upper()
    s = s.str.replace(r"[^\w\s]", " ", regex=True).str.replace(r"\s+", " ", regex=True).str.strip()
    return s


def normalizar_estado(serie: pd.Series) -> pd.Series:
    canonicos = {clave: e for clave, e in zip(clave_texto(pd.Series(ESTADOS)), ESTADOS)}
    canonicos |= ALIAS_ESTADO
    claves = clave_texto(serie)
    # "D.F." queda como "D F" y "QRO." como "QRO"; se prueba también sin espacios.
    return claves.map(canonicos).fillna(claves.str.replace(" ", "").map(canonicos))


def espacios(serie: pd.Series) -> pd.Series:
    return serie.str.replace(r"\s+", " ", regex=True).str.strip()
