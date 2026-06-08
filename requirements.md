# Requerimientos: Personalización de Aliados y Competidores en Reportes

## 1. Descripción
Este documento define los requerimientos funcionales y no funcionales para permitir al usuario seleccionar qué tipos de comercios actúan como sus competidores y aliados estratégicos. El sistema debe procesar esta información geoespacialmente, integrarla en el modelo cognitivo (LLM) y plasmarla dinámicamente en el reporte ejecutivo PDF según el nivel de pago.

## 2. Requerimientos Funcionales

### RF-01: Selección de Categorías desde la Entrada
* El panel izquierdo permite al usuario seleccionar hasta 5 competidores y hasta 5 aliados estratégicos de forma interactiva en la vista previa gratuita.
* El endpoint de creación de preferencias de pago acepta dos listas opcionales de strings:
  * `competidores_seleccionados`: Categorías de Google Places a catalogar como competidores.
  * `aliados_seleccionados`: Categorías de Google Places a catalogar como aliados.
* Al iniciar el checkout de un plan, el frontend recorta las listas seleccionadas por el usuario de acuerdo a los límites del plan adquirido y muestra un resumen de confirmación en el modal.

### RF-02: Distribución y Límites por Tier de Pago
* **Tier Básico**:
  * Permite personalizar **hasta 1 competidor** (se toma el primero de la lista del usuario).
  * No permite personalizar aliados (se omite la sección).
* **Tier Pro**:
  * Permite personalizar **hasta 3 competidores** (se toman los primeros 3 de la lista del usuario).
  * No permite personalizar aliados (se omite la sección).
* **Tier Premium**:
  * Permite personalizar **hasta 5 competidores y hasta 5 aliados** (se toman todos los elementos seleccionados).
  * Toda la información en el PDF (mapas, tablas de competidores, tablas de atractores POIs) y el prompt de IA se adapta a estas selecciones.

### RF-03: Consulta Espacial Dinámica
* El motor de analítica debe realizar consultas independientes a la API de Google Places para cada una de las categorías seleccionadas por el usuario que correspondan a su plan.
* Debe unificar y calcular las distancias correspondientes y el Índice de Saturación Comercial (ISC) en base a todos los competidores encontrados de las categorías solicitadas.

### RF-04: Análisis Estratégico de IA Adaptativo
* El prompt enviado a Amazon Bedrock/Groq debe incluir explícitamente las listas de aliados y competidores elegidos y sus conteos geodésicos para que el LLM los use en la redacción del FODA cruzado, la segmentación y el ROI.

### RF-05: PDF Ejecutivo Dinámico
* La tabla de atractores (POIs) en la página 10 y la tabla de competidores en la página 8 deben generar sus filas dinámicamente basándose en los tipos de comercios seleccionados por el usuario de acuerdo al plan.

## 3. Requerimientos No Funcionales

### RNF-01: Rendimiento
* Las consultas a la API de Google Places para múltiples categorías deben realizarse de forma segura, y el backend asíncrono debe manejar fallos parciales sin abortar el reporte.

### RNF-02: Persistencia
* Las elecciones del usuario deben guardarse en formato JSON serializado en la tabla `ordenes_pagos`.

## 4. Requerimientos de Formato y Layout del PDF (Ajustes Estéticos)

### RF-06: Formato del Título de la Portada
* El título secundario en la portada del PDF debe aparecer en mayúsculas completas ("ANÁLISIS ESPACIAL Y DIAGNÓSTICO DE GEOMARKETING INTELIGENTE EN MÉXICO") o mayúsculas convencionales con acentuación correcta, de forma estandarizada.

### RF-07: Formato de Fecha en Español
* El mes de la fecha de emisión en la portada del PDF debe aparecer en español de manera explícita (por ejemplo: "05 de junio de 2026"), evitando nombres de meses en inglés.

### RF-08: Alineación del Tier de Compra en el PDF
* El campo "NIVEL ADQUIRIDO" en la portada del PDF debe reflejar exactamente el plan adquirido por el usuario en español y mayúsculas (por ejemplo: "TIER BÁSICO", "TIER PRO", "TIER PREMIUM").
* Las secciones y páginas del reporte generado deben truncarse y limitarse exactamente según las páginas estipuladas para cada tier de pago (Básico: 6 páginas, Pro: 10 páginas, Premium: 13 páginas).

### RF-09: Diseño de Portada Sin Desbordamiento
* Los márgenes y espaciados (`Spacer`) en la portada del PDF deben optimizarse para evitar desbordar el texto hacia la página 2, garantizando que la portada ocupe exactamente 1 página.

### RF-10: Eliminación de Terminología Técnica (Jergas y Proveedores)
* Ningún texto visible para el usuario en la interfaz web de la aplicación (SPA) ni en el reporte PDF descargable debe mencionar nombres de marcas o tecnologías de desarrollo (tales como AWS Bedrock, Amazon S3, ReportLab, PostGIS, Google Places, BestTime, Llama 3, etc.).
* El término "Búfer" debe ser reemplazado por "Radio de Influencia" o "Zona de Estudio" en todos los casos user-facing.
* El concepto de "Huff Gravity Model" debe ser denominado "Modelo de Atracción Comercial".
* El descriptor "SCIAN" debe reemplazarse por "descriptores oficiales" o "giros comerciales oficiales".

### RF-11: Consistencia de Puntuaciones y Caché de Reportes
* El Score de Viabilidad SVA y todos los indicadores cuantitativos/estratégicos deben ser exactamente iguales en el Dashboard Web que en el reporte PDF descargable.
* Una vez que la orden ha sido pagada y procesada por primera vez por la tarea en segundo plano (`generar_informe_task`), todos los datos de métricas y la conclusión de IA (FODA) deben persistir de forma estructurada en la base de datos PostgreSQL.
* El endpoint de visualización de resultados de pago (`/api/analizar/resultado/{orden_id}`) debe recuperar los datos directamente del caché almacenado en la base de datos, eliminando la duplicación en la ejecución de cálculos geoespaciales y llamadas a modelos cognitivos (LLM).

## 3. Requerimientos No Funcionales

### RNF-01: Rendimiento
* Las consultas a la API de Google Places para múltiples categorías deben realizarse de forma segura, y el backend asíncrono debe manejar fallos parciales sin abortar el reporte.

### RNF-02: Persistencia
* Las elecciones del usuario deben guardarse en formato JSON serializado en la tabla `ordenes_pagos`.

### RNF-03: Optimización de Costos y Latencia (Consistencia de APIs)
* Se debe evitar la consulta redundante de APIs de terceros (Google Places, BestTime) y del motor LLM (AWS Bedrock) al recargar o consultar repetidamente el dashboard de resultados. La recuperación del reporte almacenado debe tardar menos de 100 ms tras el precalculo.

## 5. Requerimientos para Búsqueda de Direcciones (Geocodificación Directa)

### RF-12: Entrada de Búsqueda de Dirección (Buscador)
* Se debe proporcionar un campo de entrada de texto (`#map-search-input`) y un botón de búsqueda (`#map-search-btn`) posicionados en la interfaz de la aplicación, preferentemente sobre el visor de mapa.
* Debe permitir al usuario escribir cualquier dirección, calle, colonia o código postal en lenguaje natural.

### RF-13: Autocompletado y Sugerencias de Ubicaciones
* Al iniciar la búsqueda, la aplicación consultará al backend de forma segura para obtener una lista de ubicaciones posibles que coincidan con la entrada.
* Los resultados se mostrarán de forma visual en un listado desplegable (`#map-search-results`) bajo el input de búsqueda.

### RF-14: Restricción a Territorio Nacional
* El servicio de geocodificación directa en el backend debe restringir los resultados estrictamente a la República Mexicana (usando filtros de componentes de Google `country:MX`), evitando que términos de búsqueda ambiguos devuelvan coordenadas de otros países.

### RF-15: Sincronización y Centrado del Mapa
* Al seleccionar cualquiera de las sugerencias devueltas por el buscador:
  * El mapa Leaflet debe centrarse con una animación fluida (`setView`) en la coordenada seleccionada con un zoom apropiado (nivel 16).
  * Debe dispararse el flujo de colocación de pin principal, cálculo del círculo de radio de influencia y resolución de dirección postal estructurada para el banner superior (exactamente igual a si se hubiese hecho clic directo).

### RF-16: Coexistencia de Interacción Map-Buscador
* La funcionalidad de hacer clic en cualquier punto del mapa debe continuar operativa y sin alteraciones, conviviendo plenamente con la búsqueda por dirección de texto.




