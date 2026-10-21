"""Catálogos maestros: sucursales, categorías, proveedores, productos y clientes.

Las columnas que empiezan con "_" son parámetros ocultos de la simulación
(popularidad, tendencia, etc.). Se usan para generar los datos pero nunca se
exportan: el equipo de analítica debe descubrir esos patrones en los datos.
"""

import unicodedata

import numpy as np
import pandas as pd
from faker import Faker

from .catalogs import ARTICULOS, GIROS_PROVEEDOR, MARCAS, PRESENTACIONES, SUFIJOS_PROVEEDOR
from .config import CATEGORIAS, SUCURSALES, TICKETS_DIA_POR_TAMANO, GeneratorConfig

LADAS = {"Querétaro": "442", "El Marqués": "442", "Ciudad de México": "55", "Zapopan": "33",
         "San Nicolás de los Garza": "81", "León": "477", "San Luis Potosí": "444", "Puebla": "222",
         "Aguascalientes": "449", "Morelia": "443"}


def _sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def _telefono(rng: np.random.Generator, ciudad: str) -> str:
    lada = LADAS.get(ciudad, "55")
    return lada + "".join(str(d) for d in rng.integers(0, 10, 10 - len(lada)))


def build_sucursales() -> pd.DataFrame:
    df = pd.DataFrame([s.__dict__ for s in SUCURSALES])
    df.insert(0, "id_sucursal", np.arange(1, len(df) + 1))
    df["fecha_apertura"] = pd.to_datetime(df["fecha_apertura"])
    df["_tickets_dia"] = df["tamano"].map(TICKETS_DIA_POR_TAMANO)
    return df


def build_categorias() -> pd.DataFrame:
    df = pd.DataFrame([c.__dict__ for c in CATEGORIAS])
    df.insert(0, "id_categoria", np.arange(1, len(df) + 1))
    return df


def build_proveedores(cfg: GeneratorConfig, rng: np.random.Generator, fake: Faker,
                      categorias: pd.DataFrame) -> pd.DataFrame:
    filas = []
    nombres_usados = set()
    for i in range(cfg.n_proveedores):
        while True:
            nombre = f"{rng.choice(GIROS_PROVEEDOR)} {fake.last_name()} {rng.choice(SUFIJOS_PROVEEDOR)}"
            if nombre not in nombres_usados:
                nombres_usados.add(nombre)
                break
        ciudad = rng.choice(list(LADAS))
        estado = next((s.estado for s in SUCURSALES if s.ciudad == ciudad), "Querétaro")
        siglas = "".join(p[0] for p in _sin_acentos(nombre).split()[:3]).upper()
        filas.append({
            "id_proveedor": i + 1,
            "nombre": nombre,
            "rfc": f"{siglas:X<3}{rng.integers(90, 100)}{rng.integers(1, 13):02d}{rng.integers(1, 29):02d}"
                   f"{''.join(rng.choice(list('ABCDEFGHJKLMNPQRSTUVWXYZ0123456789'), 3))}",
            "ciudad": ciudad,
            "estado": estado,
            "telefono": _telefono(rng, ciudad),
            "email": f"ventas@{_sin_acentos(nombre.split()[1]).lower()}{i + 1}.com.mx",
            "dias_entrega": int(rng.integers(2, 11)),
            "activo": True,
            # Probabilidad de que una entrega llegue tarde.
            "_prob_retraso": float(rng.uniform(0.03, 0.35)),
        })
    df = pd.DataFrame(filas)
    # Cada categoría tiene al menos tres proveedores; algunos surten dos categorías.
    surte: list[list[int]] = [[] for _ in range(len(df))]
    for cat_id in categorias["id_categoria"]:
        for p in rng.choice(len(df), size=3, replace=False):
            surte[p].append(int(cat_id))
    for lista in surte:
        if not lista:
            lista.append(int(rng.choice(categorias["id_categoria"])))
    df["_categorias"] = surte
    return df


def build_productos(cfg: GeneratorConfig, rng: np.random.Generator, categorias: pd.DataFrame,
                    proveedores: pd.DataFrame) -> pd.DataFrame:
    inicio, fin = pd.Timestamp(cfg.fecha_inicio), pd.Timestamp(cfg.fecha_fin)
    dias_periodo = (fin - inicio).days
    # Reparto de productos por categoría, ligeramente desigual.
    pesos = rng.dirichlet(np.full(len(categorias), 8.0))
    minimo = min(15, cfg.n_productos // (2 * len(categorias)))
    por_categoria = np.maximum(minimo, np.floor(pesos * cfg.n_productos)).astype(int)
    por_categoria[np.argmax(por_categoria)] += cfg.n_productos - por_categoria.sum()

    filas = []
    for cat, n in zip(categorias.itertuples(), por_categoria):
        provs = proveedores[proveedores["_categorias"].map(lambda c: cat.id_categoria in c)]["id_proveedor"].to_numpy()
        nombres = set()
        while len(nombres) < n:
            articulo = rng.choice(ARTICULOS[cat.nombre])
            marca = rng.choice(MARCAS)
            if cat.nombre in PRESENTACIONES:
                extra = rng.choice(PRESENTACIONES[cat.nombre])
            else:
                extra = f"Mod. {rng.choice(list('ABCDEFGHKLMRSTX'))}{rng.integers(10, 990)}"
            nombres.add(f"{articulo} {marca} {extra}")
        # Precio log-uniforme dentro del rango de la categoría.
        precios = np.exp(rng.uniform(np.log(cat.precio_min), np.log(cat.precio_max), n))
        for nombre, precio in zip(sorted(nombres), precios):
            filas.append({
                "nombre": nombre,
                "id_categoria": cat.id_categoria,
                "categoria": cat.nombre,
                "id_proveedor": int(rng.choice(provs)),
                "_precio_base": round(float(precio), 2),
                "_margen": float(rng.uniform(0.18, 0.45)),
            })
    df = pd.DataFrame(filas)
    df = df.sample(frac=1, random_state=int(rng.integers(1 << 31))).reset_index(drop=True)
    df.insert(0, "id_producto", np.arange(1, len(df) + 1))
    prefijo = df["categoria"].map(lambda c: _sin_acentos(c)[:3].upper())
    df.insert(1, "sku", [f"NX-{p}-{i:05d}" for p, i in zip(prefijo, df["id_producto"])])

    n = len(df)
    # Popularidad con cola larga (pocos productos concentran la mayoría de ventas).
    df["_popularidad"] = rng.lognormal(mean=0.0, sigma=1.1, size=n)
    df["_tendencia_anual"] = rng.normal(cfg.crecimiento_anual_medio, 0.12, n).clip(-0.35, 0.6)
    df["_cantidad_media"] = df["id_categoria"].map(categorias.set_index("id_categoria")["cantidad_media"])
    df["_perecedero"] = df["id_categoria"].map(categorias.set_index("id_categoria")["perecedero"])

    fecha_alta = pd.Series(inicio - pd.to_timedelta(rng.integers(60, 2500, n), unit="D"))
    nuevos = rng.random(n) < cfg.pct_productos_nuevos
    # Altas y bajas dentro del periodo caen en día 1 de mes: la mezcla de
    # productos se calcula por mes y así ninguna venta queda fuera de vigencia.
    margen = max(1, min(120, dias_periodo // 4))
    alta_nuevos = inicio + pd.to_timedelta(rng.integers(margen, dias_periodo - margen, nuevos.sum()), unit="D")
    fecha_alta[nuevos] = alta_nuevos.to_period("M").to_timestamp()
    df["fecha_alta"] = fecha_alta.dt.normalize()

    fecha_baja = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    candidatos = np.flatnonzero(~nuevos)
    baja = rng.choice(candidatos, size=int(cfg.pct_productos_descontinuados * n), replace=False)
    desde = max(1, min(180, dias_periodo // 3))
    fechas = inicio + pd.to_timedelta(rng.integers(desde, max(desde + 1, dias_periodo - 30), len(baja)), unit="D")
    fecha_baja.iloc[baja] = fechas.to_period("M").to_timestamp()
    df["_fecha_baja"] = fecha_baja.dt.normalize()
    df["activo"] = df["_fecha_baja"].isna()
    df["unidad"] = "pieza"
    return df


def build_clientes(cfg: GeneratorConfig, rng: np.random.Generator, fake: Faker,
                   sucursales: pd.DataFrame) -> pd.DataFrame:
    n = cfg.n_clientes
    peso_suc = sucursales["_tickets_dia"].to_numpy()
    suc_idx = rng.choice(len(sucursales), size=n, p=peso_suc / peso_suc.sum())
    suc = sucursales.iloc[suc_idx].reset_index(drop=True)

    nombres = [fake.first_name() for _ in range(n)]
    ap1 = [fake.last_name() for _ in range(n)]
    ap2 = [fake.last_name() for _ in range(n)]
    dominios = rng.choice(["gmail.com", "hotmail.com", "outlook.com", "yahoo.com.mx", "icloud.com"],
                          size=n, p=[0.45, 0.25, 0.15, 0.10, 0.05])
    emails = []
    for i in range(n):
        base = _sin_acentos(f"{nombres[i].split()[0]}.{ap1[i]}").lower().replace(" ", "")
        emails.append(f"{base}{rng.integers(1, 999)}@{dominios[i]}")

    fin = pd.Timestamp(cfg.fecha_fin)
    # Registro entre la apertura de su sucursal (o 2019) y el fin del periodo.
    desde = suc["fecha_apertura"].clip(lower=pd.Timestamp("2019-01-01"))
    rango = (fin - desde).dt.days.to_numpy()
    registro = desde + pd.to_timedelta((rng.random(n) ** 1.3 * rango).astype(int), unit="D")

    mayorista = rng.random(n) < cfg.pct_clientes_mayoristas
    return pd.DataFrame({
        "id_cliente": np.arange(1, n + 1),
        "nombre": nombres,
        "apellido_paterno": ap1,
        "apellido_materno": ap2,
        "email": emails,
        "telefono": [_telefono(rng, c) for c in suc["ciudad"]],
        "ciudad": suc["ciudad"],
        "estado": suc["estado"],
        "tipo_cliente": np.where(mayorista, "mayorista", "minorista"),
        "fecha_registro": registro.dt.normalize(),
        "id_sucursal_preferida": suc["id_sucursal"],
        # Lealtad: qué tan seguido compra respecto a otros clientes de su sucursal.
        "_frecuencia": rng.lognormal(0.0, 0.9, n) * np.where(mayorista, 2.5, 1.0),
    })
