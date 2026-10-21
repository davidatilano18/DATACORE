"""Cliente HTTP sin acceso directo a la base de datos."""

import os

import httpx


class ErrorAPI(Exception):
    """La API no pudo completar la solicitud."""


class ClienteAPI:
    def __init__(self, transporte=None):
        self.url = os.getenv("DATACORE_API_URL", "http://127.0.0.1:8000").rstrip("/")
        clave = os.getenv("DATACORE_API_KEY")
        self.encabezados = {"X-API-Key": clave} if clave else {}
        self.transporte = transporte

    def solicitar(self, metodo, ruta, **parametros):
        try:
            with httpx.Client(base_url=self.url, headers=self.encabezados,
                              transport=self.transporte, timeout=30) as cliente:
                respuesta = cliente.request(metodo, ruta, params={
                    k: v for k, v in parametros.items() if v is not None})
                respuesta.raise_for_status()
                return respuesta.json()
        except httpx.RequestError as exc:
            raise ErrorAPI("No se pudo conectar con la API de DATACORE. "
                           "Verifica que esté en ejecución y revisa DATACORE_API_URL.") from exc
        except httpx.HTTPStatusError as exc:
            raise ErrorAPI(f"La API rechazó la solicitud a {ruta} "
                           f"(HTTP {exc.response.status_code}). Revisa el servicio y la clave de acceso.") from exc
        except ValueError as exc:
            raise ErrorAPI("La API devolvió una respuesta que no es JSON válido.") from exc

    def obtener(self, ruta, **parametros):
        return self.solicitar("GET", ruta, **parametros)

    def atender(self, id_alerta):
        return self.solicitar("POST", f"/alertas/{id_alerta}/atender")
