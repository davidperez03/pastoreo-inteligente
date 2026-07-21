"""Contract tests del flujo OAuth2 client-credentials contra el CDSE (§6, §14).

Todo mockeado con respx: sin credenciales reales ni red.
"""

from __future__ import annotations

import urllib.parse

import httpx
import pytest
import respx

from srp.agronomia.infra_ndvi.cdse_auth import (
    TOKEN_URL,
    CdseAuth,
    CredencialesCdseFaltantesError,
)

RESPUESTA_TOKEN = {
    "access_token": "tok-cdse-abc123",
    "expires_in": 600,
    "refresh_expires_in": 3600,
    "token_type": "Bearer",
    "not-before-policy": 0,
    "scope": "user-context",
}


@respx.mock
async def test_pide_token_con_client_credentials_y_lo_parsea():
    ruta = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json=RESPUESTA_TOKEN)
    )
    auth = CdseAuth(client_id="mi-cliente", client_secret="mi-secreto")

    token = await auth.obtener_token()

    assert token == "tok-cdse-abc123"
    cuerpo = urllib.parse.parse_qs(ruta.calls.last.request.content.decode())
    assert cuerpo["grant_type"] == ["client_credentials"]
    assert cuerpo["client_id"] == ["mi-cliente"]
    assert cuerpo["client_secret"] == ["mi-secreto"]


@respx.mock
async def test_cachea_el_token_hasta_expiracion():
    ruta = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json=RESPUESTA_TOKEN)
    )
    auth = CdseAuth(client_id="c", client_secret="s")

    primero = await auth.obtener_token()
    segundo = await auth.obtener_token()

    assert primero == segundo == "tok-cdse-abc123"
    assert ruta.call_count == 1  # la segunda llamada salió del caché


@respx.mock
async def test_renueva_cuando_el_token_expira():
    ruta = respx.post(TOKEN_URL).mock(
        side_effect=[
            # expires_in menor que el margen de seguridad => expira de inmediato
            httpx.Response(
                200, json={"access_token": "tok-viejo", "expires_in": 5}
            ),
            httpx.Response(
                200, json={"access_token": "tok-nuevo", "expires_in": 600}
            ),
        ]
    )
    auth = CdseAuth(client_id="c", client_secret="s")

    assert await auth.obtener_token() == "tok-viejo"
    assert await auth.obtener_token() == "tok-nuevo"
    assert ruta.call_count == 2


@respx.mock
async def test_invalidar_fuerza_renovacion():
    ruta = respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json=RESPUESTA_TOKEN)
    )
    auth = CdseAuth(client_id="c", client_secret="s")

    await auth.obtener_token()
    auth.invalidar()
    await auth.obtener_token()

    assert ruta.call_count == 2


async def test_credenciales_faltantes_error_claro(monkeypatch):
    monkeypatch.delenv("SRP_CDSE_CLIENT_ID", raising=False)
    monkeypatch.delenv("SRP_CDSE_CLIENT_SECRET", raising=False)
    auth = CdseAuth()
    with pytest.raises(CredencialesCdseFaltantesError):
        await auth.obtener_token()


@respx.mock
async def test_error_http_del_identity_no_cachea_nada():
    ruta = respx.post(TOKEN_URL).mock(
        side_effect=[
            httpx.Response(401, json={"error": "invalid_client"}),
            httpx.Response(200, json=RESPUESTA_TOKEN),
        ]
    )
    auth = CdseAuth(client_id="c", client_secret="s")

    with pytest.raises(httpx.HTTPStatusError):
        await auth.obtener_token()
    assert await auth.obtener_token() == "tok-cdse-abc123"
    assert ruta.call_count == 2
