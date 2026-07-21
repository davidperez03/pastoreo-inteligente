"""Tests del descargador de bandas S3 (CDSE eodata) con S3 y OData fakes."""

from __future__ import annotations

import httpx
import pytest
import respx

from srp.agronomia.infra_ndvi.descarga_s3 import (
    BUCKET,
    DescargaBandasError,
    DescargadorBandasS3,
    crear_desde_env,
)

PRODUCTO_ID = "11111111-aaaa-bbbb-cccc-000000000001"
S3_PATH = "/eodata/Sentinel-2/MSI/L2A/2026/07/15/S2B_MSIL2A_20260715.SAFE"
PREFIJO = "Sentinel-2/MSI/L2A/2026/07/15/S2B_MSIL2A_20260715.SAFE"
GRANULO = f"{PREFIJO}/GRANULE/L2A_T18NAJ/IMG_DATA"

CLAVES = [
    f"{GRANULO}/R10m/T18NAJ_20260715_B02_10m.jp2",
    f"{GRANULO}/R10m/T18NAJ_20260715_B04_10m.jp2",
    f"{GRANULO}/R10m/T18NAJ_20260715_B08_10m.jp2",
    f"{GRANULO}/R20m/T18NAJ_20260715_B04_20m.jp2",  # trampa: 20m, no debe elegirse
    f"{PREFIJO}/MTD_MSIL2A.xml",
]


class _PaginadorFake:
    def __init__(self, claves: list[str]) -> None:
        self._claves = claves

    def paginate(self, Bucket: str, Prefix: str):  # noqa: N803 (interfaz boto3)
        assert Bucket == BUCKET
        contenidos = [{"Key": k} for k in self._claves if k.startswith(Prefix)]
        # Dos páginas para ejercitar la paginación.
        mitad = len(contenidos) // 2
        yield {"Contents": contenidos[:mitad]}
        yield {"Contents": contenidos[mitad:]}


class _S3Fake:
    """Stub con la interfaz de cliente boto3 que usa el descargador."""

    def __init__(self, claves: list[str], fallar_descarga: bool = False) -> None:
        self._claves = claves
        self._fallar = fallar_descarga
        self.descargas: list[str] = []

    def get_paginator(self, nombre: str) -> _PaginadorFake:
        assert nombre == "list_objects_v2"
        return _PaginadorFake(self._claves)

    def download_file(self, bucket: str, clave: str, destino: str) -> None:
        if self._fallar:
            raise RuntimeError("acceso denegado")
        self.descargas.append(clave)
        with open(destino, "wb") as f:
            f.write(b"jp2-fake:" + clave.encode())


def _mock_odata(s3_path: str | None = S3_PATH) -> None:
    cuerpo = {"Id": PRODUCTO_ID}
    if s3_path is not None:
        cuerpo["S3Path"] = s3_path
    respx.get(url__regex=r".*/odata/v1/Products\(.*\)").mock(
        return_value=httpx.Response(200, json=cuerpo)
    )


@respx.mock
async def test_descarga_bandas_b04_y_b08_de_10m(tmp_path):
    _mock_odata()
    s3 = _S3Fake(CLAVES)
    descargador = DescargadorBandasS3(s3, cache_dir=tmp_path)

    ruta_red, ruta_nir = await descargador(PRODUCTO_ID)

    assert ruta_red.endswith("_B04_10m.jp2") and ruta_nir.endswith("_B08_10m.jp2")
    # Eligió exactamente las claves R10m correctas (no la trampa de 20 m).
    assert s3.descargas == [
        f"{GRANULO}/R10m/T18NAJ_20260715_B04_10m.jp2",
        f"{GRANULO}/R10m/T18NAJ_20260715_B08_10m.jp2",
    ]
    with open(ruta_red, "rb") as f:
        assert f.read().startswith(b"jp2-fake:")


@respx.mock
async def test_cache_evita_redescarga(tmp_path):
    _mock_odata()
    s3 = _S3Fake(CLAVES)
    descargador = DescargadorBandasS3(s3, cache_dir=tmp_path)

    await descargador(PRODUCTO_ID)
    await descargador(PRODUCTO_ID)

    assert len(s3.descargas) == 2  # solo la primera llamada descargó


@respx.mock
async def test_sin_s3path_error_claro(tmp_path):
    _mock_odata(s3_path=None)
    descargador = DescargadorBandasS3(_S3Fake(CLAVES), cache_dir=tmp_path)
    with pytest.raises(DescargaBandasError, match="sin S3Path"):
        await descargador(PRODUCTO_ID)


@respx.mock
async def test_sin_bandas_10m_error_claro(tmp_path):
    _mock_odata()
    solo_metadata = [f"{PREFIJO}/MTD_MSIL2A.xml"]
    descargador = DescargadorBandasS3(_S3Fake(solo_metadata), cache_dir=tmp_path)
    with pytest.raises(DescargaBandasError, match="B04/B08"):
        await descargador(PRODUCTO_ID)


@respx.mock
async def test_descarga_fallida_no_deja_archivo_truncado(tmp_path):
    _mock_odata()
    descargador = DescargadorBandasS3(
        _S3Fake(CLAVES, fallar_descarga=True), cache_dir=tmp_path
    )
    with pytest.raises(DescargaBandasError, match="Fallo descargando"):
        await descargador(PRODUCTO_ID)
    # Ni banda final ni .part huérfano en el caché.
    assert list(tmp_path.iterdir()) == []


def test_crear_desde_env_sin_llaves(monkeypatch):
    monkeypatch.delenv("SRP_CDSE_S3_ACCESS_KEY", raising=False)
    monkeypatch.delenv("SRP_CDSE_S3_SECRET_KEY", raising=False)
    assert crear_desde_env() is None


def test_crear_desde_env_con_llaves(monkeypatch, tmp_path):
    monkeypatch.setenv("SRP_CDSE_S3_ACCESS_KEY", "AK")
    monkeypatch.setenv("SRP_CDSE_S3_SECRET_KEY", "SK")
    descargador = crear_desde_env(cache_dir=tmp_path)
    assert isinstance(descargador, DescargadorBandasS3)
