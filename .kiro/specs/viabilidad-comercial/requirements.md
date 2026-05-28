# Especificación de Requerimientos (requirements.md)

## 🗺️ 1. Descripción General del Proyecto
**GeoViabilidad Hook** es una plataforma de **Location Intelligence (Geomarketing)** de alta gama enfocada en el territorio mexicano, diseñada para inversionistas, franquiciadores y emprendedores. La plataforma opera bajo un modelo de infraestructura en **Amazon Web Services (AWS)** diseñado para **minimizar drásticamente los costos de operación mensual** sin sacrificar rendimiento ni robustez técnica, sirviendo como una solución sumamente eficiente.

### Flujo Comercial basado en Tiers (Niveles de Pago):
El sistema ofrece una **Vista Previa Gratuita** inicial en el visor cartográfico y permite adquirir tres niveles de informes detallados a través de **Mercado Pago (Checkout Pro)**:

1.  **BÁSICO ($99 MXN)**:
    *   Análisis completo de viabilidad cuantitativa en la zona de estudio.
    *   Desglose demográfico detallado (Población total y densidad habitacional del Censo 2020 de **INEGI**).
    *   Acceso a la descarga de un **reporte en formato PDF de 6 páginas** con la demografía y score inicial.
2.  **PRO ⭐ ($499 MXN)**:
    *   Incluye todos los beneficios del nivel Básico.
    *   **Mapa Detallado de Competidores**: Visualización interactiva y listado de comercios competidores directos/indirectos (vía **Google Places API**).
    *   **Estimación de Ticket Promedio**: Cálculo predictivo del consumo promedio en la zona según la competencia.
    *   **Forecast de Mercado**: Proyección de saturación comercial (ISC) y potencial de mercado.
    *   Descarga de reporte PDF extendido.
3.  **PREMIUM 💎 ($999 MXN)**:
    *   Incluye todos los beneficios del nivel Pro.
    *   **Cálculo de ROI (Retorno de Inversión)** y análisis comparativo sectorial detallado.
    *   **Recomendación de Ticket de Venta**: Sugerencia inteligente de precios de venta recomendados.
    *   **Dashboard Interactivo Completo**: Acceso de exploración sin restricciones en la UI de forma permanente para el punto analizado.

---

## 🎯 2. Requerimientos Funcionales (RF)

### RF-01: Visor Cartográfico e Interactividad (Leaflet.js)
*   **RF-01.1**: El usuario deberá visualizar un mapa interactivo nacional de México.
*   **RF-01.2**: El usuario podrá seleccionar una ubicación haciendo clic directo en el mapa.
*   **RF-01.3**: El sistema deberá renderizar dinámicamente un **búfer espacial** (círculo de influencia) alrededor del marcador, cuyo radio será configurable mediante un slider en la UI (valores permitidos: $500\text{m}$, $1\text{Km}$, $3\text{km}$, $5\text{km}$).
*   **RF-01.4**: El mapa deberá mostrar capas dinámicas según el nivel de acceso (tier) del usuario:
    *   *Gratuito / Básico*: Búfer demográfico e indicador demográfico de calor de INEGI.
    *   *Pro / Premium*: Capa detallada de pins categorizados para competidores directos/indirectos y atractores de tráfico.

### RF-02: Entrada de Configuración del Negocio
*   **RF-02.1**: El usuario podrá seleccionar la categoría del negocio a evaluar a partir de una lista precargada.
*   **RF-02.2**: El usuario podrá refinar la búsqueda ingresando palabras clave específicas si lo desea.
*   **RF-02.3**: El usuario podrá buscar direcciones específicas a través de una barra de búsqueda con autocompletado geográfico.
*   **RF-02.4**: El usuario podrá ingresar en **lenguaje natural las intenciones específicas** de su negocio (ej. *"Quiero abrir una pizzería gourmet para familias de clase media-alta, que cuente con zona infantil y ofrezca servicio a domicilio rápido"*).

### RF-03: Ingesta e Integración de Datos
*   **RF-03.1**: El sistema deberá integrar bases de datos relacionales espaciales de **INEGI** correspondientes a la estructura geodemográfica de México (Población total y densidad por AGEB o Manzana según disponibilidad) para realizar consultas de intersección espacial (`ST_Intersects`).
*   **RF-03.2**: El sistema deberá conectarse a la **API de Google Places** utilizando la clave de API configurada, recuperando los comercios y puntos de interés dentro del radio definido (disponible para Tiers **Pro** y **Premium**).
*   **RF-03.3**: El sistema de análisis deberá conectarse a la **API de BestTime** para obtener información sobre la afluencia de personas por rangos de horarios y días de la semana en la zona seleccionada (disponible para Tiers **Pro** y **Premium**).
*   **RF-03.4**: El sistema deberá implementar un **Mapeo de Categorías** entre el clasificador industrial mexicano **SCIAN** (usado en censo y demografía) y los **Tipos de Google Places** para identificar competencia directa e indirecta de forma semántica.

### RF-04: Motor Analítico, Ciencia de Datos e Inteligencia Artificial (LLM)
*   **RF-04.1**: El sistema deberá calcular el **Índice de Saturación Comercial (ISC)** de manera ponderada por distancia utilizando el Modelo de Huff o decaimiento exponencial (disponible para Tiers **Pro** y **Premium**).
*   **RF-04.2**: El sistema deberá calcular el **Índice de Atracción de Tráfico (IAT)** sumando ponderadamente los POIs atractores encontrados (transporte, escuelas, bancos, etc.) y los patrones de afluencia dinámica de **BestTime API** (disponible para Tiers **Pro** y **Premium**).
*   **RF-04.3**: El sistema deberá calcular el **Score de Viabilidad de Apertura (SVA)**, una métrica de $0$ a $100$ que sintetice la competencia, demografía y atracciones.
*   **RF-04.4**: El sistema deberá integrar el modelo **Groq LLM** a través de una API Key configurada para interpretar las intenciones del usuario (RF-02.4) y realizar un razonamiento contextual cruzado según el Tier del usuario:
    *   *Básico*: Análisis demográfico y FODA general simplificado.
    *   *Pro*: FODA extendido, estimación de ticket promedio del nicho y forecast de viabilidad comercial del mercado local.
    *   *Premium*: FODA profundo, ticket recomendado de venta y estimación del Retorno de Inversión (ROI) adaptado a las intenciones específicas.

### RF-05: Dashboard Visual, Vista Previa e Informes por Tiers
*   **RF-05.1**: La interfaz deberá mostrar tarjetas (KPIs) con métricas críticas del punto: Score final, número de competidores directos, distancia al competidor más cercano y población residente estimada.
*   **RF-05.2**: La interfaz deberá incluir gráficos interactivos (ej. Chart.js):
    *   *Distribución de la competencia por rangos de distancia*.
    *   *Desglose de POIs atractores en un gráfico de dona o radar*.
*   **RF-05.3**: La interfaz deberá estar optimizada con diseño estético premium **Dark Glassmorphism** (uso de colores HSL armónicos, fondos semitransparentes difuminados, bordes sutiles y micro-animaciones en botones e inputs).
*   **RF-05.4**: El sistema controlará estrictamente el nivel de acceso en la UI según el Tier de pago:
    *   *Vista Previa Gratuita*: Muestra el marcador, el búfer de radio, el conteo agregado de población y competencia en tarjetas y una sugerencia de compra.
    *   *Básico*: Desbloquea la pestaña de demografía detallada e informe PDF de 6 páginas.
    *   *Pro*: Desbloquea la pestaña de mapa de competidores interactivos, ticket promedio y descarga del PDF extendido.
    *   *Premium*: Desbloquea el dashboard interactivo de forma ilimitada para el punto, gráficos dinámicos de ROI y comparativa sectorial de venta.

### RF-06: Panel de Administración e Ingesta Manual (INEGI)
*   **RF-06.1**: El sistema deberá proveer un **front-end de administración protegido** (en `/admin`) para uso exclusivo del personal de gestión de datos.
*   **RF-06.2**: El panel de administración deberá contar con un formulario interactivo para la **carga manual de archivos espaciales y demográficos de INEGI por estados** (archivos `.zip` comprimidos conteniendo el Shapefile de AGEBs urbanas estatales junto con sus archivos de censo `.csv` de resultados).
*   **RF-06.3**: El backend deberá procesar el archivo cargado de forma asíncrona mediante un pipeline de **ingesta iterativa y fragmentada (chunking)**. Deberá descomprimirlo en disco temporal, leer e iterar en memoria sobre las geometrías y variables de forma fragmentada (en lotes de 1,000 registros con control agresivo de `gc.collect()`), y **almacenarlas/actualizarlas en la base de datos RDS PostgreSQL (db.t4g.micro)** sin saturar el límite de 1 GB de RAM de la base de datos.

---

## ⚙️ 3. Requerimientos No Funcionales (RNF) - AWS Cost-Optimized

### RNF-01: Stack Tecnológico de Costo Mínimo en AWS
*   **DNS & CDN Económico**: **Amazon Route 53** para DNS y **AWS CloudFront** (con la capa gratuita) para servir el frontend estático.
*   **Frontend**: Single Page Application (SPA) construida con HTML5, CSS semántico premium y Vanilla JS (Leaflet.js y Chart.js), servido directamente desde un bucket **Amazon S3 - Frontend** (Costo aproximado: $<0.50$ USD/mes).
*   **Servicio de Cómputo Unificado**: En lugar de múltiples grupos de contenedores ALB y colas SQS, se consolida la API y las tareas pesadas en **un contenedor Docker ejecutándose en una instancia de Amazon EC2**. El procesamiento en segundo plano para generar reportes y llamar al LLM se gestionará asíncronamente con **FastAPI BackgroundTasks** en memoria, lo que elimina la necesidad de un Application Load Balancer (ALB) y de Amazon SQS (Costo de cómputo predecible y optimizado).
*   **Capa de Datos de Costo Fijo Mínimo**: En lugar de RDS Aurora Serverless v2 (con alto costo base), se utilizará una instancia de base de datos **Amazon RDS PostgreSQL (db.t4g.micro o db.t3.micro)** con almacenamiento SSD GP3 de 20GB y con la extensión espacial **PostGIS** activada. *(RDS Proxy se elimina por ser un costo redundante para cargas de trabajo optimizadas)* (Costo aproximado: $\approx 12.00$ USD/mes).
*   **Identidad y Autenticación**: **Amazon Cognito** para gestionar la base de usuarios de forma 100% gratuita para los primeros 50,000 usuarios activos mensuales (MAU).
*   **Gestión de Parámetros Gratuita**: En lugar de AWS Secrets Manager (con costo por secreto), se utilizará **AWS Systems Manager (SSM) Parameter Store** para inyectar credenciales y API Keys (Groq, Google Places, Mercado Pago) de forma completamente **gratuita** mediante parámetros estándar.
*   **Almacenamiento de Informes**: **Amazon S3 - Informes** privado con cifrado SSE-KMS integrado (Costo aproximado: $<0.10$ USD/mes).
*   **Entrega de Correos**: **Amazon SES** utilizando el nivel gratuito (Costo aproximado: $0.00$ USD/mes).

### RNF-02: Rendimiento y Optimización
*   **RNF-02.1**: Las consultas de cruce espacial en RDS PostgreSQL deben estar optimizadas mediante **Índices Espaciales GIST** sobre las columnas geométricas (`geom`).
*   **RNF-02.2**: Para optimizar los costos de las APIs externas, el backend FastAPI cacheará los resultados analíticos en la base de datos relacional durante 30 días para evitar llamadas redundantes a Google Places, Groq y BestTime.
