# Requerimientos: Personalización de Aliados y Competidores en Reportes

## 1. Descripción
Este documento define los requerimientos funcionales y no funcionales para permitir al usuario seleccionar qué tipos de comercios actúan como sus competidores y aliados estratégicos. El sistema debe procesar esta información geoespacialmente, integrarla en el modelo cognitivo (LLM) y plasmarla dinámicamente en el reporte ejecutivo PDF según el nivel de pago.

## 2. Requerimientos Funcionales

### RF-01: Selección de Categorías desde la Entrada
* El endpoint de creación de preferencias de pago debe aceptar dos listas opcionales de strings:
  * `competidores_seleccionados`: Categorías de Google Places a catalogar como competidores.
  * `aliados_seleccionados`: Categorías de Google Places a catalogar como aliados.
* Estas categorías deben ser validadas contra una lista permitida de tipos de Google Places (ej. `cafe`, `gym`, `laundry`, `supermarket`, etc.).

### RF-02: Distribución por Tier de Pago
* **Tier Básico**:
  * No se permite ninguna personalización. El sistema utiliza el resolvedor automático por defecto para el competidor y omite la sección de aliados.
* **Tier Pro**:
  * Permite personalizar **hasta 3 competidores**.
  * No permite personalizar aliados (se cargan los genéricos: Bancos, Escuelas, Transporte, o se omiten según plantilla).
* **Tier Premium**:
  * Permite personalizar **hasta 5 competidores y hasta 5 aliados**.
  * Toda la información en el PDF (mapas, tablas de competidores, tablas de atractores POIs) y el prompt de IA se adapta a estas selecciones.

### RF-03: Consulta Espacial Dinámica
* El motor de analítica debe realizar consultas independientes a la API de Google Places para cada una de las categorías seleccionadas por el usuario.
* Debe unificar y calcular las distancias correspondientes y el Índice de Saturación Comercial (ISC) en base a todos los competidores encontrados de las categorías solicitadas.

### RF-04: Análisis Estratégico de IA Adaptativo
* El prompt enviado a Amazon Bedrock/Groq debe incluir explícitamente las listas de aliados y competidores elegidos y sus conteos geodésicos para que el LLM los use en la redacción del FODA cruzado, la segmentación y el ROI.

### RF-05: PDF Ejecutivo Dinámico
* La tabla de atractores (POIs) en la página 10 y la tabla de competidores en la página 8 deben generar sus filas dinámicamente basándose en los tipos de comercios seleccionados por el usuario.

## 3. Requerimientos No Funcionales

### RNF-01: Rendimiento
* Las consultas a la API de Google Places para múltiples categorías deben realizarse de forma segura, y el backend asíncrono debe manejar fallos parciales sin abortar el reporte.

### RNF-02: Persistencia
* Las elecciones del usuario deben guardarse en formato JSON serializado en la tabla `ordenes_pagos`.
