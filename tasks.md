# Tareas de Implementación: Personalización de Aliados y Competidores

- [x] Fase de Planificación y Aprobación
  - [x] Crear documentos RFC, Requirements, Design y Tasks
  - [x] Presentar propuesta al usuario y obtener aprobación
- [x] Fase de Ingesta y Base de Datos
  - [x] Crear y ejecutar la migración `scratch/add_custom_selection_columns.py`
  - [x] Actualizar el ORM `OrdenPago` en [models.py](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/app/models.py)
  - [x] Actualizar `init_db_schemas` en [admin_app.py](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/admin_app.py)
- [x] Fase de Validación y Endpoints (API)
  - [x] Actualizar validaciones de Pydantic en [schemas.py](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/app/schemas.py) para validar límites por Tier (Básico: 1 comp / 0 aliados, Pro: 3 comp / 0 aliados, Premium: 5 comp / 5 aliados)
  - [x] Actualizar registro de órdenes en [payments.py](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/app/payments.py) para serializar y guardar las listas en base de datos
- [x] Fase del Motor Analítico e IA
  - [x] Modificar consultas a Places en [analytics.py](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/app/analytics.py) para que iteren por categorías personalizadas
  - [x] Actualizar el cálculo del SVA en [analytics.py](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/app/analytics.py) ante competencia personalizada
  - [x] Integrar inputs de aliados y competidores personalizados en el prompt del LLM en [bedrock.py](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/app/bedrock.py)
- [x] Fase de Generación de Reportes PDF
  - [x] Adaptar dinámicamente la tabla de competidores (Pág 8) y la tabla de atractores (Pág 10) en [reports.py](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/app/reports.py) en base a los datos recolectados
- [/] Fase de Ajuste y Refinamiento UX (Slicing en Checkout)
  - [ ] Habilitar selección de hasta 5 competidores y aliados en el panel izquierdo (modo gratuito) en `index.html` y deshabilitar/limitar con JS en `app.js`
  - [ ] Actualizar los textos explicativos en el panel izquierdo de `index.html` indicando cómo se recortarán según el Tier de compra
  - [ ] Implementar el contenedor `#modal-selections-summary` dentro de la pasarela de pago en `index.html`
  - [ ] Implementar en `app.js` la lógica de recorte dinámico de arrays al abrir el modal de pago
  - [ ] Poblar el resumen visual en el modal de pago según la lista recortada
  - [ ] Habilitar soporte de competidor personalizado para Tier Básico en `analytics.py` (cambiar `if tier in ["pro", "premium"]:` por `if tier in ["basico", "pro", "premium"]:`)
- [/] Fase de Verificación y Calidad
  - [ ] Adaptar pruebas unitarias para validación del Tier Básico (1 competidor) en `tests/test_suite.py`
  - [ ] Compilar reporte de prueba Premium personalizado y verificar PDF
  - [ ] Ejecutar pytest y verificar que todas las pruebas pasen con éxito
  - [ ] Ejecutar Ruff check y format para cumplir con los estándares
- [x] Fase de Corrección de Layout y Estilo de PDF
  - [x] Ajustar espaciadores de la portada en `app/reports.py` (de 150/100/60 a 80/50/40) para eliminar desbordamientos de página
  - [x] Añadir diccionario de mapeo de nombres de tiers en `app/reports.py` para acentuación correcta en español
  - [x] Actualizar el script `scratch/check_pdf_pages.py` para utilizar `pypdf` al contar las páginas
  - [x] Verificar el conteo exacto de páginas en todos los tiers (Básico: 6, Pro: 10, Premium: 13)

- [x] Fase de Remoción de Terminología Técnica en Interfaz y PDF
  - [x] Reemplazar "AWS Bedrock", "Amazon S3", "ReportLab", "PostGIS", "BestTime", "SCIAN" y "Búfer" en `frontend/index.html`
  - [x] Reemplazar términos técnicos de progreso y alertas en `frontend/app.js`
  - [x] Quitar menciones a "Bedrock" en el endpoint `routes_analytics.py` ("mensaje_tier")
  - [x] Reemplazar títulos, notas metodológicas y deslindes técnicos en `app/reports.py`
  - [x] Verificar compilación correcta y probar la SPA localmente

- [x] Fase de Búsqueda de Direcciones (Geocodificación Directa)
  - [x] Implementar la función `buscar_coordenadas_por_direccion` en [google_places.py](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/app/google_places.py) para resolver textos con Google Geocoding restringido a México
  - [x] Implementar el endpoint GET `/api/analizar/buscar-direccion` en [routes_analytics.py](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/app/routes_analytics.py)
  - [x] Añadir la caja flotante de búsqueda y lista de resultados en [index.html](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/frontend/index.html) sobre el contenedor del mapa
  - [x] Definir estilos visuales premium para la caja de búsqueda y dropdown flotante en [index.css](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/frontend/index.css)
  - [x] Integrar event listeners de búsqueda, despliegue de coincidencias y centrado de Leaflet en [app.js](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/frontend/app.js)
  - [x] Escribir pruebas automatizadas para el endpoint `/buscar-direccion` en [test_suite.py](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/tests/test_suite.py)
  - [x] Ejecutar linting/formatting de Ruff y suite completa de pytest

- [ ] Fase de Consistencia y Calidad de Reportes (FODA, Competidores y Atractores)
  - [ ] Implementar mapeo de `fast_food` a `restaurant` con palabra clave en `app/google_places.py`
  - [ ] Adaptar prompt de sistema en `app/bedrock.py` para unificar el diagnóstico del LLM con la puntuación SVA
  - [ ] Adaptar simulación local (`DEV_MODE`) en `app/bedrock.py` para generar diagnósticos alineados al score SVA (Alto/Medio/Bajo)
  - [ ] Ajustar el pilar de atractores en la Página 4 de `app/reports.py` para que calcule de forma dinámica la presencia de aliados personalizados
  - [ ] Ajustar la sección de Forecast de Mercado en la Página 10 de `app/reports.py` ante conteo de atractores igual a 0
  - [ ] Implementar la lista compacta al pie de la Página 8 de `app/reports.py` para desglosar competidores adicionales
  - [ ] Simplificar y remover jergas técnicas y términos complejos (AGEBs, Fricción, etc.) en `app/reports.py`
  - [ ] Implementar consulta espacial y cálculo del Nivel Socioeconómico (NSE) y fallbacks en `app/analytics.py`
  - [ ] Adaptar prompts de sistema y mocks de `app/bedrock.py` para incorporar el valor de NSE (precio y ticket sugerido)
  - [ ] Ajustar maquetación del PDF en `app/reports.py` para la tarjeta de NSE en Página 2 y desglose en Página 3
  - [ ] Agregar la tarjeta de KPI de NSE en `frontend/index.html` y adaptar `.kpis-grid` a 4 columnas en `frontend/index.css`
  - [ ] Configurar bloqueo/desbloqueo de la tarjeta de NSE en `frontend/app.js`
  - [ ] Ejecutar suite de pruebas unitarias (`pytest`) y verificar que todas las pruebas pasen con éxito
  - [ ] Ejecutar ruff check y formateador para asegurar el estilo de código

- [x] Fase de Contexto de la Aplicación y Ayudas Contextuales (Tooltips)
  - [x] Crear la estructura HTML de la tarjeta introductoria `#app-intro-card` y del botón de cierre en [index.html](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/frontend/index.html)
  - [x] Diseñar estilos glassmorphic para `.intro-card` y animaciones de colapsado en [index.css](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/frontend/index.css)
  - [x] Agregar la lógica en [app.js](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/frontend/app.js) para colapsar la tarjeta, guardar el estado en `localStorage` y restaurarlo al cargar
  - [x] Definir los estilos de los tooltips de información (`.info-tooltip-wrapper`, `.info-icon`, `.tooltip-text`, con soporte para temas claro/oscuro y orientación de burbuja) en [index.css](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/frontend/index.css)
  - [x] Inyectar los iconos `ℹ️` y sus tooltips asociados en las secciones de formulario y de resultados en [index.html](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/frontend/index.html)
  - [x] Ejecutar auditoría visual de tooltips para asegurar legibilidad en temas claro/oscuro y pantallas de tamaño reducido

- [ ] Fase de Autodetección de Competidores y Aliados por IA
  - [ ] Agregar checkboxes de autodetección por IA en las secciones de competidores y aliados en `index.html`
  - [ ] Diseñar estilos para el checkbox `.checkbox-ia-auto` y elementos atenuados `.disabled-by-ia` en `index.css`
  - [ ] Implementar la interacción de exclusión mutua de checkboxes en `app.js` (deshabilitar y atenuar otros controles si la IA está activa)
  - [ ] Modificar la preparación del payload en `app.js` para enviar `"ia_auto"`
  - [ ] Modificar la intercepción de `"ia_auto"` en `app/analytics.py` para realizar búsquedas estándar en Google Places
  - [ ] Modificar el prompt estratégico en `app/bedrock.py` para ordenar al LLM autodetectar y justificar competidores y aliados
  - [ ] Ejecutar auditoría y pruebas automatizadas (Ruff, pytest) para validar el flujo
  - [ ] Actualizar el changelog `resumen_cambios_reporte.md` en el histórico

- [ ] Fase de Refactorización por Capas en API (Fase 1b)
  - [ ] Crear estructura de directorios `infrastructure/` y `domain/` en `geo-viabilidad-api/app`
  - [ ] Crear paquete `app/tiers/` con `definitions.json` (límites, precios y páginas por tier) y `registry.py` (registro resolvedor de tiers)
  - [ ] Migrar clients externos (`google_places.py`, `besttime.py`, `bedrock.py`) a `app/clients/`
  - [ ] Migrar lógica de dominio (`sva_calculo.py`, `nse.py`, `seleccion_atractores.py`, `vigencia_comercio.py`, `demografia_segmentos.py`, `competencia_busqueda.py`, `aliados_deterministico.py`, `aliados_guiados.py`) a `app/domain/`
  - [ ] Crear re-exports temporales en la raíz de `app/` para todos los módulos migrados a `clients/` y `domain/`
  - [ ] Crear `app/services/analytics_service.py` moviendo la lógica principal de orquestación de `app/analytics.py`
  - [ ] Crear `app/services/report_pdf_service.py` moviendo la lógica de PDF de `app/reports.py`
  - [ ] Crear `app/services/aliados_guiados_service.py` moviendo la lógica de cuestionario de `app/aliados_guiados.py`
  - [ ] Crear re-exports temporales en la raíz de `app/` para `analytics.py`, `reports.py` y `aliados_guiados.py`
  - [ ] Crear enrutador `app/routers/analytics.py` conteniendo todas las rutas REST de `app/routes_analytics.py` y delegando a la capa de servicios
  - [ ] Actualizar `app/main.py` para cargar el enrutador desde `app.routers.analytics`
  - [ ] Reemplazar `app/routes_analytics.py` con re-exports hacia `app.routers.analytics`
  - [ ] Ajustar importaciones relativas dentro de todos los archivos migrados y asegurar resolución limpia

- [ ] Fase de Versionamiento y Preparación de Split (Fase 2)
  - [ ] Crear archivo `VERSION` con `1.0.0` en la raíz de `geo-viabilidad-api/`
  - [ ] Crear archivo `VERSION` con `1.0.0` en la raíz de `geo-viabilidad-web/`
  - [ ] Crear archivo `VERSION` con `1.0.0` en la raíz de `geo-viabilidad-admin/`
  - [ ] Configurar variables de entorno y documentar OpenAPI en `/api/openapi.json`
  - [ ] Ejecutar suite completa de tests de la API (`pytest`) y verificar paso exitoso
  - [ ] Ejecutar Ruff check y format en el código refactorizado para cumplimiento de lints






