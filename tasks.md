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




