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
    currentUserRole: 'guest', // 'guest', 'user', o 'admin'
    currentTheme: 'light', // 'dark' o 'light'
    
    // Capas de azulejos de Leaflet
    tileLayer: null,
    tilesDark: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    tilesLight: 'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    tilesAttrib: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    
    // Gráficos activos de Chart.js (para destruirlos al actualizar)
    charts: {
        competitors: null
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
    
    // Registrar capa de azulejos según el tema (Claro por defecto)
    state.tileLayer = L.tileLayer(state.tilesLight, {
        attribution: state.tilesAttrib,
        maxZoom: 20
    }).addTo(state.map);
    
    // Escuchar clics en el mapa
    state.map.on("click", (e) => {
        handleMapClick(e.latlng.lat, e.latlng.lng);
    });
    
    logger("Leaflet.js cargado con tema claro (CartoDB Positron).");
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
    const customGiroContainer = document.getElementById("custom-giro-container");
    const customGiroInput = document.getElementById("custom-giro-input");

    giroSelect.addEventListener("change", (e) => {
        if (e.target.value === "otro") {
            customGiroContainer.classList.remove("hidden");
            state.selectedGiro = customGiroInput.value.trim();
        } else {
            customGiroContainer.classList.add("hidden");
            state.selectedGiro = e.target.value;
        }
        checkFormValidity();
    });

    customGiroInput.addEventListener("input", (e) => {
        if (giroSelect.value === "otro") {
            state.selectedGiro = e.target.value.trim();
            checkFormValidity();
        }
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
    document.getElementById("buy-basico-btn").addEventListener("click", () => checkAuthAndBuy("basico"));
    document.getElementById("buy-pro-btn").addEventListener("click", () => checkAuthAndBuy("pro"));
    document.getElementById("buy-premium-btn").addEventListener("click", () => checkAuthAndBuy("premium"));
    
    // G. Cerrar Modal de Pago y de Login Google
    document.getElementById("close-modal-btn").addEventListener("click", closePaymentModal);
    document.getElementById("cancel-payment-btn").addEventListener("click", closePaymentModal);
    document.getElementById("close-login-modal-btn").addEventListener("click", () => {
        document.getElementById("google-login-modal").classList.add("hidden");
    });
    
    // G2. Iniciar Sesión con Google
    document.getElementById("google-signin-btn").addEventListener("click", processGoogleSigninMock);
    
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
    
    // K. Enforzar límites de selección de checkboxes en el panel izquierdo (máximo 5 cada uno)
    setupLeftPanelCheckboxLimits();
    
    // L. Buscador de dirección flotante sobre el mapa
    setupMapSearchBox();

    // M. Configurar la tarjeta introductoria de contexto
    setupIntroCard();
}

function setupIntroCard() {
    const introCard = document.getElementById("app-intro-card");
    const closeBtn = document.getElementById("close-intro-btn");
    if (!introCard || !closeBtn) return;

    // Verificar localStorage
    if (localStorage.getItem("hide_intro_card") === "true") {
        introCard.classList.add("collapsed");
        introCard.classList.add("hidden");
    }

    // Event listener
    closeBtn.addEventListener("click", () => {
        logger("Ocultando tarjeta de descripción de la app...");
        introCard.classList.add("collapsed");
        localStorage.setItem("hide_intro_card", "true");
        
        // Esperar a que termine la animación de transición CSS antes de aplicar hidden
        setTimeout(() => {
            introCard.classList.add("hidden");
        }, 400);
    });
}

function setupLeftPanelCheckboxLimits() {
    const enforceLimits = (containerId, maxLimit, textInputId, iaCheckboxId) => {
        const container = document.getElementById(containerId);
        if (!container) return;
        const checkboxes = container.querySelectorAll("input[type='checkbox']");
        const iaCheckbox = document.getElementById(iaCheckboxId);
        const textInput = document.getElementById(textInputId);

        const updateState = () => {
            if (iaCheckbox && iaCheckbox.checked) {
                // Si la IA está activa, desmarcar y deshabilitar todos los demás
                checkboxes.forEach(c => {
                    if (c !== iaCheckbox) {
                        c.checked = false;
                        c.disabled = true;
                        c.parentElement.classList.add("disabled-by-ia");
                    }
                });
                if (textInput) {
                    textInput.disabled = true;
                    textInput.value = "";
                    textInput.classList.add("disabled-by-ia");
                }
            } else {
                // Si la IA no está activa, habilitar de acuerdo al límite
                // Contar seleccionados (excluyendo el checkbox de IA)
                const normalCheckboxes = Array.from(checkboxes).filter(c => c !== iaCheckbox);
                const checkedCount = normalCheckboxes.filter(c => c.checked).length;

                normalCheckboxes.forEach(c => {
                    c.disabled = checkedCount >= maxLimit && !c.checked;
                    if (c.disabled) {
                        c.parentElement.classList.add("disabled-by-ia");
                    } else {
                        c.parentElement.classList.remove("disabled-by-ia");
                    }
                });

                if (iaCheckbox) {
                    iaCheckbox.disabled = false;
                    iaCheckbox.parentElement.classList.remove("disabled-by-ia");
                }
                if (textInput) {
                    textInput.disabled = false;
                    textInput.classList.remove("disabled-by-ia");
                }
            }
        };

        checkboxes.forEach(cb => {
            cb.addEventListener("change", () => {
                // Si se selecciona un checkbox normal y el de IA estaba marcado, desmarcar IA
                if (iaCheckbox && cb !== iaCheckbox && cb.checked && iaCheckbox.checked) {
                    iaCheckbox.checked = false;
                }
                updateState();
            });
        });

        if (textInput) {
            textInput.addEventListener("input", () => {
                if (textInput.value.trim() !== "" && iaCheckbox && iaCheckbox.checked) {
                    iaCheckbox.checked = false;
                    updateState();
                }
            });
        }

        // Ejecutar inicialmente
        updateState();
    };
    enforceLimits("competidores-checkboxes", 5, "competidores-adicionales-input", "competidores-ia-auto");
    enforceLimits("aliados-checkboxes", 5, "aliados-adicionales-input", "aliados-ia-auto");
}

function setupMapSearchBox() {
    const searchInput = document.getElementById("map-search-input");
    const searchBtn = document.getElementById("map-search-btn");
    const searchResults = document.getElementById("map-search-results");
    
    if (!searchInput || !searchBtn || !searchResults) return;
    
    // Función para disparar la búsqueda
    const executeSearch = async () => {
        const query = searchInput.value.trim();
        if (!query) {
            searchResults.innerHTML = "";
            searchResults.classList.add("hidden");
            return;
        }
        
        logger(`Iniciando búsqueda de dirección en México para: '${query}'`);
        
        try {
            const headers = getAuthHeaders();
            const response = await fetch(`/api/analizar/buscar-direccion?direccion=${encodeURIComponent(query)}`, {
                method: "GET",
                headers: headers
            });
            
            if (response.ok) {
                const data = await response.json();
                const resultados = data.resultados || [];
                
                if (resultados.length === 0) {
                    searchResults.innerHTML = '<p style="cursor: default; text-align: center; color: var(--text-secondary);">Sin resultados en México</p>';
                } else {
                    searchResults.innerHTML = resultados.map(item => `
                        <p data-lat="${item.latitud}" data-lng="${item.longitud}" title="${item.direccion}">${item.direccion}</p>
                    `).join("");
                    
                    // Agregar event listeners a cada opción
                    searchResults.querySelectorAll("p[data-lat]").forEach(p => {
                        p.addEventListener("click", (e) => {
                            const lat = parseFloat(e.target.getAttribute("data-lat"));
                            const lng = parseFloat(e.target.getAttribute("data-lng"));
                            const address = e.target.textContent;
                            
                            logger(`Ubicación seleccionada en buscador: ${address} en (${lat}, ${lng})`);
                            
                            // Centrar mapa
                            state.map.setView([lat, lng], 16);
                            
                            // Invocar al click handler estándar
                            handleMapClick(lat, lng);
                            
                            // Actualizar input y ocultar dropdown
                            searchInput.value = address;
                            searchResults.classList.add("hidden");
                        });
                    });
                }
                searchResults.classList.remove("hidden");
            } else {
                logger("Error al buscar dirección en el servidor.");
            }
        } catch (err) {
            logger("Error de red al geocodificar dirección:", err);
        }
    };
    
    // Buscar al dar clic al botón de lupa
    searchBtn.addEventListener("click", executeSearch);
    
    // Buscar al presionar Enter en el input
    searchInput.addEventListener("keypress", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            executeSearch();
        }
    });
    
    // Ocultar dropdown al hacer clic fuera
    document.addEventListener("click", (e) => {
        if (!e.target.closest("#search-box-container")) {
            searchResults.classList.add("hidden");
        }
    });
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
// --- APLICAR REGLAS DE BLUR Y CANDADO SEGÚN TIER ---
function applyBlurRules(tier) {
    const compWrapper = document.querySelector("#competitor-chart-card .canvas-wrapper");
    const poiWrapper = document.querySelector("#poi-chart-card .table-wrapper");
    const heatWrapper = document.getElementById("heatmap-grid-container");
    
    const compMsg = document.getElementById("comp-chart-locked-msg");
    const poiMsg = document.getElementById("poi-chart-locked-msg");
    const heatMsg = document.getElementById("heatmap-locked-msg");

    if (!compWrapper || !poiWrapper || !compMsg || !poiMsg) return;

    if (tier === "gratuito" || tier === "basico") {
        // Blur en todos
        compWrapper.classList.add("blurred-premium");
        poiWrapper.classList.add("blurred-premium");
        if (heatWrapper) heatWrapper.classList.add("blurred-premium");
        
        compMsg.classList.remove("hidden");
        poiMsg.classList.remove("hidden");
        if (heatMsg) heatMsg.classList.remove("hidden");
    } else if (tier === "pro") {
        // Competidores y Heatmap nítido, atractores blur
        compWrapper.classList.remove("blurred-premium");
        poiWrapper.classList.add("blurred-premium");
        if (heatWrapper) heatWrapper.classList.remove("blurred-premium");
        
        compMsg.classList.add("hidden");
        poiMsg.classList.remove("hidden");
        if (heatMsg) heatMsg.classList.add("hidden");
    } else if (tier === "premium") {
        // Todos nítidos
        compWrapper.classList.remove("blurred-premium");
        poiWrapper.classList.remove("blurred-premium");
        if (heatWrapper) heatWrapper.classList.remove("blurred-premium");
        
        compMsg.classList.add("hidden");
        poiMsg.classList.add("hidden");
        if (heatMsg) heatMsg.classList.add("hidden");
    }
}

// --- EJECUTAR VISTA PREVIA GRATUITA (RF-05.4 & RF-01.4) ---
async function runPreviewAnalysis() {
    logger("Detonando Vista Previa (Modo de Compra Directo)...");
    
    // Cambiar estado visual del botón
    const btn = document.getElementById("analyze-btn");
    btn.innerHTML = `<span class="btn-icon">⏳</span> CALCULANDO DATOS...`;
    btn.setAttribute("disabled", "true");
    
    try {
        // 1. Mostrar el Dashboard de Resultados
        document.getElementById("results-dashboard").classList.remove("hidden");
        
        // 2. Rellenar placeholders visuales iniciales
        document.getElementById("tier-badge").textContent = "VISTA PREVIA GRATUITA";
        document.getElementById("tier-badge").className = "badge";
        document.getElementById("dashboard-subtitle").textContent = "Estás viendo información real del INEGI y conteos de competencia en la zona de estudio.";
        
        // Estilo neutro de la tarjeta del Score SVA
        const kpiCard = document.getElementById("kpi-sva-card");
        if (kpiCard) kpiCard.style.borderLeft = "4px solid var(--text-secondary)";
        
        // 3. Bloquear / Vaciar Paneles de Gráficos y FODA
        lockAdvancedFeatures();
        
        // 4. Limpiar marcadores antiguos de competidores/POIs del mapa
        clearMapPins();
        
        // 5. Consumir endpoint real de Vista Previa en caliente
        const headers = getAuthHeaders();
        headers["Content-Type"] = "application/json";
        const queryParams = `lat=${state.selectedLat}&lng=${state.selectedLng}&radio_metros=${state.selectedRadio}&rubro=${encodeURIComponent(state.selectedGiro)}`;
        
        // Recopilar selecciones de competidores/aliados del formulario (incluido ia_auto)
        const compCheckboxes = document.querySelectorAll("#competidores-checkboxes input[type='checkbox']:checked");
        const competidoresSel = Array.from(compCheckboxes).map(cb => cb.value);
        const aliadosCheckboxes = document.querySelectorAll("#aliados-checkboxes input[type='checkbox']:checked");
        const aliadosSel = Array.from(aliadosCheckboxes).map(cb => cb.value);

        const previewBody = {
            competidores_seleccionados: competidoresSel.length > 0 ? competidoresSel : null,
            aliados_seleccionados: aliadosSel.length > 0 ? aliadosSel : null
        };

        const response = await fetch(`/api/analizar/previa?${queryParams}`, {
            method: "POST",
            headers: headers,
            body: JSON.stringify(previewBody)
        });
        
        if (response.ok) {
            const data = await response.json();
            logger("Datos de vista previa recibidos del backend:", data);
            
            // Rellenar los KPIs con los valores reales calculados
            document.getElementById("kpi-sva").textContent = `${data.score_viabilidad_sva}/100`;
            document.getElementById("kpi-poblacion").textContent = data.poblacion_estimada.toLocaleString();
            document.getElementById("kpi-competidores").textContent = data.competidores_conteo;

            // Actualizar descripciones de KPIs con explicaciones comerciales
            const sva = data.score_viabilidad_sva || 0;
            let svaDesc = "";
            if (sva >= 80) {
                svaDesc = "Obtuviste este puntaje alto porque la zona presenta un excelente balance: una sólida base de clientes potenciales cercanos y un nivel de competencia controlado que te facilitará crecer rápidamente.";
            } else if (sva >= 60) {
                svaDesc = "Tu puntaje es favorable. La zona tiene buena demanda residencial, aunque existe competencia activa con la que deberás competir ofreciendo un valor agregado o mejor servicio.";
            } else {
                svaDesc = "Tu puntaje es moderado o bajo debido a que la población en la zona es limitada para este rubro, o bien, existe una alta saturación de competidores disputándose a los mismos clientes.";
            }
            document.getElementById("kpi-sva-desc").textContent = svaDesc;
            document.getElementById("kpi-pob-desc").textContent = "Representa la cantidad de personas que viven a la redonda de tu local. Son tus clientes potenciales más valiosos porque, al residir en el área, comprarán de forma constante y recurrente.";
            document.getElementById("kpi-comp-desc").textContent = "Es el número de negocios parecidos al tuyo en la zona. Conocerlos te ayuda a saber con quiénes compartirás el mercado y qué tan difícil será destacar o si la zona ya está saturada.";

            // Estilo dinámico de la tarjeta del Score SVA según el puntaje obtenido
            if (kpiCard) {
                if (sva >= 80) {
                    kpiCard.style.borderLeft = "4px solid var(--success-color)";
                } else if (sva >= 50) {
                    kpiCard.style.borderLeft = "4px solid var(--warning-color)";
                } else {
                    kpiCard.style.borderLeft = "4px solid var(--danger-color)";
                }
            }

            // Generar Gráficos Avanzados
            renderCompetitorsChart(data.competidores_listado);
            renderPOITable(data);
            renderHeatmap(data.afluencia_peatonal);

            // Aplicar las reglas de blur para la vista previa
            applyBlurRules("gratuito");
            
            // Hacer scroll suave hacia el Dashboard
            document.getElementById("results-dashboard").scrollIntoView({ behavior: 'smooth' });
        } else {
            logger("Error al calcular la vista previa gratuita en el servidor.");
        }
        
    } catch (err) {
        logger("Error en la vista previa:", err);
    } finally {
        setTimeout(() => {
            btn.innerHTML = `<span class="btn-icon">⚡</span> ANALIZAR UBICACIÓN`;
            btn.removeAttribute("disabled");
        }, 300);
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
    
    const heatmapMsg = document.getElementById("heatmap-locked-msg");
    if (heatmapMsg) heatmapMsg.classList.remove("hidden");
    
    // Ocultar descargas
    document.getElementById("download-section").classList.add("hidden");
    
    // Mostrar botones de compra
    document.getElementById("dashboard-actions").classList.remove("hidden");
    
    // Destruir gráficos de Chart.js si existían
    if (state.charts.competitors) {
        state.charts.competitors.destroy();
        state.charts.competitors = null;
    }
    
    // Limpiar contenedor de mapa de calor
    const heatContainer = document.getElementById("heatmap-grid-container");
    if (heatContainer) heatContainer.innerHTML = "";
    
    // Restablecer la tabla de atractores / POIs a su estado inicial de carga
    const tbody = document.getElementById("poi-table-body");
    if (tbody) {
        tbody.innerHTML = `
            <tr>
                <td>Transporte Público</td>
                <td id="poi-count-transit">--</td>
                <td><span class="badge info">Cargando...</span></td>
            </tr>
            <tr>
                <td>Centros Educativos</td>
                <td id="poi-count-school">--</td>
                <td><span class="badge info">Cargando...</span></td>
            </tr>
            <tr>
                <td>Bancos y Finanzas</td>
                <td id="poi-count-bank">--</td>
                <td><span class="badge info">Cargando...</span></td>
            </tr>
        `;
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
        billingTitle.textContent = "Reporte Comercial BÁSICO (6 Páginas)";
        billingPrice.textContent = "$299.00 MXN";
    } else if (tier === "pro") {
        billingTitle.textContent = "Reporte Comercial PRO (10 Páginas + Mapas + Atracción)";
        billingPrice.textContent = "$649.00 MXN";
    } else {
        billingTitle.textContent = "Reporte PREMIUM (14 Páginas + ROI + Afluencia)";
        billingPrice.textContent = "$799.00 MXN";
    }
    
    // Ocultar barra de carga anterior
    document.getElementById("compilation-progress-container").classList.add("hidden");
    document.getElementById("confirm-payment-btn").removeAttribute("disabled");
    
    // 1. Invocar API de preferencia para registrar en BD
    try {
        const headers = getAuthHeaders();
        
        // Obtener competidores seleccionados
        const compCheckboxes = document.querySelectorAll("#competidores-checkboxes input[type='checkbox']:checked");
        let competidores_seleccionados = Array.from(compCheckboxes).map(cb => cb.value);

        // Obtener aliados seleccionados
        const aliadosCheckboxes = document.querySelectorAll("#aliados-checkboxes input[type='checkbox']:checked");
        let aliados_seleccionados = Array.from(aliadosCheckboxes).map(cb => cb.value);

        // Obtener entradas de texto libre
        const compAdicionales = document.getElementById("competidores-adicionales-input").value.trim();
        const aliadosAdicionales = document.getElementById("aliados-adicionales-input").value.trim();

        const categoryMap = {
            "ia_auto": "🤖 Determinar automáticamente por IA",
            "cafe": "Cafetería",
            "restaurant": "Restaurante",
            "fast_food": "Comida Rápida",
            "gym": "Gimnasio",
            "pharmacy": "Farmacia",
            "bakery": "Panadería",
            "beauty_salon": "Estética",
            "laundry": "Lavandería",
            "doctor": "Consultorio Médico",
            "bank": "Bancos",
            "school": "Escuelas",
            "transit_station": "Transporte Público",
            "supermarket": "Supermercado",
            "shopping_mall": "Centro Comercial",
            "convenience_store": "Tiendas de Conveniencia",
            "park": "Parques"
        };

        const summaryContainer = document.getElementById("modal-selections-summary");
        const summaryComps = document.getElementById("modal-summary-comps");
        const summaryAllies = document.getElementById("modal-summary-allies");

        // Ajustar según el nivel de pago (Tier)
        if (tier === "basico") {
            competidores_seleccionados = competidores_seleccionados.length > 0 ? competidores_seleccionados.slice(0, 1) : null;
            aliados_seleccionados = null;
        } else if (tier === "pro") {
            competidores_seleccionados = competidores_seleccionados.length > 0 ? competidores_seleccionados.slice(0, 3) : null;
            aliados_seleccionados = null;
        } else if (tier === "premium") {
            competidores_seleccionados = competidores_seleccionados.length > 0 ? competidores_seleccionados.slice(0, 5) : null;
            aliados_seleccionados = aliados_seleccionados.length > 0 ? aliados_seleccionados.slice(0, 5) : null;
        }

        // Configurar textos del resumen visual en el modal
        if (tier === "basico") {
            summaryContainer.classList.remove("hidden");
            const compLabel = competidores_seleccionados ? categoryMap[competidores_seleccionados[0]] : "Giro principal (Cafetería por defecto)";
            let compText = `🏪 <b>Competidor a analizar:</b> ${compLabel}`;
            if (compAdicionales) {
                compText += ` (+ "${compAdicionales}")`;
            }
            summaryComps.innerHTML = compText;
            summaryAllies.innerHTML = `🌱 <b>Aliados incluidos:</b> Ninguno (Omitido en Tier Básico)`;
        } else if (tier === "pro") {
            summaryContainer.classList.remove("hidden");
            const compLabels = competidores_seleccionados ? competidores_seleccionados.map(c => categoryMap[c] || c).join(", ") : "Giro principal por defecto";
            let compText = `🏪 <b>Competidores a analizar (Máx 3):</b> ${compLabels}`;
            if (compAdicionales) {
                compText += ` (+ "${compAdicionales}")`;
            }
            summaryComps.innerHTML = compText;
            summaryAllies.innerHTML = `🌱 <b>Aliados incluidos:</b> Ninguno (Omitido en Tier Pro)`;
        } else if (tier === "premium") {
            summaryContainer.classList.remove("hidden");
            const compLabels = competidores_seleccionados ? competidores_seleccionados.map(c => categoryMap[c] || c).join(", ") : "Giro principal por defecto";
            const allyLabels = aliados_seleccionados ? aliados_seleccionados.map(a => categoryMap[a] || a).join(", ") : "Bancos, Escuelas y Transporte por defecto";
            let compText = `🏪 <b>Competidores a analizar (Máx 5):</b> ${compLabels}`;
            if (compAdicionales) {
                compText += ` (+ "${compAdicionales}")`;
            }
            let allyText = `🌱 <b>Aliados a analizar (Máx 5):</b> ${allyLabels}`;
            if (aliadosAdicionales) {
                allyText += ` (+ "${aliadosAdicionales}")`;
            }
            summaryComps.innerHTML = compText;
            summaryAllies.innerHTML = allyText;
        } else {
            summaryContainer.classList.add("hidden");
        }

        const payload = {
            tier_adquirido: tier,
            latitud: state.selectedLat,
            longitud: state.selectedLng,
            radio_metros: state.selectedRadio,
            rubro: state.selectedGiro,
            intenciones: document.getElementById("intenciones-textarea").value || "Evaluación comercial del giro en la zona residencial mexicana.",
            competidores_seleccionados: competidores_seleccionados,
            aliados_seleccionados: aliados_seleccionados,
            competidores_adicionales: compAdicionales || null,
            aliados_adicionales: aliadosAdicionales || null
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
            statusText.textContent = "Procesando el cálculo analítico. Compilando reporte PDF...";
            
            const progressInterval = setInterval(() => {
                progress += 5;
                progressFill.style.width = `${progress}%`;
                
                if (progress === 40) {
                    statusText.textContent = "Generando diagnóstico estratégico inteligente con IA...";
                } else if (progress === 70) {
                    statusText.textContent = "Guardando reporte de forma segura...";
                } else if (progress === 90) {
                    statusText.textContent = "Enviando confirmación de compra con enlace de descarga...";
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
            
            // Actualizar KPIs de la interfaz con los datos reales del reporte pagado
            document.getElementById("kpi-sva").textContent = `${metricas.sva}/100`;
            document.getElementById("kpi-poblacion").textContent = metricas.poblacion_ponderada.toLocaleString();
            document.getElementById("kpi-competidores").textContent = metricas.competidores_conteo;

            // Estilo dinámico de la tarjeta del Score SVA según el puntaje obtenido
            const kpiCard = document.getElementById("kpi-sva-card");
            if (kpiCard) {
                if (metricas.sva >= 80) {
                    kpiCard.style.borderLeft = "4px solid var(--success-color)";
                } else if (metricas.sva >= 50) {
                    kpiCard.style.borderLeft = "4px solid var(--warning-color)";
                } else {
                    kpiCard.style.borderLeft = "4px solid var(--danger-color)";
                }
            }

            // Actualizar descripciones de KPIs con explicaciones claras para el usuario
            const sva = metricas.sva || 0;
            let svaDesc = "";
            if (sva >= 80) {
                svaDesc = "Obtuviste este puntaje alto porque la zona presenta un excelente balance: una sólida base de clientes potenciales cercanos y un nivel de competencia controlado que te facilitará crecer rápidamente.";
            } else if (sva >= 60) {
                svaDesc = "Tu puntaje es favorable. La zona tiene buena demanda residencial, aunque existe competencia activa con la que deberás competir ofreciendo un valor agregado o mejor servicio.";
            } else {
                svaDesc = "Tu puntaje es moderado o bajo debido a que la población en la zona es limitada para este rubro, o bien, existe una alta saturación de competidores disputándose a los mismos clientes.";
            }
            document.getElementById("kpi-sva-desc").textContent = svaDesc;

            document.getElementById("kpi-pob-desc").textContent = "Representa la cantidad de personas que viven a la redonda de tu local. Son tus clientes potenciales más valiosos porque, al residir en el área, comprarán de forma constante y recurrente.";
            
            document.getElementById("kpi-comp-desc").textContent = "Es el número de negocios parecidos al tuyo en la zona. Conocerlos te ayuda a saber con quiénes compartirás el mercado y qué tan difícil será destacar o si la zona ya está saturada.";
            
            // Ocultar botones de compra y mostrar el botón de descarga
            document.getElementById("dashboard-actions").classList.add("hidden");
            document.getElementById("download-section").classList.remove("hidden");
            
            // Pintar pines de competidores y aliados en el mapa (solo si Pro o Premium para el mapa físico)
            if (state.activeTier === "pro" || state.activeTier === "premium") {
                renderCompetitorPins(metricas.competidores_listado, metricas.aliados_listado);
            } else {
                clearMapPins();
            }
            
            // Generar Gráficos Avanzados siempre (el blur controla su visualización)
            renderCompetitorsChart(metricas.competidores_listado);
            renderPOITable(metricas);
            renderHeatmap(metricas.afluencia_peatonal);

            // Aplicar las reglas de blur y visibilidad de mensajes según el Tier activo
            applyBlurRules(state.activeTier);
            
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

// --- RENDERIZAR PINS DE LA COMPETENCIA Y POIs ---
function renderCompetitorPins(competidores, aliados) {
    clearMapPins();
    
    logger(`Trazando pins en el mapa para ${competidores.length} competidores locales.`);
    
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
                .bindPopup(`<b>${comp.nombre}</b><br/>${comp.direccion || 'Dirección no disponible'}<br/>⭐ ${comp.rating} / 5.0`);
            state.competitorMarkers.push(marker);
        }
    });
    
    // Colocar atractores / POIs reales de forma elegante en verde si es PREMIUM
    if (state.activeTier === "premium" && aliados) {
        const allyIcon = L.divIcon({
            html: '<div style="background-color: #10b981; width: 10px; height: 10px; border-radius: 50%; border: 1.5px solid white; box-shadow: 0 0 8px #34d399;"></div>',
            className: 'ally-pin',
            iconSize: [10, 10],
            iconAnchor: [5, 5]
        });
        
        aliados.forEach(poi => {
            if (poi.latitud && poi.longitud) {
                const marker = L.marker([poi.latitud, poi.longitud], { icon: allyIcon })
                    .addTo(state.map)
                    .bindPopup(`<b>🌱 Aliado Comercial (Atractor)</b><br/>${poi.nombre}<br/>Categoría: ${poi.tipo}<br/>⭐ ${poi.rating} / 5.0`);
                state.poiMarkers.push(marker);
            }
        });
    }
}

// --- RENDERIZAR MAPA DE CALOR (HEATMAP) ---
function renderHeatmap(afluencia) {
    const gridContainer = document.getElementById("heatmap-grid-container");
    if (!gridContainer) return;
    
    // Limpiar contenedor anterior
    gridContainer.innerHTML = "";
    
    // Si no hay datos, mostrar aviso
    if (!afluencia || afluencia.status === "no_data" || !afluencia.afluencia_semanal) {
        gridContainer.innerHTML = `<p class="chart-helper-text" style="padding: 20px;">⚠️ No hay datos de telemetría peatonal disponibles en esta zona.</p>`;
        return;
    }
    
    const afluenciaSemanal = afluencia.afluencia_semanal;
    const dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
    
    // Crear tabla HTML
    const table = document.createElement("table");
    table.className = "heatmap-table";
    
    // 1. Cabecera (Horas: de 08:00 a 22:00)
    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    
    const dayHeader = document.createElement("th");
    dayHeader.className = "day-col-header";
    dayHeader.textContent = "Día";
    headerRow.appendChild(dayHeader);
    
    for (let h = 8; h <= 22; h++) {
        const th = document.createElement("th");
        th.textContent = `${h.toString().padStart(2, '0')}:00`;
        headerRow.appendChild(th);
    }
    thead.appendChild(headerRow);
    table.appendChild(thead);
    
    // 2. Filas (Días x Horas)
    const tbody = document.createElement("tbody");
    dias.forEach(dia => {
        const row = document.createElement("tr");
        
        // Celda del nombre del día
        const dayCell = document.createElement("td");
        dayCell.className = "day-name-cell";
        dayCell.textContent = dia;
        row.appendChild(dayCell);
        
        const curve = afluenciaSemanal[dia] || new Array(24).fill(0);
        
        // Celdas de horas (de 8 a 22)
        for (let h = 8; h <= 22; h++) {
            const val = curve[h] !== undefined ? curve[h] : 0;
            const td = document.createElement("td");
            
            // Celda interna con color y tooltip
            const cellDiv = document.createElement("div");
            cellDiv.className = "heatmap-cell";
            
            // Opacidad en base a valor (0 a 100)
            const alpha = (val / 100).toFixed(2);
            cellDiv.style.background = `rgba(37, 99, 235, ${alpha})`;
            
            // Tooltip nativo interactivo (title)
            cellDiv.setAttribute("title", `${dia} ${h.toString().padStart(2, '0')}:00 — Tránsito: ${val}%`);
            
            td.appendChild(cellDiv);
            row.appendChild(td);
        }
        tbody.appendChild(row);
    });
    table.appendChild(tbody);
    gridContainer.appendChild(table);
}

// --- GRÁFICO 1: COMPETIDORES (Chart.js Bar) ---
function renderCompetitorsChart(competidores) {
    if (state.charts.competitors) {
        state.charts.competitors.destroy();
    }
    
    // Clasificar competidores por rating (de menor a mayor valorados: menos valorados a la izquierda, más a la derecha)
    const ratings = {
        "< 3.0 o Sin Rating": 0,
        "3.0 - 3.9": 0,
        "4.0 - 4.4": 0,
        "4.5 - 5.0": 0
    };
    competidores.forEach(c => {
        const r = c.rating || 0;
        if (r >= 4.5) ratings["4.5 - 5.0"]++;
        else if (r >= 4.0) ratings["4.0 - 4.4"]++;
        else if (r >= 3.0) ratings["3.0 - 3.9"]++;
        else ratings["< 3.0 o Sin Rating"]++;
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

// --- TABLA 2: ATRACTORES / POIs (Aliados Comerciales) ---
function renderPOITable(metricas) {
    const tbody = document.getElementById("poi-table-body");
    if (!tbody) return;
    tbody.innerHTML = "";
    
    const categoryMap = {
        "bank": "Bancos y Finanzas",
        "school": "Centros Educativos",
        "transit_station": "Transporte Público",
        "cafe": "Cafeterías",
        "restaurant": "Restaurantes",
        "fast_food": "Comida Rápida",
        "gym": "Gimnasios",
        "pharmacy": "Farmacias",
        "bakery": "Panaderías",
        "beauty_salon": "Estéticas",
        "laundry": "Lavanderías",
        "doctor": "Consultorios Médicos",
        "supermarket": "Supermercados",
        "shopping_mall": "Centros Comerciales",
        "convenience_store": "Abarrotes y Conveniencia",
        "park": "Parques"
    };
    
    let counts = {};
    if (metricas.aliados_conteos && Object.keys(metricas.aliados_conteos).length > 0) {
        counts = metricas.aliados_conteos;
    } else {
        // Fallback de atractores generales en caso de no contar con aliados calculados
        counts = {
            "transit_station": metricas.transporte_conteo || 4,
            "school": metricas.escuelas_conteo || 2,
            "bank": metricas.bancos_conteo || 1
        };
    }
    
    for (const [key, count] of Object.entries(counts)) {
        const label = categoryMap[key] || key.replace("_", " ").replace(/\b\w/g, c => c.toUpperCase());
        
        let impactHtml = "";
        if (count >= 5) {
            impactHtml = '<span class="badge success">Muy Favorable</span>';
        } else if (count >= 2) {
            impactHtml = '<span class="badge success">Favorable</span>';
        } else if (count >= 1) {
            impactHtml = '<span class="badge info">Moderado</span>';
        } else {
            impactHtml = '<span class="badge secondary">Sin Impacto</span>';
        }
        
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><b>${label}</b></td>
            <td>${count} establecimientos</td>
            <td>${impactHtml}</td>
        `;
        tbody.appendChild(tr);
    }
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
        alert("Error de red al conectar con el servidor de análisis.");
    }
}

// --- INTERCEPCIÓN DE COMPRA Y AUTENTICACIÓN GOOGLE ---
function checkAuthAndBuy(tier) {
    if (state.currentUserRole === 'guest') {
        state.pendingTier = tier;
        // Limpiar cargador anterior del modal de login
        document.getElementById("login-progress-container").classList.add("hidden");
        document.getElementById("google-signin-btn").removeAttribute("disabled");
        // Mostrar modal de registro/login
        document.getElementById("google-login-modal").classList.remove("hidden");
        logger(`Redirigiendo flujo de compra para Tier ${tier.toUpperCase()} a modal de registro Google/Cognito.`);
    } else {
        openPaymentModal(tier);
    }
}

async function processGoogleSigninMock() {
    const signinBtn = document.getElementById("google-signin-btn");
    const progressContainer = document.getElementById("login-progress-container");
    const progressFill = document.getElementById("login-progress-bar-fill");
    const statusText = document.getElementById("login-status-text");

    signinBtn.setAttribute("disabled", "true");
    progressContainer.classList.remove("hidden");
    statusText.textContent = "Conectando con Google Accounts...";
    progressFill.style.width = "0%";

    let progress = 0;
    const interval = setInterval(() => {
        progress += 10;
        progressFill.style.width = `${progress}%`;

        if (progress === 30) {
            statusText.textContent = "Autenticando sesión y validando credenciales...";
        } else if (progress === 60) {
            statusText.textContent = "Verificando perfil de usuario...";
        } else if (progress === 90) {
            statusText.textContent = "Generando accesos seguros...";
        }

        if (progress >= 100) {
            clearInterval(interval);
            
            // Cambiar rol a Cliente y actualizar selector visual
            state.currentUserRole = 'user';
            document.getElementById("user-role-select").value = 'user';
            
            // Ocultar modal de login
            document.getElementById("google-login-modal").classList.add("hidden");
            
            // Notificación visual de éxito
            alert("¡Autenticación con Google exitosa! Bienvenido, demo_google@geoviabilidad.com. Se reanuda tu compra.");
            
            // Proceder con la compra
            openPaymentModal(state.pendingTier);
        }
    }, 150);
}
