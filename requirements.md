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

## 6. Requerimientos de Consistencia y Calidad de Reportes (FODA, Competidores y Atractores)

### RF-17: Unificación de Criterios y Diagnóstico Dinámico de IA
* Se debe garantizar la alineación semántica entre la puntuación numérica SVA y todos los textos cualitativos generados por la IA en el PDF (Diagnóstico Estratégico en la Página 5 y Viabilidad Financiera en la Página 12) y en el Dashboard.
* **Score de Viabilidad Bajo (< 50)**: Todo diagnóstico, recomendación de rentabilidad, viabilidad financiera y dictamen final debe reflejar un escenario de **alto riesgo comercial** o viabilidad desfavorable.
* **Score de Viabilidad Moderado (50 - 79)**: Todo diagnóstico debe reflejar una viabilidad **moderada**, condicionando el éxito a la diferenciación comercial frente a competidores.
* **Score de Viabilidad Excelente (>= 80)**: Todo diagnóstico debe ser **favorable** y con una proyección de alta rentabilidad comercial.
* Esto debe aplicar tanto para las respuestas simuladas en modo de desarrollo (`DEV_MODE=True`) como para las llamadas reales a los LLM (a través del prompt de sistema).

### RF-18: Corrección del Pilar Atractores e Inferencia en Portada y Reporte
* El estatus del pilar de atractores en la Página 4 ("Detectados X bancos, Y escuelas y Z transporte") debe reflejar los conteos de los aliados seleccionados por el usuario si se utilizaron selecciones personalizadas, en lugar de mostrar siempre 0 bancos/escuelas/transporte si no se consultaron los tipos por defecto.
* La conclusión del Forecast del Mercado en la Página 10 del reporte no debe asumir de forma estática una "confluencia de atractores consolidados" si la zona tiene un conteo total de atractores de 0. En este escenario, debe advertir de manera realista sobre la ausencia de magnetos comerciales y recomendar estrategias de atracción de tráfico autónomas.

### RF-19: Mapeo y Depuración de Competidores ("Fast Food")
* El motor de Google Places debe mapear correctamente las categorías de competidores personalizadas. Específicamente, el tipo `fast_food` (no admitido nativamente por la API de Google) debe convertirse en el backend a `restaurant` con la palabra clave `"fast food"` para evitar búsquedas sin filtro que incorporen establecimientos no relacionados (iglesias, barberías, florerías) en la lista de competidores directos.

### RF-20: Desglose Completo de Competidores en PDF (Evitar Desbordamiento)
* Para resolver la discrepancia entre el número total de competidores y los mostrados en la tabla, el reporte en PDF en su Página 8 (Pro/Premium) debe desglosar explícitamente en un párrafo de texto compacto (en letra pequeña al pie de la tabla) los nombres y giros de todos los competidores adicionales detectados que no cupieron en la tabla de 4 filas.
* Se debe asegurar que esta información adicional se organice en un formato compacto (ej: lista separada por comas de hasta 15 elementos adicionales) para que no altere el presupuesto de páginas del reporte (Básico: 6, Pro: 10, Premium: 13 páginas).

### RF-21: Análisis y Reporte de Nivel Socioeconómico (NSE)
* El motor analítico en el backend debe calcular de forma dinámica el Nivel Socioeconómico (NSE) del área de estudio consultando la tabla `ageb_demographics` en PostgreSQL + PostGIS (que contiene variables censales detalladas como escolaridad promedio `graproes`, internet `vph_inter`, automóviles `vph_autom`, computadoras `vph_pc`, etc. a nivel de AGEB).
* Si las variables en la tabla `ageb_demographics` no están disponibles en la zona (retornan NULL o cero registros), el sistema debe aplicar un mecanismo de fallback determinista (usando un hash basado en las coordenadas consultadas) para asignar un nivel y porcentajes simulados consistentes de equipamiento.
* El NSE estimado debe ser incorporado y expuesto de las siguientes maneras:
  1. **En el prompt de IA**: Incluir el nivel socioeconómico predominante (y sus métricas de escolaridad y equipamiento) en los datos de entorno enviados a la IA para que el FODA, la estrategia de precios y el ROI se adapten al poder adquisitivo local.
  2. **En el Dashboard Web**: Agregar una cuarta tarjeta de KPI para "Nivel Socioeconómico" que permanezca bloqueada en la vista previa gratuita y muestre el nivel (ej: `"C+ (Medio Alto)"`) una vez pagado el reporte.
  3. **En el PDF - Página 2**: Ampliar la tabla de KPI principales para incorporar el Nivel Socioeconómico en una cuarta columna de la tabla (`colWidths=[126, 126, 126, 126]`).
  4. **En el PDF - Página 3**: Incluir en la tabla demográfica detallada del INEGI 2020 cuatro filas nuevas con los valores reales (o fallbacks) de: Nivel Socioeconómico Predominante, Grado Promedio de Escolaridad, Conexión a Internet en Viviendas y Viviendas con Automóvil.

## 7. Requerimientos de Experiencia de Usuario: Contexto de la App y Ayudas Contextuales (Tooltips)

### RF-22: Tarjeta Introductoria de Contexto (Descripción de la App)
* Se debe agregar un componente visual interactivo del tipo tarjeta glassmorphic en la parte superior del panel izquierdo (antes de la Configuración del Negocio) o como cabecera dedicada en la interfaz.
* Esta tarjeta debe explicar de manera premium, clara y concisa:
  * **Propósito (Qué es)**: GeoViabilidad Hook es una plataforma de geointeligencia y geomarketing que analiza la viabilidad comercial de un punto en México a través de datos demográficos oficiales, presencia de competidores y flujos de afluencia peatonal.
  * **Uso (Cómo funciona)**: Un proceso de 3 pasos:
    1. **Ubicar**: Hacer clic en el mapa de México o buscar una dirección física.
    2. **Configurar**: Elegir el giro del negocio, definir el radio de influencia y describir las intenciones del local.
    3. **Analizar**: Ejecutar el análisis para revisar los KPIs interactivos y adquirir reportes ejecutivos en PDF.
* Debe ser colapsable o cerrable mediante un botón de cierre discreto, guardando el estado de visualización en `localStorage` para no saturar al usuario recurrente.

### RF-23: Iconos y Tooltips de Información en Secciones Clave
* Se debe agregar un símbolo de información `ℹ️` (o un botón de información interactivo) junto a las etiquetas de los siguientes campos y secciones clave:
  * **En el Formulario de Configuración (Panel Izquierdo)**:
    * *Giro / Rubro del Negocio*: Explica que el rubro determina el tipo de competidor y el perfil de mercado objetivo.
    * *Radio de Influencia*: Explica que delimita el radio geográfico en metros para el cálculo de estadísticas censales e identificación de locales.
    * *Intenciones Específicas*: Explica que describe las metas y nichos para que la Inteligencia Artificial analice el FODA cruzado.
    * *Competidores Personalizados*: Explica que permite buscar y evaluar negocios específicos en la zona que compiten directamente contigo.
    * *Aliados Estratégicos*: Explica que evalúa negocios complementarios que potencian y atraen flujo comercial indirecto.
  * **En el Dashboard de Resultados (KPIs y Gráficos)**:
    * *Score de Viabilidad SVA*: Explica la métrica ponderada del 0 al 100 de idoneidad del punto (población, competencia y peatones).
    * *Demanda Residente*: Explica que representa la población cercana obtenida de cartografías urbanas oficiales.
    * *Competidores Locales*: Explica la densidad de competidores directos detectados en el radio elegido.
    * *Nivel Socioeconómico (NSE)*: Explica el indicador de poder adquisitivo y equipamiento promedio de los hogares del área.
    * *Distribución de Competidores por Rating*: Explica cómo se clasifican los competidores de la zona según valoraciones de clientes.
    * *Atractores de Tráfico y Aliados*: Explica el volumen e impacto comercial de los magnetos de tráfico (bancos, escuelas, transporte).
    * *Diagnóstico Estratégico Inteligente con IA (FODA)*: Explica que es un análisis situacional personalizado y cruzado elaborado por nuestro motor cognitivo.
* **Comportamiento Estético**:
  * Al pasar el cursor (hover) sobre el icono `ℹ️`, se debe desplegar un tooltip flotante estilizado.
  * Los tooltips deben contar con un diseño premium: fondo semi-translúcido con desenfoque (`backdrop-filter`), bordes curvos, sombras sutiles y textos con la tipografía oficial (Inter/Outfit).
  * Deben ser 100% responsivos y auto-ajustables en posición para no salirse de la pantalla.
  * Deben adaptarse al modo claro y oscuro manteniendo un excelente contraste y legibilidad.
  * No deben contener referencias a nombres de librerías, servidores o APIs técnicas.

## 8. Requerimientos de Autodetección de Competidores y Aliados por IA

### RF-24: Opción de Autodetección por IA en Competidores y Aliados
* Se debe agregar una opción interactiva (ej: checkbox especial `"Autodetectar por IA"`) en los contenedores de selección de Competidores Personalizados y Aliados Estratégicos.
* Esta opción debe indicar explícitamente al usuario que, si se selecciona, la Inteligencia Artificial determinará qué comercios de la zona pueden ser aliados o competidores de forma dinámica y adaptada al negocio.

### RF-25: Inhabilitación de Entradas Convencionales
* Al activar la autodetección por IA, el resto de los checkboxes de esa categoría (competidores o aliados) y el campo de texto libre respectivo deben desmarcarse, deshabilitarse e inactivarse visualmente mediante una transición suave de opacidad. Esto evita configuraciones contradictorias.
* Al desactivarse, todos los controles normales deben volver a habilitarse, respetando los límites de selección asociados al plan (Tier).

### RF-26: Integración Analítica y Generación Estratégica
* El backend debe recibir el indicador `"ia_auto"` en las listas de selección.
* Si se activa, el backend calculará el entorno numérico usando los tipos de comercio por defecto adaptados al rubro (para las búsquedas geográficas de Google Places e indicador SVA).
* El prompt estratégico enviado al LLM (Bedrock/Groq) recibirá la instrucción directa de identificar, fundamentar y detallar de forma dinámica en su reporte los competidores y aliados clave en la zona, sin limitarse a una lista rígida seleccionada a mano.

## 9. Requerimientos de Visualización de KPIs del INEGI y Desenfoque de Marketing (Blur)

### RF-27: Visualización de KPIs del INEGI en Vista Previa Gratuita
* Los 3 KPIs del Dashboard (Score SVA, Demanda Residente/Población y Competidores Locales) deben mostrar siempre los datos reales calculados a partir de las fuentes del INEGI y Google Places, eliminando el bloqueo estático `"🔒 Bloqueado"` en la vista previa gratuita.
* El frontend consumirá el endpoint real `/api/analizar/previa` para poblar estos KPIs de inmediato al hacer clic en "Analizar Ubicación".

### RF-28: Cálculo General de Gráficos y Atractores
* El backend debe calcular y enviar siempre la lista completa de competidores directos, atractores de tráfico/aliados y curvas de afluencia peatonal (Places y BestTime) para todos los tiers de pago y para la vista previa gratuita, eliminando la inhabilitación del cálculo en el backend.

### RF-29: Desenfoque de Marketing (Blur) de Gráficos y Tablas
* El frontend aplicará un efecto visual de desenfoque de CSS (Blur de 8px, reducción de opacidad y escala de grises sutil) a las secciones del gráfico de competidores locales y la tabla de atractores de tráfico según el nivel de privilegios del Tier activo:
  - **Vista Previa Gratuita / Básico:** Ambos elementos (gráfico y tabla) aparecen desenfocados, mostrando el mensaje de bloqueo y candado correspondiente sobrepuesto.
  - **Tier Pro:** El gráfico de competidores se muestra nítido; la tabla de atractores se mantiene con blur y candado.
  - **Tier Premium:** Ambos elementos se muestran nítidamente desbloqueados.
