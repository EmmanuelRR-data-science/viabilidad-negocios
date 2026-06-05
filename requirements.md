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

