"""Autenticación OAuth2 (client credentials) contra el CDSE (§6).

El Copernicus Data Space Ecosystem NO usa user/password básico como el viejo
Open Access Hub: emite tokens Bearer vía OAuth2 client-credentials. Las
credenciales se leen de las variables de entorno SRP_CDSE_CLIENT_ID y
SRP_CDSE_CLIENT_SECRET (nunca hardcodeadas).

El token se cachea en memoria hasta poco antes de su expiración para no
golpear el endpoint de identidad en cada búsqueda de escenas.
"""

from __future__ import annotations

import os
import time

import httpx

TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu"
    "/auth/realms/CDSE/protocol/openid-connect/token"
)

# Margen de seguridad: renovar el token este número de segundos antes de
# que expire, para no usar un token que muere en vuelo.
_MARGEN_EXPIRACION_S = 30.0


class CredencialesCdseFaltantesError(RuntimeError):
    """SRP_CDSE_CLIENT_ID / SRP_CDSE_CLIENT_SECRET no están configuradas."""


class CdseAuth:
    """Cliente OAuth2 client-credentials con caché de token en memoria."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        http: httpx.AsyncClient | None = None,
        timeout_s: float = 30.0,
    ) -> None:
        self._client_id = client_id or os.environ.get("SRP_CDSE_CLIENT_ID", "")
        self._client_secret = client_secret or os.environ.get(
            "SRP_CDSE_CLIENT_SECRET", ""
        )
        self._http = http
        self._timeout_s = timeout_s
        self._token: str | None = None
        # Instante monotónico en el que el token cacheado deja de ser válido.
        self._expira_en: float = 0.0

    async def obtener_token(self) -> str:
        """Devuelve un token Bearer válido, renovándolo solo si expiró."""
        if self._token is not None and time.monotonic() < self._expira_en:
            return self._token

        if not self._client_id or not self._client_secret:
            raise CredencialesCdseFaltantesError(
                "Faltan SRP_CDSE_CLIENT_ID / SRP_CDSE_CLIENT_SECRET en el entorno"
            )

        datos = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        if self._http is not None:
            respuesta = await self._http.post(TOKEN_URL, data=datos)
        else:
            async with httpx.AsyncClient(timeout=self._timeout_s) as cliente:
                respuesta = await cliente.post(TOKEN_URL, data=datos)
        respuesta.raise_for_status()
        cuerpo = respuesta.json()

        self._token = str(cuerpo["access_token"])
        expires_in = float(cuerpo.get("expires_in", 600))
        self._expira_en = time.monotonic() + max(
            expires_in - _MARGEN_EXPIRACION_S, 0.0
        )
        return self._token

    def invalidar(self) -> None:
        """Descarta el token cacheado (p. ej. tras un 401 del catálogo)."""
        self._token = None
        self._expira_en = 0.0
