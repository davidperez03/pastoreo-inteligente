# Sistema de Rotación de Pastos (SRP)

**Especificación técnica y plan de trabajo — v3 (DDD + hexagonal desde el inicio)**

> Esta versión parte del documento original (`SRP_Especificacion_Tecnica (1).docx`) y lo ajusta en tres direcciones:
> 1. Corrige puntos técnicamente desactualizados o riesgosos (API de Copernicus, falta de índices espaciales, ausencia de manejo de fallos).
> 2. **Decisión de producto:** DDD y arquitectura hexagonal se implementan desde la fase 1, no como refactor posterior. Esto tiene un costo real de velocidad al principio (más piezas que escribir antes del primer entregable) a cambio de no tener que reescribir límites de contexto más adelante — ver la nota de trade-off en [§17](#17-diseño-estratégico-ddd-domain-driven-design).
> 3. Agrega lo que le falta a una especificación para operar como producto real: seguridad, resiliencia ante fallos externos, testing, CI/CD, captura de datos sin conectividad, notificaciones al ganadero y un registro explícito de riesgos.

## Índice

1. [Visión general y alcance](#1-visión-general-y-alcance)
2. [Modelo de datos (PostgreSQL + PostGIS)](#2-modelo-de-datos-postgresql--postgis)
3. [Levantamiento y entrada de planimetrías](#3-levantamiento-y-entrada-de-planimetrías)
4. [Modelo de crecimiento de pasto](#4-modelo-de-crecimiento-de-pasto)
5. [Fusión de datos: Filtro de Kalman](#5-fusión-de-datos-filtro-de-kalman-modelo--ndvi)
6. [NDVI satelital](#6-ndvi-satelital)
7. [Optimización de la rotación](#7-optimización-de-la-rotación)
8. [Calibración bayesiana por potrero](#8-calibración-bayesiana-por-potrero)
9. [Endpoints API](#9-endpoints-api-fastapi)
10. [Seguridad, autenticación y cumplimiento](#10-seguridad-autenticación-y-cumplimiento)
11. [Resiliencia ante fallos de servicios externos](#11-resiliencia-ante-fallos-de-servicios-externos)
12. [Notificaciones al ganadero](#12-notificaciones-al-ganadero)
13. [Captura de campo sin conectividad (offline-first)](#13-captura-de-campo-sin-conectividad-offline-first)
14. [Estrategia de testing](#14-estrategia-de-testing)
15. [CI/CD y observabilidad](#15-cicd-y-observabilidad)
16. [Diferenciadores técnicos](#16-diferenciadores-técnicos-frente-a-otros-sistemas)
17. [Diseño estratégico DDD (Domain-Driven Design)](#17-diseño-estratégico-ddd-domain-driven-design)
18. [Arquitectura hexagonal (Puertos y Adaptadores)](#18-arquitectura-hexagonal-puertos-y-adaptadores)
19. [Escalabilidad y multi-tenancy](#19-escalabilidad-y-multi-tenancy)
20. [Registro de riesgos](#20-registro-de-riesgos)
21. [Plan de trabajo por fases](#21-plan-de-trabajo-por-fases)
22. [Stack tecnológico](#22-stack-tecnológico)

---

## 1. Visión general y alcance

El SRP gestiona potreros (definidos por planimetría georreferenciada), calcula la biomasa de pasto disponible en cada uno mediante un modelo agronómico alimentado con datos climáticos y satelitales gratuitos, y sugiere/optimiza la rotación de lotes de ganado entre potreros para maximizar el aprovechamiento del pasto sin sobrepastorear.

**Usuario objetivo:** ganaderos y administradores de finca en la región de Casanare/Llanos, con conectividad rural intermitente y bajo nivel de tolerancia a fricción de uso — el sistema compite contra "lo que el ganadero ya hace a ojo", no contra otro software.

Flujo general:

1. El usuario carga o dibuja los potreros (planimetría) → el sistema calcula áreas georreferenciadas.
2. Se registran datos base por potrero: especie de pasto, tipo de suelo, capacidad.
3. Un motor climático (datos abiertos + NDVI satelital gratuito) alimenta el cálculo diario de biomasa.
4. Dashboard muestra estado por potrero: en uso / en recuperación / listo para pastoreo.
5. El sistema sugiere el próximo movimiento de cada lote, con fecha estimada, o notifica proactivamente (ver [§12](#12-notificaciones-al-ganadero)) — el ganadero no debería tener que entrar al dashboard para enterarse de que debe mover el ganado.

---

## 2. Modelo de datos (PostgreSQL + PostGIS)

Se mantiene la estructura del documento original, con tres adiciones necesarias para producción: **índices espaciales**, **constraints de integridad** y **campos de auditoría**.

```sql
CREATE EXTENSION postgis;
CREATE EXTENSION "uuid-ossp";

CREATE TABLE organizaciones (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre TEXT NOT NULL,
  plan TEXT NOT NULL DEFAULT 'basico' CHECK (plan IN ('basico', 'pro', 'enterprise')),
  creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE fincas (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organizacion_id UUID NOT NULL REFERENCES organizaciones(id),
  nombre TEXT NOT NULL,
  ubicacion GEOGRAPHY(POINT, 4326),
  estacion_clima_id UUID REFERENCES estaciones_clima(id),
  creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE especies_pasto (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre TEXT UNIQUE NOT NULL,
  temp_optima_min NUMERIC,
  temp_optima_max NUMERIC,
  tasa_max_crecimiento NUMERIC,
  dias_descanso_ideal INT,
  curva_k NUMERIC,
  gdd_optimo_diario NUMERIC
);

CREATE TABLE potreros (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  finca_id UUID NOT NULL REFERENCES fincas(id),
  nombre TEXT NOT NULL,
  geom GEOGRAPHY(POLYGON, 4326) NOT NULL,
  area_ha NUMERIC GENERATED ALWAYS AS (ST_Area(geom) / 10000) STORED,
  especie_pasto_id UUID NOT NULL REFERENCES especies_pasto(id),
  tipo_suelo TEXT,
  pendiente_pct NUMERIC,
  fuente_agua BOOLEAN NOT NULL DEFAULT false,
  factor_fatiga NUMERIC NOT NULL DEFAULT 1.0 CHECK (factor_fatiga BETWEEN 0.5 AND 1.3),
  n_ciclos_observados INT NOT NULL DEFAULT 0,
  estado TEXT NOT NULL DEFAULT 'descanso' CHECK (estado IN ('descanso', 'ocupado', 'listo')),
  fecha_ultima_salida DATE,
  biomasa_actual_kg_ms_ha NUMERIC,
  metodo_levantamiento TEXT NOT NULL,
  accuracy_m NUMERIC,
  creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
  actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (finca_id, nombre)
);

-- Índice espacial: sin esto, cualquier consulta por bbox/intersección
-- (ej. "qué potreros están en esta vista de mapa") hace seq scan.
CREATE INDEX potreros_geom_idx ON potreros USING GIST (geom);
CREATE INDEX potreros_finca_idx ON potreros (finca_id);

CREATE TABLE registros_clima (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  estacion_clima_id UUID NOT NULL,
  fecha DATE NOT NULL,
  temp_media NUMERIC,
  temp_max NUMERIC,
  temp_min NUMERIC,
  precipitacion_mm NUMERIC,
  humedad_suelo_pct NUMERIC,
  UNIQUE (estacion_clima_id, fecha)
);

CREATE TABLE lotes_ganado (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  finca_id UUID NOT NULL REFERENCES fincas(id),
  n_animales INT NOT NULL CHECK (n_animales > 0),
  peso_promedio_kg NUMERIC NOT NULL CHECK (peso_promedio_kg > 0),
  ua_equivalente NUMERIC GENERATED ALWAYS AS (n_animales * peso_promedio_kg / 450) STORED,
  potrero_actual_id UUID REFERENCES potreros(id)
);

CREATE TABLE eventos_pastoreo (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lote_id UUID NOT NULL REFERENCES lotes_ganado(id),
  potrero_id UUID NOT NULL REFERENCES potreros(id),
  fecha_entrada DATE NOT NULL,
  fecha_salida DATE,
  biomasa_inicial NUMERIC,
  biomasa_final NUMERIC,
  CHECK (fecha_salida IS NULL OR fecha_salida >= fecha_entrada)
);

CREATE TABLE lecturas_ndvi (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  potrero_id UUID NOT NULL REFERENCES potreros(id),
  fecha DATE NOT NULL,
  ndvi_promedio NUMERIC,
  cobertura_nubes_pct NUMERIC,
  fuente TEXT NOT NULL DEFAULT 'sentinel-2',
  UNIQUE (potrero_id, fecha)
);

-- Row Level Security multi-tenant desde el día 1 (ver §19), no como
-- feature tardía: es mucho más barato de aplicar sobre tablas nuevas
-- que de retrofitear cuando ya hay datos de varios clientes.
ALTER TABLE potreros ENABLE ROW LEVEL SECURITY;
CREATE POLICY potreros_por_organizacion ON potreros
  USING (finca_id IN (
    SELECT id FROM fincas WHERE organizacion_id = current_setting('app.current_org')::uuid
  ));
```

**Cambios respecto al original:**
- `especie_pasto` pasó de `TEXT` libre a FK contra `especies_pasto` — un texto libre garantiza inconsistencias (`"Brachiaria"` vs `"brachiaria decumbens"`) que rompen el join con la tabla de parámetros agronómicos.
- Se agregó `UNIQUE (finca_id, nombre)` en potreros y `UNIQUE (estacion_clima_id, fecha)` / `UNIQUE (potrero_id, fecha)` en clima/NDVI — sin esto, un reintento de job duplica filas silenciosamente.
- `CHECK` en `estado` y `factor_fatiga` en vez de confiar en que la capa de aplicación nunca escriba un valor fuera de rango.
- RLS multi-tenant movida a la fase 1 (ver [§19](#19-escalabilidad-y-multi-tenancy)) en vez de dejarla para "cuando haya varios clientes".

---

## 3. Levantamiento y entrada de planimetrías

Sin cambios de fondo respecto al original: el contrato de datos (lista de coordenadas WGS84 → polígono) es correcto y es la decisión de diseño más importante del documento. Se agrega validación de **topología entre potreros**, que el original no cubre.

### 3.1 Métodos de captura

| Método | Precisión típica | Notas |
|---|---|---|
| GPS de smartphone (track caminado) | 3-8 m | Suficiente para potreros grandes; `navigator.geolocation.watchPosition()` |
| GPS diferencial / RTK | 1-3 cm | Red MAGNA-ECO del IGAC ofrece correcciones RTK gratuitas vía NTRIP en Colombia |
| Fotogrametría con dron | 5-15 cm (con GCPs) | OpenDroneMap/WebODM (software libre) genera el ortomosaico |
| Digitalización sobre imagen satelital | Variable (10 m Sentinel-2) | Más rápido, menor precisión de campo |

### 3.2 Pipeline agnóstico a la fuente

```python
class FormatoEntrada(Enum):
    LISTA_MANUAL = "lista_manual"
    GPX = "gpx"
    KML = "kml"
    CSV = "csv"
    DXF = "dxf"

def normalizar_entrada(archivo_o_texto, formato: FormatoEntrada) -> list[tuple[float, float]]:
    """Todo converge a una lista de (lat, lng) en WGS84"""
    match formato:
        case FormatoEntrada.LISTA_MANUAL:
            return parsear_lista_manual(archivo_o_texto)
        case FormatoEntrada.GPX | FormatoEntrada.KML:
            gdf = gpd.read_file(archivo_o_texto)
            return list(gdf.geometry.iloc[0].exterior.coords)
        case FormatoEntrada.CSV:
            return parsear_csv_coordenadas(archivo_o_texto)
        case FormatoEntrada.DXF:
            fc = dxf_a_geojson(archivo_o_texto)
            fc_wgs84 = reproyectar_geojson(fc)  # MAGNA-SIRGAS -> WGS84
            return fc_wgs84['features'][0]['geometry']['coordinates'][0]
```

### 3.3 Validación y construcción del polígono

```python
def construir_poligono_validado(puntos: list[tuple[float, float]]) -> dict:
    if len(puntos) < 3:
        raise ValueError("Se necesitan minimo 3 puntos")
    if puntos[0] != puntos[-1]:
        puntos.append(puntos[0])

    poligono = Polygon([(lng, lat) for lat, lng in puntos])

    advertencia = None
    if not poligono.is_valid:
        razon = explain_validity(poligono)
        poligono = make_valid(poligono)
        advertencia = f"Poligono corregido automaticamente: {razon}"

    area_ha = calcular_area_geodesica(poligono) / 10000
    if area_ha < 0.05 or area_ha > 5000:
        # umbral de plausibilidad: atrapa el error mas comun del usuario final,
        # invertir lat/lng, que produce un poligono "valido" pero absurdo.
        advertencia = (advertencia or "") + f" Area calculada ({area_ha:.2f} ha) fuera de rango plausible"

    return {
        "geojson": poligono.__geo_interface__,
        "area_ha": area_ha,
        "n_puntos": len(puntos),
        "advertencia": advertencia,
    }

def calcular_area_geodesica(poligono):
    """Area real en m2, usando MAGNA-SIRGAS (EPSG:9377) — precisa para Colombia,
    corrige el error de proyeccion plana cerca del Ecuador"""
    proyeccion = pyproj.Transformer.from_crs(
        "EPSG:4326", "EPSG:9377", always_xy=True
    ).transform
    return transform(proyeccion, poligono).area


def validar_sin_traslape(nuevo_poligono, finca_id: str, db) -> list[str]:
    """Un potrero nuevo que se traslapa con uno existente casi siempre es
    error de digitalizacion (deriva de GPS, punto mal tecleado), no un
    caso de negocio real. Se advierte, no se bloquea (el make_valid puede
    fallar en casos legitimos de potreros contiguos que comparten cerca)."""
    traslapes = db.potreros_que_intersectan(finca_id, nuevo_poligono)
    return [p.nombre for p in traslapes]
```

### 3.4 Import desde DXF (CAD) con reproyección

```python
def dxf_a_geojson(path_dxf):
    doc = ezdxf.readfile(path_dxf)
    msp = doc.modelspace()
    features = []
    for entity in msp.query('LWPOLYLINE POLYLINE'):
        puntos = [(p[0], p[1]) for p in entity.get_points()]
        if len(puntos) >= 3:
            poligono = Polygon(puntos)
            features.append(geojson.Feature(
                geometry=geojson.loads(geojson.dumps(poligono.__geo_interface__)),
                properties={"nombre": entity.dxf.layer}
            ))
    return geojson.FeatureCollection(features)

# MAGNA-SIRGAS Origen Nacional (EPSG:9377) -> WGS84 (EPSG:4326)
transformer = Transformer.from_crs("EPSG:9377", "EPSG:4326", always_xy=True)

def reproyectar_geojson(fc):
    for feature in fc['features']:
        coords = feature['geometry']['coordinates'][0]
        coords_wgs84 = [transformer.transform(x, y) for x, y in coords]
        feature['geometry']['coordinates'] = [coords_wgs84]
    return fc
```

### 3.5 Render en el mapa (frontend)

```tsx
function PotreroMapa({ coordenadas }) {
  const posiciones = coordenadas.map(([lat, lng]) => [lat, lng]);
  return (
    <MapContainer center={posiciones[0]} zoom={17}>
      <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <Polygon positions={posiciones} pathOptions={{ color: 'green', fillOpacity: 0.3 }} />
      {posiciones.map((pos, i) => (
        <Marker key={i} position={pos} draggable
                eventHandlers={{ dragend: (e) => actualizarPunto(i, e.target.getLatLng()) }} />
      ))}
    </MapContainer>
  );
}
```

**Dato clave:** guardar `metodo_levantamiento` y `accuracy_m` junto a cada polígono permite luego distinguir, durante la calibración del modelo, si un error de predicción viene del modelo agronómico o de una planimetría imprecisa.

---

## 4. Modelo de crecimiento de pasto

Sin cambios respecto al original — es la parte del documento con mejor fundamento agronómico. Tiempo térmico (growing degree days) en vez de días calendario, y balance hídrico de suelo (bucket model) en vez de un factor de humedad plano.

### 4.1 Tiempo térmico (grados-día)

```python
def grados_dia_acumulados(temp_diaria_lista, temp_base):
    # temp_base: umbral bajo el cual el pasto no crece (ej. 10°C para C4 tropicales)
    return sum(max(0, t - temp_base) for t in temp_diaria_lista)
```

### 4.2 Balance hídrico de suelo

```python
def balance_hidrico_diario(suelo_actual_mm, precipitacion_mm, capacidad_campo_mm, et0_mm):
    entrada = precipitacion_mm
    salida = et0_mm * KC_PASTO  # coeficiente de cultivo del pasto (~0.85-1.0)
    suelo_nuevo = min(capacidad_campo_mm, suelo_actual_mm + entrada - salida)
    return max(0, suelo_nuevo)

def hargreaves_et0(temp_max, temp_min, temp_media, radiacion_extraterrestre):
    # Formula FAO, solo necesita temperaturas (gratis via Open-Meteo)
    return 0.0023 * radiacion_extraterrestre * (temp_media + 17.8) * (temp_max - temp_min) ** 0.5
```

### 4.3 Crecimiento diario acoplado

```python
def crecimiento_diario_v2(gdd_hoy, balance_hidrico_pct, especie, potrero):
    f_termico = min(1.0, gdd_hoy / especie.gdd_optimo_diario)
    f_hidrico = balance_hidrico_pct
    f_suelo = SUELO_FACTOR[potrero.tipo_suelo]
    f_fatiga = potrero.factor_fatiga
    return especie.tasa_max_crecimiento * f_termico * f_hidrico * f_suelo * f_fatiga
```

**Impacto:** el modelo anterior fallaba en la transición lluvia-sequía típica de Casanare. El balance hídrico retiene memoria del agua en el suelo día a día, prediciendo mejor los primeros días secos tras lluvia.

---

## 5. Fusión de datos: Filtro de Kalman (modelo + NDVI)

Sin cambios de fondo. Se trata la estimación de biomasa como un problema de estimación de estado: el modelo predice, el NDVI observa, y el filtro de Kalman combina ambos ponderando por su incertidumbre — el estándar de fusión modelo+sensor remoto en agricultura de precisión, no una corrección cosmética.

```python
class KalmanBiomasa:
    def __init__(self, biomasa_inicial, varianza_inicial=100):
        self.x = biomasa_inicial
        self.P = varianza_inicial
        self.Q = 5.0    # ruido del proceso (incertidumbre del modelo)
        self.R = 15.0   # ruido de observacion (incertidumbre del NDVI)

    def predecir(self, crecimiento_estimado_dia):
        self.x = self.x + crecimiento_estimado_dia
        self.P = self.P + self.Q

    def actualizar(self, biomasa_desde_ndvi, calidad_lectura=1.0):
        R_ajustado = self.R / max(calidad_lectura, 0.05)  # evita division por ~0 con nubosidad alta
        K = self.P / (self.P + R_ajustado)
        self.x = self.x + K * (biomasa_desde_ndvi - self.x)
        self.P = (1 - K) * self.P
        return self.x
```

> Nota: `Q` y `R` como constantes fijas son un buen punto de partida, pero deberían tratarse como parámetros de calibración por especie/región una vez haya suficientes ciclos reales (fase 6-7 del plan) — no como constantes universales.

---

## 6. NDVI satelital

**Esto es lo más importante que hay que corregir del documento original.** El *Copernicus Open Access Hub* (`apihub.copernicus.eu`) fue **descontinuado** — el servicio activo hoy es el **Copernicus Data Space Ecosystem (CDSE)**, con otra URL, otro flujo de autenticación (OAuth2, no user/password básico) y otra API (openEO, Sentinel Hub Process/Statistical API, o acceso directo a S3 al bucket `eodata`). El diseño del puerto (`ProveedorNdvi`, ver [§18](#18-arquitectura-hexagonal-cuándo-introducirla)) ya aísla esto correctamente — el punto es no dejar el detalle de implementación desactualizado en la especificación, porque alguien lo va a copiar literal.

```python
def calcular_ndvi_local(banda_red_path, banda_nir_path, bbox_potrero):
    with rasterio.open(banda_red_path) as red_src, rasterio.open(banda_nir_path) as nir_src:
        red = red_src.read(1, window=bbox_a_window(bbox_potrero, red_src)).astype(float)
        nir = nir_src.read(1, window=bbox_a_window(bbox_potrero, nir_src)).astype(float)
        ndvi = np.where((nir + red) == 0, 0, (nir - red) / (nir + red))
        return float(ndvi[ndvi > -1].mean())

# Copernicus Data Space Ecosystem (reemplaza al Open Access Hub, retirado en 2023)
# Autenticación: OAuth2 client credentials, no user/password.
async def buscar_escenas_cdse(bbox_geojson, fecha_desde, fecha_hasta, token: str):
    resp = await http_client.get(
        "https://catalogue.dataspace.copernicus.eu/odata/v1/Products",
        params={
            "$filter": (
                f"Collection/Name eq 'SENTINEL-2' and "
                f"OData.CSC.Intersects(area=geography'SRID=4326;{bbox_geojson}') and "
                f"ContentDate/Start gt {fecha_desde}T00:00:00.000Z and "
                f"ContentDate/Start lt {fecha_hasta}T00:00:00.000Z and "
                f"Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' and att/OData.CSC.DoubleAttribute/Value lt 30)"
            )
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp.json()["value"]
```

**Estrategia de fallback (no estaba en el original):** si no hay escena con nubosidad aceptable en la ventana de búsqueda, el sistema debe usar la última lectura NDVI disponible y marcarla como `stale` en vez de fallar el job completo o dejar el potrero sin dato — ver [§11](#11-resiliencia-ante-fallos-de-servicios-externos).

**Alternativa a evaluar en fase 4** (menor fricción de infraestructura que descargar/recortar bandas localmente): Sentinel Hub Statistical API (dentro del mismo CDSE) devuelve el NDVI promedio de un polígono directamente sin que el backend tenga que descargar y procesar rásters completos — vale la pena comparar el costo de mantenimiento contra el enfoque de descarga local antes de comprometerse.

---

## 7. Optimización de la rotación

El enfoque greedy (ordenar potreros por biomasa) es miope: no considera el efecto de mover un lote hoy sobre la disponibilidad de potreros semanas después. El documento original resuelve esto directamente con programación lineal entera — **correcto como destino, prematuro como punto de partida.**

```python
def optimizar_calendario_rotacion(potreros, lotes, horizonte_dias=60, timeout_seg=30):
    prob = LpProblem("rotacion_ganado", LpMinimize)

    x = {(l, p, d): LpVariable(f"x_{l}_{p}_{d}", cat=LpBinary)
         for l in lotes for p in potreros for d in range(horizonte_dias)}

    for l in lotes:
        for d in range(horizonte_dias):
            prob += lpSum(x[l, p, d] for p in potreros) == 1

    for p in potreros:
        for d in range(horizonte_dias):
            consumo_dia = lpSum(x[l, p, d] * lotes[l].ua_equivalente * CONSUMO_UA for l in lotes)
            prob += consumo_dia <= biomasa_proyectada(p, d)

    for p in potreros:
        agregar_restriccion_descanso_minimo(prob, x, p, lotes, horizonte_dias)

    prob += lpSum(x[l, p, d] * (1 - potreros[p].factor_fatiga)
                   for l in lotes for p in potreros for d in range(horizonte_dias))

    # Con lotes*potreros*horizonte creciendo, el numero de variables binarias
    # crece rapido. Un timeout con "mejor solucion encontrada hasta ahora"
    # (en vez de esperar la solucion optima) es obligatorio en produccion.
    prob.solve(PULP_CBC_CMD(timeLimit=timeout_seg, msg=False))
    if LpStatus[prob.status] not in ("Optimal", "Not Solved"):
        return sugerir_rotacion_greedy(potreros, lotes)  # fallback, no dejar al usuario sin respuesta

    return extraer_calendario(x, prob)
```

**Cambio de fondo respecto al original:** el LP se implementa, pero se activa en la fase 8 del plan (ver [§21](#21-plan-de-trabajo-por-fases)), después de validar con el motor greedy simple que el modelo de biomasa predice razonablemente bien. Optimizar globalmente sobre un modelo de biomasa todavía no calibrado con datos reales da una falsa sensación de precisión — el greedy expone antes los defectos del modelo agronómico, que es lo que realmente hay que validar primero.

---

## 8. Calibración bayesiana por potrero

Sin cambios de fondo. Cada potrero tiene comportamiento propio (microclima, sombra, suelo); el factor de fatiga se actualiza con cada ciclo real mediante inferencia bayesiana simple.

```python
def actualizar_factor_fatiga_bayesiano(potrero, biomasa_predicha, biomasa_medida_real):
    error_relativo = biomasa_medida_real / biomasa_predicha

    prior_media = potrero.factor_fatiga
    prior_peso = potrero.n_ciclos_observados

    nuevo_factor = (prior_media * prior_peso + error_relativo * 1) / (prior_peso + 1)

    potrero.factor_fatiga = clamp(nuevo_factor, 0.5, 1.3)
    potrero.n_ciclos_observados += 1
    return potrero.factor_fatiga
```

El sistema mejora su precisión con cada ciclo real por potrero: los potreros con más historial dan predicciones más confiables (`prior_peso` alto = cambia poco ante una observación atípica).

---

## 9. Endpoints API (FastAPI)

```python
@app.post("/potreros/", dependencies=[Depends(rate_limit)])
async def crear_potrero(data: PotreroCreate, user=Depends(get_current_user)):
    geom_validado = validar_poligono(shape(data.geom))
    return await db.crear_potrero(data, geom_validado)

@app.post("/potreros/import")
async def importar_planimetria(file: UploadFile, finca_id: str, user=Depends(get_current_user)):
    ext = file.filename.split('.')[-1].lower()
    if ext == 'dxf':
        fc = reproyectar_geojson(dxf_a_geojson(await file.read()))
    elif ext in ('kml', 'gpx'):
        fc = gpx_kml_a_geojson(await file.read())
    else:
        raise HTTPException(400, "Formato no soportado")
    return await crear_potreros_masivo(finca_id, fc)

@app.get("/fincas/{finca_id}/rotacion/sugerir")
async def sugerir_rotacion_endpoint(finca_id: str, user=Depends(get_current_user)):
    return await motor_rotacion.sugerir(finca_id, fecha_hoy=date.today())

@app.post("/eventos/entrada")
async def registrar_entrada(lote_id: str, potrero_id: str, user=Depends(get_current_user)):
    ...

@app.post("/eventos/salida")
async def registrar_salida(evento_id: str, biomasa_final_estimada: float, user=Depends(get_current_user)):
    # actualiza factor_fatiga si hubo sobrepastoreo
    ...

@app.get("/potreros/{id}/historial")
async def historial_potrero(id: str, user=Depends(get_current_user)):
    # serie temporal: biomasa modelo vs NDVI vs eventos reales
    # clave para que el ganadero confie en la sugerencia del sistema
    ...
```

`get_current_user` y `rate_limit` se detallan en [§10](#10-seguridad-autenticación-y-cumplimiento) — el original los dejaba implícitos (`Depends(get_current_user)` aparecía sin especificar qué hace).

---

## 10. Seguridad, autenticación y cumplimiento

*(Sección nueva — no estaba en el documento original.)*

- **Autenticación:** Supabase Auth (JWT) o equivalente — evita construir gestión de sesiones/contraseñas propia. El token lleva `organizacion_id`, que se propaga a `current_setting('app.current_org')` en cada conexión de base de datos para que la RLS de [§2](#2-modelo-de-datos-postgresql--postgis) aplique automáticamente.
- **Autorización:** roles mínimos por organización — `admin` (gestiona fincas/usuarios), `operador` (registra eventos de entrada/salida, no borra potreros).
- **Rate limiting** en endpoints de escritura (`/potreros/import`, `/eventos/*`) — evita que un cliente con un bug en su integración degrade el servicio para otros tenants.
- **Secretos:** credenciales de Copernicus/Open-Meteo y llaves de base de datos en un secret manager (no en `.env` versionado); rotación documentada.
- **Habeas data (Ley 1581 de 2012, Colombia):** los datos de finca/producción son datos del titular (el ganadero); se necesita política de privacidad, base legal de tratamiento y mecanismo de eliminación de datos a solicitud — relevante porque el sistema es multi-tenant y almacena datos de producción que pueden considerarse sensibles comercialmente.
- **Auditoría:** tabla de eventos de dominio (`PotreroLevantado`, `LoteSalioDePotrero`, etc. — ver [§17.3](#173-eventos-de-dominio)) ya provee el rastro de auditoría necesario si se persiste, sin trabajo adicional.

---

## 11. Resiliencia ante fallos de servicios externos

*(Sección nueva.)* El sistema depende de tres servicios externos que **van a fallar o degradarse** (Open-Meteo, Copernicus/CDSE, y el solver LP si se aloja como servicio aparte). El documento original no contempla esto — asume que las llamadas siempre responden.

- **Reintentos con backoff exponencial** en los adaptadores `OpenMeteoClimaAdapter` y `CopernicusNdviAdapter` (3 intentos, backoff 2/4/8s) antes de marcar el job como fallido.
- **Valores de último-conocido como fallback:** si el clima de hoy no está disponible, usar el registro del día anterior y marcarlo `estimado=true` en vez de detener el cálculo de biomasa de toda la finca.
- **Idempotencia de jobs:** el job diario de biomasa y el semanal de NDVI deben poder reejecutarse sin duplicar datos (los `UNIQUE` agregados en [§2](#2-modelo-de-datos-postgresql--postgis) son la base de esto — `INSERT ... ON CONFLICT DO UPDATE`).
- **Alertas de job fallido:** si el job de clima o NDVI falla 2 días consecutivos para una finca, se notifica al equipo (no al ganadero) — un fallo silencioso que degrada progresivamente la calidad de la predicción sin que nadie se entere es el peor escenario para la confianza en el producto.

---

## 12. Notificaciones al ganadero

*(Sección nueva.)* El documento original asume que el ganadero entra al dashboard a consultar el estado. Para el usuario objetivo (ver [§1](#1-visión-general-y-alcance)), eso es una apuesta arriesgada: es más realista que reciba un aviso donde ya está — WhatsApp o SMS.

- Integración con WhatsApp Business Cloud API (Meta) o, como alternativa más simple de operar, Twilio (WhatsApp/SMS) — evaluar según costo por mensaje y facilidad de aprobación de plantillas en Colombia.
- Eventos que disparan notificación: potrero listo para pastoreo, sobrepastoreo detectado al registrar salida, fallo persistente de datos climáticos/NDVI para su finca (transparencia: si el sistema está prediciendo con datos viejos, el ganadero debería poder saberlo).
- El dashboard sigue existiendo para el detalle/histórico, pero no es el canal primario de alerta.

---

## 13. Captura de campo sin conectividad (offline-first)

*(Sección nueva.)* Casanare/Llanos tiene conectividad rural intermitente. Una app de captura de planimetría (§3) que dependa de conexión en vivo va a fallar exactamente en el escenario más común: caminando el borde de un potrero lejos de la casa.

- Captura de track GPS con almacenamiento local (IndexedDB en PWA, o SQLite si es app nativa) y sincronización diferida cuando vuelve la conectividad.
- El polígono se valida y calcula localmente (Turf.js en el cliente) para dar retroalimentación inmediata de área, sin esperar al backend.
- Cola de sincronización visible al usuario ("2 potreros pendientes de subir") — la falta de esto es una fuente típica de pérdida de datos de campo silenciosa.

---

## 14. Estrategia de testing

*(Sección nueva.)* El diseño hexagonal del documento original (§18) hace el dominio testeable sin infraestructura — pero el documento nunca lo aterriza en una estrategia concreta.

- **Unitarios de dominio:** `Potrero`, `KalmanBiomasa`, `crecimiento_diario_v2`, `actualizar_factor_fatiga_bayesiano` — puros, sin mocks de base de datos ni HTTP.
- **Property-based / edge cases de geometría:** polígonos autointersectados, menos de 3 puntos tras deduplicar, coordenadas lat/lng invertidas (el error más común de usuario) — casos que el `construir_poligono_validado` de §3.3 debe cubrir explícitamente en tests, no solo manejar en runtime.
- **Contract tests de adaptadores:** `OpenMeteoClimaAdapter` y `CopernicusNdviAdapter`/CDSE contra respuestas grabadas (fixtures), para detectar cuando el proveedor externo cambia su contrato antes de que rompa producción.
- **Backtesting del modelo agronómico:** correr el modelo de crecimiento + Kalman sobre series climáticas históricas de una finca piloto y comparar contra mediciones físicas reales — esto **es** la validación del producto, no un test más; sin esto no hay forma de afirmar que el modelo predice bien.

---

## 15. CI/CD y observabilidad

*(Sección nueva.)*

- **CI:** lint + type-check + tests en cada PR (GitHub Actions); migraciones de base de datos versionadas (Alembic) y revisadas como parte del PR, no aplicadas a mano.
- **Logs estructurados** (JSON) en jobs de clima/NDVI/rotación, con `finca_id` y `job_id` para poder rastrear un fallo específico sin grep manual.
- **Métricas mínimas:** tasa de éxito de jobs diarios/semanales, latencia del endpoint de sugerencia de rotación, error medio entre biomasa predicha y NDVI (esto último es, en la práctica, el KPI de calidad del producto).
- **Alertas** sobre las métricas anteriores, no solo sobre caídas del servidor.

---

## 16. Diferenciadores técnicos frente a otros sistemas

- Calibración con NDVI real y gratuito (Copernicus Data Space Ecosystem), no solo modelo teórico — poco común en apps ganaderas de la región.
- Curvas de crecimiento especializadas para especies y clima de Casanare/Llanos, en vez de curvas genéricas de EE.UU./Europa.
- Factor de fatiga por potrero: memoria del sobrepastoreo, evita degradar potreros por seguir un calendario ciego.
- Import de planimetría real (DXF/CAD/GPS) con reproyección correcta MAGNA-SIRGAS, agnóstico a la fuente de captura, con **captura offline** para conectividad rural (§13).
- Explicabilidad: historial que compara biomasa modelo vs NDVI vs eventos reales, generando confianza y adopción en campo.
- **Notificación proactiva** en vez de dashboard pasivo (§12) — encaja con cómo el usuario objetivo realmente opera.

---

## 17. Diseño estratégico DDD (Domain-Driven Design)

Se implementa desde la fase 1, como en el documento original. El sistema se modela como un conjunto de contextos delimitados (bounded contexts), cada uno con su propio lenguaje ubicuo, en vez de un monolito de tablas compartidas.

> **Trade-off a tener presente (no desaparece por decidir esto desde el día 1):** contextos delimitados formales, agregados y eventos de dominio dan disciplina y facilitan escalar equipos/servicios más adelante, pero cuestan velocidad de iteración temprana — hay más piezas que escribir antes de tener el primer entregable de la fase 1 (§21), y los límites de contexto definidos en §17.1 son una apuesta sobre cómo va a crecer el dominio antes de tener datos reales de un piloto. Si en la fase 6 el piloto muestra que algún límite de contexto no encaja con cómo realmente se usa el sistema, hay que estar dispuestos a mover código entre contextos — DDD reduce el costo de esa corrección, no lo elimina.

### 17.1 Contextos delimitados (Bounded Contexts)

| Contexto | Responsabilidad | Lenguaje ubicuo clave |
|---|---|---|
| Gestión de Potreros | Planimetría, geometría, levantamiento, validación | Potrero, Geometría, Levantamiento, Área geodésica |
| Modelado Agronómico | Crecimiento de biomasa, clima, NDVI, Kalman | Biomasa, GDD, Balance hídrico, Estimación |
| Gestión de Ganado | Lotes, unidades animal, consumo | Lote, UA equivalente, Consumo diario |
| Rotación y Optimización | Sugerencia y calendario de rotación | Ciclo de pastoreo, Calendario, Restricción |
| Calibración | Aprendizaje bayesiano por potrero | Factor de fatiga, Prior, Observación |

Cada contexto es dueño de sus propias tablas/modelos; la comunicación entre contextos ocurre por eventos de dominio o contratos explícitos (anti-corruption layer), nunca por acceso directo a la base de datos de otro contexto — desde la fase 1. En una fase temprana con pocos desarrolladores, el bus de eventos puede ser en memoria (dentro del mismo proceso); lo que importa es que ningún contexto haga `SELECT`/`JOIN` directo sobre las tablas de otro, para que separar procesos más adelante (§19) sea un cambio de infraestructura, no una reescritura de lógica.

### 17.2 Modelo táctico: agregados, entidades y value objects

```python
# --- Contexto: Gestión de Potreros ---

@dataclass(frozen=True)
class Coordenada:
    lat: float
    lng: float

@dataclass(frozen=True)
class Geometria:
    puntos: tuple[Coordenada, ...]
    metodo_levantamiento: str
    accuracy_m: float

    def area_ha(self) -> float:
        return calcular_area_geodesica(self) / 10000

class Potrero:
    def __init__(self, id: PotreroId, finca_id: FincaId, geometria: Geometria,
                 especie_pasto: EspeciePasto):
        self._id = id
        self._geometria = geometria
        self._especie_pasto = especie_pasto
        self._estado = EstadoPotrero.DESCANSO
        self._factor_fatiga = FactorFatiga.neutro()
        self._eventos: list[DomainEvent] = []

    def registrar_salida_lote(self, biomasa_final: float):
        if self._estado != EstadoPotrero.OCUPADO:
            raise DomainError("No se puede registrar salida de un potrero no ocupado")
        self._estado = EstadoPotrero.DESCANSO
        self._factor_fatiga = self._factor_fatiga.actualizar(biomasa_final)
        self._eventos.append(LoteSalioDePotrero(self._id, biomasa_final))

    def eventos_pendientes(self) -> list["DomainEvent"]:
        return self._eventos

# --- Contexto: Modelado Agronómico ---

class EstimacionBiomasa:
    def __init__(self, potrero_id: PotreroId, kalman: KalmanBiomasa):
        self._potrero_id = potrero_id
        self._kalman = kalman

    def actualizar_con_clima(self, clima: RegistroClima, especie: EspeciePasto):
        crecimiento = crecimiento_diario_v2(clima.gdd, clima.balance_hidrico_pct, especie)
        self._kalman.predecir(crecimiento)

    def corregir_con_ndvi(self, lectura: LecturaNdvi):
        self._kalman.actualizar(lectura.biomasa_equivalente, lectura.calidad)
```

### 17.3 Eventos de dominio

```python
class DomainEvent: ...

@dataclass(frozen=True)
class PotreroLevantado(DomainEvent):
    potrero_id: PotreroId
    area_ha: float
    metodo: str

@dataclass(frozen=True)
class LoteSalioDePotrero(DomainEvent):
    potrero_id: PotreroId
    biomasa_final: float

@dataclass(frozen=True)
class BiomasaRecalculada(DomainEvent):
    potrero_id: PotreroId
    biomasa_kg_ms_ha: float
    fuente: str  # "modelo" | "ndvi" | "kalman"

@dataclass(frozen=True)
class RotacionSugerida(DomainEvent):
    finca_id: FincaId
    calendario: dict
```

Los eventos de dominio son el mecanismo de integración entre contextos: el contexto de Rotación se suscribe a `BiomasaRecalculada` para saber cuándo un potrero pasa a estar disponible, sin depender directamente de las tablas internas del contexto Agronómico. Persistidos, también sirven como registro de auditoría (§10).

---

## 18. Arquitectura hexagonal (Puertos y Adaptadores)

Se implementa desde la fase 1, junto con DDD (§17) — no se espera a tener un segundo adaptador real por contexto. Cada contexto se implementa con el dominio en el centro, aislado de frameworks, bases de datos y proveedores externos. Los puertos definen contratos; los adaptadores implementan esos contratos para una tecnología concreta. Esto permite cambiar Postgres por otra base, o Copernicus por otro proveedor NDVI, sin tocar la lógica de negocio — y da testabilidad de dominio (fakes en vez de infraestructura real, §14) desde el primer sprint.

### 18.1 Estructura de carpetas (por contexto, desde la fase 1)

```
gestion_potreros/
  domain/
    entities.py        # Potrero, Finca (aggregates)
    value_objects.py   # Geometria, Coordenada, FactorFatiga
    events.py           # PotreroLevantado, LoteSalioDePotrero
    ports/
      potrero_repository.py     # Puerto de salida (interface)
      geometria_validator.py    # Puerto de salida
    services/
      levantamiento_service.py  # Caso de uso / puerto de entrada

  application/
    use_cases/
      importar_planimetria.py
      registrar_potrero_manual.py
    dto.py

  infrastructure/
    adapters/
      postgres_potrero_repository.py   # Adaptador de salida (implementa el puerto)
      dxf_import_adapter.py
      shapely_geometria_validator.py
    api/
      fastapi_router.py                 # Adaptador de entrada (HTTP)
    events/
      event_bus_adapter.py
```

### 18.2 Puertos (interfaces del dominio)

```python
from abc import ABC, abstractmethod

class PotreroRepository(ABC):
    @abstractmethod
    async def guardar(self, potrero: Potrero) -> None: ...
    @abstractmethod
    async def obtener(self, id: PotreroId) -> Potrero | None: ...
    @abstractmethod
    async def listar_por_finca(self, finca_id: FincaId) -> list[Potrero]: ...

class ProveedorClima(ABC):
    @abstractmethod
    async def obtener_clima_diario(self, ubicacion: Coordenada, fecha: date) -> RegistroClima: ...

class ProveedorNdvi(ABC):
    @abstractmethod
    async def obtener_ndvi(self, geometria: Geometria, fecha: date) -> LecturaNdvi: ...

class OptimizadorRotacion(ABC):
    @abstractmethod
    def optimizar(self, potreros: list[Potrero], lotes: list[LoteGanado],
                   horizonte_dias: int) -> Calendario: ...

class PublicadorEventos(ABC):
    @abstractmethod
    async def publicar(self, eventos: list[DomainEvent]) -> None: ...
```

### 18.3 Caso de uso (puerto de entrada)

```python
class ImportarPlanimetria:
    """Caso de uso: orquesta el dominio, solo depende de puertos (interfaces)"""
    def __init__(self, repo: PotreroRepository, validador: GeometriaValidator,
                 eventos: PublicadorEventos):
        self._repo = repo
        self._validador = validador
        self._eventos = eventos

    async def ejecutar(self, cmd: ImportarPlanimetriaCommand) -> PotreroId:
        puntos = normalizar_entrada(cmd.archivo, cmd.formato)
        geometria = self._validador.construir_y_validar(puntos, cmd.metodo, cmd.accuracy_m)

        potrero = Potrero.crear(cmd.finca_id, geometria, cmd.especie_pasto)
        await self._repo.guardar(potrero)
        await self._eventos.publicar(potrero.eventos_pendientes())
        return potrero.id
```

### 18.4 Adaptadores (implementaciones concretas)

```python
class PostgresPotreroRepository(PotreroRepository):
    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def guardar(self, potrero: Potrero) -> None:
        await self._pool.execute(
            "INSERT INTO potreros (id, finca_id, geom, ...) VALUES ($1, $2, ST_GeomFromGeoJSON($3), ...)",
            potrero.id, potrero.finca_id, potrero.geometria.to_geojson()
        )

class CopernicusNdviAdapter(ProveedorNdvi):
    async def obtener_ndvi(self, geometria: Geometria, fecha: date) -> LecturaNdvi:
        token = await obtener_token_oauth_cdse()
        escenas = await buscar_escenas_cdse(geometria.to_bbox(), fecha - timedelta(days=10), fecha, token)
        if not escenas:
            return await self._ultima_lectura_conocida(geometria)  # fallback, ver §11
        ndvi = calcular_ndvi_local(escenas.banda_red, escenas.banda_nir, geometria.to_bbox())
        return LecturaNdvi(ndvi_promedio=ndvi, calidad=escenas.calidad_nubosidad)

class OpenMeteoClimaAdapter(ProveedorClima):
    async def obtener_clima_diario(self, ubicacion: Coordenada, fecha: date) -> RegistroClima:
        resp = await http_client.get("https://api.open-meteo.com/v1/forecast", params={...})
        return RegistroClima.desde_respuesta_api(resp.json())

class PulpOptimizadorAdapter(OptimizadorRotacion):
    def optimizar(self, potreros, lotes, horizonte_dias) -> Calendario:
        return optimizar_calendario_rotacion(potreros, lotes, horizonte_dias)  # ver §7

@router.post("/potreros/import")
async def importar_planimetria_endpoint(file: UploadFile, finca_id: str,
                                         caso_uso: ImportarPlanimetria = Depends(get_caso_uso)):
    resultado = await caso_uso.ejecutar(ImportarPlanimetriaCommand(file, finca_id))
    return {"potrero_id": resultado}
```

La regla de dependencia es siempre hacia adentro: `infrastructure` depende de `application` y `domain`, nunca al revés. El dominio no importa FastAPI, asyncpg ni ninguna librería externa — eso permite testear la lógica de negocio con fakes en vez de base de datos real (§14), y reemplazar cualquier proveedor externo sin tocar el núcleo.

---

## 19. Escalabilidad y multi-tenancy

### 19.1 Separación de lecturas y escrituras (CQRS ligero)

El cálculo de biomasa (escritura, con Kalman y modelo agronómico) es costoso; la consulta del dashboard debe ser rápida y frecuente.

- Comandos (import, registrar entrada/salida, recalcular biomasa) pasan por los casos de uso del dominio.
- Consultas (dashboard, historial, mapa) leen de una vista materializada/proyección de solo lectura, actualizada por los eventos de dominio.

### 19.2 Procesamiento asíncrono con cola de trabajos

```python
# Productor: la API solo encola, no calcula
@router.post("/fincas/{finca_id}/rotacion/recalcular")
async def solicitar_recalculo(finca_id: str, cola: ColaTrabajos = Depends(get_cola)):
    await cola.encolar("recalcular_rotacion", {"finca_id": finca_id})
    return {"status": "encolado"}

# Worker independiente (escalable horizontalmente, separado del proceso API)
async def worker_recalculo(mensaje):
    finca_id = mensaje["finca_id"]
    caso_uso = construir_caso_uso_optimizacion()
    calendario = await caso_uso.ejecutar(finca_id)
    await publicador_eventos.publicar([RotacionSugerida(finca_id, calendario)])
```

Redis + RQ/Celery (gratuitos y auto-hospedables) es suficiente para el volumen inicial; el dominio y los casos de uso no cambian si más adelante se reemplaza la cola por algo más robusto.

### 19.3 Multi-tenancy

Ver esquema con RLS en [§2](#2-modelo-de-datos-postgresql--postgis) — aplicado desde la fase 1, no como feature tardía.

| Etapa de negocio | Despliegue recomendado |
|---|---|
| MVP / pocas fincas | Monolito modular: un proceso FastAPI, módulos por contexto, un worker para jobs |
| Crecimiento / decenas de fincas | API + worker(s) separados; caché (Redis) para lecturas del dashboard |
| Escala / SaaS multi-cliente | Contexto Agronómico como servicio independiente (cómputo intensivo); resto permanece modular |

---

## 20. Registro de riesgos

*(Sección nueva.)*

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Copernicus Open Access Hub descontinuado; CDSE cambia su API con el tiempo | Job de NDVI roto sin aviso | Puerto `ProveedorNdvi` aísla el detalle (§18.4); contract tests (§14) detectan cambios de contrato temprano |
| LP de rotación no escala con más potreros/lotes/horizonte | Timeouts, mala experiencia | Fallback greedy con timeout (§7); introducir LP solo cuando el greedy demuestre ser insuficiente |
| Baja adopción (usuario no entra al dashboard) | Producto técnicamente correcto pero sin uso real | Notificaciones proactivas WhatsApp/SMS (§12) como canal primario |
| GPS de smartphone insuficiente en potreros pequeños | Biomasa calculada sobre área incorrecta | `accuracy_m` visible al usuario; advertencia de plausibilidad de área (§3.3) |
| Kalman/Bayes sin datos reales suficientes al inicio | Predicciones ruidosas, pierde confianza del piloto | Priors conservadores + fase de piloto explícita (fase 6) antes de exponer el modelo como autoridad |
| Conectividad rural intermitente | Pérdida de datos de campo capturados | Captura offline-first con sincronización diferida (§13) |
| Falla silenciosa de jobs externos (clima/NDVI) | Degradación progresiva de precisión sin que nadie lo note | Alertas de job fallido + fallback a último dato conocido marcado como `estimado` (§11) |
| DDD/hexagonal aplicado desde el día 1 | Velocidad de iteración más lenta en la fase de validación de producto (decisión tomada conscientemente, ver nota de trade-off en §17) | Mantener los contextos de §17.1 deliberadamente pocos y grandes al inicio (5, no 15); revisar límites de contexto contra la realidad del piloto en fase 6 y estar dispuestos a mover código entre contextos si no encajan |

---

## 21. Plan de trabajo por fases

DDD y hexagonal se establecen en la fase 1 (estructura de carpetas de §18.1, puertos de §18.2, primeros agregados de §17.2) para los contextos de Gestión de Potreros y Modelado Agronómico, que son los que existen desde el principio. El LP de optimización (§7) sigue diferido a la fase 8: es una decisión distinta — no es un problema de límites arquitectónicos sino de no optimizar globalmente sobre un modelo de biomasa todavía sin calibrar con datos reales.

| Fase | Contenido | Entregable |
|---|---|---|
| 1 (sem. 1-3) | Estructura DDD/hexagonal (domain/application/infrastructure) para contextos Gestión de Potreros y Modelado Agronómico; PostgreSQL+PostGIS con RLS, esquema, auth básica, import DXF/KML/GPX con reproyección vía casos de uso, mapa de dibujo (react-leaflet+turf.js) | Cargar/dibujar potreros reales con área calculada, con usuario autenticado, sobre arquitectura hexagonal desde el primer commit |
| 2 (sem. 4) | `ProveedorClima` (puerto) + `OpenMeteoClimaAdapter`, con reintentos/fallback, job diario de clima | Histórico climático automático y resiliente por finca |
| 3 (sem. 5-6) | Motor de crecimiento (grados-día + balance hídrico + factores) como servicio de dominio del contexto Agronómico, tabla de especies Llanos/Casanare | Biomasa estimada por potrero, actualizada a diario |
| 4 (sem. 7) | Cuenta Copernicus Data Space Ecosystem, `ProveedorNdvi`/`CopernicusNdviAdapter` con fallback, fusión con Kalman (`EstimacionBiomasa`) | Modelo autocorregido contra dato satelital real |
| 5 (sem. 8-9) | Contexto Rotación y Optimización con motor **greedy** tras el puerto `OptimizadorRotacion`, dashboard semáforo, eventos de dominio entrada/salida, notificaciones WhatsApp/SMS | Sistema usable de punta a punta, con alertas proactivas |
| 6 (sem. 10-11) | Piloto con finca real, comparación biomasa estimada vs. medición física, calibración bayesiana (contexto Calibración), backtesting; revisión de límites de contexto contra la realidad observada | Modelo calibrado y validado con datos reales |
| 7 (sem. 12-13) | CI/CD, observabilidad, testing automatizado (unitarios de dominio + contract tests de adaptadores), revisión de seguridad/habeas data, event bus real entre contextos si aún se usaba uno en memoria | Sistema listo para múltiples clientes (SaaS) |
| 8 (sem. 14+) | `PulpOptimizadorAdapter` (LP) implementando `OptimizadorRotacion` — solo si el greedy resulta insuficiente en el piloto, sin tocar el caso de uso que lo consume; captura offline-first; panel de negocio/planes | Producto diferenciado y escalable |

---

## 22. Stack tecnológico

| Componente | Herramienta |
|---|---|
| Backend | FastAPI |
| Frontend | Next.js + react-leaflet + turf.js |
| Base de datos | PostgreSQL + PostGIS (Supabase free tier) |
| Autenticación | Supabase Auth (JWT) |
| Datos climáticos | Open-Meteo / IDEAM (gratis, sin key) |
| Datos satelitales (NDVI) | Copernicus Data Space Ecosystem (Sentinel-2, gratis) — sucesor del Open Access Hub |
| Optimización | PuLP (programación lineal), a partir de fase 8 |
| Fusión de datos | Filtro de Kalman (implementación propia) |
| Jobs programados | APScheduler / pg_cron |
| Cola de trabajos | Redis + RQ/Celery |
| Notificaciones | WhatsApp Business Cloud API / Twilio |
| CI/CD | GitHub Actions |
| Observabilidad | Logs estructurados + métricas (Sentry / OpenTelemetry-compatible) |
