# Diseño Técnico: Personalización de Aliados y Competidores

## 1. Diseño del Modelo de Datos

### Cambios en Tabla `ordenes_pagos`
Se agregarán dos columnas a la tabla `ordenes_pagos` en PostgreSQL:
* `competidores_seleccionados` (`TEXT`): Almacenará la lista serializada en JSON de tipos seleccionados.
* `aliados_seleccionados` (`TEXT`): Almacenará la lista serializada en JSON de tipos seleccionados.

### Migración de Base de Datos
Se creará un script de migración en Python `scratch/add_custom_selection_columns.py` que aplicará:
```sql
ALTER TABLE ordenes_pagos 
ADD COLUMN IF NOT EXISTS competidores_seleccionados TEXT,
ADD COLUMN IF NOT EXISTS aliados_seleccionados TEXT;
```

---

## 2. Flujo y Validación de Datos

```mermaid
graph TD
    A[Usuario / Panel Izquierdo] -->|Selecciona hasta 5 comps y aliados en modo gratuito| B[Formulario Centralizado]
    B -->|Haz clic en comprar Básico/Pro/Premium| C[Frontend recorta listas según Tier]
    C -->|Muestra resumen en modal de pago| D[Modal de Mercado Pago]
    D -->|Confirma Pago| E[FastAPI /preferencia]
    E -->|Crea Orden con Selección Recortada| F[FastAPI /webhook-mock]
    F -->|Ejecuta Tarea Background| G[analytics.py / Google Places]
    G -->|Prompt con datos| H[bedrock.py LLM]
    H -->|Genera Reporte PDF| I[reports.py]
    I -->|Carga a S3 y descarga| J[Descarga PDF]
```

### Validación en `schemas.py`
Se validarán las listas en `PreferenciaCreate` utilizando decoradores de Pydantic:
* Si `tier_adquirido == 'basico'`: `competidores_seleccionados` puede tener un máximo de 1 elemento. `aliados_seleccionados` debe ser nulo o estar vacío.
* Si `tier_adquirido == 'pro'`: `competidores_seleccionados` puede tener un máximo de 3 elementos. `aliados_seleccionados` debe ser nulo o estar vacío.
* Si `tier_adquirido == 'premium'`: `competidores_seleccionados` y `aliados_seleccionados` pueden tener un máximo de 5 elementos cada uno.

---

## 3. Consultas Dinámicas en `analytics.py`

### Mapeo de Competidores
* Si no hay categorías personalizadas, se usa el resolvedor estándar `google_type`.
* Si están definidas, se ejecuta un loop que llama a `buscar_competidores` para cada categoría (soporta Básico, Pro y Premium) y se eliminan duplicados.

### Mapeo de Aliados
* En Tier Premium, si el usuario seleccionó aliados personalizados, se consultan en Google Places.
* Se unifican en `aliados_listado` con sus metadatos (nombre, tipo, rating, dirección).

---

## 4. Estructura de Prompts e Integración de IA
En `bedrock.py`, el `user_prompt` se expandirá para incluir de forma estructurada:
* Las categorías de competidores y el conteo de comercios detectados de cada tipo.
* Las categorías de aliados y el conteo de comercios detectados de cada tipo.
* Esto instruye al LLM a relacionar de forma cruzada por qué las sinergias o la saturación afectan la viabilidad del punto.

---

## 5. Diseño de Experiencia de Errores Orientada al Usuario
* Si la llamada a Google Places para alguna categoría personalizada falla por timeout o cuota, el motor de analítica continuará procesando las demás categorías de forma resiliente, registrando el error en los logs internos y mostrando lo que esté disponible en el PDF sin tracebacks para el usuario.

---

## 6. Diseño del Ajuste de Layout en Portada del PDF
Para evitar el desbordamiento de la primera página, reduciremos los espaciadores verticales (`Spacer`) en la portada:
* **Espaciador Superior**: Reducido de `150pt` a `80pt`.
* **Espaciador Central**: Reducido de `100pt` a `50pt`.
* **Espaciador Inferior**: Reducido de `60pt` a `40pt`.

### Mapeo Estético del Tier Adquirido
Para mejorar la presentación en el campo de metadatos de la portada del PDF, se implementará un mapeo explícito de los tiers:
```python
tier_map = {
    "basico": "BÁSICO",
    "pro": "PRO",
    "premium": "PREMIUM",
}
```
Esto asegura la acentuación correcta en español ("TIER BÁSICO" en lugar de "TIER BASICO" o "TIER PREMIUM" forzado).

---

## 7. Diseño de Remoción de Jergas y Proveedores Técnicos
Se implementarán modificaciones en cadenas de texto estáticas y dinámicas para ocultar la infraestructura tecnológica subyacente a los ojos del usuario:
* **En el PDF (`reports.py`)**:
  * Títulos de página simplificados (ej. "7. COMPETENCIA DETALLADA" en lugar de "7. COMPETENCIA DETALLADA (GOOGLE PLACES)").
  * Redefinición del anexo metodológico para eliminar referencias directas a APIs propietarias.
  * Cambios de cabeceras de tablas ("Valor Real PostGIS" -> "Valor Encontrado").
* **En el Frontend (`index.html` y `app.js`)**:
  * Ocultar menciones de AWS, S3, Cognito, FastAPI y ReportLab.
  * Reemplazo de los estados de la barra de progreso simulada para usar frases amigables como "Autenticando sesión..." y "Almacenando reporte..." en lugar de referencias a "Cognito User Pool" y "Amazon S3 (KMS)".
* **En variables del API (`routes_analytics.py`)**:
  * Modificación de `"mensaje_tier"` de salida para quitar la mención explicativa de "Bedrock" o "BestTime".


