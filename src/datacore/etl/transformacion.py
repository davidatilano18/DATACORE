"""Transformación: limpieza, estandarización, validación y resolución de llaves.

Cada función recibe la tabla cruda (todo texto) y devuelve la tabla con las
columnas y tipos de `core`. Los nombres de las reglas coinciden con los tipos
de defecto del generador cuando atacan el mismo problema; así se puede medir
la detección contra `data/ground_truth/defectos_inyectados.csv`.
"""

import re

import numpy as np
import pandas as pd

from .calidad import PATRON_EMAIL, Hallazgos, clave_texto, espacios, normalizar_estado

FORMATO_ISO = "%Y-%m-%d %H:%M:%S"
FORMATO_ALTERNO = "%d/%m/%Y %H:%M"
METODOS_PAGO = {"efectivo", "tarjeta_debito", "tarjeta_credito", "transferencia"}


def _bool(serie: pd.Series) -> pd.Series:
    return serie.str.strip().str.lower().isin(["true", "1", "si", "sí", "verdadero"])


def _anio_archivo(serie: pd.Series) -> pd.Series:
    return serie.str.extract(r"_(\d{4})\.csv$")[0]


def _vacio_a_nulo(serie: pd.Series) -> pd.Series:
    s = serie.str.strip()
    return s.where(s != "", None)


# --- catálogos ---------------------------------------------------------------

def sucursales(df: pd.DataFrame, h: Hallazgos) -> pd.DataFrame:
    out = pd.DataFrame({
        "id_sucursal": df["id_sucursal"].astype(int),
        "codigo": df["codigo"].str.strip().str.upper(),
        "nombre": espacios(df["nombre"]),
        "ciudad": espacios(df["ciudad"]),
        "estado": espacios(df["estado"]),
        "region": espacios(df["region"]),
        "tamano": df["tamano"].str.strip().str.lower(),
        "fecha_apertura": pd.to_datetime(df["fecha_apertura"]).dt.date,
    })
    return out


def proveedores(df: pd.DataFrame, h: Hallazgos) -> pd.DataFrame:
    return pd.DataFrame({
        "id_proveedor": df["id_proveedor"].astype(int),
        "nombre": espacios(df["nombre"]),
        "rfc": df["rfc"].str.strip().str.upper(),
        "ciudad": _vacio_a_nulo(df["ciudad"]),
        "estado": _vacio_a_nulo(df["estado"]),
        "telefono": _vacio_a_nulo(df["telefono"].str.replace(r"\D", "", regex=True)),
        "email": _vacio_a_nulo(df["email"].str.lower()),
        "dias_entrega": df["dias_entrega"].astype(int),
        "activo": _bool(df["activo"]),
    })


def categorias(productos_crudo: pd.DataFrame) -> pd.DataFrame:
    nombres = sorted(set(espacios(productos_crudo["categoria"])) - {""})
    return pd.DataFrame({"id_categoria": range(1, len(nombres) + 1), "nombre": nombres})


def productos(df: pd.DataFrame, cats: pd.DataFrame, h: Hallazgos) -> pd.DataFrame:
    p = df.copy()
    p["sku"] = p["sku"].str.strip().str.upper()
    p["categoria"] = espacios(p["categoria"])
    p["precio_unitario"] = p["precio_unitario"].astype(float)
    p["costo_unitario"] = p["costo_unitario"].astype(float)

    # Categoría faltante: se infiere del prefijo del SKU (NX-ABA-… → la categoría de los demás NX-ABA-…).
    prefijo = p["sku"].str.split("-").str[1]
    conocidos = p[p["categoria"] != ""]
    por_prefijo = conocidos.groupby(prefijo[conocidos.index])["categoria"].agg(lambda s: s.mode().iat[0])
    inferida = prefijo[p["categoria"] == ""].map(por_prefijo).dropna()
    p.loc[inferida.index, "categoria"] = inferida
    h.agregar("productos", "producto_categoria_faltante", p.loc[inferida.index, "sku"], "corregido", None, inferida)
    sin_cat = p["categoria"] == ""
    h.agregar("productos", "producto_categoria_faltante", p.loc[sin_cat, "sku"], "rechazado")
    p = p[~sin_cat]

    # Costo mayor o igual al precio: se imputa con el margen mediano de su categoría.
    margen = 1 - p["costo_unitario"] / p["precio_unitario"]
    validos = margen > 0
    margen_cat = margen[validos].groupby(p.loc[validos, "categoria"]).median()
    malo = ~validos
    nuevo = (p.loc[malo, "precio_unitario"] * (1 - p.loc[malo, "categoria"].map(margen_cat))).round(2)
    h.agregar("productos", "producto_costo_mayor_precio", p.loc[malo, "sku"], "corregido",
              p.loc[malo, "costo_unitario"], nuevo)
    p.loc[malo, "costo_unitario"] = nuevo

    return pd.DataFrame({
        "id_producto": p["id_producto"].astype(int),
        "sku": p["sku"],
        "nombre": espacios(p["nombre"]),
        "id_categoria": p["categoria"].map(cats.set_index("nombre")["id_categoria"]).astype(int),
        "id_proveedor": p["id_proveedor"].astype(int),
        "precio_unitario": p["precio_unitario"].round(2),
        "costo_unitario": p["costo_unitario"].round(2),
        "unidad": p["unidad"].str.strip(),
        "fecha_alta": pd.to_datetime(p["fecha_alta"]).dt.date,
        "activo": _bool(p["activo"]),
    })


def clientes(df: pd.DataFrame, h: Hallazgos) -> tuple[pd.DataFrame, dict[int, int]]:
    """Devuelve clientes únicos y el mapa {id_duplicado: id_maestro}."""
    c = df.copy()
    c["id_cliente"] = c["id_cliente"].astype(int)
    for col in ("nombre", "apellido_paterno", "apellido_materno", "ciudad"):
        c[col] = espacios(c[col])
    email_crudo = c["email"].str.strip().str.lower()
    c["email"] = _vacio_a_nulo(email_crudo.str.replace(r"\s+", "", regex=True))
    con_espacios = email_crudo.str.contains(r"\s", regex=True)
    h.agregar("clientes", "cliente_email_invalido", c.loc[con_espacios, "id_cliente"], "corregido",
              email_crudo[con_espacios], c.loc[con_espacios, "email"])
    c["telefono"] = _vacio_a_nulo(c["telefono"].str.replace(r"\D", "", regex=True))

    # Casi duplicados: mismo nombre normalizado y misma fecha de registro.
    llave = (clave_texto(c["nombre"]) + "|" + clave_texto(c["apellido_paterno"]) + "|"
             + clave_texto(c["apellido_materno"]) + "|" + c["fecha_registro"].str.strip())
    c = c.sort_values("id_cliente")
    c["_maestro"] = c.groupby(llave.loc[c.index])["id_cliente"].transform("min")
    dup = c["id_cliente"] != c["_maestro"]
    h.agregar("clientes", "cliente_casi_duplicado", c.loc[dup, "id_cliente"], "corregido",
              c.loc[dup, "id_cliente"], c.loc[dup, "_maestro"])
    mapa = dict(zip(c.loc[dup, "id_cliente"], c.loc[dup, "_maestro"]))

    # El registro maestro toma correo y teléfono del duplicado si a él le faltan.
    for col in ("email", "telefono"):
        respaldo = c[dup].dropna(subset=[col]).groupby("_maestro")[col].first()
        maestros = c[~dup]
        recupera = maestros[col].isna() & maestros["id_cliente"].isin(respaldo.index)
        idx = maestros.index[recupera]
        valores = c.loc[idx, "id_cliente"].map(respaldo)
        c.loc[idx, col] = valores
        h.agregar("clientes", f"cliente_{col}_faltante", c.loc[idx, "id_cliente"], "corregido", None, valores)
    c = c[~dup].copy()

    falta_email = c["email"].isna()
    h.agregar("clientes", "cliente_email_faltante", c.loc[falta_email, "id_cliente"], "marcado")
    falta_tel = c["telefono"].isna()
    h.agregar("clientes", "cliente_telefono_faltante", c.loc[falta_tel, "id_cliente"], "marcado")

    original = c["email"].copy()
    c["email"] = c["email"].str.replace(r"\.con$", ".com", regex=True)
    invalido = c["email"].notna() & ~c["email"].fillna("").str.match(PATRON_EMAIL)
    corregido = c["email"].notna() & (c["email"] != original) & ~invalido
    h.agregar("clientes", "cliente_email_invalido", c.loc[corregido, "id_cliente"], "corregido",
              original[corregido], c.loc[corregido, "email"])
    h.agregar("clientes", "cliente_email_invalido", c.loc[invalido, "id_cliente"], "marcado",
              c.loc[invalido, "email"], None)
    c.loc[invalido, "email"] = None

    tel_malo = c["telefono"].notna() & (c["telefono"].str.len() != 10)
    h.agregar("clientes", "cliente_telefono_invalido", c.loc[tel_malo, "id_cliente"], "marcado", c.loc[tel_malo, "telefono"])
    c.loc[tel_malo, "telefono"] = None

    estado = normalizar_estado(c["estado"])
    cambia = estado.notna() & (estado != c["estado"].str.strip())
    h.agregar("clientes", "cliente_estado_variante", c.loc[cambia, "id_cliente"], "corregido",
              c.loc[cambia, "estado"], estado[cambia])
    desconocido = estado.isna() & (c["estado"].str.strip() != "")
    h.agregar("clientes", "cliente_estado_desconocido", c.loc[desconocido, "id_cliente"], "marcado", c.loc[desconocido, "estado"])
    c["estado"] = estado.fillna(_vacio_a_nulo(c["estado"]))

    tipo = c["tipo_cliente"].str.strip().str.lower()
    out = pd.DataFrame({
        "id_cliente": c["id_cliente"],
        "nombre": c["nombre"],
        "apellido_paterno": c["apellido_paterno"],
        "apellido_materno": _vacio_a_nulo(c["apellido_materno"]),
        "email": c["email"],
        "telefono": c["telefono"],
        "ciudad": _vacio_a_nulo(c["ciudad"]),
        "estado": c["estado"],
        "tipo_cliente": tipo,
        "fecha_registro": pd.to_datetime(c["fecha_registro"]).dt.date,
        "id_sucursal_preferida": pd.to_numeric(c["id_sucursal_preferida"], errors="coerce").astype("Int64"),
    })
    return out.reset_index(drop=True), mapa


# --- transacciones -------------------------------------------------------------

def _quitar_duplicados(df, llave, tabla, regla, h) -> pd.DataFrame:
    """Quita renglones repetidos idénticos; si la llave se repite con contenido distinto, rechaza las copias."""
    negocio = [c for c in df.columns if not c.startswith("_")]
    exactos = df.duplicated(subset=negocio, keep="first")
    h.agregar(tabla, regla, df.loc[exactos, llave], "corregido")
    df = df[~exactos]
    choque = df.duplicated(subset=[llave], keep="first")
    h.agregar(tabla, "llave_duplicada", df.loc[choque, llave], "rechazado")
    return df[~choque]


def detalle_venta(df: pd.DataFrame, prods: pd.DataFrame, h: Hallazgos) -> pd.DataFrame:
    d = _quitar_duplicados(df.copy(), "id_detalle", "detalle_venta", "detalle_duplicado", h)
    d["sku"] = d["sku"].str.strip().str.upper()
    d["id_producto"] = d["sku"].map(prods.set_index("sku")["id_producto"])
    inexistente = d["id_producto"].isna()
    h.agregar("detalle_venta", "detalle_producto_inexistente", d.loc[inexistente, "id_detalle"], "rechazado",
              d.loc[inexistente, "sku"])
    d = d[~inexistente].copy()

    d["cantidad"] = d["cantidad"].astype(int)
    negativa = d["cantidad"] < 0
    h.agregar("detalle_venta", "detalle_cantidad_negativa", d.loc[negativa, "id_detalle"], "corregido",
              d.loc[negativa, "cantidad"], -d.loc[negativa, "cantidad"])
    d.loc[negativa, "cantidad"] = -d.loc[negativa, "cantidad"]
    cero = d["cantidad"] == 0
    h.agregar("detalle_venta", "detalle_cantidad_cero", d.loc[cero, "id_detalle"], "rechazado")
    d = d[~cero].copy()

    # Precio con el punto decimal recorrido: se compara contra la mediana del producto en ese año.
    d["precio_unitario"] = d["precio_unitario"].astype(float)
    d["descuento_pct"] = d["descuento_pct"].astype(float)
    anio = _anio_archivo(d["_archivo"])
    referencia = d.groupby([d["id_producto"], anio])["precio_unitario"].transform("median")
    razon = d["precio_unitario"] / referencia
    factor = np.select([razon.between(5, 20), razon.between(0.05, 0.2)], [0.1, 10.0], 1.0)
    escala = factor != 1.0
    # Multiplicar por 10 no recupera los centavos ya redondeados; si el subtotal capturado
    # es coherente con el precio de referencia, el precio se reconstruye a partir de él.
    desde_subtotal = (d["subtotal"].astype(float) / (d["cantidad"] * (1 - d["descuento_pct"]))).round(2)
    coherente = (desde_subtotal / referencia).between(0.8, 1.25)
    nuevo = np.where(coherente, desde_subtotal, (d["precio_unitario"] * factor).round(2))
    nuevo = pd.Series(np.where(escala, nuevo, d["precio_unitario"]), index=d.index)
    h.agregar("detalle_venta", "detalle_precio_escala", d.loc[escala, "id_detalle"], "corregido",
              d.loc[escala, "precio_unitario"], nuevo[escala])
    d["precio_unitario"] = nuevo

    d["subtotal"] = (d["cantidad"] * d["precio_unitario"] * (1 - d["descuento_pct"])).round(2)
    return pd.DataFrame({
        "id_detalle": d["id_detalle"].astype(np.int64),
        "id_venta": d["id_venta"].astype(np.int64),
        "id_producto": d["id_producto"].astype(int),
        "cantidad": d["cantidad"],
        "precio_unitario": d["precio_unitario"],
        "descuento_pct": d["descuento_pct"],
        "subtotal": d["subtotal"],
    })


def _codigos_sucursal(crudo: pd.Series, sucs: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Devuelve (id_sucursal, se_corrigio). Acepta 'qro01', ' QRO01 ', 'QRO-01'."""
    limpio = crudo.str.upper().str.replace(r"[\s\-_]", "", regex=True)
    ids = limpio.map(sucs.set_index("codigo")["id_sucursal"])
    return ids, limpio != crudo


def ventas(df: pd.DataFrame, sucs: pd.DataFrame, mapa_clientes: dict[int, int], ids_clientes: set[int],
           detalle: pd.DataFrame, detalle_crudo: pd.DataFrame, h: Hallazgos) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve (ventas, detalle) consistentes entre sí."""
    unicos = detalle_crudo.drop_duplicates(subset=[c for c in detalle_crudo.columns if not c.startswith("_")])
    detalle_crudo_subtotal = (unicos.assign(id_venta=unicos["id_venta"].astype(np.int64),
                                            subtotal=unicos["subtotal"].astype(float))
                              .groupby("id_venta")["subtotal"].sum().round(2))
    v = _quitar_duplicados(df.copy(), "id_venta", "ventas", "venta_duplicada", h)

    v["id_sucursal"], corregido = _codigos_sucursal(v["codigo_sucursal"], sucs)
    ok = corregido & v["id_sucursal"].notna()
    h.agregar("ventas", "sucursal_codigo_sucio", v.loc[ok, "id_venta"], "corregido",
              v.loc[ok, "codigo_sucursal"], v.loc[ok, "id_sucursal"])
    sin_suc = v["id_sucursal"].isna()
    h.agregar("ventas", "sucursal_inexistente", v.loc[sin_suc, "id_venta"], "rechazado", v.loc[sin_suc, "codigo_sucursal"])
    v = v[~sin_suc].copy()

    # Fecha: el año debe coincidir con el del archivo (cierre anual del POS).
    texto = v["fecha_hora"].str.strip()
    anio = _anio_archivo(v["_archivo"])
    es_iso = texto.str.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
    otro_anio = es_iso & (texto.str[:4] != anio)
    corregida = anio[otro_anio] + texto[otro_anio].str[4:]
    h.agregar("ventas", "venta_fecha_futura", v.loc[otro_anio, "id_venta"], "corregido", texto[otro_anio], corregida)
    texto = texto.where(~otro_anio, corregida)
    fecha = pd.to_datetime(texto, format=FORMATO_ISO, errors="coerce")
    alterna = fecha.isna()
    fecha_alt = pd.to_datetime(texto[alterna], format=FORMATO_ALTERNO, errors="coerce")
    ok = alterna & fecha_alt.reindex(v.index).notna()
    h.agregar("ventas", "venta_fecha_formato_alterno", v.loc[ok, "id_venta"], "corregido",
              texto[ok], fecha_alt[ok[alterna]].dt.strftime(FORMATO_ISO))
    fecha = fecha.fillna(fecha_alt.reindex(v.index))
    sin_fecha = fecha.isna()
    h.agregar("ventas", "venta_fecha_invalida", v.loc[sin_fecha, "id_venta"], "rechazado", texto[sin_fecha])
    v["fecha_hora"] = fecha
    v = v[~sin_fecha].copy()

    metodo = v["metodo_pago"].str.strip().str.lower()
    falta = ~metodo.isin(METODOS_PAGO)
    h.agregar("ventas", "venta_metodo_pago_faltante", v.loc[falta, "id_venta"], "marcado", v.loc[falta, "metodo_pago"])
    v["metodo_pago"] = metodo.where(~falta, None)

    cliente = pd.to_numeric(v["id_cliente"].str.strip(), errors="coerce").astype("Int64")
    reasigna = cliente.isin(list(mapa_clientes))
    h.agregar("ventas", "venta_cliente_duplicado", v.loc[reasigna, "id_venta"], "corregido",
              cliente[reasigna], cliente[reasigna].map(mapa_clientes))
    cliente = cliente.where(~reasigna, cliente.map(mapa_clientes)).astype("Int64")
    desconocido = cliente.notna() & ~cliente.isin(list(ids_clientes))
    h.agregar("ventas", "venta_cliente_inexistente", v.loc[desconocido, "id_venta"], "marcado", cliente[desconocido])
    v["id_cliente"] = cliente.mask(desconocido)

    v["id_venta"] = v["id_venta"].astype(np.int64)
    detalle = detalle[detalle["id_venta"].isin(v["id_venta"])]
    total = detalle.groupby("id_venta")["subtotal"].sum().round(2)
    sin_detalle = ~v["id_venta"].isin(total.index)
    h.agregar("ventas", "venta_sin_detalle", v.loc[sin_detalle, "id_venta"], "rechazado")
    v = v[~sin_detalle].copy()

    calculado = v["id_venta"].map(total)
    reportado = v["total"].astype(float)
    difiere = (reportado - calculado).abs() > 0.011
    # Si el total capturado cuadra con los renglones crudos, la diferencia viene de renglones
    # rechazados (no de un total mal capturado).
    crudo = detalle_crudo_subtotal.reindex(v["id_venta"]).to_numpy()
    por_rechazo = difiere & (np.abs(reportado - crudo) <= 0.011)
    h.agregar("ventas", "venta_total_ajustado_por_rechazo", v.loc[por_rechazo, "id_venta"], "corregido",
              reportado[por_rechazo], calculado[por_rechazo])
    inconsistente = difiere & ~por_rechazo
    h.agregar("ventas", "venta_total_inconsistente", v.loc[inconsistente, "id_venta"], "corregido",
              reportado[inconsistente], calculado[inconsistente])
    v["total"] = calculado

    out = pd.DataFrame({
        "id_venta": v["id_venta"],
        "folio": v["folio"].str.strip(),
        "fecha_hora": v["fecha_hora"],
        "id_sucursal": v["id_sucursal"].astype(int),
        "id_cliente": v["id_cliente"],
        "metodo_pago": v["metodo_pago"],
        "total": v["total"],
        "estatus": v["estatus"].str.strip().str.lower(),
    })
    return out.sort_values("id_venta").reset_index(drop=True), detalle.sort_values("id_detalle").reset_index(drop=True)


def detalle_huerfano(detalle_limpio: pd.DataFrame, detalle_final: pd.DataFrame, h: Hallazgos) -> None:
    """Registra los renglones descartados porque su venta fue rechazada."""
    perdidos = detalle_limpio[~detalle_limpio["id_detalle"].isin(detalle_final["id_detalle"])]
    h.agregar("detalle_venta", "detalle_sin_venta", perdidos["id_detalle"], "rechazado")


def _mapear_codigos(df: pd.DataFrame, sucs: pd.DataFrame, prods: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["id_sucursal"], _ = _codigos_sucursal(df["codigo_sucursal"], sucs)
    sku = df["sku"].str.strip().str.upper()
    df["id_producto"] = sku.map(prods.set_index("sku")["id_producto"])
    df.loc[sku == "", "id_producto"] = np.nan
    df["_sku_desconocido"] = (sku != "") & df["id_producto"].isna()
    return df


def movimientos(df: pd.DataFrame, sucs: pd.DataFrame, prods: pd.DataFrame, h: Hallazgos) -> pd.DataFrame:
    m = _mapear_codigos(df, sucs, prods)
    malos = m["id_sucursal"].isna() | m["id_producto"].isna()
    h.agregar("movimientos_inventario", "movimiento_llave_invalida", m.loc[malos, "id_movimiento"], "rechazado")
    m = m[~malos].copy()
    m["id_movimiento"] = m["id_movimiento"].astype(np.int64)
    m["cantidad"] = m["cantidad"].astype(int)
    m["existencia_resultante"] = m["existencia_resultante"].astype(int)
    m = m.sort_values("id_movimiento")

    # Cantidad en cero: se reconstruye con la diferencia de existencias del mismo par.
    previa = m.groupby(["id_sucursal", "id_producto"])["existencia_resultante"].shift(1).fillna(0).astype(int)
    cero = m["cantidad"] == 0
    reconstruida = m["existencia_resultante"] - previa
    h.agregar("movimientos_inventario", "movimiento_cantidad_cero", m.loc[cero, "id_movimiento"], "corregido",
              m.loc[cero, "cantidad"], reconstruida[cero])
    m.loc[cero, "cantidad"] = reconstruida[cero]
    sigue_cero = m["cantidad"] == 0
    h.agregar("movimientos_inventario", "movimiento_cantidad_cero", m.loc[sigue_cero, "id_movimiento"], "rechazado")
    m = m[~sigue_cero]
    previa = previa[m.index]
    descuadre = m["existencia_resultante"] != previa + m["cantidad"]
    h.agregar("movimientos_inventario", "movimiento_descuadrado", m.loc[descuadre, "id_movimiento"], "marcado")

    return pd.DataFrame({
        "id_movimiento": m["id_movimiento"],
        "fecha": pd.to_datetime(m["fecha"]).dt.date,
        "id_sucursal": m["id_sucursal"].astype(int),
        "id_producto": m["id_producto"].astype(int),
        "tipo": m["tipo"].str.strip().str.upper(),
        "cantidad": m["cantidad"],
        "existencia_resultante": m["existencia_resultante"],
        "referencia": _vacio_a_nulo(m["referencia"]),
    }).reset_index(drop=True)


def inventario(df: pd.DataFrame, sucs: pd.DataFrame, prods: pd.DataFrame, h: Hallazgos) -> pd.DataFrame:
    i = _mapear_codigos(df, sucs, prods)
    malos = i["id_sucursal"].isna() | i["id_producto"].isna()
    h.agregar("inventario", "inventario_llave_invalida", (i["codigo_sucursal"] + "|" + i["sku"])[malos], "rechazado")
    i = i[~malos]
    return pd.DataFrame({
        "id_sucursal": i["id_sucursal"].astype(int),
        "id_producto": i["id_producto"].astype(int),
        "existencia": i["existencia"].astype(int),
        "stock_minimo": i["stock_minimo"].astype(int),
        "stock_maximo": i["stock_maximo"].astype(int),
        "fecha_actualizacion": pd.to_datetime(i["fecha_actualizacion"]).dt.date,
    }).reset_index(drop=True)


def incidencias(df: pd.DataFrame, sucs: pd.DataFrame, prods: pd.DataFrame, h: Hallazgos) -> pd.DataFrame:
    i = _mapear_codigos(df, sucs, prods)
    malos = i["id_sucursal"].isna() | i["_sku_desconocido"]
    h.agregar("incidencias", "incidencia_llave_invalida", i.loc[malos, "id_incidencia"], "rechazado")
    i = i[~malos]
    return pd.DataFrame({
        "id_incidencia": i["id_incidencia"].astype(int),
        "fecha_reporte": pd.to_datetime(i["fecha_reporte"]).dt.date,
        "id_sucursal": i["id_sucursal"].astype(int),
        "id_producto": i["id_producto"].astype("Int64"),
        "tipo": i["tipo"].str.strip().str.upper(),
        "severidad": i["severidad"].str.strip().str.lower(),
        "descripcion": espacios(i["descripcion"]),
        "estatus": i["estatus"].str.strip().str.lower(),
        "fecha_resolucion": pd.to_datetime(_vacio_a_nulo(i["fecha_resolucion"])).dt.date,
    }).reset_index(drop=True)
