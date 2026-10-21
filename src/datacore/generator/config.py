"""Parámetros del escenario simulado de NexaTech Solutions.

Todo lo que define el "mundo" simulado vive aquí para que el dataset sea
reproducible: misma semilla + misma configuración = mismos datos.
"""

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Sucursal:
    codigo: str
    nombre: str
    ciudad: str
    estado: str
    region: str
    tamano: str  # grande | mediana | pequena
    fecha_apertura: date


SUCURSALES: tuple[Sucursal, ...] = (
    Sucursal("QRO01", "Querétaro Centro", "Querétaro", "Querétaro", "Bajío", "grande", date(2015, 3, 1)),
    Sucursal("QRO02", "Querétaro Juriquilla", "Querétaro", "Querétaro", "Bajío", "mediana", date(2018, 8, 15)),
    Sucursal("QRO03", "El Marqués", "El Marqués", "Querétaro", "Bajío", "pequena", date(2024, 4, 1)),
    Sucursal("CDMX01", "CDMX Coyoacán", "Ciudad de México", "Ciudad de México", "Centro", "grande", date(2012, 6, 1)),
    Sucursal("CDMX02", "CDMX Azcapotzalco", "Ciudad de México", "Ciudad de México", "Centro", "mediana", date(2016, 2, 1)),
    Sucursal("GDL01", "Guadalajara Zapopan", "Zapopan", "Jalisco", "Occidente", "grande", date(2014, 9, 1)),
    Sucursal("MTY01", "Monterrey San Nicolás", "San Nicolás de los Garza", "Nuevo León", "Norte", "grande", date(2017, 5, 1)),
    Sucursal("LEO01", "León Centro", "León", "Guanajuato", "Bajío", "mediana", date(2019, 1, 15)),
    Sucursal("SLP01", "San Luis Potosí", "San Luis Potosí", "San Luis Potosí", "Bajío", "pequena", date(2020, 10, 1)),
    Sucursal("PUE01", "Puebla Angelópolis", "Puebla", "Puebla", "Centro", "mediana", date(2018, 3, 1)),
    Sucursal("AGS01", "Aguascalientes", "Aguascalientes", "Aguascalientes", "Bajío", "pequena", date(2021, 7, 1)),
    Sucursal("MOR01", "Morelia", "Morelia", "Michoacán", "Occidente", "pequena", date(2024, 9, 1)),
)

# Tickets promedio por día según tamaño de sucursal (antes de factores).
TICKETS_DIA_POR_TAMANO = {"grande": 19.0, "mediana": 13.0, "pequena": 8.5}

# Perfil estacional mensual (ene..dic) por tipo; 1.0 = mes promedio.
PERFILES_ESTACIONALES = {
    "plano":       (1.00, 0.97, 1.00, 1.00, 1.02, 0.98, 1.00, 1.00, 0.98, 1.00, 1.02, 1.05),
    "verano":      (0.80, 0.82, 0.95, 1.10, 1.25, 1.30, 1.20, 1.10, 0.95, 0.88, 0.80, 0.85),
    "fin_de_ano":  (0.75, 0.70, 0.80, 0.85, 0.95, 0.85, 0.85, 0.90, 0.90, 1.00, 1.55, 1.90),
    "escolar":     (1.25, 0.90, 0.85, 0.80, 0.80, 0.80, 1.20, 1.85, 1.10, 0.85, 0.80, 0.80),
    "juguetes":    (1.30, 0.60, 0.65, 1.20, 0.80, 0.70, 0.75, 0.80, 0.80, 0.90, 1.40, 2.20),
    "hogar":       (0.85, 0.85, 0.95, 1.00, 1.35, 0.95, 0.90, 0.90, 0.90, 0.95, 1.20, 1.30),
    "dulceria":    (0.85, 1.05, 0.90, 0.95, 0.95, 0.90, 0.90, 0.90, 0.95, 1.45, 1.20, 1.40),
}


@dataclass(frozen=True)
class Categoria:
    nombre: str
    perfil: str
    precio_min: float
    precio_max: float
    cantidad_media: float  # unidades promedio por renglón (cliente minorista)
    perecedero: bool


CATEGORIAS: tuple[Categoria, ...] = (
    Categoria("Abarrotes", "plano", 15, 120, 3.0, True),
    Categoria("Bebidas", "verano", 12, 90, 4.0, True),
    Categoria("Limpieza", "plano", 20, 180, 2.0, False),
    Categoria("Cuidado personal", "plano", 25, 250, 1.8, False),
    Categoria("Electrónica", "fin_de_ano", 150, 4500, 1.0, False),
    Categoria("Papelería", "escolar", 8, 220, 3.5, False),
    Categoria("Juguetes", "juguetes", 80, 1500, 1.2, False),
    Categoria("Hogar", "hogar", 60, 1800, 1.2, False),
    Categoria("Mascotas", "plano", 30, 650, 1.5, False),
    Categoria("Dulcería y botanas", "dulceria", 8, 85, 4.0, True),
)


@dataclass(frozen=True)
class GeneratorConfig:
    seed: int = 42
    fecha_inicio: date = date(2023, 1, 1)
    fecha_fin: date = date(2025, 12, 31)
    n_productos: int = 400
    n_proveedores: int = 35
    n_clientes: int = 8000
    pct_clientes_mayoristas: float = 0.10
    pct_tickets_publico_general: float = 0.30
    pct_tickets_cancelados: float = 0.01
    renglones_extra_media: float = 2.4  # renglones por ticket = 1 + Poisson(media)
    crecimiento_anual_medio: float = 0.06
    inflacion_anual: float = 0.05
    pct_productos_nuevos: float = 0.08  # salen al mercado a mitad del periodo
    pct_productos_descontinuados: float = 0.05
    # Inventario: el error de estimación de demanda provoca faltantes y excesos.
    error_estimacion_min: float = 0.55
    error_estimacion_max: float = 1.45
    dias_recalibracion: int = 90
    prob_merma_dia_perecedero: float = 0.004
    fallas_sistema_por_mes_sucursal: float = 0.8
    # Defectos inyectados en las exportaciones crudas (fracción de registros).
    defectos: dict = field(default_factory=lambda: {
        "venta_duplicada": 0.004,
        "venta_fecha_formato_alterno": 0.02,
        "venta_fecha_futura": 0.0005,
        "venta_metodo_pago_faltante": 0.01,
        "venta_total_inconsistente": 0.003,
        "detalle_cantidad_negativa": 0.001,
        "detalle_precio_escala": 0.001,
        "detalle_producto_inexistente": 0.0005,
        "detalle_duplicado": 0.002,
        "cliente_casi_duplicado": 0.02,
        "cliente_email_faltante": 0.08,
        "cliente_telefono_faltante": 0.06,
        "cliente_email_invalido": 0.01,
        "cliente_estado_variante": 0.15,
        "producto_categoria_faltante": 0.01,
        "producto_costo_mayor_precio": 0.01,
        "movimiento_cantidad_cero": 0.001,
        "sucursal_codigo_sucio": 0.02,
    })
