/* =====================================================================
   GeoViabilidad Hook - Lógica Principal de la SPA (app.js)
   ===================================================================== */

// --- ESTADO GLOBAL DE LA APLICACIÓN ---
const state = {
    map: null,
    centerMarker: null,
    bufferOverlay: null,
    competitorMarkers: [],
    poiMarkers: [],
    
    // Configuración seleccionada
    selectedLat: null,
    selectedLng: null,
    selectedGiro: '',
    selectedRadio: 1000,
    
    // Perfiles y Tokens
    currentUserRole: 'user', // 'user' o 'admin'
    currentTheme: 'dark', // 'dark' o 'light'
    
    // Capas de azulejos de Leaflet
    tileLayer: null,
    tilesDark: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    tilesLight: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    tilesAttrib: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    
    // Gráficos activos de Chart.js (para destruirlos al actualizar)
    charts: {
        competitors: null,
        poi: null
    },
    
    // Transacciones y órdenes
    activeOrderId: null,
    activeCheckoutId: null,
    activeTier: null
};

// --- INICIALIZACIÓN AL CARGAR LA PÁGINA ---
document.addEventListener("DOMContentLoaded", () => {
    logger("Iniciando SPA de GeoViabilidad Hook...");
    
    // 1. Inicializar el Visor Cartográfico (Leaflet)
    initMap();
    
    // 2. Vincular Eventos de la UI
    bindUIEvents();
    
    // 3. Comprobar y crear carpetas locales estáticas en desarrollo
    logger("Inicialización completa. Esperando clic en el mapa...");
});

// --- LOGGER INTERNO ---
function logger(message, data = null) {
    const timestamp = new Date().toLocaleTimeString();
    if (data) {
        console.log(`[${timestamp}] 📍 ${message}`, data);
    } else {
        console.log(`[${timestamp}] 📍 ${message}`);
    }
}

// --- CONFIGURACIÓN E INICIALIZACIÓN DEL MAPA ---
function initMap() {
    // Coordenadas iniciales: Zócalo de la Ciudad de México
    const cdmxCoords = [19.432608, -99.133208];
    
    // Instanciar mapa Leaflet
    state.map = L.map("map", {
        zoomControl: true,
        attributionControl: true
    }).setView(cdmxCoords, 14);
    
    // Registrar capa de azulejos según el tema (Oscuro por defecto)
    state.tileLayer = L.tileLayer(state.tilesDark, {
        attribution: state.tilesAttrib,
        maxZoom: 20
    }).addTo(state.map);
    
    // Escuchar clics en el mapa
    state.map.on("click", (e) => {
        handleMapClick(e.latlng.lat, e.latlng.lng);
    });
    
    logger("Leaflet.js cargado con tema oscuro (CartoDB Dark Matter).");
}

// --- VINCULACIÓN DE EVENTOS DE CONTROLES ---
function bindUIEvents() {
    // A. Slider de Radio
    const slider = document.getElementById("radio-slider");
    const radioVal = document.getElementById("radio-val");
    slider.addEventListener("input", (e) => {
        state.selectedRadio = parseInt(e.target.value);
        radioVal.textContent = `${state.selectedRadio.toLocaleString()} m`;
        
        // Redibujar círculo de búfer en tiempo real si hay un marcador situado
        if (state.centerMarker) {
            drawBufferCircle();
        }
    });
    
    // B. Giro comercial
    const giroSelect = document.getElementById("giro-select");
    giroSelect.addEventListener("change", (e) => {
        state.selectedGiro = e.target.value;
        checkFormValidity();
    });
    
    // C. Alternador de Tema Dinámico (Sun/Moon Switcher)
    const themeBtn = document.getElementById("theme-toggle-btn");
    themeBtn.addEventListener("click", toggleTheme);
    
    // D. Perfil de Usuario Cognito Simulado
    const roleSelect = document.getElementById("user-role-select");
    roleSelect.addEventListener("change", (e) => {
        state.currentUserRole = e.target.value;
        logger(`Usuario Cognito cambiado a: ${state.currentUserRole}`);
    });
    
    // E. Botón de Analizar Ubicación (Previa)
    const analyzeBtn = document.getElementById("analyze-btn");
    analyzeBtn.addEventListener("click", runPreviewAnalysis);
    
    // F. Botones de Compra de Tiers
    document.getElementById("buy-basico-btn").addEventListener("click", () => openPaymentModal("basico"));
    document.getElementById("buy-pro-btn").addEventListener("click", () => openPaymentModal("pro"));
    document.getElementById("buy-premium-btn").addEventListener("click", () => openPaymentModal("premium"));
    
    // G. Cerrar Modal de Pago
    document.getElementById("close-modal-btn").addEventListener("click", closePaymentModal);
    document.getElementById("cancel-payment-btn").addEventListener("click", closePaymentModal);
    
    // H. Cambiar Opción de Pago Simulada
    const payOptions = document.querySelectorAll(".pay-option-btn");
    payOptions.forEach(btn => {
        btn.addEventListener("click", (e) => {
            payOptions.forEach(b => b.classList.remove("active"));
            const targetBtn = e.target.closest(".pay-option-btn");
            targetBtn.classList.add("active");
        });
    });
    
    // I. Confirmar Pago Simulado
    document.getElementById("confirm-payment-btn").addEventListener("click", processSimulatedPayment);
    
    // J. Descarga de PDF
    document.getElementById("download-pdf-btn").addEventListener("click", triggerPDFDownload);
}

// --- DETECTAR Y APLICAR CAMBIO DE TEMA (Alternador de Temas) ---
function toggleTheme() {
    const body = document.getElementById("body-app");
    const themeIcon = document.getElementById("theme-icon");
    
    if (state.currentTheme === 'dark') {
        // Cambiar a Claro
        state.currentTheme = 'light';
        body.classList.remove("dark-theme");
        body.classList.add("light-theme");
        themeIcon.textContent = "🌙";
        
        // Reemplazar azulejos del mapa
        state.map.removeLayer(state.tileLayer);
        state.tileLayer = L.tileLayer(state.tilesLight, {
            attribution: state.tilesAttrib,
            maxZoom: 20
        }).addTo(state.map);
        
        logger("Alternado a Modo Claro (CartoDB Positron).");
    } else {
        // Cambiar a Oscuro
        state.currentTheme = 'dark';
        body.classList.remove("light-theme");
        body.classList.add("dark-theme");
        themeIcon.textContent = "☀️";
        
        // Reemplazar azulejos del mapa
        state.map.removeLayer(state.tileLayer);
        state.tileLayer = L.tileLayer(state.tilesDark, {
            attribution: state.tilesAttrib,
            maxZoom: 20
        }).addTo(state.map);
        
        logger("Alternado a Modo Oscuro (CartoDB Dark Matter).");
    }
}

// --- MANEJO DE CLIC EN EL MAPA ---
async function handleMapClick(lat, lng) {
    state.selectedLat = lat;
    state.selectedLng = lng;
    
    logger(`Clic detectado en coordenadas: (${lat.toFixed(6)}, ${lng.toFixed(6)})`);
    
    // 1. Mostrar Coordenadas en la UI
    const coordsDisplay = document.getElementById("lat-lng-text");
    coordsDisplay.textContent = `${lat.toFixed(6)}, ${lng.toFixed(6)}`;
    
    // 2. Colocar o Mover Marcador Principal
    if (state.centerMarker) {
        state.centerMarker.setLatLng([lat, lng]);
    } else {
        const customIcon = L.divIcon({
            html: '<div style="background-color: #2563eb; width: 14px; height: 14px; border-radius: 50%; border: 2px solid white; box-shadow: 0 0 10px #3b82f6;"></div>',
            className: 'custom-pin',
            iconSize: [14, 14],
            iconAnchor: [7, 7]
        });
        state.centerMarker = L.marker([lat, lng], { icon: customIcon }).addTo(state.map);
    }
    
    // 3. Trazar Círculo de Amortiguamiento
    drawBufferCircle();
    
    // 4. Invocar Geocodificación Inversa (GET /api/analizar/geocodificar)
    const addressBanner = document.getElementById("address-banner");
    const addressText = document.getElementById("address-text");
    
    addressBanner.classList.remove("hidden");
    addressText.textContent = "Resolviendo dirección postal mexicana...";
    
    try {
        const headers = getAuthHeaders();
        const response = await fetch(`/api/analizar/geocodificar?lat=${lat}&lng=${lng}`, {
            method: "GET",
            headers: headers
        });
        
        if (response.ok) {
            const data = await response.json();
            const formattedAddress = data.direccion.formato_completo;
            addressText.textContent = formattedAddress;
            logger("Geocodificación resuelta con éxito:", formattedAddress);
        } else {
            addressText.textContent = "Ubicación en México detectada.";
        }
    } catch (err) {
        logger("Falla de red en geocodificador inverso:", err);
        addressText.textContent = "Ubicación detectada (Sin red).";
    }
    
    // Centrar mapa suavemente
    state.map.panTo([lat, lng]);
    
    // Validar formulario
    checkFormValidity();
}

// --- DIBUJAR CÍRCULO DE BÚFER ---
function drawBufferCircle() {
    if (state.bufferOverlay) {
        state.map.removeLayer(state.bufferOverlay);
    }
    
    state.bufferOverlay = L.circle([state.selectedLat, state.selectedLng], {
        color: '#3b82f6',
        fillColor: '#3b82f6',
        fillOpacity: 0.12,
        radius: state.selectedRadio,
        weight: 1.5,
        dashArray: '5, 5'
    }).addTo(state.map);
}

// --- CABECERAS DE AUTENTICACIÓN SIMULADAS DE COGNITO ---
function getAuthHeaders() {
    // Inyecta el JWT simulado de Cognito en base al rol para satisfacer app/auth.py
    const token = state.currentUserRole === 'admin' ? "mock-jwt-admin" : "mock-jwt-user";
    return {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
    };
}

// --- COMPROBAR VALIDEZ DE FORMULARIO ---
function checkFormValidity() {
    const analyzeBtn = document.getElementById("analyze-btn");
    const isGiroSelected = state.selectedGiro !== '';
    const isCoordsSelected = state.selectedLat !== null && state.selectedLng !== null;
    
    if (isGiroSelected && isCoordsSelected) {
        analyzeBtn.removeAttribute("disabled");
    } else {
        analyzeBtn.setAttribute("disabled", "true");
    }
}

// --- EJECUTAR VISTA PREVIA GRATUITA (RF-05.4 & RF-01.4) ---
async function runPreviewAnalysis() {
    logger("Detonando Vista Previa Gratuita...");
    
    // Cambiar estado visual del botón
    const btn = document.getElementById("analyze-btn");
    btn.innerHTML = `<span class="btn-icon">⏳</span> PROCESANDO DATOS INEGI...`;
    btn.setAttribute("disabled", "true");
    
    try {
        const headers = getAuthHeaders();
        // Llamar a la Previa (POST /api/analizar/previa)
        const url = `/api/analizar/previa?lat=${state.selectedLat}&lng=${state.selectedLng}&radio_metros=${state.selectedRadio}&rubro=${state.selectedGiro}`;
        const response = await fetch(url, {
            method: "POST",
            headers: headers
        });
        
        if (response.ok) {
            const data = await response.json();
            logger("Resultados de Vista Previa recibidos exitosamente", data);
            
            // 1. Mostrar el Dashboard de Resultados
            document.getElementById("results-dashboard").classList.remove("hidden");
            
            // 2. Rellenar los KPIs de la Vista Previa
            document.getElementById("tier-badge").textContent = "VISTA PREVIA GRATUITA";
            document.getElementById("tier-badge").className = "badge";
            
            document.getElementById("kpi-sva").textContent = `${data.score_viabilidad_sva}/100`;
            document.getElementById("kpi-poblacion").textContent = data.poblacion_estimada.toLocaleString();
            document.getElementById("kpi-competidores").textContent = data.competidores_conteo;
            
            // Estilo dinámico de la tarjeta del Score SVA
            const kpiCard = document.getElementById("kpi-sva-card");
            if (data.score_viabilidad_sva >= 80) {
                kpiCard.style.borderLeft = "4px solid var(--success-color)";
            } else if (data.score_viabilidad_sva >= 50) {
                kpiCard.style.borderLeft = "4px solid var(--warning-color)";
            } else {
                kpiCard.style.borderLeft = "4px solid var(--danger-color)";
            }
            
            // 3. Bloquear / Vaciar Paneles de Gráficos y FODA
            lockAdvancedFeatures();
            
            // 4. Limpiar marcadores antiguos de competidores/POIs del mapa
            clearMapPins();
            
            // Hacer scroll suave hacia el Dashboard
            document.getElementById("results-dashboard").scrollIntoView({ behavior: 'smooth' });
        } else {
            alert("Error al procesar el análisis de la previa. Comprueba la conexión.");
        }
    } catch (err) {
        logger("Error en petición a la previa:", err);
        alert("Falla de red al conectar con el servidor FastAPI.");
    } finally {
        btn.innerHTML = `<span class="btn-icon">⚡</span> ANALIZAR UBICACIÓN`;
        btn.removeAttribute("disabled");
    }
}

// --- LIMPIAR PINS DE COMPETIDORES Y POIs ---
function clearMapPins() {
    state.competitorMarkers.forEach(m => state.map.removeLayer(m));
    state.competitorMarkers = [];
    state.poiMarkers.forEach(m => state.map.removeLayer(m));
    state.poiMarkers = [];
}

// --- BLOQUEAR CAMPOS DEL TIER GRATUITO ---
function lockAdvancedFeatures() {
    // Mensajes de bloqueo
    document.getElementById("comp-chart-locked-msg").classList.remove("hidden");
    document.getElementById("poi-chart-locked-msg").classList.remove("hidden");
    document.getElementById("foda-locked-msg").classList.remove("hidden");
    
    // Ocultar proyecciones financieras y descargas
    document.getElementById("financial-section").classList.add("hidden");
    document.getElementById("download-section").classList.add("hidden");
    
    // Mostrar botones de compra
    document.getElementById("dashboard-actions").classList.remove("hidden");
    
    // Desactivar FODA textos
    document.getElementById("foda-f-text").textContent = "🔒 Requiere plan Básico o Pro.";
    document.getElementById("foda-o-text").textContent = "🔒 Requiere plan Básico o Pro.";
    document.getElementById("foda-d-text").textContent = "🔒 Requiere plan Básico o Pro.";
    document.getElementById("foda-a-text").textContent = "🔒 Requiere plan Básico o Pro.";
    
    // Destruir gráficos de Chart.js si existían
    if (state.charts.competitors) {
        state.charts.competitors.destroy();
        state.charts.competitors = null;
    }
    if (state.charts.poi) {
        state.charts.poi.destroy();
        state.charts.poi = null;
    }
}

// --- ABRIR MODAL DE PASARELA DE PAGOS ---
async function openPaymentModal(tier) {
    state.activeTier = tier;
    
    logger(`Solicitando preferencia de Mercado Pago para Tier: ${tier.toUpperCase()}`);
    
    const billingTitle = document.getElementById("billing-title");
    const billingPrice = document.getElementById("billing-price");
    
    // Asignar conceptos en base al Tier
    if (tier === "basico") {
        billingTitle.textContent = "Reporte Comercial BÁSICO (6 Páginas + INEGI)";
        billingPrice.textContent = "$99.00 MXN";
    } else if (tier === "pro") {
        billingTitle.textContent = "Reporte Comercial PRO (10 Páginas + Mapas + Huff)";
        billingPrice.textContent = "$249.00 MXN";
    } else {
        billingTitle.textContent = "Reporte PREMIUM (14 Páginas + ROI + Afluencia Satelital)";
        billingPrice.textContent = "$499.00 MXN";
    }
    
    // Ocultar barra de carga anterior
    document.getElementById("compilation-progress-container").classList.add("hidden");
    document.getElementById("confirm-payment-btn").removeAttribute("disabled");
    
    // 1. Invocar API de preferencia para registrar en BD
    try {
        const headers = getAuthHeaders();
        const payload = {
            tier_adquirido: tier,
            latitud: state.selectedLat,
            longitud: state.selectedLng,
            radio_metros: state.selectedRadio,
            rubro: state.selectedGiro,
            intenciones: document.getElementById("intenciones-textarea").value || "Evaluación comercial del giro en la zona residencial mexicana."
        };
        
        const response = await fetch("/api/pagos/preferencia", {
            method: "POST",
            headers: headers,
            body: JSON.stringify(payload)
        });
        
        if (response.ok) {
            const data = await response.json();
            state.activeOrderId = data.orden_id;
            state.activeCheckoutId = data.checkout_id;
            logger(`Preferencia generada correctamente. Orden ID: ${data.orden_id} | Checkout: ${data.checkout_id}`);
            
            // Mostrar modal en la interfaz
            document.getElementById("payment-modal").classList.remove("hidden");
        } else {
            alert("No se pudo generar la orden de cobro temporal.");
        }
    } catch (err) {
        logger("Falla de red al crear preferencia:", err);
        alert("Error al conectar con la pasarela de Mercado Pago.");
    }
}

// --- CERRAR MODAL ---
function closePaymentModal() {
    document.getElementById("payment-modal").classList.add("hidden");
}

// --- PROCESAR PAGO SIMULADO (WEBHOOK MOCK & POLLING) ---
async function processSimulatedPayment() {
    const activeOption = document.querySelector(".pay-option-btn.active");
    const paymentStatus = activeOption.getAttribute("data-status");
    
    logger(`Confirmando pago simulado. Estatus elegido: ${paymentStatus.toUpperCase()}`);
    
    // 1. Bloquear controles del modal
    document.getElementById("confirm-payment-btn").setAttribute("disabled", "true");
    const progressContainer = document.getElementById("compilation-progress-container");
    const progressFill = document.getElementById("progress-bar-fill");
    const statusText = document.getElementById("compilation-status-text");
    
    progressContainer.classList.remove("hidden");
    statusText.textContent = "Acreditando pago seguro en Mercado Pago...";
    progressFill.style.width = "0%";
    
    // 2. Invocar Webhook de simulación (/api/pagos/webhook-mock)
    try {
        const response = await fetch("/api/pagos/webhook-mock", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                checkout_id: state.activeCheckoutId,
                estado_pago: paymentStatus
            })
        });
        
        if (!response.ok) {
            alert("El webhook mock del servidor rechazó la simulación.");
            closePaymentModal();
            return;
        }
        
        const resData = await response.json();
        logger("Acreditación simulada de webhook procesada:", resData);
        
        if (paymentStatus === "approved") {
            // Animación de barra de progreso interactiva (3 segundos) para simular ReportLab / S3
            let progress = 0;
            statusText.textContent = "Detonando BackgroundTask en FastAPI. Compilando PDF ReportLab...";
            
            const progressInterval = setInterval(() => {
                progress += 5;
                progressFill.style.width = `${progress}%`;
                
                if (progress === 40) {
                    statusText.textContent = "Invocando IA estratégica en AWS Bedrock (Llama 3 70B)...";
                } else if (progress === 70) {
                    statusText.textContent = "Escribiendo reporte encriptado en Amazon S3 (KMS)...";
                } else if (progress === 90) {
                    statusText.textContent = "Enviando confirmación de SES con enlace privado...";
                }
                
                if (progress >= 100) {
                    clearInterval(progressInterval);
                    logger("Simulación de compilación finalizada con éxito.");
                    closePaymentModal();
                    
                    // Cargar los resultados desbloqueados
                    unlockPaidReport();
                }
            }, 150);
        } else {
            statusText.textContent = `Pago finalizado con estatus: ${paymentStatus.toUpperCase()}`;
            setTimeout(() => {
                closePaymentModal();
                alert(`La transacción fue marcada como: ${paymentStatus.toUpperCase()}. El reporte permanece bloqueado.`);
            }, 1500);
        }
        
    } catch (err) {
        logger("Falla al notificar webhook simulado:", err);
        alert("Error de red en el webhook mock.");
        closePaymentModal();
    }
}

// --- DESBLOQUEAR Y RENDERIZAR RESULTADOS ADQUIRIDOS (RF-05.4 & RF-01.4) ---
async function unlockPaidReport() {
    logger(`Desbloqueando resultados del reporte. Orden ID: ${state.activeOrderId} | Tier: ${state.activeTier.toUpperCase()}`);
    
    const headers = getAuthHeaders();
    try {
        const response = await fetch(`/api/analizar/resultado/${state.activeOrderId}`, {
            method: "GET",
            headers: headers
        });
        
        if (response.ok) {
            const data = await response.json();
            logger("Datos completos del reporte comercial recibidos:", data);
            
            const metricas = data.metricas;
            const iaAnalisis = data.analisis_estrategico_ia;
            
            // 1. Actualizar Badge y cabecera
            const tierBadge = document.getElementById("tier-badge");
            tierBadge.textContent = `REPORTE ${state.activeTier.toUpperCase()}`;
            tierBadge.className = `badge ${state.activeTier}`;
            
            // Ocultar botones de compra y mostrar el botón de descarga
            document.getElementById("dashboard-actions").classList.add("hidden");
            document.getElementById("download-section").classList.remove("hidden");
            
            // 2. Rellenar FODA
            document.getElementById("foda-locked-msg").classList.add("hidden");
            renderFODA(iaAnalisis.foda_analisis || iaAnalisis);
            
            // 3. Rellenar gráficos dinámicos (si PRO o PREMIUM)
            if (state.activeTier === "pro" || state.activeTier === "premium") {
                document.getElementById("comp-chart-locked-msg").classList.add("hidden");
                document.getElementById("poi-chart-locked-msg").classList.add("hidden");
                
                // Pintar pines de competidores en el mapa
                renderCompetitorPins(metricas.competidores_listado);
                
                // Generar Gráfico de Competidores
                renderCompetitorsChart(metricas.competidores_listado);
                
                // Generar Gráfico de Atractores/POIs
                renderPOIChart();
            }
            
            // 4. Rellenar finanzas y ROI (si PREMIUM)
            if (state.activeTier === "premium") {
                document.getElementById("financial-section").classList.remove("hidden");
                document.getElementById("financial-ticket").textContent = iaAnalisis.ticket_recomendado || "$180 - $250 MXN";
                document.getElementById("financial-roi").textContent = iaAnalisis.roi_estimado || "14 a 18 Meses";
            } else {
                document.getElementById("financial-section").classList.add("hidden");
            }
            
            // Scroll suave a los gráficos
            document.getElementById("advanced-charts-section").scrollIntoView({ behavior: 'smooth' });
            
        } else {
            alert("No pudimos recuperar los datos completos del reporte.");
        }
    } catch (err) {
        logger("Falla al recuperar resultados pagados:", err);
        alert("Error de red al consultar el endpoint de resultados.");
    }
}

// --- RENDERIZAR PINS DE LA COMPETENCIA ---
function renderCompetitorPins(competidores) {
    clearMapPins();
    
    logger(`Trazando pins en el mapa para ${competidores.length} comercios locales.`);
    
    // Icono rojo premium con sombra para competidores
    const competitorIcon = L.divIcon({
        html: '<div style="background-color: #dc2626; width: 10px; height: 10px; border-radius: 50%; border: 1.5px solid white; box-shadow: 0 0 8px #ef4444;"></div>',
        className: 'competitor-pin',
        iconSize: [10, 10],
        iconAnchor: [5, 5]
    });
    
    competidores.forEach(comp => {
        if (comp.latitud && comp.longitud) {
            const marker = L.marker([comp.latitud, comp.longitud], { icon: competitorIcon })
                .addTo(state.map)
                .bindPopup(`<b>${comp.nombre}</b><br/>${comp.direccion}<br/>⭐ ${comp.rating} / 5.0`);
            state.competitorMarkers.push(marker);
        }
    });
    
    // Colocar atractores / POIs simulados de forma elegante en verde si es PREMIUM
    if (state.activeTier === "premium") {
        const allyIcon = L.divIcon({
            html: '<div style="background-color: #10b981; width: 10px; height: 10px; border-radius: 50%; border: 1.5px solid white; box-shadow: 0 0 8px #34d399;"></div>',
            className: 'ally-pin',
            iconSize: [10, 10],
            iconAnchor: [5, 5]
        });
        
        // Colocar 3 atractores alrededor del pin central
        const offset = 0.003;
        const pois = [
            { nombre: "Estación de Transporte Público", tipo: "Transporte" },
            { nombre: "Sucursal BBVA / Bancomer", tipo: "Banco" },
            { nombre: "Escuela Primaria Lic. Benito Juárez", tipo: "Escuela" }
        ];
        
        pois.forEach((poi, idx) => {
            const lat = state.selectedLat + (offset * (idx === 0 ? 1 : -0.5));
            const lng = state.selectedLng + (offset * (idx === 1 ? 1 : -0.8));
            const marker = L.marker([lat, lng], { icon: allyIcon })
                .addTo(state.map)
                .bindPopup(`<b>🌱 Aliado Comercial (Atractor)</b><br/>${poi.nombre}<br/>Categoría: ${poi.tipo}`);
            state.poiMarkers.push(marker);
        });
    }
}

// --- RENDERIZAR FODA ---
function renderFODA(fodaData) {
    const cardF = document.getElementById("foda-f-text");
    const cardO = document.getElementById("foda-o-text");
    const cardD = document.getElementById("foda-d-text");
    const cardA = document.getElementById("foda-a-text");
    
    if (typeof fodaData === "string") {
        // En caso de que Bedrock devuelva texto crudo plano en lugar de JSON
        const lines = fodaData.split("\n");
        let f = "", o = "", d = "", a = "";
        
        lines.forEach(line => {
            if (line.includes("Fortalezas") || line.includes("💪")) f += line + "<br/>";
            else if (line.includes("Oportunidades") || line.includes("🚀")) o += line + "<br/>";
            else if (line.includes("Debilidades") || line.includes("⚠️")) d += line + "<br/>";
            else if (line.includes("Amenazas") || line.includes("🔥")) a += line + "<br/>";
        });
        
        cardF.innerHTML = f || "La densidad de población proporciona un excelente colchón de demanda.";
        cardO.innerHTML = o || "Alianza estratégica con atractores viales cercanos.";
        cardD.innerHTML = d || "Presencia de competidores consolidados en el mismo radio.";
        cardA.innerHTML = a || "Riesgo de saturación por apertura rápida de franquicias.";
    } else {
        // Formato JSON limpio esperado
        cardF.innerHTML = fodaData.fortalezas || "Suficiente densidad de población residente.";
        cardO.innerHTML = fodaData.oportunidades || "Alta tracción en horas de comida/salida laboral.";
        cardD.innerHTML = fodaData.debilidades || "Existencia de competidores directos en la avenida.";
        cardA.innerHTML = fodaData.amenazas || "Saturación del nicho a mediano plazo.";
    }
}

// --- GRÁFICO 1: COMPETIDORES (Chart.js Bar) ---
function renderCompetitorsChart(competidores) {
    if (state.charts.competitors) {
        state.charts.competitors.destroy();
    }
    
    // Clasificar competidores por rating
    const ratings = { "5.0 - 4.5": 0, "4.4 - 4.0": 0, "3.9 - 3.0": 0, "< 3.0 / Sin Rating": 0 };
    competidores.forEach(c => {
        const r = c.rating || 0;
        if (r >= 4.5) ratings["5.0 - 4.5"]++;
        else if (r >= 4.0) ratings["4.4 - 4.0"]++;
        else if (r >= 3.0) ratings["3.9 - 3.0"]++;
        else ratings["< 3.0 / Sin Rating"]++;
    });
    
    const ctx = document.getElementById("competitors-chart").getContext("2d");
    state.charts.competitors = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: Object.keys(ratings),
            datasets: [{
                label: 'Número de Comercios',
                data: Object.values(ratings),
                backgroundColor: 'rgba(59, 130, 246, 0.65)',
                borderColor: '#3b82f6',
                borderWidth: 1.5,
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { precision: 0, color: '#94a3b8' },
                    grid: { color: 'rgba(255, 255, 255, 0.05)' }
                },
                x: {
                    ticks: { color: '#94a3b8' },
                    grid: { display: false }
                }
            }
        }
    });
}

// --- GRÁFICO 2: ATRACTORES / POIs (Chart.js Doughnut) ---
function renderPOIChart() {
    if (state.charts.poi) {
        state.charts.poi.destroy();
    }
    
    const dataValues = state.activeTier === "premium" ? [5, 4, 2] : [4, 2, 0];
    
    const ctx = document.getElementById("poi-chart").getContext("2d");
    state.charts.poi = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Transporte Público', 'Escuelas Privadas', 'Bancos'],
            datasets: [{
                data: dataValues,
                backgroundColor: [
                    'rgba(16, 185, 129, 0.65)', // Verde
                    'rgba(245, 158, 11, 0.65)', // Ámbar
                    'rgba(239, 68, 68, 0.65)'  // Rojo
                ],
                borderColor: [
                    '#10b981', '#f59e0b', '#ef4444'
                ],
                borderWidth: 1.5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#94a3b8', font: { size: 11 } }
                }
            }
        }
    });
}

// --- DESCARGA DE REPORTE PDF (GET /api/analizar/pdf/{orden_id}) ---
async function triggerPDFDownload() {
    logger(`Solicitando descarga de PDF para Orden ID: ${state.activeOrderId}...`);
    
    const headers = getAuthHeaders();
    try {
        const response = await fetch(`/api/analizar/pdf/${state.activeOrderId}`, {
            method: "GET",
            headers: headers
        });
        
        if (response.ok) {
            const data = await response.json();
            const downloadUrl = data.url_descarga;
            logger(`URL firmada privada resuelta. Descargando desde: ${downloadUrl}`);
            
            // Abrir descarga en pestaña del navegador
            window.open(downloadUrl, "_blank");
        } else {
            alert("No se pudo resolver la URL privada de descarga.");
        }
    } catch (err) {
        logger("Falla al descargar PDF:", err);
        alert("Error de red al conectar con el servidor S3/FastAPI.");
    }
}
