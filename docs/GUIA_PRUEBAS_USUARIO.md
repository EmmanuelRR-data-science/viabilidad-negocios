# Guía para probar GeoViabilidad Hook

## ¿Para qué sirve esta aplicación?

**GeoViabilidad Hook** es una plataforma de geointeligencia y geomarketing para México. Está pensada para quien va a **abrir, ampliar o reubicar un negocio** y necesita decidir con datos si una dirección conviene o no.

Responde la pregunta central:

> **¿Tiene sentido poner mi negocio aquí?**

Para eso combina en un solo lugar información que, de otro modo, tomaría mucho tiempo y dinero reunir por separado:

| Qué analiza | Qué te ayuda a entender |
|-------------|-------------------------|
| **Demografía (INEGI Censo 2020)** | Cuánta gente hay en el radio, su perfil y poder adquisitivo aproximado. |
| **Competencia en la zona** | Cuántos negocios parecidos al tuyo hay cerca, cómo están valorados y si el mercado está saturado. |
| **Afluencia peatonal** *(planes Pro y Premium)* | En qué horarios suele haber más tránsito de personas cerca del local. |

En pantalla verás un **mapa interactivo**, indicadores resumidos y el **Score de Viabilidad (SVA)**: una calificación de 0 a 100 que integra clientes potenciales, competencia y tráfico peatonal. Si quieres el análisis completo, puedes obtener un **reporte ejecutivo en PDF** con mapas, gráficas y una lectura estratégica del punto.

**Esta guía** es para personas que van a **probar** la aplicación en el navegador: marcar una ubicación, revisar el análisis de la zona y simular la compra de un reporte.

---

## Lo más importante antes de empezar

- La aplicación está **en desarrollo**. Puede haber cambios, tiempos de espera o mensajes que se ajusten en versiones futuras.
- **No se harán cobros reales.** En esta etapa los pagos están **simulados dentro de la app**: no sales a Mercado Pago ni se carga dinero a tu tarjeta.
- Los precios que ves en pantalla ($299, $649 y $799 pesos) son **referencia del producto final**; en estas pruebas solo sirven para recorrer el flujo completo.
- Puedes abrir la app en **http://localhost:8000** o en la URL pública que te indique el equipo (ngrok). Con pagos simulados, **localhost es suficiente**.

---

## Cómo entrar a la aplicación

1. Abre en tu navegador **http://localhost:8000** (o la URL que te comparta el equipo).
2. Verás una pantalla de acceso con el título **GeoViabilidad Hook**.
3. Escribe:

   | | |
   |---|---|
   | **Usuario** | `PhiQus` |
   | **Contraseña** | `viabilidad-negocios` |

4. Pulsa **Entrar a la plataforma**.

Si el usuario o la contraseña no coinciden, revisa mayúsculas: la **P** de PhiQus va en mayúscula.

---

## Recorrido en 5 pasos (visión general)

1. **Elige dónde estaría tu negocio** en el mapa.
2. **Analiza la zona** (vista previa gratuita).
3. **Inicia sesión con Google** cuando la app te lo pida.
4. **Compra un reporte** y confirma el **pago simulado** en el modal de la app.
5. **Descarga el PDF** cuando el reporte esté listo.

---

## Paso 1 — Ubicar tu negocio en el mapa

### Opción A: Buscar una dirección

1. A la derecha verás el mapa y arriba un buscador: **“Busca la dirección de tu local”**.
2. Escribe una dirección en México (por ejemplo: *Av. Insurgentes 123, Roma, Ciudad de México*).
3. El mapa se moverá hacia esa zona.

### Opción B: Marcar con un clic

1. Haz **clic** en el mapa donde imaginas tu local.
2. Aparecerá un **pin** y un **círculo** alrededor: ese círculo es el área que se analizará.

### Completar el formulario (panel izquierdo)

1. **Giro del negocio:** elige en la lista (Cafetería, Restaurante, Gimnasio, etc.). Si tu giro no está, selecciona **Otro** y escríbelo.
2. **Radio de análisis:** define qué tan lejos quieres estudiar alrededor del punto (por ejemplo 500 m o 1 km).
3. *(Opcional)* Puedes marcar tipos de **competidores** o **aliados** si quieres personalizar el análisis; no es obligatorio para la primera prueba.

Cuando el giro y el punto en el mapa estén listos, el botón **ANALIZAR UBICACIÓN** se activará.

---

## Paso 2 — Ver la vista previa (gratis)

1. Pulsa **⚡ ANALIZAR UBICACIÓN**.
2. La primera vez puede pedirte **iniciar sesión con Google** (ver paso 3).
3. Espera entre **10 y 30 segundos**.
4. Verás números resumidos: población en la zona, competidores cercanos, un puntaje de viabilidad (SVA), etc.

Esta parte **no cuesta nada**: sirve para explorar la zona antes de decidir si quieres el reporte completo.

---

## Paso 3 — Iniciar sesión con Google

Google se usa para **identificarte** y asociar tu compra con tu reporte. **No te cobra nada.**

1. Cuando aparezca la ventana de Google, pulsa **Continuar con Google**.
2. Elige tu cuenta de Gmail.
3. Acepta los permisos si el navegador lo solicita.
4. Verás tu nombre en la parte superior de la pantalla.

**Importante:** usa **la misma cuenta de Google** durante toda la prueba (análisis, compra y descarga del PDF).

---

## Paso 4 — Comprar un reporte (pago simulado)

### Elige un plan

| Plan | Precio de referencia | Para qué sirve en la prueba |
|------|----------------------|-----------------------------|
| **Básico** | $299 MXN | Reporte más corto, ideal para una primera prueba |
| **Pro** | $649 MXN | Incluye más detalle y mapas |
| **Premium** | $799 MXN | El reporte más completo (afluencia, aliados, etc.) |

Para probar por primera vez, **Básico** suele ser suficiente.

### Qué hacer en pantalla

1. Con la vista previa ya cargada, pulsa **🔒 COMPRAR BÁSICO** (o Pro / Premium).
2. Si aún no entraste con Google, la app te pedirá login primero.
3. Se abrirá un **modal de pago simulado** dentro de la app. **No sales a Mercado Pago** ni a ninguna pasarela externa.
4. Deja seleccionada la opción **«Aprobado al instante»** (es la predeterminada).
5. Pulsa **CONFIRMAR PAGO SIMULADO**.
6. Verás una barra de progreso con el mensaje *“Acreditando pago simulado…”*.
7. Cuando termine, aparecerá un aviso del tipo *“Pago acreditado”* o *“Generando tu reporte…”*.

### Otras opciones del modal (opcional)

El modal también permite simular pagos **pendientes** o **rechazados** para pruebas internas. Para la experiencia normal de usuario, usa siempre **«Aprobado al instante»**.

### Qué esperar después

- El reporte completo tarda **entre 30 segundos y 2 minutos** en generarse.
- Mantén la **misma sesión de Google** con la que compraste.
- Si cierras el navegador, vuelve a entrar con usuario **PhiQus**, inicia sesión otra vez con **la misma cuenta de Google** y la app intentará recuperar tu orden pagada.

---

## Paso 5 — Ver tu reporte en pantalla

Cuando el pago simulado quede confirmado:

1. La pantalla mostrará **más secciones** que en la vista previa: gráficas, mapas, lectura del punto, etc. (según el plan que elegiste).
2. Desplázate hacia abajo para revisar todo el contenido.
3. Si el panel sigue bloqueado tras un minuto, recarga la página (F5) manteniendo la sesión de Google.

---

## Paso 6 — Descargar el reporte en PDF

1. Baja hasta la sección **“Tu reporte ejecutivo está listo para descarga”**.
2. Pulsa **⬇️ DESCARGAR REPORTE EN PDF**.
3. Espera mientras aparece una barra de progreso (el PDF puede tardar un poco en generarse).
4. Se descargará un archivo PDF en tu carpeta de descargas, con un nombre similar a `Reporte_Viabilidad_123.pdf`.

Si el botón no funciona a la primera, espera un minuto y vuelve a pulsarlo: a veces el PDF aún se está armando.

---

## Si algo no funciona

| Qué pasa | Qué puedes hacer |
|----------|------------------|
| No acepta usuario o contraseña PhiQus | Revisa: usuario `PhiQus` (P mayúscula) y contraseña `viabilidad-negocios` |
| No puedo iniciar sesión con Google | Prueba otro navegador o ventana de incógnito; avisa al equipo si persiste |
| No aparece el modal de pago | Recarga la página (Ctrl+F5) e intenta comprar de nuevo |
| El botón dice «Ir a Mercado Pago» en lugar de «CONFIRMAR PAGO SIMULADO» | El equipo debe activar pagos simulados; avísales |
| Confirmé el pago pero no veo el reporte | Espera 1–2 minutos, recarga (F5) e inicia sesión con la **misma cuenta Google** |
| No descarga el PDF | Espera 1–2 minutos y pulsa otra vez **DESCARGAR REPORTE EN PDF** |
| Nada de lo anterior ayuda | Toma captura de pantalla del mensaje y compártela con el equipo de PhiQus |

---

## Credenciales de prueba — resumen

| Dónde | Usuario | Contraseña |
|-------|---------|------------|
| **Entrada a GeoViabilidad** | `PhiQus` | `viabilidad-negocios` |
| **Google** | Tu cuenta Gmail habitual | *(la de Google)* |

No necesitas cuenta ni tarjeta de Mercado Pago en esta etapa.

---

## Qué estás probando exactamente

Al seguir esta guía ayudas al equipo a validar:

- Que el **mapa** y el buscador de direcciones funcionen bien.
- Que el **análisis de la zona** (demografía, competencia) se entienda en pantalla.
- Que el **flujo de compra simulada** sea claro y rápido.
- Que el **reporte en PDF** se genere y descargue correctamente.

Tus comentarios sobre claridad de textos, tiempos de espera y facilidad de uso son muy valiosos. No hace falta conocimientos técnicos para probar: solo navegador, las credenciales de esta guía y unos minutos de paciencia mientras se genera el reporte.

---

## Anexo — Mercado Pago (desactivado en esta etapa)

> **Nota para el equipo y usuarios avanzados:** el sandbox de Mercado Pago mostró inestabilidad (pagos rechazados, redirects, cuentas de prueba caducadas). Por eso **los pagos simulados están activos** hasta que el equipo reactive Checkout Pro en un entorno estable (sandbox o producción).

Cuando el equipo vuelva a activar Mercado Pago, el flujo cambiará así:

1. Al comprar, serás redirigido a la **página de Mercado Pago** (entorno de prueba o cobro real).
2. Necesitarás abrir la app por una **URL HTTPS pública** (ngrok o dominio), no por `localhost`.
3. Podrás pagar como **invitado** con tarjeta de prueba o iniciar sesión con un **comprador de prueba** del panel de Mercado Pago Developers.

### Tarjeta de prueba (referencia para sandbox)

| Campo | Valor |
|-------|-------|
| Número | `5474 9254 3267 0366` |
| CVV | `123` |
| Vencimiento | `11/30` |
| Titular | `APRO` |
| Documento (IFE, si lo pide) | `aaaaaa11111111a111` |

### Consejos si se reactiva Mercado Pago

- Usa **ventana de incógnito** y no mezcles tu cuenta real de Mercado Pago con cuentas de prueba.
- No uses tarjetas guardadas en la cuenta de prueba; elige **«Pagar con otro medio»** y una tarjeta nueva con titular **APRO**.
- Las credenciales del comprador de prueba se generan en [Mercado Pago Developers](https://www.mercadopago.com.mx/developers/panel/app) → **Cuentas de prueba** → **Comprador** (cada cuenta tiene su propio usuario y contraseña).

---

*GeoViabilidad Hook — guía para usuarios de prueba · PhiQus · Entorno de desarrollo (pagos simulados, sin cobros reales)*
