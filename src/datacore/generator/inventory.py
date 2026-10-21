"""Simulación diaria de inventario por sucursal y producto.

Política (s, S) con revisión diaria: cuando la existencia cae por debajo del
punto de reorden `s` se pide hasta `S`. Los parámetros se recalibran cada
trimestre con las ventas observadas, multiplicadas por un error de
estimación propio de cada par sucursal-producto. Ese error, junto con la
estacionalidad y los retrasos de proveedores, genera faltantes y excesos
realistas, que son justo lo que el módulo predictivo debe anticipar.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import GeneratorConfig


@dataclass
class ResultadoInventario:
    vendido: np.ndarray          # (n_suc, n_prod, n_dias) unidades surtidas
    perdido: np.ndarray          # demanda no surtida por falta de existencia
    movimientos: pd.DataFrame
    existencia_final: pd.DataFrame
    entregas: pd.DataFrame       # órdenes de compra con su retraso real


def simular(cfg: GeneratorConfig, rng: np.random.Generator, demanda: np.ndarray,
            sucursales: pd.DataFrame, productos: pd.DataFrame, proveedores: pd.DataFrame,
            dias: pd.DatetimeIndex) -> ResultadoInventario:
    n_suc, n_prod, n_dias = demanda.shape
    forma = (n_suc, n_prod)

    prov = proveedores.set_index("id_proveedor")
    lead = productos["id_proveedor"].map(prov["dias_entrega"]).to_numpy()[None, :].repeat(n_suc, 0)
    p_retraso = productos["id_proveedor"].map(prov["_prob_retraso"]).to_numpy()[None, :].repeat(n_suc, 0)
    perecedero = productos["_perecedero"].to_numpy()[None, :].repeat(n_suc, 0)

    dia_apertura = np.searchsorted(dias, sucursales["fecha_apertura"].to_numpy())[:, None]
    dia_alta = np.searchsorted(dias, productos["fecha_alta"].to_numpy())[None, :]
    baja = productos["_fecha_baja"].fillna(dias[-1] + pd.Timedelta(days=365))
    # Se deja de resurtir 30 días antes de descontinuar; lo que sobre queda como inventario muerto.
    dia_fin_resurtido = np.searchsorted(dias, (baja - pd.Timedelta(days=30)).to_numpy())[None, :]

    error = rng.uniform(cfg.error_estimacion_min, cfg.error_estimacion_max, forma)
    dias_seguridad = rng.uniform(2.0, 8.0, forma)
    dias_cobertura = rng.uniform(10, 35, forma)
    # La demanda llega en pedidos (a veces de mayoristas), no pieza por pieza: el
    # encargado deja un colchón de unos cuantos pedidos típicos además del promedio.
    pedido_tipico = productos["_cantidad_media"].to_numpy()[None, :].repeat(n_suc, 0)
    colchon_pedidos = rng.uniform(1.0, 4.0, forma)

    # Estimación inicial: demanda media de los primeros 60 días de vida del par (como si
    # la empresa tuviera historia previa), con el error del par.
    estimado = np.zeros(forma)
    inicio_par = np.maximum(dia_apertura, dia_alta)
    for i in range(n_suc):
        for j in range(n_prod):
            a = inicio_par[i, j]
            if a < n_dias:
                estimado[i, j] = demanda[i, j, a:a + 60].mean()
    estimado = np.maximum(estimado * error, 0.02)

    def parametros(est):
        s = np.ceil(est * (lead + dias_seguridad) + 1.65 * np.sqrt(est * lead) + colchon_pedidos * pedido_tipico)
        S = np.maximum(s + 2, np.ceil(s + est * dias_cobertura))
        return s, S

    s, S = parametros(estimado)
    existencia = np.zeros(forma)
    pendiente = np.zeros(forma)
    llegada = np.full(forma, -1)
    orden_id = np.zeros(forma, dtype=np.int64)
    retraso_orden = np.zeros(forma, dtype=np.int64)
    dia_orden = np.zeros(forma, dtype=np.int64)

    vendido = np.zeros_like(demanda)
    perdido = np.zeros_like(demanda)
    movs: list[pd.DataFrame] = []
    entregas: list[pd.DataFrame] = []
    siguiente_oc = 1
    trimestre_fin = set(np.flatnonzero(dias.is_quarter_end))

    def registrar(d, mask, tipo, cantidad, existencia_tras, referencia=None):
        ii, jj = np.nonzero(mask)
        if len(ii) == 0:
            return
        movs.append(pd.DataFrame({
            "dia": d, "i": ii, "j": jj, "tipo": tipo,
            "cantidad": cantidad[ii, jj].astype(np.int64),
            "existencia_resultante": existencia_tras[ii, jj].astype(np.int64),
            "referencia": None if referencia is None else referencia[ii, jj],
        }))

    for d in range(n_dias):
        vivo = (d >= dia_apertura) & (d >= dia_alta)
        # Arranque de pares nuevos (sucursal recién abierta o producto recién lanzado).
        arranca = (d == inicio_par)
        if arranca.any():
            existencia[arranca] = S[arranca]
            registrar(d, arranca, "INVENTARIO_INICIAL", existencia, existencia)

        llega = llegada == d
        if llega.any():
            existencia[llega] += pendiente[llega]
            registrar(d, llega, "ENTRADA_COMPRA", pendiente, existencia, np.char.mod("OC-%07d", orden_id))
            ii, jj = np.nonzero(llega)
            entregas.append(pd.DataFrame({
                "id_orden": orden_id[ii, jj], "i": ii, "j": jj, "dia_orden": dia_orden[ii, jj],
                "dia_llegada": d, "cantidad": pendiente[ii, jj].astype(np.int64),
                "dias_retraso": retraso_orden[ii, jj]}))
            pendiente[llega] = 0
            llegada[llega] = -1

        dem = demanda[:, :, d]
        v = np.minimum(dem, existencia)
        vendido[:, :, d] = v
        perdido[:, :, d] = dem - v
        existencia -= v
        registrar(d, v > 0, "SALIDA_VENTA", -v, existencia)

        merma = perecedero & vivo & (existencia > 0) & (rng.random(forma) < cfg.prob_merma_dia_perecedero)
        if merma.any():
            q = np.minimum(existencia, 1 + rng.poisson(2.0, forma))
            q = np.where(merma, q, 0)
            existencia -= q
            registrar(d, merma, "MERMA", -q, existencia)

        if d in trimestre_fin:
            # Conteo físico trimestral: diferencias pequeñas entre sistema y anaquel.
            ajusta = vivo & (rng.random(forma) < 0.12)
            delta = np.where(ajusta, np.round(rng.normal(0, 2.5, forma)), 0)
            delta = np.maximum(delta, -existencia)
            ajusta &= delta != 0
            existencia += delta
            registrar(d, ajusta, "AJUSTE_CONTEO", delta, existencia)

        if d > 0 and d % cfg.dias_recalibracion == 0:
            ventana = vendido[:, :, max(0, d - cfg.dias_recalibracion):d].mean(axis=2)
            ruido = rng.uniform(0.9, 1.1, forma)
            nuevo = np.maximum(ventana * error * ruido, 0.02)
            # Se recalibra con ventas (no con demanda, que nadie observa); el encargado no
            # baja la estimación más de 20 % por trimestre aunque haya habido faltantes.
            estimado = np.where(vivo, np.maximum(nuevo, 0.8 * estimado), estimado)
            s, S = parametros(estimado)

        pide = vivo & (pendiente == 0) & (existencia <= s) & (d < dia_fin_resurtido)
        if pide.any():
            ii, jj = np.nonzero(pide)
            q = S[ii, jj] - existencia[ii, jj]
            retraso = np.where(rng.random(len(ii)) < p_retraso[ii, jj], rng.integers(2, 9, len(ii)), 0)
            pendiente[ii, jj] = q
            llegada[ii, jj] = d + lead[ii, jj] + retraso
            orden_id[ii, jj] = np.arange(siguiente_oc, siguiente_oc + len(ii))
            retraso_orden[ii, jj] = retraso
            dia_orden[ii, jj] = d
            siguiente_oc += len(ii)

    m = pd.concat(movs, ignore_index=True)
    m["fecha"] = dias[m["dia"].to_numpy()]
    m["id_sucursal"] = sucursales["id_sucursal"].to_numpy()[m["i"]]
    m["id_producto"] = productos["id_producto"].to_numpy()[m["j"]]
    orden_tipo = {"INVENTARIO_INICIAL": 0, "ENTRADA_COMPRA": 1, "SALIDA_VENTA": 2, "MERMA": 3, "AJUSTE_CONTEO": 4}
    m["_orden"] = m["tipo"].map(orden_tipo)
    m = m.sort_values(["dia", "id_sucursal", "id_producto", "_orden"]).reset_index(drop=True)
    m.insert(0, "id_movimiento", np.arange(1, len(m) + 1))
    m = m[["id_movimiento", "fecha", "id_sucursal", "id_producto", "tipo", "cantidad",
           "existencia_resultante", "referencia"]]

    e = pd.concat(entregas, ignore_index=True)
    e["id_sucursal"] = sucursales["id_sucursal"].to_numpy()[e["i"]]
    e["id_producto"] = productos["id_producto"].to_numpy()[e["j"]]
    e["fecha_orden"] = dias[e["dia_orden"].to_numpy()]
    e["fecha_llegada"] = dias[e["dia_llegada"].to_numpy()]
    e = e.drop(columns=["i", "j", "dia_orden", "dia_llegada"])

    ii, jj = np.meshgrid(np.arange(n_suc), np.arange(n_prod), indexing="ij")
    existentes = (dia_apertura < n_dias) & (dia_alta < n_dias)
    existentes = np.broadcast_to(existentes, forma)
    final = pd.DataFrame({
        "id_sucursal": sucursales["id_sucursal"].to_numpy()[ii[existentes]],
        "id_producto": productos["id_producto"].to_numpy()[jj[existentes]],
        "existencia": existencia[existentes].astype(np.int64),
        "stock_minimo": s[existentes].astype(np.int64),
        "stock_maximo": S[existentes].astype(np.int64),
        "fecha_actualizacion": dias[-1],
    })
    return ResultadoInventario(vendido, perdido, m, final, e)
