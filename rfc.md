# RFC: Personalización de Aliados y Competidores en Reportes

* **Author(s)**: Antigravity AI
* **Status**: Propuesta (Draft)
* **Última actualización**: 2026-06-05
* **Links**:
  * Schemas de entrada: [schemas.py](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/app/schemas.py)
  * ORM base de datos: [models.py](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/app/models.py)
  * Lógica analítica: [analytics.py](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/app/analytics.py)
  * Prompts de Bedrock: [bedrock.py](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/app/bedrock.py)
  * Generador de PDF: [reports.py](file:///c:/Users/EmmanuelRam%C3%ADrez/OneDrive%20-%20PhiQus/Escritorio/viabilidad-hook/app/reports.py)

---

## 1. Goals
* Permitir al usuario definir categorías personalizadas de competidores y aliados estratégicos durante la cotización.
* Estructurar y limitar la funcionalidad según el nivel de suscripción adquirido (Básico, Pro, Premium) para maximizar el valor del ticket de pago.
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

