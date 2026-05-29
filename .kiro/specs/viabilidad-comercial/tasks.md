# Plan de Ejecución (tasks.md)

Este es el checklist atómico e incremental para guiar el desarrollo de **GeoViabilidad Hook** bajo la arquitectura empresarial de **AWS**. Se trabajará en una tarea a la vez, marcando el estado con `- [/]` (En Progreso) y `- [x]` (Completado).

---

## 🛠️ Fase 1: Entorno de Desarrollo y Base de Datos (PostGIS)
*   [x] **Tarea 1.1**: Inicializar el entorno virtual de Python utilizando **uv** y configurar el linter/formateador **Ruff** en el workspace.
*   [x] **Tarea 1.2**: Configurar y levantar una base de datos **PostgreSQL + PostGIS** local mediante Docker para emular el entorno de RDS PostgreSQL (db.t4g.micro) de AWS.
*   [x] **Tarea 1.3**: Diseñar y ejecutar la migración inicial de base de datos para crear la tabla geodemográfica (`agebs_demografia`) con su respectivo índice espacial GIST.
*   [x] **Tarea 1.4**: Crear la tabla transaccional (`ordenes_pagos`) para gestionar los estados de cobro y derechos adquiridos (*Entitlements*), así como la tabla `categorias_cruce` con la semilla inicial SCIAN <-> Google Places.
*   [x] **Tarea 1.5**: Diseñar y ejecutar la migración para crear las tablas auxiliares `ingesta_tareas` (para el control del progreso de carga asíncrona estatal) y `cache_analisis_api` (para la persistencia y caché de peticiones a APIs externas y Bedrock).

---

## 🔑 Fase 2: Panel de Administración e Ingesta Geoespacial (INEGI)
*   [x] **Tarea 2.1**: Desarrollar el endpoint administrativo `POST /api/admin/ingestar` en la API de FastAPI que reciba archivos multipart.
*   [x] **Tarea 2.2**: Programar el pipeline de procesamiento asíncrono en Python utilizando **GeoPandas** y **Fiona** de forma fragmentada (chunking por iterador). Deberá descomprimir temporalmente los archivos Shapefile de AGEBs estatales y censos CSV, reproyectar las coordenadas al CRS EPSG:4326 (WGS84), e insertar por lotes de 1,000 en `agebs_demografia` liberando memoria de forma agresiva para evitar OOM en la base de datos db.t4g.micro y la EC2.
*   [x] **Tarea 2.3**: Desarrollar los endpoints de monitoreo administrativo `/api/admin/ingestar/estado/{id}` (para reportar el avance en tiempo real) y `/api/admin/coberturas` (para listado e indexación / borrado).
*   [x] **Tarea 2.4**: Maquetar la interfaz dedicada `/admin` con diseño premium Dark Glassmorphism, incorporando una dropzone de carga de archivos y consolas de texto con logs detallados.
*   [x] **Tarea 2.5**: Escribir la lógica en Vanilla JS para realizar el envío multipart, consultar el estado del procesamiento por polling y renderizar el catálogo de coberturas cargadas.

---

## 💳 Fase 3: Autenticación, Cobros y Asincronía (Cognito, Mercado Pago & BackgroundTasks)
*   [ ] **Tarea 3.1**: Configurar el middleware de FastAPI para validar y decodificar los tokens JWT de **Amazon Cognito**, protegiendo los endpoints transaccionales y de administración.
*   [ ] **Tarea 3.2**: Desarrollar los endpoints de integración con **Mercado Pago** (`POST /api/pagos/preferencia` para generar el link de Checkout Pro y `POST /api/pagos/webhook` para acreditar el pago e iniciar el flujo de generación).
*   [ ] **Tarea 3.3**: Configurar el cliente SDK de AWS (`boto3`) para la persistencia en Amazon S3 y programar el despachador de tareas asíncronas utilizando **FastAPI BackgroundTasks** al confirmarse el webhook de pago.
*   [ ] **Tarea 3.4**: Desarrollar e implementar el middleware global de excepciones (`UserFriendlyExceptionMiddleware`) que intercepte cualquier fallo del backend (caídas de Bedrock, errores de PostGIS, timeout de Google Places) y responda payloads JSON sanitizados con mensajes amigables y acciones sugeridas para la UI, registrando el traceback técnico real en logs internos.

---

## 🧠 Fase 4: Motor Analítico y APIs (Google Places, BestTime & Amazon Bedrock)
*   [ ] **Tarea 4.1**: Programar la función de cálculo de **Demografía Ponderada** mediante intersección geoespacial matemática en PostGIS (RDS Aurora) intersectando el búfer del marcador con los polígonos de AGEBs.
*   [ ] **Tarea 4.2**: Desarrollar la integración con **Google Places API** para mapear comercios competidores directos/indirectos y atractores de tráfico peatonal en el radio seleccionado.
*   [ ] **Tarea 4.3**: Programar la integración con **BestTime API** para obtener e incorporar patrones dinámicos de afluencia peatonal horaria en la zona del proyecto.
*   [ ] **Tarea 4.5**: Programar la integración con **Amazon Bedrock** para realizar el análisis cualitativo profundo cruzando datos demográficos, competencia directa e intenciones del usuario, devolviendo un JSON con la recomendación explicable (FODA).
*   [ ] **Tarea 4.6**: Desarrollar la integración con la **API de Google Geocoding** (Geocodificación Inversa) para obtener la dirección postal estructurada (calle, número, colonia, código postal, localidad, municipio, estado, país) al hacer clic en el mapa y exponer el endpoint `GET /api/analizar/geocodificar`.

---

## 📄 Fase 5: Compilación y Entrega de Informes (ReportLab, S3 KMS & SES)
*   [ ] **Tarea 5.1**: Desarrollar el servicio del generador de PDF con **ReportLab** ejecutado en segundo plano por el contenedor FastAPI, aplicando una maquetación y diseño de geomarketing de primer nivel.
*   [ ] **Tarea 5.2**: Integrar el almacenamiento en **Amazon S3 - Informes**, configurando el cifrado del lado del servidor con claves administradas de AWS KMS (**SSE-KMS**).
*   [ ] **Tarea 5.3**: Desarrollar el endpoint de FastAPI `GET /api/analizar/pdf/{orden_id}` que verifique los permisos de Cognito JWT y genere la **URL firmada temporal (Presigned URL)** de descarga en S3.
*   [ ] **Tarea 5.4**: Programar la integración con **Amazon SES** para enviar por correo electrónico el PDF de forma automática una vez concluida la generación en segundo plano.

---

## 🎨 Fase 6: Frontend Público (Glassmorphic SPA)
*   [ ] **Tarea 6.1**: Diseñar y maquetar la interfaz del visor público en HTML y **Vanilla CSS estructurado** en modo Glassmorphic Dark con tipografías de alta gama, transiciones sutiles y micro-animaciones en hovers y clics.
*   [ ] **Tarea 6.2**: Integrar el mapa interactivo con **Leaflet.js**, permitiendo situar marcadores arrastrables, renderizar el polígono del búfer dinámico, mapa de calor, y pins categorizados de la competencia.
*   [ ] **Tarea 6.3**: Programar los controles interactivos de entrada, integrando un **textarea para escribir intenciones específicas en lenguaje natural** y sliders de radio.
*   [ ] **Tarea 6.4**: Diseñar el panel de visualización del dashboard: tarjetas de KPIs interactivos, gráficos dinámicos con **Chart.js** (competencia e IAT), visualizador de la recomendación resumida de la IA y el botón para pagar / descargar el PDF.
*   [ ] **Tarea 6.5**: Programar el flujo de Vanilla JS para consumir las APIs públicas, validar el inicio de sesión con Cognito, interactuar con Checkout Pro de Mercado Pago y abrir la URL de descarga segura de S3.

---

## 🔍 Fase 7: QA, Validación e Infraestructura AWS
*   [ ] **Tarea 7.1**: Realizar la verificación de calidad de código ejecutando **Ruff** en todo el backend para corregir detalles de formato y lints.
*   [ ] **Tarea 7.2**: Escribir pruebas unitarias y de integración para validar el enrutamiento de webhooks, el procesamiento asíncrono local y el cómputo analítico bajo diferentes escenarios.
*   [ ] **Tarea 7.3**: Crear el **Dockerfile** específico optimizado para compilar la imagen Docker de FastAPI con soporte de librerías nativas geoespaciales (GDAL, Fiona, Proj) e inyectar secretos mediante **AWS SSM Parameter Store** en producción.
*   [ ] **Tarea 7.4**: Crear el archivo de configuración `docker-compose.yml` y los scripts de levantamiento automático (systemd o bash) para ejecutar y mantener el contenedor Docker permanente en la instancia de **Amazon EC2**.
*   [ ] **Tarea 7.5**: Escribir y ejecutar pruebas específicas de QA para verificar que el middleware de excepciones intercepte y mitigue fallos simulados respondiendo con la estructura JSON user-centric correcta sin exponer tracebacks.
