"""Reporte reproducible: python -m datacore.eda.reporte --datos data/ground_truth."""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as fechas
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd


TABLAS = ("sucursales", "categorias", "proveedores", "productos", "clientes", "ventas",
          "detalle_venta", "inventario", "movimientos_inventario", "incidencias")
MESES = ("Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")


def _millones(eje, etiqueta="Ingreso (millones de MXN)"):
    """Eje Y en millones de pesos en lugar de notación científica (1e7)."""
    eje.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1e6:,.1f}"))
    eje.set_ylabel(etiqueta)


def _guardar(fig, salida, nombre, texto, secciones):
    fig.tight_layout()
    fig.savefig(salida / f"{nombre}.png", dpi=150)
    plt.close(fig)
    secciones.append(f"## {nombre.replace('_', ' ').capitalize()}\n\n{texto}\n\n![{nombre}]({nombre}.png)\n")


def _mensuales(ventas, detalle, salida, secciones):
    mensual = ventas.set_index("fecha_hora")["total"].resample("MS").sum()
    fig, ejes = plt.subplots(1, 2, figsize=(13, 4))
    ejes[0].plot(mensual.index, mensual.values)
    ejes[0].set(title="Ventas mensuales totales", xlabel="Mes", ylabel="Ingreso (MXN)")
    localizador = fechas.MonthLocator(interval=max(1, int(np.ceil(len(mensual) / 6))))
    ejes[0].xaxis.set_major_locator(localizador)
    ejes[0].xaxis.set_major_formatter(fechas.DateFormatter("%Y-%m"))
    for anio, grupo in mensual.groupby(mensual.index.year):
        ejes[1].plot(grupo.index.month, grupo.values, marker="o", label=str(anio))
    ejes[1].set(title="Estacionalidad por año", xlabel="Mes", ylabel="Ingreso (MXN)",
                xticks=range(1, 13), xticklabels=MESES)
    ejes[1].legend()
    for eje in ejes:
        _millones(eje)
    _guardar(fig, salida, "ventas_mensuales",
             f"El máximo mensual fue {mensual.idxmax():%Y-%m}: {mensual.max():,.2f} MXN; "
             f"el mínimo fue {mensual.idxmin():%Y-%m}: {mensual.min():,.2f} MXN.", secciones)
    # Promedio por mes observado: los meses ausentes no se confunden con cero.
    matriz = detalle.groupby(["categoria", detalle.fecha_hora.dt.to_period("M")])["subtotal"].sum().unstack(0)
    matriz = matriz.reindex(mensual.index.to_period("M")).fillna(0)
    perfiles = matriz.groupby(matriz.index.month).mean().T.reindex(columns=range(1, 13))
    normalizado = perfiles.div(perfiles.mean(axis=1).replace(0, np.nan), axis=0)
    fig, eje = plt.subplots(figsize=(11, 5))
    imagen = eje.imshow(normalizado, aspect="auto", cmap="YlOrRd")
    eje.set(yticks=range(len(perfiles)), yticklabels=perfiles.index,
            xticks=range(12), xticklabels=MESES, xlabel="Mes", ylabel="Categoría",
            title="Perfil mensual de ingresos por categoría (media = 1)")
    fig.colorbar(imagen, ax=eje, label="Ingreso relativo a la media de la categoría")
    categoria, mes = normalizado.stack().idxmax()
    _guardar(fig, salida, "categorias_mes",
             f"El mayor índice estacional es {categoria} en {MESES[mes-1]}: "
             f"{normalizado.loc[categoria, mes]:.2f} veces su media mensual "
             f"({perfiles.loc[categoria, mes]:,.2f} MXN). Se promedian los años disponibles por mes.", secciones)


def _sucursales(ventas, salida, secciones):
    resumen = ventas.groupby("codigo").total.agg(["sum", "mean"]).sort_values("sum", ascending=False)
    fig, ejes = plt.subplots(1, 2, figsize=(13, 5))
    for eje, columna, titulo in zip(ejes, ("sum", "mean"), ("Ventas por sucursal", "Ticket promedio por sucursal")):
        resumen[columna].plot.bar(ax=eje)
        eje.set(title=titulo, xlabel="Sucursal", ylabel="MXN")
    _millones(ejes[0])
    lider = resumen.index[0]
    _guardar(fig, salida, "sucursales",
             f"{lider} encabeza el ingreso con {resumen.loc[lider, 'sum']:,.2f} MXN "
             f"({resumen.loc[lider, 'sum']/ventas.total.sum():.1%}); su ticket promedio es "
             f"{resumen.loc[lider, 'mean']:,.2f} MXN. Los totales no ajustan por antigüedad de apertura.", secciones)


def _pareto(detalle, productos, salida, secciones):
    ingresos = detalle.groupby("id_producto").subtotal.sum().reindex(productos.id_producto, fill_value=0)
    ingresos = ingresos.sort_values(ascending=False)
    acumulado = ingresos.cumsum() / ingresos.sum() * 100
    cantidad = int(np.searchsorted(acumulado.to_numpy(), 80) + 1)
    porcentaje = cantidad / len(ingresos) * 100
    abc = pd.DataFrame({"ingreso_mxn": ingresos, "porcentaje_acumulado": acumulado})
    previo = acumulado.shift(fill_value=0)
    abc["clase"] = np.select([previo < 80, previo < 95], ["A", "B"], default="C")
    abc.join(productos.set_index("id_producto")[["sku"]]).to_csv(salida / "abc_productos.csv", encoding="utf-8", index=True)
    fig, eje = plt.subplots(figsize=(8, 4))
    eje.plot(np.r_[0, np.arange(1, len(ingresos)+1)/len(ingresos)*100], np.r_[0, acumulado])
    eje.axhline(80, color="gray", linestyle="--")
    eje.axvline(porcentaje, color="red", linestyle="--", label=f"{porcentaje:.1f} % de productos")
    eje.legend()
    eje.set(title="Pareto de productos por ingreso (ABC: 80/95/100 %)", xlabel="Productos acumulados (%)",
            ylabel="Ingreso acumulado (%)")
    _guardar(fig, salida, "pareto_productos",
             f"{cantidad} de {len(ingresos)} productos ({porcentaje:.1f} %) generan "
             f"{acumulado.iloc[cantidad-1]:.1f} % del ingreso. ABC incluye el producto que cruza cada umbral; "
             "el detalle está en [abc_productos.csv](abc_productos.csv).", secciones)


def _calendario(ventas, inicio, cierre, salida, secciones):
    dias = pd.date_range(inicio, cierre)
    diario = ventas.groupby(ventas.fecha_hora.dt.normalize()).total.sum().reindex(dias, fill_value=0)
    semana = diario.groupby(diario.index.dayofweek).mean().reindex(range(7), fill_value=0)
    horas = ventas.groupby(ventas.fecha_hora.dt.hour).total.sum().reindex(range(24), fill_value=0) / len(dias)
    nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    fig, ejes = plt.subplots(1, 2, figsize=(13, 4))
    ejes[0].bar(nombres, semana)
    ejes[0].tick_params(axis="x", rotation=30)
    ejes[0].set(title="Patrón semanal", xlabel="Día de la semana", ylabel="Ingreso medio por día (MXN)")
    ejes[1].bar(horas.index, horas)
    ejes[1].set(title="Patrón horario", xlabel="Hora local", ylabel="Ingreso por día observado (MXN)")
    _guardar(fig, salida, "calendario",
             f"{nombres[semana.idxmax()]} tiene el mayor ingreso diario medio: {semana.max():,.2f} MXN; "
             f"la hora pico es {horas.idxmax():02d}:00 con {horas.max():,.2f} MXN por día. "
             "Se incluyen días sin ventas; no se ajusta por sucursales activas.", secciones)


def _mezcla(ventas, clientes, salida, secciones):
    ventas = ventas.copy()
    ventas["segmento"] = ventas.id_cliente.map(clientes.set_index("id_cliente").tipo_cliente).fillna("público general")
    fig, ejes = plt.subplots(1, 2, figsize=(13, 5))
    textos = []
    for eje, columna, titulo in zip(ejes, ("metodo_pago", "segmento"), ("Métodos de pago", "Segmentos de clientes")):
        participacion = ventas.groupby(columna, dropna=False).total.sum() / ventas.total.sum() * 100
        participacion.plot.bar(ax=eje)
        eje.set(title=titulo, xlabel="Método" if columna == "metodo_pago" else "Segmento", ylabel="Participación en ingreso (%)")
        textos.append("; ".join(f"{nombre}: {valor:.1f} %" for nombre, valor in participacion.items()))
    _guardar(fig, salida, "mezcla", "Por ingreso en MXN, pagos: " + textos[0] + ". Segmentos: " + textos[1] + ".", secciones)


def calcular_cobertura(tablas, detalle, cierre):
    """Usa 90 días naturales inclusive; sin venta y con stock equivale a infinito."""
    recientes = detalle[detalle.fecha_hora.dt.normalize().between(cierre - pd.Timedelta(days=89), cierre)]
    unidades = recientes.groupby(["id_sucursal", "id_producto"]).cantidad.sum().rename("unidades_90_dias")
    cobertura = tablas["inventario"].merge(unidades, on=["id_sucursal", "id_producto"], how="left")
    cobertura["unidades_90_dias"] = cobertura.unidades_90_dias.fillna(0)
    cobertura["venta_diaria_promedio"] = cobertura.unidades_90_dias / 90
    cobertura["cobertura_dias"] = cobertura.existencia / cobertura.venta_diaria_promedio.replace(0, np.nan)
    cobertura.loc[(cobertura.existencia > 0) & (cobertura.unidades_90_dias == 0), "cobertura_dias"] = np.inf
    cobertura.loc[cobertura.existencia == 0, "cobertura_dias"] = 0
    cobertura = cobertura.merge(tablas["sucursales"][["id_sucursal", "codigo"]]).merge(tablas["productos"][["id_producto", "sku"]])
    return cobertura


def _inventario(tablas, detalle, cierre, salida, secciones):
    cobertura = calcular_cobertura(tablas, detalle, cierre)
    exceso = cobertura.cobertura_dias > 180
    cero = cobertura.existencia == 0
    cobertura.to_csv(salida / "cobertura_inventario.csv", index=False, encoding="utf-8")
    cobertura[exceso | cero].to_csv(salida / "alertas_inventario.csv", index=False, encoding="utf-8")
    finita = cobertura.loc[np.isfinite(cobertura.cobertura_dias), "cobertura_dias"]
    fig, eje = plt.subplots(figsize=(9, 4))
    eje.hist(finita, bins=40)
    eje.axvline(180, color="red", linestyle="--", label="Exceso: >180 días")
    eje.legend()
    eje.set(title="Cobertura de inventario al cierre (valores finitos)", xlabel="Cobertura (días)", ylabel="Pares sucursal-producto")
    _guardar(fig, salida, "inventario",
             f"Al {cierre:%Y-%m-%d}, {exceso.sum()} de {len(cobertura)} pares tienen cobertura >180 días, "
             f"incluidos {np.isinf(cobertura.cobertura_dias).sum()} con stock y sin ventas en 90 días; "
             f"{cero.sum()} tienen existencia cero. Mediana finita: {finita.median():.1f} días. "
             "Cobertura = existencia / (unidades vendidas en los últimos 90 días / 90), incluyendo ceros diarios. "
             "Stock cero se representa con cobertura cero; stock positivo sin ventas, con infinito (fuera del histograma). "
             "Lista completa: [alertas_inventario.csv](alertas_inventario.csv); "
             "todos los pares: [cobertura_inventario.csv](cobertura_inventario.csv).", secciones)
    return cobertura


def _incidencias(incidencias, inicio, cierre, salida, secciones):
    conteos = incidencias.groupby([pd.to_datetime(incidencias.fecha_reporte).dt.to_period("M"), "tipo"]).size().unstack(fill_value=0)
    conteos = conteos.reindex(pd.period_range(inicio, cierre, freq="M"), fill_value=0)
    fig, eje = plt.subplots(figsize=(12, 5))
    if not conteos.empty and len(conteos.columns):
        conteos.set_axis(conteos.index.astype(str)).plot(ax=eje)
        tipo = conteos.sum().idxmax()
        texto = f"{tipo} concentra {conteos[tipo].sum():,} de {conteos.to_numpy().sum():,} incidencias; su pico es {conteos[tipo].idxmax()} con {conteos[tipo].max():,}."
    else:
        texto = "Se registraron 0 incidencias en el periodo."
    eje.set(title="Incidencias por tipo y mes", xlabel="Mes", ylabel="Número de incidencias")
    _guardar(fig, salida, "incidencias", texto, secciones)


def _implicaciones(tablas, detalle, inicio, cierre, cobertura):
    pares = cobertura[["id_sucursal", "id_producto"]].merge(tablas["sucursales"][["id_sucursal", "fecha_apertura"]]).merge(tablas["productos"][["id_producto", "fecha_alta", "activo"]])
    pares["inicio_observable"] = pares[["fecha_apertura", "fecha_alta"]].apply(pd.to_datetime).max(axis=1).clip(lower=inicio)
    pares["dias_observables"] = (cierre - pares.inicio_observable).dt.days.add(1).clip(lower=0)
    positivos = detalle.groupby(["id_sucursal", "id_producto"]).fecha_hora.agg(lambda serie: serie.dt.normalize().nunique()).rename("dias_con_venta")
    pares = pares.merge(positivos, on=["id_sucursal", "id_producto"], how="left").fillna({"dias_con_venta": 0})
    # El catálogo no proporciona fecha de baja: no se inventa una vigencia histórica.
    activos = pares[(pares.dias_observables > 0) & pares.activo]
    proporcion = 1 - activos.dias_con_venta.sum() / activos.dias_observables.sum()
    nuevos = pd.to_datetime(tablas["productos"].fecha_alta).between(inicio, cierre).sum()
    aperturas = tablas["sucursales"][pd.to_datetime(tablas["sucursales"].fecha_apertura).between(inicio, cierre)]
    return ("## Implicaciones para el modelo de demanda\n\n"
            f"- Incorporar mes, día semanal, hora, quincena y eventos comerciales; validar con cortes temporales. "
            "El ingreso combina unidades, precios y descuentos: pronosticar unidades semanales por par y usar el ingreso como diagnóstico.\n"
            f"- Intermitencia: {proporcion:.1%} de los días-par observables de productos activos al cierre no tienen venta. "
            "El denominador comienza en el máximo entre apertura, alta e inicio del periodo e incluye pares sin ventas; "
            "comparar métodos para series intermitentes y medir error agregado y por segmento ABC.\n"
            f"- Hay {nuevos} productos dados de alta dentro del periodo y {(~tablas['productos'].activo).sum()} inactivos al cierre. "
            "No interpretar días previos al alta como demanda cero; usar categoría y atributos para arranque. "
            "La fecha de descontinuación no está en core, por lo que no puede reconstruirse la vigencia final exacta.\n"
            f"- Aperturas dentro del periodo: {len(aperturas)} ({', '.join(aperturas.codigo) or 'ninguna'}). "
            "Modelar antigüedad y maduración; comparar tasas por día operativo además de ventas totales.\n"
            "- Las ventas observadas están censuradas por disponibilidad. Existencia cero al cierre no demuestra "
            "desabasto durante todo el periodo; contrastar movimientos e incidencias sin atribuir los ceros automáticamente a falta de demanda. "
            "No se consultan tablas ocultas ni se estima aquí demanda perdida.\n")


def generar_reporte(datos: Path, salida: Path) -> Path:
    """Lee exclusivamente la lista explícita de tablas core y escribe el reporte."""
    tablas = {nombre: pd.read_parquet(Path(datos) / f"{nombre}.parquet") for nombre in TABLAS}
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    ventas = tablas["ventas"].query("estatus == 'completada'").copy()
    ventas["fecha_hora"] = pd.to_datetime(ventas.fecha_hora)
    inicio = pd.to_datetime(tablas["movimientos_inventario"].fecha).min().normalize()
    cierre = pd.to_datetime(tablas["inventario"].fecha_actualizacion).max().normalize()
    ventas["codigo"] = ventas.id_sucursal.map(tablas["sucursales"].set_index("id_sucursal").codigo)
    detalle = tablas["detalle_venta"].merge(ventas[["id_venta", "fecha_hora", "id_sucursal"]], on="id_venta", validate="many_to_one")
    categorias = tablas["productos"].merge(tablas["categorias"], on="id_categoria", suffixes=("", "_categoria"))
    detalle["categoria"] = detalle.id_producto.map(categorias.set_index("id_producto").nombre_categoria)
    secciones = [f"# EDA de DATACORE — NexaTech Solutions\n\nPeriodo: {inicio:%Y-%m-%d} a {cierre:%Y-%m-%d}. "
                 f"Se analizan {len(ventas):,} ventas completadas por {ventas.total.sum():,.2f} MXN; "
                 f"se excluyen {len(tablas['ventas'])-len(ventas):,} canceladas de todos los indicadores de venta. "
                 "Fuentes: únicamente las diez tablas core; no se leen tablas ocultas. "
                 "Los montos históricos usan total del ticket o subtotal del detalle, sin duplicar tickets en las uniones.\n"]
    _mensuales(ventas, detalle, salida, secciones)
    _sucursales(ventas, salida, secciones)
    _pareto(detalle, tablas["productos"], salida, secciones)
    _calendario(ventas, inicio, cierre, salida, secciones)
    _mezcla(ventas, tablas["clientes"], salida, secciones)
    cobertura = _inventario(tablas, detalle, cierre, salida, secciones)
    _incidencias(tablas["incidencias"], inicio, cierre, salida, secciones)
    secciones.append(_implicaciones(tablas, detalle, inicio, cierre, cobertura))
    destino = salida / "README.md"
    destino.write_text("\n".join(secciones), encoding="utf-8")
    return destino


def main() -> None:
    parser = argparse.ArgumentParser(description="EDA de las tablas core de DATACORE.")
    parser.add_argument("--datos", type=Path, default=Path("data/ground_truth"))
    parser.add_argument("--salida", type=Path, default=Path("reports/eda"))
    argumentos = parser.parse_args()
    print(generar_reporte(argumentos.datos, argumentos.salida))


if __name__ == "__main__":
    main()
