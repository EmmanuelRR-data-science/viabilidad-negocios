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
