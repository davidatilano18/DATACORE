"""Capturas de pantalla del dashboard con Edge/Chrome headless vía DevTools.

Uso (con la API y el dashboard corriendo):
    .venv\\Scripts\\python scripts\\capturas_dashboard.py [--url http://localhost:8501] [--salida reports/dashboard]

Espera a que cada página termine de dibujarse (sin indicador de ejecución y con
contenido visible) antes de capturar. Útil para la memoria y para revisar la UI.
"""

import argparse
import asyncio
import base64
import json
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from websockets.asyncio.client import connect

PAGINAS = {"inicio": "", "ventas": "Ventas", "inventario": "Inventario", "alertas": "Alertas",
           "pronostico": "Pron%C3%B3stico", "calidad": "Calidad_y_operaci%C3%B3n"}
NAVEGADORES = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
               r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
               r"C:\Program Files\Google\Chrome\Application\chrome.exe", "google-chrome", "chromium"]

# La página está lista cuando Streamlit dejó de ejecutar y hay elementos debajo del título.
LISTA_JS = """(() => {
  const corriendo = document.querySelector('[data-testid="stStatusWidget"]');
  const bloques = document.querySelectorAll('[data-testid="stMetric"], .js-plotly-plot, [data-testid="stDataFrame"]');
  return !corriendo && bloques.length > 0;
})()"""


class CDP:
    def __init__(self, ws):
        self.ws, self.n = ws, 0

    async def llamar(self, metodo, **params):
        self.n += 1
        await self.ws.send(json.dumps({"id": self.n, "method": metodo, "params": params}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("id") == self.n:
                return msg.get("result", {})


async def capturar(url_base: str, salida: Path, ancho: int, alto: int, puerto: int) -> None:
    info = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{puerto}/json/version").read())
    async with connect(info["webSocketDebuggerUrl"], max_size=200 * 2**20) as navegador:
        destino = await CDP(navegador).llamar("Target.createTarget", url="about:blank")
    objetivos = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{puerto}/json/list").read())
    ws_pagina = next(o["webSocketDebuggerUrl"] for o in objetivos if o["id"] == destino["targetId"])
    async with connect(ws_pagina, max_size=200 * 2**20) as ws:
        await _recorrer(CDP(ws), url_base, salida, ancho, alto)


async def _recorrer(cdp: CDP, url_base: str, salida: Path, ancho: int, alto: int) -> None:
    await cdp.llamar("Emulation.setDeviceMetricsOverride", width=ancho, height=alto, deviceScaleFactor=1, mobile=False)
    salida.mkdir(parents=True, exist_ok=True)
    for nombre, ruta in PAGINAS.items():
        await cdp.llamar("Page.navigate", url=f"{url_base.rstrip('/')}/{ruta}")
        limite = time.time() + 60
        while time.time() < limite:
            await asyncio.sleep(1)
            r = await cdp.llamar("Runtime.evaluate", expression=LISTA_JS, returnByValue=True)
            if r.get("result", {}).get("value"):
                break
        await asyncio.sleep(2.5)  # animaciones de plotly
        png = await cdp.llamar("Page.captureScreenshot", format="png", captureBeyondViewport=False)
        (salida / f"{nombre}.png").write_bytes(base64.b64decode(png["data"]))
        print(f"{nombre}: {salida / (nombre + '.png')}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:8501")
    p.add_argument("--salida", type=Path, default=Path("reports/dashboard"))
    p.add_argument("--ancho", type=int, default=1440)
    p.add_argument("--alto", type=int, default=1400)
    a = p.parse_args()
    exe = next((n for n in NAVEGADORES if Path(n).exists() or shutil.which(n)), None)
    if not exe:
        raise SystemExit("No se encontró Edge ni Chrome")
    puerto = 9333
    with tempfile.TemporaryDirectory() as perfil:
        proc = subprocess.Popen([exe, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                                 f"--remote-debugging-port={puerto}", f"--user-data-dir={perfil}", "about:blank"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(40):
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{puerto}/json/version", timeout=1)
                    break
                except OSError:
                    time.sleep(0.5)
            asyncio.run(capturar(a.url, a.salida, a.ancho, a.alto, puerto))
        finally:
            proc.terminate()
            proc.wait(timeout=10)


if __name__ == "__main__":
    main()
