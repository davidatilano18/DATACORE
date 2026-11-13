"""¿Por qué salió esta alerta? Los 2 o 3 factores principales, en lenguaje sencillo.

Método: reglas transparentes sobre las mismas cantidades con las que se decide la alerta
(existencia, demanda esperada, días de entrega) y sobre variables que el modelo también usa
(tendencia reciente, calendario, estacionalidad de la categoría, días agotado). Cada regla
que aplica produce un factor con un puntaje de gravedad; se muestran los de mayor puntaje.

Se prefirió a la atribución del modelo (p. ej., SHAP) porque la alerta compara existencia
contra demanda: su "por qué" se entiende en esos términos, no como el peso de una variable
dentro de los árboles; además, cada frase se puede verificar contra los datos.
"""

import numpy as np
import pandas as pd

from . import caracteristicas as car
from .datos import Series

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
EVENTOS = {"buen_fin": "el Buen Fin", "navidad": "la temporada navideña", "fin_de_anio": "el fin de año",
           "reyes": "el Día de Reyes", "dia_madres": "el Día de las Madres", "dia_nino": "el Día del Niño",
           "regreso_clases": "el regreso a clases"}
MAX_FACTORES = 3
UMBRAL_TENDENCIA = 15.0      # % de cambio contra la venta de las últimas 8 semanas para mencionarlo
UMBRAL_TEMPORADA = 1.2       # índice estacional de la categoría para hablar de temporada alta
UMBRAL_AGOTADO = 3           # días agotado (de 28) para mencionar la venta censurada
ENTREGA_LARGA = 8            # días de entrega a partir de los cuales se menciona al proveedor


def contexto(series: Series, pares: pd.MultiIndex, semanas_objetivo: int = 2) -> pd.DataFrame:
    """Variables por par que no están en la tabla de alertas: venta reciente, días agotado,
    evento de calendario próximo e índice estacional de la categoría en el mes que viene."""
    ultima = series.unidades.index.max()
    venta_8 = series.unidades.iloc[-8:].mean()
    agotado_28 = (series.agotado.iloc[-4:] * 7).sum().round()
    proximas = pd.DatetimeIndex([ultima + pd.Timedelta(weeks=k) for k in range(1, semanas_objetivo + 1)])
    cal = car.calendario(proximas)
    evento = next((nombre for col, nombre in EVENTOS.items() if col in cal and cal[col].any()), None)
    mes = (proximas[0] + pd.Timedelta(days=3)).month  # mes de la mitad de la próxima semana

    # Índice estacional de la categoría: unidades del mes que viene contra el promedio mensual (historia completa).
    categoria = series.productos.set_index("id_producto")["categoria"]
    cat_par = pd.Series(categoria.reindex(series.unidades.columns.get_level_values("id_producto")).to_numpy(),
                        index=series.unidades.columns)
    por_cat = series.unidades.T.groupby(cat_par).sum().T
    mensual = por_cat.groupby(por_cat.index.month).mean()
    indice = (mensual.loc[mes] / mensual.mean()) if mes in mensual.index else pd.Series(1.0, index=mensual.columns)

    out = pd.DataFrame(index=pares)
    out["venta_8_semanas"] = venta_8.reindex(pares).to_numpy()
    out["dias_agotado_28"] = agotado_28.reindex(pares).fillna(0).to_numpy()
    out["categoria"] = cat_par.reindex(pares).to_numpy()
    out["indice_temporada"] = out["categoria"].map(indice).fillna(1.0).to_numpy()
    out["mes_siguiente"] = MESES[mes - 1]
    precio = series.productos.set_index("id_producto")["precio_unitario"]
    out["precio"] = precio.reindex(pares.get_level_values("id_producto")).to_numpy()
    out["evento_proximo"] = evento
    return out


def _dias(n: float) -> str:
    n = int(round(n))
    return "1 día" if n == 1 else f"{n} días"


def factores(fila: pd.Series) -> list[tuple[float, str]]:
    """(puntaje, frase) para una alerta. `fila` trae tipo, existencia, dias_entrega, demanda_diaria,
    cobertura_dias, tendencia_pct, unidades_13_semanas y las columnas de `contexto`."""
    tipo, L = fila["tipo"], int(fila["dias_entrega"])
    out: list[tuple[float, str]] = []
    tendencia = fila.get("tendencia_pct")
    if tipo == "RIESGO_DESABASTO":
        diaria = max(float(fila["demanda_diaria"]), 1e-9)
        dura = float(fila["existencia"]) / diaria
        if fila["existencia"] <= 0:
            out.append((4.0, f"Ya no hay existencia y un pedido tarda {_dias(L)} en llegar"))
        elif dura < L:
            out.append((3.0 + (L - dura) / L, f"La existencia alcanza para {_dias(dura)} y un pedido tarda {_dias(L)}"))
        else:
            out.append((2.5, f"La existencia alcanza para {_dias(dura)}, poco más que la entrega de {_dias(L)}"))
        if tendencia is not None and tendencia >= UMBRAL_TENDENCIA:
            out.append((1.0 + min(tendencia, 200) / 50, f"Se espera vender {tendencia:.0f} % más que en las últimas 8 semanas"))
        if fila.get("evento_proximo"):
            out.append((2.0, f"Se acerca {fila['evento_proximo']}"))
        if fila.get("indice_temporada", 1) >= UMBRAL_TEMPORADA:
            out.append((1.0 + fila["indice_temporada"] - 1,
                        f"{fila['mes_siguiente'].capitalize()} es temporada alta de {str(fila['categoria']).lower()}"))
        if fila.get("dias_agotado_28", 0) >= UMBRAL_AGOTADO:
            n = int(fila["dias_agotado_28"])
            out.append((1.0 + n / 14, f"Estuvo agotado {n} de los últimos 28 días: vendió menos de lo que se le pidió"))
        if L >= ENTREGA_LARGA:
            out.append((1.0, f"Su proveedor tarda {_dias(L)} en entregar"))
    elif tipo == "EXCESO_INVENTARIO":
        out.append((3.0, f"La existencia cubre {_dias(fila['cobertura_dias'])} al ritmo esperado"))
        if tendencia is not None and tendencia <= -UMBRAL_TENDENCIA:
            out.append((1.0 + min(-tendencia, 100) / 50, f"Se espera vender {-tendencia:.0f} % menos que en las últimas 8 semanas"))
        semanal = float(fila.get("media_semanal") or 0)
        if semanal < 1:
            out.append((1.5, "Vende menos de una pieza por semana"))
        if fila.get("indice_temporada", 1) <= 1 / UMBRAL_TEMPORADA:
            out.append((1.0, f"{fila['mes_siguiente'].capitalize()} es temporada baja de {str(fila['categoria']).lower()}"))
    elif tipo == "SIN_ROTACION":
        out.append((3.0, "No se ha vendido en las últimas 13 semanas"))
        valor = float(fila.get("precio") or 0) * float(fila["existencia"])
        pesos = f" ($ {valor:,.0f} a precio de lista)" if valor > 0 else ""
        out.append((2.0, f"Tiene {int(fila['existencia'])} piezas paradas{pesos}"))
        if fila.get("indice_temporada", 1) <= 1 / UMBRAL_TEMPORADA:
            out.append((1.0, f"{fila['mes_siguiente'].capitalize()} es temporada baja de {str(fila['categoria']).lower()}"))
    return out


def motivos(fila: pd.Series, maximo: int = MAX_FACTORES) -> str:
    """Los factores de mayor puntaje, separados por punto y coma."""
    elegidos = sorted(factores(fila), key=lambda f: -f[0])[:maximo]
    frases = [frase if i == 0 else frase[:1].lower() + frase[1:] for i, (_, frase) in enumerate(elegidos)]
    return "; ".join(frases)


def explicar(alertas: pd.DataFrame, series: Series) -> pd.Series:
    """Texto de motivos para cada fila de `alertas` (mismas columnas que arma publicacion.alertas)."""
    if alertas.empty:
        return pd.Series(dtype=str)
    pares = pd.MultiIndex.from_frame(alertas[["id_sucursal", "id_producto"]])
    ctx = contexto(series, pares)
    datos = alertas.reset_index(drop=True).join(ctx.reset_index(drop=True))
    semanal = datos["media_semanal"].to_numpy(dtype=float)
    base = datos["venta_8_semanas"].to_numpy(dtype=float)
    datos["tendencia_pct"] = np.where(base > 0.25, (semanal / np.where(base > 0, base, 1) - 1) * 100, np.nan)
    datos["tendencia_pct"] = datos["tendencia_pct"].where(datos["tendencia_pct"].notna(), None)
    return pd.Series([motivos(f) for _, f in datos.iterrows()], index=alertas.index)
