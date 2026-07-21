# Credenciales CDSE (Copernicus Data Space Ecosystem)

El pipeline NDVI (§6 de la especificación) necesita **dos pares de credenciales
distintos**, generados en portales diferentes del CDSE. Los valores viven en
`backend/.env` (ignorado por git — **nunca** committearlo); este documento
explica cómo regenerarlos si se pierden o expiran.

Cuenta CDSE: se crea gratis en <https://dataspace.copernicus.eu> (botón
Register). Ambos generadores usan ese mismo login.

## 1. Cliente OAuth — catálogo / APIs

Variables: `SRP_CDSE_CLIENT_ID`, `SRP_CDSE_CLIENT_SECRET`

1. Entrar al dashboard de Sentinel Hub del CDSE:
   <https://shapps.dataspace.copernicus.eu/dashboard/>
2. **User settings** → sección **OAuth clients** → **"+ Create"**.
3. Nombre sugerido: `srp-worker`. Copiar client id y secret de inmediato:
   **el secret se muestra una sola vez**.

- El client id tiene forma `sh-xxxxxxxx-xxxx-...`.
- Token endpoint que usa el código (`cdse_auth.py`):
  `https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token`
  (grant `client_credentials`).
- Documentación: <https://documentation.dataspace.copernicus.eu/APIs/openEO/authentication/client_credentials.html>
  y guía general <https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/UserGuides/BeginnersGuide.html>

## 2. Llaves S3 de eodata — descarga de bandas Sentinel-2

Variables: `SRP_CDSE_S3_ACCESS_KEY`, `SRP_CDSE_S3_SECRET_KEY`

1. Entrar al generador de llaves S3:
   <https://eodata-s3keysmanager.dataspace.copernicus.eu/>
2. **"Add credentials"** → elegir fecha de expiración → **Confirm**.
3. Copiar access key y secret key de inmediato: **la secret key se muestra una
   sola vez**; si se cierra el diálogo sin copiarla hay que generar otro par.

- Endpoint S3 que usa el código (`descarga_s3.py`):
  `https://eodata.dataspace.copernicus.eu`, bucket `eodata`.
- Documentación: <https://documentation.dataspace.copernicus.eu/APIs/S3.html>

> **Expiración**: las llaves S3 expiran en la fecha elegida al crearlas (el par
> actual expira **2027-01-01**). Si el job semanal de NDVI empieza a fallar con
> 403, lo primero a revisar es esa expiración — se regeneran en el mismo
> portal y se actualiza `backend/.env`.

## Dónde van los valores

Archivo `backend/.env` (plantilla):

```bash
SRP_CDSE_CLIENT_ID=sh-...
SRP_CDSE_CLIENT_SECRET=...
SRP_CDSE_S3_ACCESS_KEY=...
SRP_CDSE_S3_SECRET_KEY=...
```

`make worker` y `make worker-una-vez` cargan `backend/.env` automáticamente si
existe. En GitHub Codespaces, la alternativa recomendada es guardarlas como
Codespaces secrets del repositorio (Settings → Secrets and variables →
Codespaces) con esos mismos nombres.

## Verificación rápida

```bash
# El worker lista los jobs programados al arrancar; con credenciales completas
# aparece `ndvi_semanal`, y si falta un par el log dice exactamente cuál:
make worker
```

## Rotación / revocación

- OAuth: en el mismo dashboard de Sentinel Hub se puede borrar el client y
  crear otro.
- S3: en el S3 keys manager se pueden revocar llaves activas y emitir nuevas.
- Tras rotar: actualizar `backend/.env` (o los Codespaces secrets) y reiniciar
  el worker.
