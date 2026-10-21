"""Vocabulario para nombrar productos y proveedores. Las marcas son ficticias."""

ARTICULOS = {
    "Abarrotes": ["Arroz", "Frijol negro", "Frijol pinto", "Aceite vegetal", "Azúcar", "Harina de trigo",
                  "Pasta para sopa", "Atún en agua", "Café soluble", "Avena", "Lenteja", "Sal de mesa",
                  "Mayonesa", "Chiles en vinagre", "Puré de tomate"],
    "Bebidas": ["Agua natural", "Refresco de cola", "Refresco de limón", "Jugo de naranja", "Té helado",
                "Bebida isotónica", "Agua mineral", "Néctar de mango", "Bebida energética", "Leche entera"],
    "Limpieza": ["Detergente en polvo", "Suavizante de telas", "Cloro", "Limpiador multiusos", "Lavatrastes",
                 "Desengrasante", "Fibra para trastes", "Bolsas para basura", "Aromatizante", "Jabón de barra"],
    "Cuidado personal": ["Shampoo", "Acondicionador", "Pasta dental", "Desodorante", "Jabón líquido",
                         "Crema corporal", "Rastrillo", "Papel higiénico", "Toallas húmedas", "Protector solar"],
    "Electrónica": ["Audífonos inalámbricos", "Bocina Bluetooth", "Cargador USB-C", "Power bank",
                    "Smartwatch", "Teclado inalámbrico", "Mouse óptico", "Memoria USB", "Cable HDMI",
                    "Foco inteligente"],
    "Papelería": ["Cuaderno profesional", "Bolígrafo", "Lápiz", "Colores", "Marcatextos", "Carpeta",
                  "Pegamento en barra", "Tijeras escolares", "Hojas blancas", "Mochila escolar"],
    "Juguetes": ["Carrito a escala", "Muñeca", "Rompecabezas", "Juego de mesa", "Bloques de construcción",
                 "Pelota", "Peluche", "Pista de carreras", "Kit de ciencia", "Dron de juguete"],
    "Hogar": ["Juego de sartenes", "Licuadora", "Cafetera", "Juego de toallas", "Almohada", "Lámpara de mesa",
              "Set de vasos", "Organizador", "Plancha", "Ventilador"],
    "Mascotas": ["Croquetas para perro", "Croquetas para gato", "Arena para gato", "Premios para perro",
                 "Collar", "Juguete para mascota", "Shampoo para mascota", "Cama para mascota"],
    "Dulcería y botanas": ["Papas fritas", "Cacahuates", "Chocolate", "Gomitas", "Paleta", "Galletas",
                           "Palomitas", "Chicharrones", "Dulce de tamarindo", "Mazapán"],
}

MARCAS = ["Nexa", "Altavista", "Del Bajío", "Sol de Oro", "Montaña Azul", "Casa Real", "Prisma",
          "Vértice", "Quetzal", "Aurora", "Tierra Viva", "Brisa", "Monarca", "Lumen", "Kosmo"]

PRESENTACIONES = {
    "Abarrotes": ["500 g", "1 kg", "900 ml", "250 g", "2 kg"],
    "Bebidas": ["600 ml", "1 L", "2 L", "355 ml", "1.5 L"],
    "Limpieza": ["1 L", "2 L", "500 ml", "5 kg", "750 ml"],
    "Cuidado personal": ["400 ml", "120 g", "4 pzas", "200 ml", "750 ml"],
    "Mascotas": ["2 kg", "4 kg", "10 kg", "1 pza", "500 g"],
    "Dulcería y botanas": ["45 g", "170 g", "1 pza", "300 g", "Paquete familiar"],
}

GIROS_PROVEEDOR = ["Distribuidora", "Comercializadora", "Grupo", "Industrias", "Importadora", "Abastecedora"]
SUFIJOS_PROVEEDOR = ["S.A. de C.V.", "S. de R.L. de C.V.", "S.A.P.I. de C.V."]

# Variantes de captura de nombres de estado (defecto "cliente_estado_variante").
VARIANTES_ESTADO = {
    "Querétaro": ["Qro", "QRO.", "Queretaro", "QUERETARO", "Qro."],
    "Ciudad de México": ["CDMX", "D.F.", "Cd. de México", "Mexico City", "CIUDAD DE MEXICO"],
    "Jalisco": ["Jal", "JAL.", "jalisco"],
    "Nuevo León": ["NL", "N.L.", "Nuevo Leon"],
    "Guanajuato": ["Gto", "GTO.", "guanajuato"],
    "San Luis Potosí": ["SLP", "S.L.P.", "San Luis Potosi"],
    "Puebla": ["Pue", "PUE.", "puebla"],
    "Aguascalientes": ["Ags", "AGS.", "aguascalientes"],
    "Michoacán": ["Mich", "MICH.", "Michoacan"],
}
