# Especificación de Diseño (design.md)

Este documento detalla la arquitectura de infraestructura optimizada en costos en AWS, el modelo relacional espacial en RDS PostgreSQL con soporte de Tiers, el flujo asíncrono interno de procesamiento y las integraciones del motor analítico de Ciencia de Datos y LLM.

---

## 🏛️ 1. Arquitectura de Componentes en AWS (Cost-Optimized)

Para minimizar los costos fijos de AWS a menos de **$22.00 USD mensuales** garantizando el 100% de la operatividad empresarial, el sistema consolida componentes y elimina servicios redundantes en una instancia EC2:

```mermaid
graph TD
    User[Usuario - Navegador Web] <-->|HTTPS| CloudFront[AWS CloudFront - Capa Gratuita]
    
    subgraph Frontend [S3 Static Web Hosting]
        CloudFront -->|Contenido Estático| S3_Front[(Amazon S3 - Frontend)]
    end
    
    subgraph Capa de Cómputo Unificada [AWS EC2 Single Instance]
        CloudFront -->|/api/*| ECS_API[AWS EC2 - FastAPI (Docker Container)]
        ECS_API -->|BackgroundTasks Internas| PDF_Engine[Generador PDF ReportLab]
    end
    
    subgraph Capa de Identidad
        ECS_API <-->|Valida JWT Gratuito| Cognito[Amazon Cognito - <50k MAU gratis]
    end
    
    subgraph Integraciones de Cobro
        ECS_API <-->|Preferencia / Webhook| MP[Mercado Pago - Checkout Pro]
    end
    
    subgraph Capa de Datos y Almacenamiento
        ECS_API <--> RDS[(Amazon RDS PostgreSQL - t4g.micro single-AZ + PostGIS)]
        ECS_API -->|Guarda PDF privado| S3_Reports[(Amazon S3 - Informes)]
    end
    
    subgraph APIs Externas (Consumo según Tier)
        ECS_API -->|Afluencia| BestTime[BestTime API]
        ECS_API -->|Comercios| Google[Google Places API]
        ECS_API -->|Razonamiento IA| Bedrock[AWS Bedrock - Llama 3.1]
    end
    
    subgraph Servicios Transversales Gratuitos o de Bajo Costo
        SSM[SSM Parameter Store - Gratis] -.-> ECS_API
        KMS[AWS KMS] -.-> S3_Reports
        SES[Amazon SES] <-- ECS_API
        CW[Amazon CloudWatch - Logs]
    end
```

---

## 💾 2. Modelo de Datos y Estructura PostGIS (RDS PostgreSQL)

### Tabla: `agebs_demografia`
Almacena los polígonos de las **AGEBs Urbanas** de México y variables del Censo 2020 de INEGI.

```sql
CREATE TABLE agebs_demografia (
    id SERIAL PRIMARY KEY,
    cve_ageb VARCHAR(13) UNIQUE NOT NULL,
    entidad VARCHAR(2) NOT NULL,
    municipio VARCHAR(3) NOT NULL,
    pobtot INTEGER NOT NULL,
    pobmas INTEGER,
    pobfem INTEGER,
    vivtot INTEGER NOT NULL,
    geom GEOMETRY(MultiPolygon, 4326)
);

CREATE INDEX idx_agebs_geom ON agebs_demografia USING GIST (geom);
```

### Tabla: `ordenes_pagos`
Registra las transacciones procesadas con Mercado Pago e identifica el **Tier de servicio adquirido** para segmentar los privilegios de visualización y análisis.

```sql
CREATE TABLE ordenes_pagos (
    id SERIAL PRIMARY KEY,
    cognito_user_id VARCHAR(100) NOT NULL,
    checkout_id VARCHAR(100) UNIQUE NOT NULL,
    monto NUMERIC(10, 2) NOT NULL,
    estado_pago VARCHAR(20) NOT NULL,            -- 'pending', 'approved', 'rejected'
    tier_adquirido VARCHAR(20) NOT NULL,         -- 'basico', 'pro', 'premium'
    latitud NUMERIC(9, 6) NOT NULL,
    longitud NUMERIC(9, 6) NOT NULL,
    radio_metros INTEGER NOT NULL,
    rubro VARCHAR(50) NOT NULL,
    intenciones TEXT,
    s3_key_reporte VARCHAR(255),                 -- Ruta del PDF en S3
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_aprobacion TIMESTAMP
);

CREATE INDEX idx_pago_user ON ordenes_pagos (cognito_user_id);

### Tabla: `categorias_cruce`
Mapea códigos SCIAN de INEGI con tipos de Google Places para identificar competencia directa/indirecta y atractores de forma semántica.

```sql
CREATE TABLE categorias_cruce (
    id SERIAL PRIMARY KEY,
    codigo_scian VARCHAR(10) UNIQUE NOT NULL,
    nombre_scian VARCHAR(200) NOT NULL,
    google_place_type VARCHAR(50) NOT NULL,
    categoria_negocio VARCHAR(50) NOT NULL, -- 'restaurante', 'retail', etc.
    peso_competencia NUMERIC(3, 2) DEFAULT 1.0
);
```

### Tabla: `ingesta_tareas`
Rastrea el progreso asíncrono y los estados de carga y reproyección de Shapefiles y CSVs de INEGI.

```sql
CREATE TABLE ingesta_tareas (
    id VARCHAR(100) PRIMARY KEY,
    archivo_nombre VARCHAR(255) NOT NULL,
    estado VARCHAR(20) NOT NULL, -- 'pendiente', 'procesando', 'completado', 'fallido'
    progreso_porcentaje INTEGER DEFAULT 0,
    registros_insertados INTEGER DEFAULT 0,
    error_mensaje TEXT, -- Mensaje amigable (el traceback real va a logs)
    fecha_inicio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fecha_fin TIMESTAMP
);
```

### Tabla: `cache_analisis_api`
Caché relacional para almacenar las respuestas analíticas y mitigar llamadas costosas e innecesarias a APIs externas y LLMs.

```sql
CREATE TABLE cache_analisis_api (
    id SERIAL PRIMARY KEY,
    latitud NUMERIC(9, 6) NOT NULL,
    longitud NUMERIC(9, 6) NOT NULL,
    radio_metros INTEGER NOT NULL,
    rubro VARCHAR(50) NOT NULL,
    servicio_tipo VARCHAR(20) NOT NULL, -- 'places', 'besttime', 'bedrock'
    payload_respuesta JSONB NOT NULL,
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_cache_coords ON cache_analisis_api (latitud, longitud, radio_metros, rubro, servicio_tipo);
```
```

---

## 💳 3. Flujo Transaccional e Ingesta Asíncrona con FastAPI BackgroundTasks

Para evitar los costos de AWS SQS y un contenedor Worker dedicado, implementamos **procesamiento asíncrono nativo en memoria** a través de `BackgroundTasks` de FastAPI en la misma instancia de EC2:

1.  **Aprobación del Pago**: Cuando Mercado Pago confirma el pago vía webhook, el endpoint `/api/pagos/webhook` en FastAPI actualiza la base de datos a `'approved'`.
2.  **Encolamiento Interno**: La API registra una tarea en segundo plano mediante `BackgroundTasks.add_task(generar_informe_task, orden_id)`.
3.  **Respuesta Inmediata**: FastAPI responde con un estado HTTP 200 al webhook de Mercado Pago, liberando la conexión de red en milisegundos.
4.  **Ejecución en Background**: El contenedor Docker de la API en la instancia EC2 procesa el informe en un hilo de fondo de forma no bloqueante, consumiendo las APIs y persistiendo el PDF en **Amazon S3** cifrado con KMS, enviando finalmente el correo por SES.

---

## 🧮 4. Motor Analítico de Ciencia de Datos y Segmentación de Tiers

El motor analítico adapta los cálculos espaciales y llamadas a APIs según el **Tier Adquirido**:

```
                              [Cálculo de Viabilidad]
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        ▼                                ▼                                ▼
   [Tier BÁSICO]                    [Tier PRO]                      [Tier PREMIUM]
        │                                │                                │
  - Intersección PostGIS           - Todo lo del Básico            - Todo lo del Pro
    (Demografía INEGI)             - API Google Places             - API BestTime
  - Bedrock LLM (FODA              - Bedrock LLM (FODA extendido   - Bedrock LLM (FODA profundo,
    General Simplificado)            + Ticket promedio +              Ticket recomendado
  - PDF 6 páginas                    Forecast de Mercado)             + Estimación de ROI)
                                   - PDF 10 páginas                - PDF 14 páginas +
                                                                     Dashboard interactivo
```

### A. Demografía Ponderada (INEGI - Todos los Tiers)
Cálculo de intersección espacial geodésica del búfer $B_R(P)$ con las AGEBs de INEGI:

$$D_P = \sum_{i} \left( \text{PobTot}_i \times \frac{\text{Área}\left(B_R(P) \cap \text{geom}_i\right)}{\text{Área}(\text{geom}_i)} \right)$$

### B. Índice de Saturación Comercial (ISC - Tiers Pro y Premium)
Modelo de gravedad Huff utilizando competidores mapeados en tiempo real por Google Places API:

$$\text{ISC} = \sum_{k \in \text{Competencia Directa}} \frac{C_{\text{Directa}}}{d_k^2} + \sum_{m \in \text{Competencia Indirecta}} \frac{C_{\text{Indirecta}}}{d_m^2}$$

### C. Índice de Atracción de Tráfico y Afluencia (IAT - Tiers Pro y Premium)
Suma de POIs atractores. En el **Tier Premium**, se añade la afluencia de peatones dinámica e histórica obtenida de la **API de BestTime**.

### E. Geocodificación Inversa (API de Google Geocoding - Todos los Tiers)
*   **Propósito**: Al hacer clic en el mapa, el sistema consume la API de Google Geocoding (`/maps/api/geocode/json?latlng=lat,lng`) para obtener y mostrar en la UI de forma inmediata la dirección postal completa estructurada.
*   **Mapeo de Atributos**:
    *   `route` -> calle
    *   `street_number` -> número
    *   `sublocality_level_1` o `political` -> colonia
    *   `postal_code` -> código postal
    *   `locality` -> localidad (ciudad/población)
    *   `administrative_area_level_2` -> municipio o alcaldía
    *   `administrative_area_level_1` -> estado (entidad federativa)
    *   `country` -> país

---

## 📄 5. Generador de Reportes PDF (ReportLab & S3 Presigned URLs)

El generador de PDF compila el reporte ejecutivo variando su extensión y profundidad de datos:
*   **Básico (6 páginas)**: Portada, resumen de viabilidad general, reporte demográfico detallado del INEGI, Score final, mapa de ubicación estático.
*   **Pro (10 páginas)**: Todo lo del básico + mapa detallado de competidores, tabla de competidores directos con distancias y forecast de mercado.
*   **Premium (14 páginas)**: Todo lo del Pro + análisis comparativo sectorial, estimaciones de ROI detalladas, ticket de venta recomendado y el diagnóstico estratégico profundo de Amazon Bedrock.

El archivo se sube a **Amazon S3 - Informes** cifrado. Para descargarlo, la API genera una **URL firmada temporal (Presigned URL)** de $10$ minutos que expone el PDF de forma segura al cliente.

---

## 🔑 6. Panel de Administración y Pipeline de Carga (INEGI)

1.  El Administrador (con rol Cognito `admin`) sube un Shapefile comprimido en `.zip`.
2.  El backend de FastAPI procesa el archivo asíncronamente con `BackgroundTasks` para evitar timeouts.
3.  Descomprime el zip en un directorio temporal, lee los archivos con **GeoPandas** y **Fiona**.
4.  Reproyecta la cartografía del datum de INEGI (ej. ITRF92) al CRS **EPSG:4326 (WGS84)** de forma nativa en memoria.
5.  Inserta lotes de 1000 polígonos a **RDS PostgreSQL (db.t4g.micro)** y reconstruye el índice espacial GIST.

---

## 🛑 7. Diseño de Experiencia de Manejo de Errores User-Centric

De acuerdo con las directrices de ciberseguridad y usabilidad, queda prohibido exponer excepciones del sistema, tracebacks o códigos de error crudos de red en la interfaz. El backend implementa un middleware de captura de excepciones personalizado (`UserFriendlyExceptionMiddleware`) que intercepta y sanitiza todos los fallos. El error técnico real se guarda únicamente en los logs internos mediante `logger.exception()`.

### Matriz de Traducción de Excepciones

| Excepción Interna | Causa Técnica | Mensaje en Logs | Mensaje Amigable en la UI | Acción Propuesta |
| :--- | :--- | :--- | :--- | :--- |
| `BedrockAPIError` / `BedrockTimeout` | Falla del modelo de IA o caída de AWS Bedrock. | `CRITICAL: AWS Bedrock API returned error or timeout.` | "Estamos experimentando una alta demanda en nuestro motor de análisis estratégico inteligente." | "Tu reporte cuantitativo e INEGI está a salvo. Puedes intentar regenerar el análisis estratégico en unos minutos sin costo adicional." |
| `GoogleAPIQuotaError` | Clave bloqueada, sin saldo o cuota de Places superada. | `ERROR: Google Places API: Over Query Limit or API Key invalid.` | "El mapa de competidores locales no se pudo cargar temporalmente debido a una sincronización de mapas pendiente." | "El resto de la viabilidad de población y demografía está listo. Intenta consultar el mapa detallado en breve." |
| `PostgisSpatialError` | Coordenadas fuera de México o geometría inválida. | `ERROR: PostGIS ST_Intersects failed: Coordinate is invalid or out of bounds.` | "No pudimos trazar el círculo de análisis correctamente en esta coordenada exacta." | "Asegúrate de que la ubicación se encuentra dentro del territorio mexicano y prueba moviendo un poco el pin en el mapa." |
| `WebhookIntegrityError` | Firma inválida del webhook de Mercado Pago o cobro repetido. | `WARNING: Webhook signature check failed. Possible spoofing attempt or duplicate webhook.` | "No logramos verificar la firma de tu transacción segura." | "No te preocupes; si tu cobro fue aprobado, nuestro soporte procesará tu reporte manualmente al instante. Contáctanos." |
| `InvalidShapefileZip` | ZIP de administración no tiene archivos shapefile válidos. | `ERROR: Admin ingestion: Fiona failed to parse .shp file in zip.` | "El archivo de cartografía INEGI seleccionado no cuenta con el formato requerido o está corrupto." | "Asegúrate de cargar el archivo .zip comprimido directamente con sus archivos .shp, .shx, .dbf y .prj incluidos." |
| `DatabaseConnectionError` | Caída de RDS PostgreSQL o pool de conexiones lleno. | `CRITICAL: Connection refused on postgresql://...` | "Estamos realizando un mantenimiento rápido en nuestra base de datos." | "Por favor, espera unos segundos e intenta recargar la página." |

### Formato Estándar de Respuesta de Error (JSON)

En caso de cualquier fallo no controlado, el middleware interceptará la excepción y retornará un HTTP 500 (o el código correspondiente) con el siguiente formato uniforme para que el frontend lo dibuje en una alerta visual elegante:

```json
{
  "status": "error",
  "friendly_message": "Estamos experimentando una alta demanda en nuestro motor de análisis estratégico inteligente.",
  "suggested_action": "Tu reporte cuantitativo e INEGI está a salvo. Puedes intentar regenerar el análisis estratégico en unos minutos sin costo adicional.",
  "transaction_id": "err_bedrock_01j8f92a"
}
```
