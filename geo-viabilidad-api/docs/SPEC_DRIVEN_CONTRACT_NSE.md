# SPEC_DRIVEN_CONTRACT — Nivel Socioeconómico (NSE)

**Feature:** RF-21 · Fase B del Roadmap (Hito H3)  
**Versión:** 1.0  
**Fecha:** 11 de junio de 2026  
**Estado del contrato:** Aprobado e implementado (v1.0 — jun 2026)  
**Repositorio:** `viabilidad-hook` / rama `update-user-x`

---

## 1. User Story

**Como** emprendedor que evalúa abrir un negocio en un punto de México,  
**quiero** conocer el **nivel socioeconómico (NSE)** del radio de influencia,  
**para** adaptar mi propuesta de valor, precios y estrategia comercial al poder adquisitivo real de la zona.

**Criterios de aceptación:**
1. El NSE aparece en el dashboard (4ª tarjeta KPI) tras pagar cualquier tier.
2. El NSE aparece en el PDF (página 2 — KPIs; página 3 — desglose demográfico).
3. El LLM recibe el NSE en el contexto y no contradice el poder adquisitivo inferido.
4. Si no hay datos censales en la zona: en producción «Sin datos censales»; en `DEV_MODE` fallback determinista.
5. El NSE en dashboard y PDF es idéntico para la misma orden.

---

## 2. Decisiones técnicas (Closed)

| Decisión | Elección | Estado |
|----------|----------|--------|
| Fuente de datos NSE | Tabla `agebs_demografia` (PostGIS) con variables Censo 2020 | **Closed** |
| Método espacial | Promedio ponderado por población en intersección con radio (Haversine) | **Closed** |
| Variables censales | `graproes`, `vivpar_hab`, `vph_autom`, `vph_inter`, `vph_pc` | **Closed** |
| Escala de salida | Niveles AMAI simplificados (A/B, C+, C/C-, D+, D/E) | **Closed** |
| Fallback sin datos | Hash determinista `int(abs(lat*1000 + lng*1000)) % 100` | **Closed** |
| Visibilidad en preview | Bloqueado (blur/candado); desbloqueado post-pago | **Closed** |
| ORM de persistencia | Campos dentro de `resultado_json` (sin nueva tabla) | **Closed** |
| Migración BD | `ALTER TABLE agebs_demografia ADD COLUMN` vía script en `scratch/` | **Closed** |

---

## 3. Contrato de tipos (interfaces bloqueadas)

```python
# app/schemas_nse.py (nuevo — definir ANTES de lógica)

from typing import TypedDict


class NSEMetricasRaw(TypedDict):
    escolaridad_promedio: float      # graproes ponderado (0–18 años equiv.)
    internet_pct: float              # % viviendas con internet (0–100)
    autos_pct: float                 # % viviendas con automóvil (0–100)
    pc_pct: float                    # % viviendas con computadora (0–100)
    fuente: str                      # "censo_2020" | "fallback_determinista"


class NSEDiagnostico(TypedDict):
    nse_score: float                 # 0–100 heurístico interno
    nse_etiqueta: str                # ej. "C+ (Medio Alto)"
    metricas: NSEMetricasRaw
    agebs_consultadas: int


class AnalisisCuantitativoNSE(TypedDict, total=False):
    nse: NSEDiagnostico
```

**Payload API** (`metricas` en `/api/analizar/resultado/{orden_id}`):

```json
{
  "nse": {
    "nse_score": 62.4,
    "nse_etiqueta": "C+ (Medio Alto)",
    "metricas": {
      "escolaridad_promedio": 11.2,
      "internet_pct": 78.5,
      "autos_pct": 45.3,
      "pc_pct": 52.1,
      "fuente": "censo_2020"
    },
    "agebs_consultadas": 12
  }
}
```

---

## 4. Fórmula de cálculo (Closed)

```
nse_score = (escolaridad_promedio / 18.0 * 40.0)
          + (internet_pct * 0.3)
          + (autos_pct * 0.3)
```

**Mapeo AMAI:**

| Rango `nse_score` | Etiqueta |
|-------------------|----------|
| ≥ 70 | A/B (Alto / Alto Medio) |
| 55 – 69.9 | C+ (Medio Alto) |
| 40 – 54.9 | C / C- (Medio / Medio Bajo) |
| 25 – 39.9 | D+ (Bajo Alto) |
| < 25 | D / E (Bajo / Muy Bajo) |

**Fallback** (cuando `agebs_consultadas == 0` o métricas NULL):

```
hash_val = int(abs(lat * 1000 + lng * 1000)) % 100
```

| `hash_val` | Etiqueta asignada |
|------------|-------------------|
| < 10 | A/B (Alto / Alto Medio) |
| 10 – 34 | C+ (Medio Alto) |
| 35 – 69 | C / C- (Medio / Medio Bajo) |
| 70 – 89 | D+ (Bajo Alto) |
| ≥ 90 | D / E (Bajo / Muy Bajo) |

Porcentajes de equipamiento se derivan proporcionalmente del nivel asignado (función `derivar_metricas_fallback(hash_val)` — implementar en contrato).

---

## 5. Plan de implementación atómico

| # | Tarea | Archivo(s) | Test |
|---|-------|------------|------|
| 5.1 | Migración columnas NSE en `agebs_demografia` | `scratch/add_nse_columns.py` | Script idempotente |
| 5.2 | Tipos `NSEDiagnostico` | `app/schemas_nse.py` | Import lint |
| 5.3 | `calcular_nse(db, lat, lng, radio)` | `app/analytics.py` | `test_calcular_nse_*` |
| 5.4 | Integrar en `procesar_calculo_analitico` | `app/analytics.py` | `test_webhook_*` |
| 5.5 | Prompt LLM con NSE | `app/bedrock.py` | `llm_stress_test` |
| 5.6 | PDF páginas 2–3 | `app/reports.py` | PDF page count |
| 5.7 | KPI `#kpi-nse` dashboard | `frontend/index.html`, `app.js`, `index.css` | Manual UAT |
| 5.8 | Re-ingesta variables censales (32 estados + NSE) | `app/ingest_nacional.py`, `ingest_censo_nse.py` | ✅ 58,978 AGEBs con GRAPROES |

**Orden obligatorio:** 5.1 → 5.2 → 5.3 → 5.4 → (5.5, 5.6, 5.7 en paralelo) → 5.8

---

## 6. Migración de base de datos

```sql
ALTER TABLE agebs_demografia
  ADD COLUMN IF NOT EXISTS graproes NUMERIC(6,2) DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS vivpar_hab NUMERIC(8,2) DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS vph_autom NUMERIC(8,2) DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS vph_inter NUMERIC(8,2) DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS vph_pc NUMERIC(8,2) DEFAULT NULL;
```

---

## 7. Consulta espacial (referencia)

```sql
SELECT
  SUM(a.pobtot * a.graproes) / NULLIF(SUM(a.pobtot), 0) AS escolaridad_promedio,
  AVG(a.vph_inter / NULLIF(a.vivtot, 0) * 100) AS internet_pct,
  AVG(a.vph_autom / NULLIF(a.vivtot, 0) * 100) AS autos_pct,
  AVG(a.vph_pc / NULLIF(a.vivtot, 0) * 100) AS pc_pct,
  COUNT(*) AS agebs_consultadas
FROM agebs_demografia a
WHERE ST_Intersects(
  a.geom,
  ST_Buffer(ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radio)::geometry
)
AND a.pobtot > 0;
```

---

## 8. Criterios de verificación (audit)

- [x] `pytest tests/test_suite.py::test_calcular_nse_*` pasa
- [x] Misma orden: NSE idéntico en dashboard y PDF (mismo `resultado_json`)
- [x] Preview gratuita: tarjeta NSE bloqueada
- [x] Post-pago: tarjeta NSE con etiqueta real
- [x] Zona sin AGEBs: fallback determinista reproducible
- [x] Prompt IA: regla NSE en `bedrock.py`
- [x] Re-ingesta censal nacional con variables NSE (`scripts/ingest_inegi/ingest_censo_nse.py`; sync VPS vía `scripts/demografia/sync_demografia_vps.sh`)

---

## 9. Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Columnas vacías tras migración | Alta | NSE siempre fallback | Re-ingesta estados CDMX, Jalisco, NL primero |
| Fórmula AMAI imprecisa | Media | Confianza usuario | Disclaimer en PDF: «estimación basada en Censo 2020» |
| Ampliar PDF página 2 rompe layout | Baja | Desbordamiento | Validar con `scratch/check_pdf_pages.py` |

---

*Contrato bloqueado para implementación. No escribir lógica de aplicación hasta aprobación explícita del usuario (protocolo PHIQUSINO).*
