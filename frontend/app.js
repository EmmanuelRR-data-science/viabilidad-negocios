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
    activeTier: null,

    // Modo guiado de aliados (Premium)
    aliadosGuiadoActivo: false,
    aliadosGuiadoSugerencias: [],
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
    setupAliadosGuiado();
    
    // L. Buscador de dirección flotante sobre el mapa
    setupMapSearchBox();

    // M. Configurar la tarjeta introductoria de contexto
    setupIntroCard();
}

function setupIntroCard() {
    const introCard = document.getElementById("app-intro-card");
    const toggleBtn = document.getElementById("toggle-intro-btn");
    if (!introCard || !toggleBtn) return;

    const toggleText = toggleBtn.querySelector(".intro-toggle-text");
    const STORAGE_KEY = "intro_card_collapsed";

    const setIntroVisible = (visible, { persist = true } = {}) => {
        toggleBtn.setAttribute("aria-expanded", visible ? "true" : "false");
        toggleBtn.classList.toggle("is-collapsed", !visible);

        if (toggleText) {
            toggleText.textContent = visible
                ? toggleText.dataset.stateVisible
                : toggleText.dataset.stateHidden;
        }

        if (visible) {
            introCard.classList.remove("hidden");
            requestAnimationFrame(() => {
                introCard.classList.remove("collapsed");
            });
        } else {
            introCard.classList.add("collapsed");
            setTimeout(() => {
                if (toggleBtn.getAttribute("aria-expanded") === "false") {
                    introCard.classList.add("hidden");
                }
            }, 400);
        }

        if (persist) {
            localStorage.setItem(STORAGE_KEY, visible ? "false" : "true");
        }
    };

    const savedCollapsed = localStorage.getItem(STORAGE_KEY);
    if (savedCollapsed === "true" || localStorage.getItem("hide_intro_card") === "true") {
        localStorage.removeItem("hide_intro_card");
        setIntroVisible(false, { persist: true });
    }

    toggleBtn.addEventListener("click", () => {
        const isVisible = toggleBtn.getAttribute("aria-expanded") === "true";
        logger(isVisible ? "Ocultando guía de la app..." : "Mostrando guía de la app...");
        setIntroVisible(!isVisible);
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

const GUIADO_PERFIL_LABELS = {
    publico_general: "Público en general",
    familias: "Familias con niños",
    estudiantes: "Estudiantes y jóvenes",
    oficinistas: "Oficinistas",
    transporte_publico: "Transporte público",
    compradores_paso: "Compradores de paso",
    salud_bienestar: "Salud y bienestar",
    adultos_mayores: "Adultos mayores",
};

const GUIADO_HORARIO_LABELS = {
    manana: "Mañana",
    mediodia: "Mediodía",
    tarde: "Tarde",
    noche_finde: "Noche y fin de semana",
};

function getRubroActual() {
    const giroSelect = document.getElementById("giro-select");
    const customGiroInput = document.getElementById("custom-giro-input");
    if (giroSelect?.value === "otro") {
        return (customGiroInput?.value || "").trim() || state.selectedGiro;
    }
    return state.selectedGiro || giroSelect?.value || "";
}

function isAliadosGuiadoActivo() {
    const body = document.getElementById("aliados-guiado-body");
    return Boolean(state.aliadosGuiadoActivo && body && !body.classList.contains("hidden"));
}

function getGuiadoCheckedValues(containerId, max) {
    const boxes = document.querySelectorAll(`#${containerId} input[type='checkbox']:checked`);
    return Array.from(boxes).map(cb => cb.value).slice(0, max);
}

function setGuiadoError(msg) {
    const aviso = document.getElementById("guiado-aviso-error");
    if (!aviso) return;
    if (msg) {
        aviso.textContent = msg;
        aviso.classList.remove("hidden");
    } else {
        aviso.textContent = "";
        aviso.classList.add("hidden");
    }
}

function renderGuiadoAtractores(sugerencias) {
    const container = document.getElementById("guiado-atractores-checkboxes");
    const hint = document.getElementById("guiado-atractores-hint");
    if (!container) return;

    const prevChecked = new Set(getGuiadoCheckedValues("guiado-atractores-checkboxes", 5));
    container.innerHTML = "";

    sugerencias.forEach(item => {
        const label = document.createElement("label");
        label.className = "checkbox-item guiado-atractor-item";
        const checked = prevChecked.has(item.tipo) || (prevChecked.size === 0 && item.sugerido);
        label.innerHTML = `
            <input type="checkbox" value="${item.tipo}" ${checked ? "checked" : ""}>
            <span class="guiado-atractor-text">
                <strong>${item.etiqueta}</strong>
                <small>${item.explicacion}</small>
                <em class="guiado-atractor-motivo">${item.motivo}</em>
            </span>
        `;
        container.appendChild(label);
    });

    if (hint) {
        hint.textContent = "Marca entre 2 y 5 tipos de lugares. Las sugerencias se basan en tu giro y respuestas anteriores.";
    }

    container.querySelectorAll("input[type='checkbox']").forEach(cb => {
        cb.addEventListener("change", () => {
            enforceGuiadoLimit("guiado-atractores-checkboxes", 5, 2);
            updateGuiadoResumen();
        });
    });
    enforceGuiadoLimit("guiado-atractores-checkboxes", 5, 2);
    updateGuiadoResumen();
}

function enforceGuiadoLimit(containerId, max, minOptional = 0) {
    const boxes = Array.from(document.querySelectorAll(`#${containerId} input[type='checkbox']`));
    const checked = boxes.filter(cb => cb.checked);
    if (checked.length > max) {
        checked[max].checked = false;
    }
    if (minOptional > 0 && checked.length < minOptional) {
        setGuiadoError(`Selecciona al menos ${minOptional} tipos de lugares que creas relevantes para tu negocio.`);
    } else if (containerId === "guiado-atractores-checkboxes") {
        setGuiadoError("");
    }
}

async function refreshGuiadoSugerencias() {
    const perfiles = getGuiadoCheckedValues("guiado-perfil-checkboxes", 3);
    const horarios = getGuiadoCheckedValues("guiado-horario-checkboxes", 2);
    const rubro = getRubroActual();

    if (perfiles.length === 0 || horarios.length === 0 || !rubro) {
        return;
    }

    try {
        const headers = getAuthHeaders();
        headers["Content-Type"] = "application/json";
        const response = await fetch("/api/analizar/aliados/sugerir", {
            method: "POST",
            headers,
            body: JSON.stringify({
                rubro,
                perfil_cliente: perfiles,
                horarios_pico: horarios,
            }),
        });
        if (!response.ok) {
            throw new Error("No se pudieron cargar las sugerencias");
        }
        const data = await response.json();
        state.aliadosGuiadoSugerencias = data.sugerencias || [];
        renderGuiadoAtractores(state.aliadosGuiadoSugerencias);
    } catch (err) {
        logger("Error sugerencias guiadas:", err);
        setGuiadoError("No pudimos cargar sugerencias. Intenta de nuevo en unos segundos.");
    }
}

function updateGuiadoResumen() {
    const resumenBox = document.getElementById("guiados-aliados-resumen");
    const resumenText = document.getElementById("guiado-resumen-text");
    if (!resumenBox || !resumenText) return;

    const perfiles = getGuiadoCheckedValues("guiado-perfil-checkboxes", 3);
    const horarios = getGuiadoCheckedValues("guiado-horario-checkboxes", 2);
    const atractores = getGuiadoCheckedValues("guiado-atractores-checkboxes", 5);

    if (perfiles.length === 0 && horarios.length === 0 && atractores.length === 0) {
        resumenBox.classList.add("hidden");
        return;
    }

    const perfilTxt = perfiles.map(p => GUIADO_PERFIL_LABELS[p] || p).join(", ") || "—";
    const horarioTxt = horarios.map(h => GUIADO_HORARIO_LABELS[h] || h).join(", ") || "—";
    const atractorTxt = atractores.map(t => {
        const sug = (state.aliadosGuiadoSugerencias || []).find(s => s.tipo === t);
        return sug?.etiqueta || t;
    }).join(", ") || "—";

    resumenText.innerHTML = `
        <b>Cliente principal:</b> ${perfilTxt}<br>
        <b>Horarios clave:</b> ${horarioTxt}<br>
        <b>Buscaremos cerca:</b> ${atractorTxt}
    `;
    resumenBox.classList.remove("hidden");
}

function syncAliadosManualPanel(guiadoOn) {
    const manualGroup = document.getElementById("aliados-checkboxes");
    if (!manualGroup) return;
    manualGroup.closest(".form-group")?.classList.toggle("aliados-manual-muted", guiadoOn);
    if (guiadoOn) {
        manualGroup.querySelectorAll("input[type='checkbox']").forEach(cb => { cb.checked = false; });
    }
}

function collectAliadosPayload() {
    if (!isAliadosGuiadoActivo()) {
        const aliadosCheckboxes = document.querySelectorAll("#aliados-checkboxes input[type='checkbox']:checked");
        const aliadosSel = Array.from(aliadosCheckboxes).map(cb => cb.value);
        return {
            modo_analisis_aliados: "automatico",
            config_aliados_guiados: null,
            aliados_seleccionados: aliadosSel.length > 0 ? aliadosSel : null,
        };
    }

    const perfiles = getGuiadoCheckedValues("guiado-perfil-checkboxes", 3);
    const horarios = getGuiadoCheckedValues("guiado-horario-checkboxes", 2);
    const atractores = getGuiadoCheckedValues("guiado-atractores-checkboxes", 5);

    if (perfiles.length === 0 || horarios.length === 0 || atractores.length < 2) {
        return { invalid: true };
    }

    const config = {
        perfil_cliente: perfiles,
        horarios_pico: horarios,
        atractores_confirmados: atractores,
    };

    return {
        modo_analisis_aliados: "guiado",
        config_aliados_guiados: config,
        aliados_seleccionados: atractores,
    };
}

function setupAliadosGuiado() {
    const toggle = document.getElementById("aliados-guiado-toggle");
    const body = document.getElementById("aliados-guiado-body");
    if (!toggle || !body) return;

    toggle.addEventListener("click", () => {
        const opening = body.classList.contains("hidden");
        body.classList.toggle("hidden", !opening);
        toggle.setAttribute("aria-expanded", opening ? "true" : "false");
        state.aliadosGuiadoActivo = opening;
        syncAliadosManualPanel(opening);
        if (opening) {
            refreshGuiadoSugerencias();
        } else {
            setGuiadoError("");
        }
    });

    const bindGuiadoGroup = (containerId, max) => {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.querySelectorAll("input[type='checkbox']").forEach(cb => {
            cb.addEventListener("change", () => {
                enforceGuiadoLimit(containerId, max);
                if (containerId !== "guiado-atractores-checkboxes") {
                    refreshGuiadoSugerencias();
                }
                updateGuiadoResumen();
            });
        });
    };

    bindGuiadoGroup("guiado-perfil-checkboxes", 3);
    bindGuiadoGroup("guiado-horario-checkboxes", 2);
}

function setupMapSearchBox() {
    const searchContainer = document.getElementById("search-box-container");
    const searchInput = document.getElementById("map-search-input");
    const searchBtn = document.getElementById("map-search-btn");
    const searchResults = document.getElementById("map-search-results");

    if (!searchContainer || !searchInput || !searchBtn || !searchResults) return;

    if (!localStorage.getItem("map_search_hint_seen")) {
        searchContainer.classList.add("map-search-pulse");
        localStorage.setItem("map_search_hint_seen", "true");
        setTimeout(() => searchContainer.classList.remove("map-search-pulse"), 5200);
    }

    searchInput.addEventListener("focus", () => {
        searchContainer.classList.add("is-highlighted");
    });
    searchInput.addEventListener("blur", () => {
        searchContainer.classList.remove("is-highlighted");
    });
    
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
function hasBestTimeHeatmapData(afluencia) {
    return (
        afluencia?.status === "success" &&
        afluencia?.afluencia_semanal &&
        Object.keys(afluencia.afluencia_semanal).length > 0
    );
}

function tierIncluyeHeatmap(tier) {
    return tier === "pro" || tier === "premium";
}

/** Muestra el bloque del heatmap solo si hay pago Pro/Premium y BestTime devolvió curvas reales. */
function syncHeatmapSection(tier, afluencia) {
    const section = document.getElementById("heatmap-container");
    const grid = document.getElementById("heatmap-grid-container");
    const legend = document.getElementById("heatmap-legend-container");
    if (!section) return;

    const shouldShow = tierIncluyeHeatmap(tier) && hasBestTimeHeatmapData(afluencia);

    if (shouldShow) {
        section.classList.remove("hidden");
        if (legend) legend.style.display = "flex";
        renderHeatmap(afluencia);
        logger("Mapa de calor visible: tier pagado y telemetría BestTime disponible.");
    } else {
        section.classList.add("hidden");
        if (grid) grid.innerHTML = "";
        if (legend) legend.style.display = "none";
        if (tierIncluyeHeatmap(tier) && !hasBestTimeHeatmapData(afluencia)) {
            logger("Mapa de calor oculto: BestTime sin cobertura en esta coordenada.");
        }
    }
}

function renderNseKpi(metricas, locked) {
    const card = document.getElementById("kpi-nse-card");
    const valueEl = document.getElementById("kpi-nse");
    const descEl = document.getElementById("kpi-nse-desc");
    if (!card || !valueEl) return;

    if (locked) {
        valueEl.textContent = "🔒 Bloqueado";
        card.classList.add("kpi-locked");
        if (descEl) {
            descEl.textContent = "Indicador del poder adquisitivo promedio en la zona. Desbloquéalo al adquirir cualquier plan de reporte.";
        }
        return;
    }

    const nse = metricas?.nse || {};
    const metricasNse = nse.metricas || {};
    valueEl.textContent = nse.nse_etiqueta || "—";
    card.classList.remove("kpi-locked");
    if (descEl) {
        descEl.textContent = `Poder adquisitivo estimado del radio. Escolaridad ${metricasNse.escolaridad_promedio ?? "—"} años equiv., internet ${metricasNse.internet_pct ?? "—"}%, autos ${metricasNse.autos_pct ?? "—"}%.`;
    }
}

function applyBlurRules(tier) {
    const compWrapper = document.querySelector("#competitor-chart-card .canvas-wrapper");
    const poiWrapper = document.querySelector("#poi-chart-card .table-wrapper");
    const reviewsBlock = document.getElementById("competitor-reviews-block");
    const topTableWrap = document.getElementById("competitor-top-table-wrap");

    const compMsg = document.getElementById("comp-chart-locked-msg");
    const poiMsg = document.getElementById("poi-chart-locked-msg");

    if (!compWrapper || !poiWrapper || !compMsg || !poiMsg) return;

    if (tier === "gratuito" || tier === "basico") {
        compWrapper.classList.add("blurred-premium");
        poiWrapper.classList.add("blurred-premium");
        if (reviewsBlock) reviewsBlock.classList.add("blurred-premium");
        if (topTableWrap) topTableWrap.classList.add("blurred-premium");

        compMsg.classList.remove("hidden");
        poiMsg.classList.remove("hidden");
    } else if (tier === "pro") {
        compWrapper.classList.remove("blurred-premium");
        poiWrapper.classList.add("blurred-premium");
        if (reviewsBlock) reviewsBlock.classList.remove("blurred-premium");
        if (topTableWrap) topTableWrap.classList.remove("blurred-premium");

        compMsg.classList.add("hidden");
        poiMsg.classList.remove("hidden");
    } else if (tier === "premium") {
        compWrapper.classList.remove("blurred-premium");
        poiWrapper.classList.remove("blurred-premium");
        if (reviewsBlock) reviewsBlock.classList.remove("blurred-premium");
        if (topTableWrap) topTableWrap.classList.remove("blurred-premium");

        compMsg.classList.add("hidden");
        poiMsg.classList.add("hidden");
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
        const aliadosPayload = collectAliadosPayload();
        if (aliadosPayload.invalid) {
            setGuiadoError("Completa el cuestionario guiado: perfil, horarios y al menos 2 tipos de lugares.");
            btn.innerHTML = `<span class="btn-icon">⚡</span> ANALIZAR UBICACIÓN`;
            btn.removeAttribute("disabled");
            return;
        }

        const intenciones = document.getElementById("intenciones-textarea")?.value?.trim() || null;
        const compAdicionales = document.getElementById("competidores-adicionales-input")?.value?.trim() || null;
        const aliadosAdicionales = document.getElementById("aliados-adicionales-input")?.value?.trim() || null;

        const previewBody = {
            competidores_seleccionados: competidoresSel.length > 0 ? competidoresSel : null,
            aliados_seleccionados: aliadosPayload.aliados_seleccionados,
            intenciones,
            competidores_adicionales: compAdicionales,
            aliados_adicionales: aliadosAdicionales,
            modo_analisis_aliados: aliadosPayload.modo_analisis_aliados,
            config_aliados_guiados: aliadosPayload.config_aliados_guiados,
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

            renderNseKpi(data, true);

            renderSvaComposition(
                {
                    sva: data.score_viabilidad_sva,
                    score_demog: data.score_demog,
                    score_competencia: data.score_competencia,
                    score_trafico: data.score_trafico,
                    poblacion_estimada: data.poblacion_estimada,
                    densidad_hab_km2: data.densidad_hab_km2,
                    competidores_conteo: data.competidores_conteo,
                    afluencia_peatonal: data.afluencia_peatonal,
                },
                "gratuito"
            );

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
            renderTopCompetitorsTable(data);
            renderCompetitorReviews(data);
            renderPOITable(data);
            syncHeatmapSection("gratuito", data.afluencia_peatonal);

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
    const svaComp = document.getElementById("sva-composition-card");
    if (svaComp) svaComp.classList.add("hidden");

    const lecturaSection = document.getElementById("lectura-estrategica-section");
    if (lecturaSection) lecturaSection.classList.add("hidden");

    const reviewsBlock = document.getElementById("competitor-reviews-block");
    if (reviewsBlock) reviewsBlock.classList.add("hidden");
    const reviewsList = document.getElementById("competitor-reviews-list");
    if (reviewsList) reviewsList.innerHTML = "";

    const topTableWrap = document.getElementById("competitor-top-table-wrap");
    if (topTableWrap) topTableWrap.classList.add("hidden");
    const topTableBody = document.getElementById("competitor-top-table-body");
    if (topTableBody) topTableBody.innerHTML = "";

    // Mensajes de bloqueo
    document.getElementById("comp-chart-locked-msg").classList.remove("hidden");
    document.getElementById("poi-chart-locked-msg").classList.remove("hidden");
    
    syncHeatmapSection("gratuito", null);

    // Ocultar descargas
    document.getElementById("download-section").classList.add("hidden");
    
    // Mostrar botones de compra
    document.getElementById("dashboard-actions").classList.remove("hidden");
    
    // Destruir gráficos de Chart.js si existían
    if (state.charts.competitors) {
        state.charts.competitors.destroy();
        state.charts.competitors = null;
    }
    
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

        // Obtener aliados (modo automático o guiado)
        const aliadosPayload = collectAliadosPayload();
        if (aliadosPayload.invalid) {
            alert("Completa el cuestionario guiado de aliados: perfil, horarios y al menos 2 tipos de lugares.");
            return;
        }
        let aliados_seleccionados = aliadosPayload.aliados_seleccionados;

        // Obtener entradas de texto libre
        const compAdicionales = document.getElementById("competidores-adicionales-input").value.trim();
        const aliadosAdicionales = document.getElementById("aliados-adicionales-input").value.trim();

        const categoryMap = {
            "ia_auto": "🤖 Determinar automáticamente por IA",
            "ia_auto_aliado": "📊 Matriz automática por rubro (geomarketing)",
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
            if (aliadosPayload.modo_analisis_aliados === "guiado") {
                aliados_seleccionados = aliadosPayload.aliados_seleccionados;
            } else {
                aliados_seleccionados = aliados_seleccionados.length > 0 ? aliados_seleccionados.slice(0, 5) : null;
            }
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
            const allyLabels = aliados_seleccionados
                ? aliados_seleccionados.map(a => {
                    if (a === "ia_auto") return categoryMap.ia_auto_aliado;
                    const sug = (state.aliadosGuiadoSugerencias || []).find(s => s.tipo === a);
                    return sug?.etiqueta || categoryMap[a] || a;
                }).join(", ")
                : "Bancos, Escuelas y Transporte por defecto";
            let compText = `🏪 <b>Competidores a analizar (Máx 5):</b> ${compLabels}`;
            if (compAdicionales) {
                compText += ` (+ "${compAdicionales}")`;
            }
            let allyText = aliadosPayload.modo_analisis_aliados === "guiado"
                ? `🧭 <b>Aliados (modo guiado):</b> ${allyLabels}`
                : `🌱 <b>Aliados a analizar (Máx 5):</b> ${allyLabels}`;
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
            intenciones: document.getElementById("intenciones-textarea").value.trim() || null,
            competidores_seleccionados: competidores_seleccionados,
            aliados_seleccionados: aliadosPayload.modo_analisis_aliados === "guiado" ? null : aliados_seleccionados,
            competidores_adicionales: compAdicionales || null,
            aliados_adicionales: aliadosAdicionales || null,
            modo_analisis_aliados: aliadosPayload.modo_analisis_aliados,
            config_aliados_guiados: aliadosPayload.config_aliados_guiados,
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

function renderLecturaEstrategica(iaAnalisis) {
    const section = document.getElementById("lectura-estrategica-section");
    if (!section || !iaAnalisis) return;

    const fillList = (id, items, fallback) => {
        const el = document.getElementById(id);
        if (!el) return;
        const lista = (items || []).slice(0, 3);
        if (lista.length === 0) {
            el.innerHTML = `<li>${fallback}</li>`;
            return;
        }
        el.innerHTML = lista.map(t => `<li>${t}</li>`).join("");
    };

    fillList("lectura-fortalezas", iaAnalisis.fortalezas, "Demanda residencial en el radio analizado.");
    fillList("lectura-oportunidades", iaAnalisis.oportunidades, "Espacio para diferenciación en el giro.");
    fillList(
        "lectura-consideraciones",
        iaAnalisis.consideraciones_apertura,
        "Validar permisos, renta y operación con cifras reales."
    );

    const conclusionEl = document.getElementById("lectura-conclusion");
    if (conclusionEl) {
        const texto = iaAnalisis.conclusion;
        if (texto) {
            // Reportes antiguos pueden traer <b> para PDF; renderizar negritas sin mostrar etiquetas crudas.
            if (/<\/?b>/i.test(texto)) {
                conclusionEl.innerHTML = texto;
            } else {
                conclusionEl.textContent = texto;
            }
            conclusionEl.classList.remove("hidden");
        } else {
            conclusionEl.textContent = "";
            conclusionEl.classList.add("hidden");
        }
    }

    section.classList.remove("hidden");
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

            renderNseKpi(metricas, false);

            renderSvaComposition(metricas, state.activeTier || data.orden?.tier || "basico");
            renderLecturaEstrategica(iaAnalisis);
            
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
            renderTopCompetitorsTable(metricas);
            renderCompetitorReviews(metricas);
            renderPOITable(metricas);
            syncHeatmapSection(state.activeTier, metricas.afluencia_peatonal);

            // Aplicar las reglas de blur según el Tier activo
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
            const distTxt = _formatDistanceMeters(comp.distancia_metros);
            const marker = L.marker([comp.latitud, comp.longitud], { icon: competitorIcon })
                .addTo(state.map)
                .bindPopup(
                    `<b>${_escapeHtml(comp.nombre)}</b><br/>${_escapeHtml(comp.direccion || "Dirección no disponible")}`
                    + `<br/>⭐ ${comp.rating || 0} / 5.0`
                    + (distTxt ? `<br/>📍 ${distTxt} desde tu punto` : "")
                );
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
// Escala térmica para el heatmap: interpola tono dorado (45°) → rojo (0°) según la afluencia,
// con opacidad creciente para que las horas muertas se desvanezcan y los picos resalten.
function heatColor(val) {
    const intensity = Math.max(0, Math.min(100, val)) / 100;
    if (intensity === 0) return "rgba(148, 163, 184, 0.08)";
    const hue = 45 - intensity * 45;
    const alpha = 0.18 + intensity * 0.82;
    return `hsla(${hue}, 95%, 55%, ${alpha.toFixed(2)})`;
}

function renderHeatmap(afluencia) {
    const gridContainer = document.getElementById("heatmap-grid-container");
    if (!gridContainer) return;
    
    // Limpiar contenedor anterior
    gridContainer.innerHTML = "";
    
    if (!hasBestTimeHeatmapData(afluencia)) {
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
            
            // Escala térmica vibrante: dorado (poca afluencia) → naranja → rojo intenso (pico)
            cellDiv.style.background = heatColor(val);
            if (val >= 75) {
                cellDiv.style.boxShadow = "0 0 8px rgba(239, 68, 68, 0.45)";
            }
            
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

function _escapeHtml(text) {
    return String(text ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function _formatDistanceMeters(metros) {
    const m = Number(metros);
    if (!Number.isFinite(m) || m < 0) return "";
    if (m < 1000) return `${Math.round(m)} m lineales`;
    return `${(m / 1000).toFixed(2)} km lineales`;
}

const MIN_RESENAS_DESTACADO = 5;

function _filtrarDestacadosConfiables(lista) {
    return (lista || [])
        .filter(c => Number(c.rating) > 0 && Number(c.user_ratings_total || 0) >= MIN_RESENAS_DESTACADO)
        .sort((a, b) => {
            const ratingDiff = Number(b.rating) - Number(a.rating);
            if (ratingDiff !== 0) return ratingDiff;
            const reviewsDiff = Number(b.user_ratings_total || 0) - Number(a.user_ratings_total || 0);
            if (reviewsDiff !== 0) return reviewsDiff;
            return Number(a.distancia_metros || 999999) - Number(b.distancia_metros || 999999);
        })
        .slice(0, 5);
}

function _resolveDestacados(payload) {
    if (!payload) return [];
    const metricas = payload.metricas || payload;
    const destacados = metricas.competidores_destacados;
    if (Array.isArray(destacados) && destacados.length > 0) {
        return destacados.filter(c => c.giro_relevante !== false);
    }
    const listado = metricas.competidores_listado || [];
    return _filtrarDestacadosConfiables(listado).filter(c => c.giro_relevante !== false);
}

function renderTopCompetitorsTable(metricas) {
    const wrap = document.getElementById("competitor-top-table-wrap");
    const tbody = document.getElementById("competitor-top-table-body");
    if (!wrap || !tbody) return;

    const top = _resolveDestacados(metricas);
    if (top.length === 0) {
        wrap.classList.add("hidden");
        tbody.innerHTML = "";
        return;
    }

    tbody.innerHTML = top.map(comp => `
        <tr>
            <td>${_escapeHtml(comp.nombre || "Comercio local")}</td>
            <td>⭐ ${Number(comp.rating || 0).toFixed(1)}</td>
            <td>${Number(comp.user_ratings_total || 0).toLocaleString()}</td>
            <td>${_escapeHtml(_formatDistanceMeters(comp.distancia_metros) || "—")}</td>
        </tr>
    `).join("");
    wrap.classList.remove("hidden");
}

function renderCompetitorReviews(metricas) {
    const block = document.getElementById("competitor-reviews-block");
    const list = document.getElementById("competitor-reviews-list");
    if (!block || !list) return;

    const cards = [];
    _resolveDestacados(metricas).forEach(comp => {
        (comp.reseñas_google || []).forEach(rev => {
            if (!rev?.texto) return;
            const distTxt = _formatDistanceMeters(comp.distancia_metros);
            const meta = [
                distTxt ? `📍 ${distTxt}` : null,
                rev.rating ? `⭐ ${rev.rating}/5` : null,
                rev.fecha_relativa || null,
                rev.autor || null,
            ].filter(Boolean).join(" · ");
            cards.push(`
                <div class="competitor-review-card">
                    <div class="competitor-review-name">${_escapeHtml(comp.nombre || "Competidor local")}</div>
                    <div class="competitor-review-text">“${_escapeHtml(rev.texto)}”</div>
                    ${meta ? `<div class="competitor-review-meta">${_escapeHtml(meta)}</div>` : ""}
                </div>
            `);
        });
    });

    if (cards.length === 0) {
        block.classList.add("hidden");
        list.innerHTML = "";
        return;
    }

    list.innerHTML = cards.join("");
    block.classList.remove("hidden");
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
    
    // Paleta vibrante semántica: rojo (mal valorados) → naranja → ámbar → verde (mejor valorados)
    const ratingColors = {
        backgrounds: [
            'rgba(244, 63, 94, 0.8)',   // rose - "< 3.0 o Sin Rating"
            'rgba(249, 115, 22, 0.8)',  // orange - "3.0 - 3.9"
            'rgba(251, 191, 36, 0.8)',  // amber - "4.0 - 4.4"
            'rgba(34, 197, 94, 0.8)'    // green - "4.5 - 5.0"
        ],
        borders: ['#f43f5e', '#f97316', '#fbbf24', '#22c55e']
    };

    const ctx = document.getElementById("competitors-chart").getContext("2d");
    state.charts.competitors = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: Object.keys(ratings),
            datasets: [{
                label: 'Número de Comercios',
                data: Object.values(ratings),
                backgroundColor: ratingColors.backgrounds,
                borderColor: ratingColors.borders,
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

// --- DESGLOSE DE PILARES DEL SCORE SVA ---
function _svaScoreClass(score) {
    if (score >= 80) return "good";
    if (score >= 50) return "mid";
    return "low";
}

function _svaDemogSignal(score, metricas) {
    const pob = Number(metricas?.poblacion_ponderada ?? metricas?.poblacion_estimada ?? 0);
    const dens = Number(metricas?.densidad_hab_km2 ?? 0);
    const densTxt = dens > 0 ? `${dens.toLocaleString("es-MX")} hab/km²` : "densidad no calculada";
    if (score >= 80) return `Excelente densidad en el radio (${densTxt} · ${pob.toLocaleString()} hab.)`;
    if (score >= 50) return `Densidad aceptable en el radio (${densTxt} · ${pob.toLocaleString()} hab.)`;
    return `Baja concentración en el radio (${densTxt} · ${pob.toLocaleString()} hab.)`;
}

function _svaCompSignal(competidores) {
    const n = Number(competidores || 0);
    if (n === 0) return "Sin competidores directos detectados";
    if (n <= 3) return `Baja competencia (${n} competidores)`;
    if (n <= 8) return `Competencia intermedia (${n} competidores)`;
    return `Alta saturación (${n} competidores)`;
}

function _svaTraficoSignal(score, metricas, tier) {
    const afl = metricas?.afluencia_peatonal;
    if (tier === "premium" && afl?.status === "success") {
        return "Tráfico peatonal medido en la zona";
    }
    if (tier === "premium") {
        return "Sin medición de tráfico peatonal en la zona (valor base)";
    }
    return "Tráfico peatonal estimado (Premium usa medición real cuando hay cobertura)";
}

function renderSvaComposition(metricas, tier = "gratuito") {
    const card = document.getElementById("sva-composition-card");
    const tbody = document.getElementById("sva-pillar-body");
    const formulaEl = document.getElementById("sva-formula-line");
    if (!card || !tbody || !formulaEl) return;

    const dem = Number(metricas.score_demog ?? 0);
    const comp = Number(metricas.score_competencia ?? 0);
    const traf = Number(metricas.score_trafico ?? 0);
    const sva = Number(metricas.sva ?? metricas.score_viabilidad_sva ?? Math.round(dem * 0.4 + comp * 0.3 + traf * 0.3));

    const wDem = 0.4;
    const wComp = 0.3;
    const wTraf = 0.3;
    const cDem = dem * wDem;
    const cComp = comp * wComp;
    const cTraf = traf * wTraf;
    const raw = cDem + cComp + cTraf;

    const rows = [
        {
            name: "Pilar demográfico",
            weight: "40%",
            score: dem,
            contrib: cDem,
            signal: _svaDemogSignal(dem, metricas),
        },
        {
            name: "Pilar competencia",
            weight: "30%",
            score: comp,
            contrib: cComp,
            signal: _svaCompSignal(metricas.competidores_conteo),
        },
        {
            name: "Pilar tráfico peatonal",
            weight: "30%",
            score: traf,
            contrib: cTraf,
            signal: _svaTraficoSignal(traf, metricas, tier),
        },
    ];

    tbody.innerHTML = rows
        .map(
            (row) => `
        <tr>
            <td><b>${row.name}</b></td>
            <td>${row.weight}</td>
            <td><span class="sva-pillar-score ${_svaScoreClass(row.score)}">${row.score.toFixed(1)}</span></td>
            <td>${row.contrib.toFixed(1)}</td>
            <td class="sva-pillar-signal">${row.signal}</td>
        </tr>`
        )
        .join("");

    formulaEl.innerHTML =
        `<strong>Cálculo:</strong> (${dem.toFixed(1)} × 40%) + (${comp.toFixed(1)} × 30%) + (${traf.toFixed(1)} × 30%) ` +
        `= ${raw.toFixed(1)} → <strong>${sva}/100</strong> (redondeo entero del SVA).`;

    card.classList.remove("hidden");
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
