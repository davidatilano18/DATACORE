"""Exporta los SVG de branding/ a PNG con fondo transparente (Edge/Chrome headless).

Uso: .venv\\Scripts\\python scripts\\exportar_marca.py
Genera branding/png/: íconos de 16 a 512 px (favicon incluido) y logotipos a 2x.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
MARCA = RAIZ / "branding"
NAVEGADORES = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
               r"C:\Program Files\Microsoft\Edge\Application\msedge.exe", "google-chrome", "chromium"]

SALIDAS = [("datacore_icono.svg", f"icono_{n}.png", n, n) for n in (16, 32, 64, 128, 256, 512)] + [
    ("datacore_logotipo.svg", "logotipo.png", 1040, 240),
    ("datacore_logotipo_oscuro.svg", "logotipo_oscuro.png", 1040, 240),
]


def main() -> None:
    exe = next((n for n in NAVEGADORES if Path(n).exists() or shutil.which(n)), None)
    if not exe:
        raise SystemExit("No se encontró Edge ni Chrome")
    destino = MARCA / "png"
    destino.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for svg, png, ancho, alto in SALIDAS:
            html = Path(tmp) / "lienzo.html"
            html.write_text(
                "<!doctype html><html><head><style>html,body{margin:0;background:transparent}"
                f"img{{width:{ancho}px;height:{alto}px;display:block}}</style></head>"
                f"<body><img src='{(MARCA / svg).as_uri()}'></body></html>", encoding="utf-8")
            subprocess.run([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                            "--default-background-color=00000000", f"--user-data-dir={tmp}/perfil",
                            f"--window-size={ancho},{alto}", f"--screenshot={destino / png}", html.as_uri()],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
            print(f"{png}: {ancho}x{alto}")


if __name__ == "__main__":
    main()
