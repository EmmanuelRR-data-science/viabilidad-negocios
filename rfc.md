# RFC: Extensiones y Evolución de GeoViabilidad Hook

* **Author(s)**: Antigravity AI · Emmanuel Ramírez Romero
* **Status**: Documento vivo — beta operativa (VPS Jun 2026)
* **Última actualización**: 2026-06-18
* **Versión de referencia**: API `1.0.0` · Frontend `app.js v1.0.4` · Rama `spotlight`
* **RFC arquitectónico principal**: [.kiro/specs/viabilidad-comercial/rfc-viabilidad-comercial.md](.kiro/specs/viabilidad-comercial/rfc-viabilidad-comercial.md)
* **Links**:
  * Schemas de entrada: [schemas.py](app/schemas.py)
  * ORM base de datos: [models.py](app/models.py)
  * Lógica analítica: [analytics.py](app/analytics.py)
  * Prompts LLM: [bedrock.py](app/bedrock.py)
  * Generador de PDF: [reports.py](app/reports.py)

---

## Estado de secciones (sincronizado con código)

| Sección | Tema | Estado |
|---------|------|--------|
| §1–7 | Personalización competidores/aliados por tier | ✅ Implementado |
| §8 | Corrección desbordamiento PDF portada | ✅ Implementado |
| §9 | Eliminación terminología técnica en UI/PDF | ✅ Implementado |
| §10 | Caché `resultado_json` / `foda_json` | ✅ Implementado |
| §11 | Búsqueda de direcciones | ✅ Implementado |
| §12 | Calidad reportes (FODA, fast_food, NSE, etc.) | ✅ Implementado |
| §13 | Tooltips y tarjeta intro | ✅ Implementado |
| §14 | Autodetección IA competidores/aliados | ✅ Implementado |
| §15 | Precios $299 / $649 / $799 MXN | ✅ Implementado |
| §16 | Heatmap BestTime en dashboard (sin FODA web) | ✅ Implementado |
| §17 | NSE y lectura estratégica | ✅ Implementado |
| §18 | Aliados guiados (Premium) | ✅ Implementado |
| §19 | Vigencia operativa de comercios | ✅ Implementado |
| §20 | Pagos mock y beta VPS | ✅ Implementado |
| §21 | Endurecimiento seguridad VPS | ✅ Implementado |

---

## 1. Goals
* Permitir al usuario definir categorías personalizadas de competidores y aliados estratégicos durante la cotización.
* Estructurar y limitar la funcionalidad según el **tipo de reporte** adquirido (Básico, Pro, Premium) para maximizar el valor del pago único por análisis.
* Enriquecer el análisis del modelo LLM (SWOT, ROI, nichos) con estas preferencias.
* Ajustar dinámicamente el layout del PDF compilado de acuerdo a los aliados y atractores reales configurados.

## 2. Non-Goals
* No se modificará el proceso transaccional de Mercado Pago (monto e integración).
* No se alterará el mapa cartográfico nacional (PostGIS de INEGI) ni la geocodificación base.
* No se modificará la estructura de diseño geométrico de la portada.

## 3. Background
Actualmente, GeoViabilidad Hook asume de forma estricta un solo tipo de competidor (basado en el rubro) y tres tipos fijos de aliados (Bancos, Escuelas, Transporte). Sin embargo, un negocio de retail específico (como un gimnasio o una cafetería de especialidad) puede tener aliados muy específicos (como supermercados, oficinas o universidades) y competidores adyacentes que influyen directamente en su viabilidad. La personalización de estos ecosistemas comerciales representa una característica premium de gran valor.

## 4. Overview
La solución incorpora listas opcionales (`competidores_seleccionados` y `aliados_seleccionados`) que son validadas en el backend según el Tier del usuario. Se almacenan en base de datos serializadas a JSON.

**Refinamiento de la Experiencia de Usuario (UX)**: 
El usuario puede seleccionar hasta 5 competidores y 5 aliados en el panel izquierdo (modo gratuito). Al momento de iniciar la compra de un plan, el frontend recorta las listas seleccionadas de acuerdo a las limitaciones del plan adquirido (Básico: 1 competidor, Pro: 3 competidores, Premium: 5 competidores y 5 aliados) y muestra un resumen claro en el modal de pago de Mercado Pago antes de proceder. Esto incentiva de forma visual al usuario a actualizar a planes superiores (ej: Básico avisa que solo analizará el primero).

---

## 5. Detailed Design

### API & Validation (`schemas.py`)
```python
class PreferenciaCreate(BaseModel):
    ...
    competidores_seleccionados: list[str] | None = None
    aliados_seleccionados: list[str] | None = None

    @model_validator(mode="after")
    def validate_custom_selections(self) -> "PreferenciaCreate":
        tier = self.tier_adquirido
        comps = self.competidores_seleccionados
        allies = self.aliados_seleccionados

        if tier == "basico":
            if comps and len(comps) > 1:
                raise ValueError("El Tier Básico permite un máximo de 1 competidor personalizado.")
            if allies and len(allies) > 0:
                raise ValueError("El Tier Básico no permite personalizar aliados estratégicos.")
        elif tier == "pro":
            if allies and len(allies) > 0:
                raise ValueError("El Tier Pro no permite personalizar aliados estratégicos.")
            if comps and len(comps) > 3:
                raise ValueError("El Tier Pro permite un máximo de 3 competidores personalizados.")
        elif tier == "premium":
            if comps and len(comps) > 5:
                raise ValueError("El Tier Premium permite un máximo de 5 competidores personalizados.")
            if allies and len(allies) > 5:
                raise ValueError("El Tier Premium permite un máximo de 5 aliados personalizados.")
        return self
```

### Base de Datos (`models.py`)
Se agregan los atributos correspondientes a la clase ORM:
```python
    competidores_seleccionados = Column(Text, nullable=True) # Almacenado como JSON string
    aliados_seleccionados = Column(Text, nullable=True)      # Almacenado como JSON string
```

### Motor Analítico (`analytics.py`)
```python
# Dentro de procesar_calculo_analitico
# Si el usuario especificó competidores_seleccionados (Soportado en Básico, Pro y Premium):
competidores = []
if competidores_seleccionados:
    seen_ids = set()
    for custom_type in competidores_seleccionados:
        found = buscar_competidores(lat, lng, float(radio), custom_type)
        for c in found:
            c_key = (round(c["latitud"], 5), round(c["longitud"], 5)) # Detección de duplicados simple
            if c_key not in seen_ids:
                seen_ids.add(c_key)
                competidores.append(c)
else:
    # Comportamiento estándar
    competidores = buscar_competidores(lat, lng, float(radio), google_type)
```

### Lógica de Aliados en `analytics.py` (Premium)
```python
# Si se definieron aliados personalizados en Premium:
aliados_listado = []
if aliados_seleccionados:
    for custom_type in aliados_seleccionados:
        found_allies = buscar_competidores(lat, lng, float(radio), custom_type)
        # Enriquecer y unificar en aliados_listado
        ...
else:
    # Comportamiento por defecto (bancos, escuelas, transporte)
    ...
```

### PDF Dinámico (`reports.py`)
* La tabla de la página 10 del reporte Premium listará dinámicamente los aliados definidos por el usuario, mostrando su conteo y peso adaptativo.

## 6. Consideraciones
* **Cuotas de API de Google**: Cada categoría personalizada implica una llamada adicional a la API de Places. El límite de 3 (Pro) y 5 (Premium) previene el abuso y mantiene la latencia y costos bajo control.

## 7. Métricas y Pruebas
* **Test de Validación**: Pruebas en `test_suite.py` para asegurar que payloads inválidos (ej. enviar aliados en Tier Pro o más de 1 competidor en Básico) sean rechazados con `422 Unprocessable Entity` y mensajes user-centric correctos.

---

## 8. Corrección Estética y de Desbordamiento de PDF
Se identificó que el diseño original de la portada en `reports.py` generaba un desbordamiento invisible de pocos puntos debido a márgenes y espaciadores altos (`Spacer(1, 150)`, `Spacer(1, 100)`, `Spacer(1, 60)`). Esto desplazaba la fecha y el pie de página de la portada a la página 2 del PDF, dejando la página 2 vacía e incrementando la longitud total de cada tier de reporte por exactamente 1 página (Básico: 7 en lugar de 6, Pro: 11 en lugar de 10, Premium: 14 en lugar de 13).

### Solución Propuesta
1. Reducir los valores de espaciado en la portada de la siguiente forma:
   * `Spacer(1, 150)` -> `Spacer(1, 80)`
   * `Spacer(1, 100)` -> `Spacer(1, 50)`
   * `Spacer(1, 60)` -> `Spacer(1, 40)`
2. Mapear el tier de pago en español y con acentos para el campo "NIVEL ADQUIRIDO" en la portada (por ejemplo: `basico` -> `TIER BÁSICO`).
3. Actualizar la fecha de emisión en español a través del mapeo de meses preexistente.
4. Ajustar el validador de pruebas (`check_pdf_pages.py`) para utilizar `pypdf`, midiendo con precisión absoluta el número de páginas lógicas del archivo PDF compilado.

---

## 9. Eliminación de Terminología Técnica y Proveedores
Los usuarios finales son dueños de negocios e inversionistas inmobiliarios que buscan valor comercial, no especificaciones de software o de infraestructura en la nube. Mostrar términos como "AWS Bedrock", "ReportLab", "PostGIS" o "BestTime Peatonal" distrae al usuario y añade complejidad innecesaria.

### Cambios Detallados en Texto
1. **Reemplazo del término "Búfer"**: En la UI y PDF pasará a ser "Radio de Influencia" o "Zona de Estudio".
2. **Reemplazo de modelos de IA y servicios de AWS**:
   * "AWS Bedrock (Llama 3 70B)" -> "Motor Cognitivo de Inteligencia Artificial" o "IA Estratégica".
   * "Amazon S3 (cifrado KMS)" -> "Servidor de almacenamiento seguro y encriptado".
3. **Reemplazo de herramientas de compilación y base de datos**:
   * "ReportLab PDF Library" -> Eliminado del texto de descarga y diálogos.
   * "PostGIS" -> "Base de datos demográfica" o "Análisis geoespacial".
4. **Reemplazo de resolvedores sectoriales**:
   * "SCIAN de INEGI" -> "descriptores comerciales oficiales".

---

## 10. Caché de Reportes y Consistencia de Score SVA

### Problema Detectado
Actualmente, el Score de Viabilidad SVA y el diagnóstico FODA se calculan de manera independiente en dos flujos síncronos y asíncronos distintos:
1. **Background Task (`generar_informe_task`)**: Al aprobar la orden, ejecuta el motor analítico y LLM para compilar el PDF final.
2. **Dashboard API Route (`obtener_resultado_analisis`)**: Al ingresar a la visualización de resultados en la web, re-ejecuta el motor analítico y LLM en caliente.

Esto causa los siguientes inconvenientes:
- **Discrepancia de datos**: Al re-calcularlos en momentos diferentes, variaciones en APIs externas (Google Places, BestTime) o el comportamiento estocástico del LLM (Bedrock) provocan que el score y los textos en el panel web no coincidan exactamente con los que se encuentran impresos en el PDF compilado.
- **Rendimiento e Ineficiencia**: Cada carga del Dashboard web genera llamadas costosas de red y cobros de consumo a APIs propietarias.
- **Diferencia entre Vista Previa y Reporte de Pago**: La vista previa se calcula siempre bajo el Tier "Básico" por defecto (donde la afluencia peatonal BestTime se ignora, usando una constante de 55.0 puntos). Cuando el usuario adquiere un Tier Premium o personaliza competidores, el motor recalcula el score incorporando estos factores avanzados (afluencia real, competidores y aliados elegidos), lo que altera legítimamente la puntuación de viabilidad para reflejar las preferencias específicas de su plan.

### Solución Técnica
1. **Persistencia del Reporte**: Agregar columnas `resultado_json` y `foda_json` a la tabla `ordenes_pagos` en la base de datos PostgreSQL.
2. **Registro Único (Single Source of Truth)**: Modificar la tarea asíncrona de compilación (`generar_informe_task`) para guardar el resultado serializado de las analíticas geoespaciales y la respuesta del LLM en la base de datos.
3. **Lectura Inmediata**: Modificar el endpoint del dashboard para retornar directamente este JSON si está disponible, sirviendo como caché definitivo y asegurando 100% de consistencia entre la vista digital y el reporte PDF.

---

## 11. Búsqueda de Direcciones (Geocodificación Directa)

### 11.1 Metas
* Permitir al usuario teclear una dirección en lenguaje natural (calle, número, colonia, etc.) en lugar de depender únicamente de clics en el mapa.
* Autocompletar u ofrecer sugerencias coincidentes en una lista desplegable interactiva.
* Centrar automáticamente la vista del mapa e iniciar el análisis de viabilidad al seleccionar una dirección.

### 11.2 Diseño Detallado
* **Búsqueda Geográfica**: Se integra la API de Google Geocoding directa en el archivo [google_places.py](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/app/google_places.py) con el filtro `components=country:MX` para acotar los resultados de forma estricta a México.
* **API Route**: Se añade el endpoint `GET /api/analizar/buscar-direccion` en [routes_analytics.py](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/app/routes_analytics.py) que retorna una lista de candidatos `{"direccion": formatted_address, "latitud": lat, "longitud": lng}`.
* **Componente de UI Flotante**: Se inyecta un buscador `.map-search-box` con posicionamiento absoluto sobre la esquina superior izquierda del mapa `#map`.
* **Eventos Leaflet**: Al hacer clic en un resultado de búsqueda, el frontend actualiza el marcador con `state.centerMarker.setLatLng([lat, lng])` y llama a la función unificada `handleMapClick(lat, lng)`.
* **Coexistencia**: El mapa continúa escuchando clics con normalidad, de forma que el usuario puede usar ambos métodos indistintamente.

---

## 12. Consistencia y Calidad de Reportes (FODA, Competidores y Atractores)

### 12.1 Unificación de Criterios (SVA y IA)
* Se modificará la función `generar_analisis_foda` en [bedrock.py](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/app/bedrock.py):
  * En `DEV_MODE` (Mocks), las llaves `conclusion`, `recomendacion_roi`, `viabilidad_financiera`, `dictamen_final`, `inversion_estimada`, `tir_proyectada` y `roi_estimado` se calcularán de manera condicional basada en el valor de la clave `sva`.
  * En modo de producción, se inyectará una sección explícita en `system_prompt` que instruya al LLM a ajustar la viabilidad comercial y proyecciones financieras en base al score `SVA` enviado (ej: desaconsejar si es <50).
* Se simplificarán tecnicismos en [reports.py](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/app/reports.py):
  * "Áreas Geoestadísticas Básicas (AGEBs)" -> "cartografía urbana oficial del INEGI".
  * "Pilar Atractores e Inferencia" -> "Pilar de Atractores y Zonas de Interés".
  * "Índice de Saturación Comercial (ISC)" -> "Saturación de Competencia".
  * "Fricción Espacial Inmediata" -> "Competencia muy cercana".
  * "Fricción" en tablas de horarios -> "Competencia".

### 12.2 Mapeo Correcto de "Fast Food"
* En la función `buscar_competidores` de [google_places.py](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/app/google_places.py):
  * Se agregará un bloque de control condicional para interceptar `google_type == "fast_food"`.
  * Si coincide, se reasignará `google_type = "restaurant"` e inyectará `keyword = "fast food"` (si keyword es nulo). Esto forzará una búsqueda semántica de comida rápida en Google Places en vez de disparar una consulta sin tipo que regrese comercios ajenos como iglesias y estéticas.

### 12.3 Dinamismo en Atractores y Forecast
* En [reports.py](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/app/reports.py):
  * Se calculará el estatus `inf_est` de la Página 4 sumando dinámicamente los aliados elegidos del usuario si se personalizaron.
  * Se evaluará la suma total de atractores en la Página 10. Si es igual a 0, se reemplazará la frase predeterminada por una advertencia de que la zona carece de atractores significativos y que el negocio dependerá de demanda local y atracción autónoma.

### 12.4 Desglose de Competidores Adicionales en la Página 8
* En [reports.py](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/app/reports.py):
  * Al pie de la tabla de competidores directos, si `len(comp_list) > 4`, se añadirá un párrafo en letra pequeña (`fontSize=7.5`, `leading=9.5`) listando de forma explícita el nombre y tipo comercial de los primeros 15 competidores que no cupieron en la tabla, finalizando con un indicador de remanentes (ej. "y X más" si aplica).
  * Esto asegura la total transparencia del cálculo numérico del score sin impactar el límite de páginas de cada tier.

### 12.5 Estimación e Integración de Nivel Socioeconómico (NSE) — ✅ Implementado
* **Nueva Función en `analytics.py`**:
  * Se implementará la consulta espacial a `ageb_demographics` con pesos proporcionales de población para variables de censo 2020: `graproes`, `vivpar_hab`, `vph_autom`, `vph_inter` y `vph_pc`.
  * Se calculará el `nse_score` con ponderación de educación (40%) y equipamientos (60%).
  * Se definirá un fallback determinista para coordenadas basadas en un hash modular de 100 de latitud y longitud.
* **Integración del Prompt Estratégico (`bedrock.py`)**:
  * El LLM recibirá las métricas socioeconómicas estimadas del entorno (nivel, escolaridad promedio e internet %) para adaptar su FODA y estrategias recomendadas de precios.
  * Los textos de mock en `DEV_MODE` también variarán sus tickets recomendados y dictámenes según el NSE obtenido (ej: A/B = ticket $220-$350, D+ = ticket $55-$90).
* **Integración en PDF (`reports.py`)**:
  * La tabla de la Página 2 se expande a 4 columnas: `[SCORE VIABILIDAD, POBLACIÓN RESIDENTE, NIVEL SOCIOECONÓMICO, COMPETIDORES]`.
  * La tabla demográfica de la Página 3 agregará 4 filas para detallar la estimación de NSE, grado de escolaridad, % de internet y % de automóviles.
* **Integración en Web (`index.html` y `app.js`)**:
  * Se creará la cuarta tarjeta de KPI en la interfaz con ID `#kpi-nse-card`.
  * En `app.js` se bloqueará en la vista previa gratuita y se actualizará a la respuesta real de la orden aprobada.

---

## 13. Experiencia de Usuario: Contexto de la Aplicación y Ayudas Contextuales (Tooltips)

### 13.1 Objetivos de Negocio y UX
* Facilitar que usuarios no técnicos (inversionistas, emprendedores) entiendan el flujo operativo y el valor añadido de la geointeligencia comercial inmediatamente al abrir la SPA.
* Proveer explicaciones rápidas en lenguaje de negocio (evitando jerga técnica como "Leaflet", "PostgreSQL", "Bedrock" o "APIs") en cada input de configuración y tarjeta de KPI/gráficos del dashboard, mejorando la retención de usuarios y reduciendo la fricción en la conversión de ventas.

### 13.2 Especificación del Diseño de Componentes

#### A. Tarjeta de Contexto Introductorio
* **Posición**: En la parte superior de la barra de configuración izquierda (`#config-panel`), antes del formulario.
* **Componente**: `.intro-card` con estilo glassmorphic, bordes de `12px` y fondo translúcido.
* **Comportamiento**:
  * Incluye un botón de cierre superior derecho (`#close-intro-btn`).
  * Al hacer clic, se contrae suavemente (`max-height: 0`, `opacity: 0`, `padding: 0`) y desaparece del flujo visual.
  * El estado se registra en `localStorage.setItem("hide_intro_card", "true")`.
  * Al inicializar la página, la lógica de `app.js` lee el estado en `localStorage` y oculta inmediatamente el elemento si ya fue cerrado anteriormente.

#### B. Tooltips de Información
* **Estructura HTML**:
  ```html
  <span class="info-tooltip-wrapper">
      <span class="info-icon" aria-label="Información">ℹ️</span>
      <span class="tooltip-text">Texto descriptivo en lenguaje amigable...</span>
  </span>
  ```
* **Estilos CSS Puros**:
  * Se evitan scripts de JavaScript o librerías de terceros (como Popper.js o Tippy) para optimizar el rendimiento y peso de la SPA.
  * El contenedor `.info-tooltip-wrapper` actúa como el disparador relativo (`position: relative; display: inline-flex; align-items: center; margin-left: 5px; vertical-align: middle;`).
  * El `.info-icon` es un elemento interactivo con cursor `help`.
  * El globo `.tooltip-text` se dibuja en posición absoluta arriba del icono por defecto, centrado, con una micro-animación en hover (transición de opacidad y desplazamiento de 5px a 0px en 0.25s).
  * Soporte dinámico para temas:
    * En **Modo Oscuro** (por defecto): fondo oscuro (`rgba(15, 23, 42, 0.95)`), borde blanco translúcido y texto blanco.
    * En **Modo Claro** (bajo `body.light-theme`): fondo claro (`rgba(255, 255, 255, 0.98)`), borde oscuro translúcido y texto oscuro (`#0f172a`).
  * **Manejo de Bordes y Desbordamientos**:
    * Para evitar desbordamientos en los tooltips que están cerca del borde de la pantalla (como las tarjetas KPI laterales), se utilizarán clases de orientación `.tooltip-left`, `.tooltip-right`, y `.tooltip-bottom` que modifican las propiedades de alineación absoluta y el posicionamiento del pseudo-elemento flecha (`::after`).

---

## 14. Extensión de RFC: Autodetección de Competidores y Aliados por IA

### 14.1 Arquitectura e Interfaces
* Se inyectan en el HTML checkboxes de ID `#competidores-ia-auto` y `#aliados-ia-auto`.
* Al enviar el formulario, si la opción está activa, la lista enviada incluye la palabra clave `"ia_auto"`.
* La base de datos guarda este valor serializado en JSON en la columna `competidores_seleccionados` o `aliados_seleccionados` de `ordenes_pagos`.

### 14.2 Flujo Backend
* `procesar_calculo_analitico` intercepta la palabra `"ia_auto"` en las listas.
* Si se encuentra `"ia_auto"` en competidores, se remueve de la lista de Places y se busca por defecto según el rubro, pero se mantiene la bandera `competidores_ia_auto = True`.
* Si se encuentra en aliados, se busca la tríada por defecto (bancos, escuelas, transporte), pero se mantiene la bandera `aliados_ia_auto = True`.
* La tarea de fondo pasa estas banderas a `generar_analisis_foda` en `bedrock.py`.
* El prompt del LLM recibe la instrucción de autodetectar, justificar y redactar dinámicamente qué comercios del entorno son aliados o competidores de alto impacto comercial en la sección de FODA y conclusión.

---

## 15. Actualización de Precios de Planes de Geomarketing — ✅ Implementado
* **Objetivo:** Adecuar las tarifas comerciales a la nueva propuesta de valor que integra información real del INEGI desde la versión gratuita y autodetección por IA en reportes avanzados.
* **Nuevas Tarifas:**
  - **Plan Básico:** $299.00 MXN
  - **Plan Pro:** $649.00 MXN
  - **Plan Premium:** $799.00 MXN
* **Impacto en Sistemas:**
  - **Backend (`payments.py`):** Modificar el diccionario `PRECIOS_TIER` de mapeo de precios.
  - **Frontend (`index.html` y `app.js`):** Ajustar leyendas y botones de compra, así como el importe dinámico desplegado en el modal de confirmación de compra.
  - **Tests (`test_suite.py` y mocks):** Adecuar las validaciones y aserciones de precios esperados para los endpoints de transacciones.

---

## 16. Reemplazo de FODA y ROI por Mapa de Calor Peatonal (BestTime) en el Dashboard — ✅ Implementado
* **Objetivo:** Reemplazar el análisis estratégico cualitativo (FODA) y las tarjetas financieras (ROI) en el Dashboard Web por una visualización de ciencia de datos: un mapa de calor dinámico semanal por horas que muestre los picos de tránsito peatonal de la zona de estudio.
* **Especificaciones del Mapa de Calor:**
  - **Formato:** Tabla de 7 días (Lunes a Domingo) y 15 columnas de horas (08:00 a 22:00) para asegurar responsividad.
  - **Gradiente:** Celdas con opacidad de fondo proporcional al porcentaje de tránsito obtenido de la API de BestTime (`rgba(37, 99, 235, alpha)`).
  - **Tooltips:** Hover en cada celda muestra detalles (ej. "Lunes 12:00 - Tránsito: 70%").
* **Impacto en Sistemas:**
  - **Backend (`besttime.py` y `analytics.py`):** Recuperar o calcular la matriz `afluencia_semanal` (7x24 horas) en la respuesta del análisis de afluencia peatonal, implementando un extractor seguro y fallback generativo.
  - **Frontend (`index.html`, `index.css`, `app.js`):** Remover elementos de FODA y ROI, inyectar el contenedor `#heatmap-container`, estilizar la cuadrícula del mapa de calor, renderizar los datos y aplicar las reglas de desenfoque (`applyBlurRules(tier)`) para bloquearlo en Gratuito y Básico (desbloqueado en Pro y Premium).
  - **Consistencia:** Mantener intacta la lógica de generación del PDF descargable (que conserva FODA y ROI en el reporte impreso) y las pruebas del backend para proteger la validez del producto de pago y compatibilidad.

**Estado:** ✅ Implementado (`frontend/app.js` heatmap, `applyBlurRules`, `app/besttime.py`).

---

## 17. Nivel Socioeconómico (NSE) y Lectura Estratégica

### 17.1 NSE — **Cerrado / Implementado**
* **Módulo:** `app/nse.py` consulta columnas censales INEGI 2020 en PostGIS (`graproes`, `vivpar_hab`, `vph_autom`, `vph_inter`, `vph_pc`).
* **Integración:** `calcular_nse()` en `procesar_calculo_analitico`; fallback determinista en DEV; `construir_nse_sin_datos()` en prod sin censo.
* **Dashboard:** cuarta tarjeta KPI `#kpi-nse-card` (bloqueada en vista previa, desbloqueada post-pago).
* **PDF:** tablas páginas 2–3 con etiqueta NSE, escolaridad, internet %, autos %.
* **LLM:** prompt y respaldo cuantitativo adaptan ticket y dictamen al NSE.
* **Contrato:** `docs/SPEC_DRIVEN_CONTRACT_NSE.md`.

### 17.2 Lectura estratégica (reemplazo parcial de FODA en web) — **Cerrado**
* **Módulo:** `app/lectura_estrategica.py` genera bloques 3+3+3: fortalezas, oportunidades, consideraciones + conclusión.
* **Dashboard:** sección "Lectura estratégica" post-pago; FODA clásico solo en PDF.
* **Tests:** cobertura en `tests/test_suite.py`.

---

## 18. Aliados Guiados (Premium) — **Cerrado / Implementado**

* **Objetivo:** Permitir al usuario Premium configurar aliados mediante cuestionario guiado sin depender de listas manuales de tipos Google.
* **API:** `POST /api/analizar/aliados/sugerir` → motor determinista `app/aliados_guiados.py` (sin LLM).
* **Persistencia:** columnas `modo_analisis_aliados`, `config_aliados_guiados` en `ordenes_pagos`.
* **Validación:** modo `guiado` solo en tier `premium` (`schemas.py`); no combinable con `aliados_seleccionados` manual.
* **UI:** flujo de 3 pasos en `frontend/index.html` + lógica en `app.js`.
* **Contrato:** `docs/SPEC_DRIVEN_CONTRACT_ALIADOS_GUIADOS.md`.

---

## 19. Vigencia Operativa de Comercios — **Cerrado / Implementado**

### 19.1 Metas
* Indicar si competidores y aliados detectados siguen operando con base en Google Places (`business_status`) y antigüedad de reseñas.
* Excluir del ISC comercios cerrados permanentemente.
* Mostrar disclaimers claros en dashboard y PDF.

### 19.2 Diseño (`app/vigencia_comercio.py`)
* **Niveles:** `alta`, `media`, `baja`, `inactivo`, `sin_verificar`.
* **Señales:** `CLOSED_PERMANENTLY`, `CLOSED_TEMPORARILY`, fecha de reseña más reciente (`reviews_sort=newest`).
* **Enriquecimiento:** `enriquecer_lugares_con_vigencia()` en `google_places.py` (hasta 15 competidores, 10 aliados).
* **Analytics:** `competidores_activos_conteo`; ISC omite `activo_para_analisis = false`.
* **UI:** badges de vigencia en tabla de competidores; `VIGENCIA_DISCLAIMER` en `app.js`.
* **PDF:** columna Vigencia en tablas; textos aclaratorios en `reports.py`.
* **Tests:** `test_vigencia_comercio_cerrado_y_reciente`, `test_calcular_isc_excluye_cerrados`.

---

## 20. Pagos Simulados y Entorno Beta VPS — **Cerrado / Implementado**

* **Config:** `PAYMENTS_MOCK` en `app/config.py` (default `True` con `DEV_MODE`).
* **Endpoints:** `POST /api/pagos/webhook-mock` solo disponible con mock activo.
* **Frontend:** modal "CONFIRMAR PAGO SIMULADO"; manejo de errores en `openPaymentModal`.
* **Health:** `/health` expone `payments_mock: true/false`.
* **Despliegue beta:** VPS `135.181.30.179`, `/opt/viabilidad-negocios`, `docker-compose.yml`, red `geo-analisis_geo-network`.
* **Pendiente H4:** Mercado Pago live + Cognito JWT real (`auth.py` retorna `501` fuera de DEV).

---

## 21. Endurecimiento de Seguridad VPS — **Cerrado / Implementado**

* **Objetivo:** Exponer solo frontends públicos; aislar DB y paneles admin.
* **Puertos públicos:** `8000` (GeoViabilidad), `22` (SSH limitado).
* **Internos (127.0.0.1):** admin Streamlit `8501`, herramientas auxiliares.
* **PostgreSQL:** sin mapeo al host; solo red Docker.
* **Firewall:** UFW + reglas `DOCKER-USER` en `/etc/ufw/after.rules`.
* **Scripts:** `scripts/vps-hardening.sh`, `scripts/vps-recover-ssh.sh`, `scripts/vps-ufw-cleanup.sh`, `infra/vps/`.
* **Admin remoto:** túnel SSH `ssh -L 8501:127.0.0.1:8501 root@<vps>`.

---

## 22. UI temporal y flags de producto

| Flag / decisión | Valor actual | Notas |
|-----------------|--------------|-------|
| `UI_FEATURES.intencionesNegocio` | `false` | Oculta sección intenciones; backend acepta campo |
| Textos checkboxes detección | Actualizados Jun 2026 | "giro/rubro" y "aliados automáticos" |
| `NOTA_BESTTIME_TRAFICO` | En PDF | Aclara origen peatonal BestTime |
| Cognito en frontend | Mock `Bearer mock-jwt-*` | Sin integración SDK Cognito en cliente |

---
