# SPEC_DRIVEN_CONTRACT — Aliados guiados (Modo descubrimiento)

**Feature:** RF-22 · Configuración avanzada de atractores de tráfico  
**Versión:** 1.0  
**Fecha:** 9 de junio de 2026  
**Estado del contrato:** Aprobado e implementado (v1.0 — jun 2026)  
**Repositorio:** `viabilidad-hook` / rama `update-user-x`

---

## 1. User Story

**Como** emprendedor que va a abrir un local en México,  
**quiero** responder preguntas sencillas sobre mi cliente y mi zona para **descubrir por mí mismo** qué tipos de establecimientos complementarios conviene buscar cerca,  
**para** que el reporte evalúe aliados relevantes sin depender de que la IA adivine mis intenciones, y entender *por qué* esos lugares importan para mi negocio.

**Criterios de aceptación:**
1. Existen dos modos: **Automático** (default) y **Guiado** (acordeón avanzado, Premium).
2. En modo Guiado el usuario responde 3 bloques de preguntas en lenguaje de negocio (no categorías técnicas de Google).
3. El sistema muestra sugerencias pre-marcadas con explicación breve («por qué») antes de analizar.
4. El usuario confirma o ajusta las sugerencias; la selección final es **100 % trazable** a sus respuestas.
5. La búsqueda en Places usa solo las categorías confirmadas — **sin LLM** en la resolución de aliados.
6. El PDF incluye una nota: *«Atractores definidos por configuración guiada»* y lista las respuestas del usuario (perfil, horarios, tipos elegidos).
7. Modo Automático conserva el comportamiento actual (matriz por rubro + checkboxes técnicos opcionales).

---

## 2. Decisiones técnicas (Closed)

| Decisión | Elección | Estado |
|----------|----------|--------|
| Modos de análisis | `automatico` (default) · `guiado` (Premium) | **Closed** |
| LLM en resolución de aliados (modo guiado) | No participa | **Closed** |
| LLM en narrativa FODA (modo guiado) | Sí, solo con métricas reales ya calculadas | **Closed** |
| Fuente de categorías Places | `CATEGORIAS_ALIADOS_PERMITIDAS` existente | **Closed** |
| Motor de sugerencias | Reglas deterministas: matriz rubro + boosts por perfil/horario | **Closed** |
| Máximo de tipos de aliado a buscar | 5 (límite Premium actual) | **Closed** |
| Persistencia | Campos JSON en `OrdenPago` + eco en `resultado_json` | **Closed** |
| Intenciones (textarea) en modo guiado | Opcional; no afecta búsqueda de aliados | **Closed** |
| Competidores en v1 | Sin cambio (fase 2: mismo patrón guiado) | **Closed** |
| UI | Acordeón «Configuración avanzada» debajo de aliados Premium | **Closed** |

---

## 3. Contrato de tipos (interfaces bloqueadas)

Definir en `app/schemas_aliados_guiados.py` **antes** de implementar lógica.

```python
from typing import Literal, TypedDict

ModoAnalisisAliados = Literal["automatico", "guiado"]

# Respuestas del cuestionario (claves estables, no texto libre)
PerfilCliente = Literal[
    "publico_general",
    "familias",
    "estudiantes",
    "oficinistas",
    "transporte_publico",
    "compradores_paso",
    "salud_bienestar",
    "adultos_mayores",
]

HorarioPico = Literal["manana", "mediodia", "tarde", "noche_finde"]

# Coincide con claves de CATEGORIAS_ALIADOS_PERMITIDAS
TipoAtractor = Literal[
    "school", "transit_station", "bank", "shopping_mall",
    "supermarket", "convenience_store", "park", "doctor",
    "restaurant", "cafe", "gym", "pharmacy", "beauty_salon", "laundry",
]


class ConfiguracionAliadosGuiados(TypedDict, total=False):
    modo: ModoAnalisisAliados
    perfil_cliente: list[PerfilCliente]       # min 1, max 3
    horarios_pico: list[HorarioPico]           # min 1, max 2
    atractores_confirmados: list[TipoAtractor] # min 2, max 5 — selección final del usuario


class SugerenciaAtractor(TypedDict):
    tipo: TipoAtractor
    etiqueta: str          # español, para UI y PDF
    motivo: str            # frase corta «por qué»
    sugerido: bool         # pre-marcado por el motor
    puntaje: int           # solo trazabilidad interna


class ResolucionAliadosGuiados(TypedDict):
    tipos_busqueda: list[TipoAtractor]
    fuente: Literal["guiado_usuario", "matriz_rubro", "categorias_usuario"]
    sugerencias: list[SugerenciaAtractor]
    configuracion: ConfiguracionAliadosGuiados
```

**Payload API** (extensión de checkout y `/api/analizar/previa`):

```json
{
  "modo_analisis_aliados": "guiado",
  "config_aliados_guiados": {
    "perfil_cliente": ["familias", "oficinistas"],
    "horarios_pico": ["manana", "tarde"],
    "atractores_confirmados": ["school", "transit_station", "supermarket"]
  },
  "aliados_seleccionados": ["school", "transit_station", "supermarket"],
  "aliados_adicionales": "OXXO, Soriana"
}
```

---

## 4. Cuestionario guiado — preguntas al usuario

El flujo educa antes de pedir datos. Cada bloque incluye una línea de contexto.

### Bloque 0 — Introducción (solo modo Guiado)

**Título:** ¿Quién trae clientes a tu zona?  
**Texto:** Los *aliados* no compiten contigo: son lugares que concentran gente cerca de tu local (escuelas, transporte, plazas…). Marcar los correctos hace que el reporte mida el flujo real que podrías captar.

---

### Pregunta 1 — Perfil de cliente principal

**Enunciado:** ¿A quién le venderás **principalmente**?  
**Ayuda:** Elige hasta 3 perfiles. Si tu negocio atiende a **cualquier persona** que transite la zona (abarrotes, farmacia, conveniencia…), marca «Público en general». Si además tienes un foco claro, combínalo con otro perfil.

| Opción (UI) | Clave | Ejemplo de aliado que suele aportar |
|-------------|-------|-------------------------------------|
| **Público en general** (cualquier transeúnte o vecino) | `publico_general` | Transporte, conveniencia, supermercados — según tu giro |
| Familias con niños | `familias` | Escuelas, parques, supermercados |
| Estudiantes y jóvenes | `estudiantes` | Universidades, transporte, cafeterías |
| Oficinistas y trabajadores de oficina | `oficinistas` | Bancos, corporativos, restaurantes de comida |
| Personas que usan transporte público | `transporte_publico` | Metro, metrobús, paradas de camión |
| Compradores de paso (van de compras) | `compradores_paso` | Plazas, supermercados, tiendas de conveniencia |
| Salud, ejercicio y bienestar | `salud_bienestar` | Gimnasios, consultorios, farmacias |
| Adultos mayores y servicios cotidianos | `adultos_mayores` | Farmacias, consultorios, bancos |

**Validación:** mínimo 1, máximo 3.  
**Regla UX:** si el usuario marca solo `publico_general`, en P3 el motivo por defecto es *«Sugerido por tu giro — tráfico mixto en la colonia»*. Si combina `publico_general` con perfiles específicos, los boosts de sugerencia aplican solo a los perfiles específicos.

---

### Pregunta 2 — Horarios en que esperas más ventas

**Enunciado:** ¿En qué **momentos** esperas recibir más clientes?  
**Ayuda:** Un mismo barrio se comporta distinto a las 8:00, a la hora de comida o al salir del trabajo.

| Opción (UI) | Clave | Tráfico típico |
|-------------|-------|----------------|
| Mañana (6:00 – 12:00) | `manana` | Escuelas, bancos, cafeterías temprano |
| Mediodía / hora de comida | `mediodia` | Restaurantes, oficinas, supermercados |
| Tarde / salida de trabajo | `tarde` | Transporte, plazas, conveniencia |
| Noche y fin de semana | `noche_finde` | Restaurantes, centros comerciales, parques |

**Validación:** mínimo 1, máximo 2.

---

### Pregunta 3 — Descubrimiento de atractores (núcleo del flujo)

**Enunciado:** ¿Qué **tipos de lugares** crees que traen gente cerca de donde abrirás?  
**Ayuda:** No necesitas conocer nombres de marcas todavía. Marca los que tendrían sentido en tu colonia. El reporte después contará cuántos hay en tu radio.

El sistema **pre-marca** opciones según P1 + P2 + giro (motor de sugerencias). El usuario ve el motivo y puede quitar o agregar.

| Opción (UI) | Clave Places | Micro-explicación (tooltip / subtítulo) |
|-------------|--------------|----------------------------------------|
| Escuelas, universidades o guarderías | `school` | Flujo diario de padres y estudiantes |
| Paradas de transporte público | `transit_station` | Personas entrando y saliendo todo el día |
| Bancos, cajeros u oficinas | `bank` | Empleados y trámites que generan visitas repetidas |
| Centros comerciales o plazas | `shopping_mall` | Concentran visitas planeadas de compra |
| Supermercados | `supermarket` | Familias en rutina de abastecimiento |
| Tiendas de conveniencia / abarrotes | `convenience_store` | Compras rápidas de vecinos y transeúntes |
| Parques o áreas recreativas | `park` | Familias y ejercicio en fines de semana |
| Consultorios, clínicas u hospitales | `doctor` | Visitas por salud y acompañantes |
| Restaurantes cercanos | `restaurant` | Generan flujo de comida (complementan, no sustituyen) |
| Cafeterías cercanas | `cafe` | Punto de reunión y consumo frecuente |
| Gimnasios o estudios de fitness | `gym` | Rutina de asistencia varias veces por semana |
| Farmacias | `pharmacy` | Visitas cotidianas de salud |
| Estéticas y salones | `beauty_salon` | Citas programadas en la zona |
| Lavanderías | `laundry` | Recurrencia semanal de vecinos |

**Validación:** mínimo 2, máximo 5.  
**Regla UX:** si el usuario desmarca todas las sugeridas, mostrar aviso: *«Selecciona al menos 2 tipos de lugares que creas relevantes para tu negocio»*.

---

### Pregunta 4 — Marcas o nombres específicos (opcional)

**Enunciado:** ¿Hay **marcas o establecimientos concretos** que quieras que el reporte busque además?  
**Campo:** texto libre (existente `aliados_adicionales`).  
**Ayuda:** Ej.: «OXXO, Walmart, Hospital Ángeles». Esto no reemplaza las categorías; agrega búsquedas por nombre.

---

### Pantalla de confirmación (antes de analizar)

Resumen legible:

> **Tu configuración de aliados**  
> Cliente principal: Familias, Oficinistas  
> Horarios clave: Mañana, Tarde  
> Buscaremos cerca: Escuelas, Transporte público, Supermercados  
> *Motivo:* combinación de tu giro (florería), perfil familiar y salida de escuelas por la tarde.

Botón: **Confirmar y analizar** (o regresar a ajustar).

---

## 5. Motor de sugerencias (determinista)

Función bloqueada: `sugerir_atractores(config_parcial, rubro) -> list[SugerenciaAtractor]`

### 5.1 Puntaje base por giro

Partir de `resolver_aliados_por_rubro(rubro)` — cada tipo en posición `i` recibe `(4 - i) * 10` puntos.

### 5.2 Boost por perfil de cliente

Perfiles aplicables = `perfil_cliente` **sin** `publico_general`.  
Si la lista queda vacía (solo eligió público en general), **no** se aplican boosts de esta tabla; entran solo matriz por giro (5.1), horario (5.3) y boosts universales (5.2b).

| Perfil | +puntos a tipos |
|--------|-----------------|
| `familias` | school +15, park +12, supermarket +10 |
| `estudiantes` | school +15, transit_station +12, cafe +8, convenience_store +8 |
| `oficinistas` | bank +15, transit_station +12, restaurant +10, shopping_mall +8 |
| `transporte_publico` | transit_station +20, convenience_store +12 |
| `compradores_paso` | shopping_mall +15, supermarket +12, transit_station +8 |
| `salud_bienestar` | doctor +15, pharmacy +12, gym +12 |
| `adultos_mayores` | doctor +12, pharmacy +15, bank +10, supermarket +8 |

### 5.2b Boost universal (solo `publico_general` aislado)

Cuando `perfil_cliente == ["publico_general"]`:

| Tipo | +puntos | Motivo plantilla |
|------|---------|------------------|
| `transit_station` | +10 | Tráfico cotidiano de transeúntes |
| `convenience_store` | +8 | Vecinos y compras de paso |
| `supermarket` | +8 | Rutina de abastecimiento del barrio |
| `bank` | +6 | Trámites y empleados de la zona |

Estos puntos **se suman** a la matriz por giro; no sustituyen P3 ni la confirmación del usuario.

### 5.3 Boost por horario

| Horario | +puntos a tipos |
|---------|-----------------|
| `manana` | school +12, bank +10, cafe +8 |
| `mediodia` | restaurant +12, supermarket +10, bank +8 |
| `tarde` | transit_station +12, school +10, shopping_mall +8, convenience_store +8 |
| `noche_finde` | restaurant +12, shopping_mall +10, park +8 |

### 5.4 Reglas de salida

1. Sumar puntos por tipo; ordenar descendente.
2. Pre-marcar (`sugerido: true`) los **top 4** con puntaje > 0.
3. Siempre incluir en la lista visible los tipos de la matriz del rubro aunque puntaje sea bajo (educación: «también considera…»).
4. Generar `motivo` con plantilla fija:  
   `«Relevante para {perfil legible} y tráfico en {horario legible}»`  
   o `«Sugerido por tu giro ({rubro})»` si solo aplica matriz.
5. **No** añadir tipos que el usuario no haya visto en P3.

### 5.5 Resolución final

`atractores_confirmados` del usuario → `tipos_busqueda` directos (sin recorte por LLM).  
Si `modo == "guiado"` y hay confirmados → `fuente = "guiado_usuario"`.  
Si modo guiado pero vacío → error 422.

---

## 6. Cambios por capa

| Capa | Archivo | Cambio |
|------|---------|--------|
| Domain | `app/schemas_aliados_guiados.py` | Tipos del contrato |
| Domain | `app/aliados_guiados.py` | Motor sugerencias + validación |
| Application | `app/competencia_busqueda.py` | `resolver_tipos_aliados_busqueda` acepta `config_aliados_guiados` |
| Application | `app/analytics.py` | Pasar config; persistir trazabilidad en resultado |
| Infrastructure | `app/models.py` | Columna `config_aliados_guiados` TEXT JSON (nullable) |
| Infrastructure | `app/payments.py` | Validar payload Premium |
| Presentation | `frontend/index.html` | Acordeón 3 preguntas + confirmación |
| Presentation | `frontend/app.js` | Flujo guiado, pre-marcado, envío payload |
| Presentation | `app/reports.py` | Nota + resumen configuración guiada en sección IAT |
| Tests | `tests/test_suite.py` | Matriz de boosts, validaciones, E2E resolución |

---

## 7. Comportamiento por modo

### Modo Automático (sin cambio visible)

1. Checkbox «Matriz automática por rubro» o categorías manuales.
2. `intenciones` pueden reordenar matriz (comportamiento actual).
3. Sin bloque de preguntas guiadas.

### Modo Guiado (Premium)

1. Usuario abre acordeón «Descubrir mis aliados paso a paso».
2. Responde P1 → P2 → ve P3 con sugerencias pre-marcadas y motivos.
3. Ajusta checkboxes en P3 (mín. 2, máx. 5).
4. Opcional P4 marcas.
5. Confirma resumen.
6. `aliados_seleccionados` = `atractores_confirmados` (sin `ia_auto`).
7. PDF muestra badge y tabla de «Tu configuración».

---

## 8. PDF — sección IAT (modo guiado)

Texto fijo adicional bajo «Establecimientos Complementarios»:

> *Atractores definidos por configuración guiada del solicitante (sin inferencia automática de categorías).*

Tabla resumen (máx. 6 filas):

| Campo usuario | Valor mostrado |
|---------------|----------------|
| Perfil de cliente | Etiquetas legibles de P1 |
| Horarios clave | Etiquetas legibles de P2 |
| Tipos elegidos | Lista de P3 en español |
| Marcas adicionales | `aliados_adicionales` o «No especificadas» |

---

## 9. Plan de implementación atómico

| # | Tarea | Verificación |
|---|-------|--------------|
| 5.1 | Crear `schemas_aliados_guiados.py` | Import sin errores |
| 5.2 | Crear `aliados_guiados.py` con `sugerir_atractores` y `validar_config_guiada` | pytest unitario |
| 5.3 | Extender `resolver_tipos_aliados_busqueda` | Tests existentes + nuevos pasan |
| 5.4 | Migración BD + `payments` / `routes_analytics` | 422 en payload inválido |
| 5.5 | UI acordeón + flujo confirmación | Manual: florería CDMX |
| 5.6 | PDF trazabilidad | PDF contiene badge y resumen |
| 5.7 | Tests integración `procesar_calculo_analitico` modo guiado | pytest |

---

## 10. Pruebas obligatorias

```text
test_sugerir_atractores_floreria_familias_tar
test_sugerir_atractores_publico_general_solo
test_validar_config_guiada_minimo_dos_atractores
test_resolver_aliados_modo_guiado_sin_llm
test_procesar_calculo_analitico_aliados_guiados_premium
test_crear_preferencia_guiado_solo_premium
test_pdf_incluye_configuracion_guiada
```

---

## 11. Fuera de alcance (v1)

- Cuestionario guiado para **competidores** (fase 2, mismo patrón).
- Recomendaciones con LLM en el wizard.
- Cambios en tiers Básico / Pro (solo Premium).
- Nuevas categorías Places fuera de `CATEGORIAS_ALIADOS_PERMITIDAS`.

---

## 12. Aprobación

| Rol | Nombre | Fecha | Estado |
|-----|--------|-------|--------|
| Producto | — | — | Pendiente |
| Desarrollo | — | — | Pendiente |

**Siguiente paso tras aprobación:** `/implement` — tarea 5.1 (schemas) en adelante.
