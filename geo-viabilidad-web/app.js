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
    googleAuthenticated: false,
    googleAuthPromise: null,
    googleClientId: null,
    googleAuthEnabled: false,
    googleUser: null,
    googleAuthPending: null,
    paymentsMock: false,
    checkoutProEnabled: true,
    paymentsConfigLoaded: false,
    mercadoPagoSandbox: true,
    sandboxBuyerConfigured: false,
    publicReturnUrlConfigured: false,
    appBootstrapped: false,
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
    checkoutPollActive: false,
    checkoutLaunchInProgress: false,
    postPaymentFlow: false,

    // Modo guiado de aliados (Premium)
    aliadosGuiadoActivo: false,
    aliadosGuiadoSugerencias: [],
};

// Precios alineados con app/payments.py (PRECIOS_TIER, MXN)
const TIER_PRICING = {
    basico: {
        amount: 299,
        label: "BÁSICO",
        title: "Reporte Comercial BÁSICO (6 Páginas)",
    },
    pro: {
        amount: 649,
        label: "PRO",
        title: "Reporte Comercial PRO (10 Páginas + Mapas + Atracción)",
    },
    premium: {
        amount: 799,
        label: "PREMIUM",
        title: "Reporte PREMIUM (14 Páginas + ROI + Afluencia)",
    },
};

const priceFormatter = new Intl.NumberFormat("es-MX", {
    style: "currency",
    currency: "MXN",
    minimumFractionDigits: 2,
});

const progressTimers = {};
const KPI_VALUE_IDS = ["kpi-sva", "kpi-poblacion", "kpi-competidores"];

const PHIQUS_GATE = {
    username: "PhiQus",
    password: "viabilidad-negocios",
    storageKey: "phiqus_gate_session",
};

const GOOGLE_AUTH_STORAGE_KEY = "google_auth_session";
const PAID_ORDER_STORAGE_KEY = "geoviabilidad_paid_orden_id";
const PAID_TIER_STORAGE_KEY = "geoviabilidad_paid_tier";
const MP_RETURN_CONTEXT_KEY = "mp_return_context";

function getUrlSearchParams() {
    return new URLSearchParams(window.location.search);
}

function isMercadoPagoReturnUrl(searchParams = getUrlSearchParams()) {
    const ordenId = searchParams.get("orden_id");
    if (!ordenId) return false;
    return Boolean(
        searchParams.get("pago") ||
            searchParams.get("collection_status") ||
            searchParams.get("payment_id") ||
            searchParams.get("external_reference") ||
            searchParams.get("status")
    );
}

function hasPaidOrderPendingUnlock() {
    return Boolean(
        localStorage.getItem(PAID_ORDER_STORAGE_KEY) ||
            getMpPendingOrdenId()
    );
}

function activatePostPaymentFlow() {
    state.postPaymentFlow = true;
}

function scrollToPostPaymentSection() {
    document
        .getElementById("mp-checkout-banner")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
}

// Flags de UI — cambiar a true para reactivar secciones ocultas temporalmente
const UI_FEATURES = {
    intencionesNegocio: false,
};

const INTRO_COPY = {
    conIntenciones: {
        step: "Elige tu giro, ajusta el radio de influencia y detalla tus intenciones comerciales en lenguaje natural.",
        panel: "Ingresa las variables operativas y tus intenciones comerciales.",
    },
    sinIntenciones: {
        step: "Elige tu giro y ajusta el radio de influencia de análisis.",
        panel: "Ingresa las variables operativas de tu negocio.",
    },
};

// --- INICIALIZACIÓN AL CARGAR LA PÁGINA ---
document.addEventListener("DOMContentLoaded", () => {
    logger("Iniciando SPA de GeoViabilidad Hook...");
    initPhiqusGate();
});

function initPhiqusGate() {
    const gate = document.getElementById("phiqus-gate");
    const shell = document.getElementById("app-shell");
    const form = document.getElementById("phiqus-gate-form");

    if (!gate || !shell || !form) {
        bootstrapApp();
        return;
    }

    if (
        sessionStorage.getItem(PHIQUS_GATE.storageKey) === "1" ||
        isMercadoPagoReturnUrl() ||
        hasPaidOrderPendingUnlock()
    ) {
        if (isMercadoPagoReturnUrl() || hasPaidOrderPendingUnlock()) {
            sessionStorage.setItem(PHIQUS_GATE.storageKey, "1");
        }
        gate.classList.add("hidden");
        shell.classList.remove("hidden");
        bootstrapApp();
        return;
    }

    gate.classList.remove("hidden");
    shell.classList.add("hidden");

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        const username = document.getElementById("phiqus-username")?.value?.trim() || "";
        const password = document.getElementById("phiqus-password")?.value || "";
        const errorEl = document.getElementById("phiqus-gate-error");

        if (username === PHIQUS_GATE.username && password === PHIQUS_GATE.password) {
            sessionStorage.setItem(PHIQUS_GATE.storageKey, "1");
            sessionStorage.removeItem(GOOGLE_AUTH_STORAGE_KEY);
            localStorage.removeItem(GOOGLE_AUTH_STORAGE_KEY);
            state.googleAuthenticated = false;
            state.googleUser = null;
            state.currentUserRole = "guest";
            updateUserChip(null);
            if (errorEl) errorEl.classList.add("hidden");
            gate.classList.add("hidden");
            shell.classList.remove("hidden");
            bootstrapApp();
            logger("Acceso PhiQus concedido.");
            return;
        }

        if (errorEl) {
            errorEl.textContent = "Usuario o contraseña incorrectos.";
            errorEl.classList.remove("hidden");
        }
    });
}

async function bootstrapApp() {
    if (state.appBootstrapped) return;
    state.appBootstrapped = true;

    restoreGoogleSession();
    await Promise.all([initGoogleAuthConfig(), ensurePaymentsConfig()]);
    initMap();
    bindUIEvents();
    initTierPricingLabels();
    initUIFeatures();
    await handleMercadoPagoReturn();
    await resumePendingMercadoPagoCheckout();
    await tryUnlockOrderFromUrl();
    await tryRestorePaidReport();
    logger("Inicialización completa. Esperando clic en el mapa...");
}

function restoreGoogleSession() {
    const raw =
        localStorage.getItem(GOOGLE_AUTH_STORAGE_KEY) ||
        sessionStorage.getItem(GOOGLE_AUTH_STORAGE_KEY);
    if (!raw || raw === "1") {
        return;
    }
    try {
        const data = JSON.parse(raw);
        if (data?.token && data?.email) {
            if (isGoogleTokenExpired(data.token)) {
                logger("Sesión Google guardada expirada; se pedirá iniciar sesión de nuevo.");
                localStorage.removeItem(GOOGLE_AUTH_STORAGE_KEY);
                sessionStorage.removeItem(GOOGLE_AUTH_STORAGE_KEY);
                return;
            }
            state.googleAuthenticated = true;
            state.googleUser = data;
            state.currentUserRole = "user";
            updateUserChip(data.user || data);
        }
    } catch (err) {
        logger("Sesión Google almacenada inválida:", err);
        localStorage.removeItem(GOOGLE_AUTH_STORAGE_KEY);
        sessionStorage.removeItem(GOOGLE_AUTH_STORAGE_KEY);
    }
}

function isGoogleTokenExpired(token, leewaySec = 90) {
    if (!token || typeof token !== "string") return true;
    if (token.startsWith("mock")) return false;
    try {
        const part = token.split(".")[1];
        if (!part) return true;
        const payload = JSON.parse(atob(part.replace(/-/g, "+").replace(/_/g, "/")));
        if (!payload.exp) return true;
        return Date.now() / 1000 >= payload.exp - leewaySec;
    } catch (_err) {
        return true;
    }
}

function googleSessionValid() {
    return Boolean(
        state.googleAuthenticated &&
        state.googleUser?.token &&
        !isGoogleTokenExpired(state.googleUser.token)
    );
}

function clearGoogleSession() {
    state.googleAuthenticated = false;
    state.googleUser = null;
    localStorage.removeItem(GOOGLE_AUTH_STORAGE_KEY);
    sessionStorage.removeItem(GOOGLE_AUTH_STORAGE_KEY);
    updateUserChip(null);
}

async function ensurePaymentsConfig() {
    try {
        const response = await fetch("/api/pagos/config");
        if (!response.ok) {
            logger("Configuración de pagos no disponible:", response.status);
            return false;
        }
        const data = await response.json();
        state.paymentsMock = Boolean(data.payments_mock);
        state.checkoutProEnabled = Boolean(data.checkout_pro);
        state.mercadoPagoSandbox = Boolean(data.sandbox);
        state.sandboxBuyerConfigured = Boolean(data.sandbox_buyer_configured);
        state.publicReturnUrlConfigured = Boolean(data.public_return_url_configured);
        state.paymentsConfigLoaded = true;
        applyPaymentsUIMode();
        logger(
            `Pagos: ${state.paymentsMock ? "MOCK (modal simulado)" : "Checkout Pro Mercado Pago"}.`
        );
        return true;
    } catch (err) {
        logger("No se pudo cargar configuración de pagos:", err);
        return false;
    }
}

function applyPaymentsUIMode() {
    const mockOptions = document.querySelector("#payment-modal .payment-options");
    const confirmBtn = document.getElementById("confirm-payment-btn");
    if (state.paymentsMock) {
        mockOptions?.classList.remove("hidden");
        if (confirmBtn) confirmBtn.textContent = "CONFIRMAR PAGO SIMULADO";
    } else {
        mockOptions?.classList.add("hidden");
        if (confirmBtn) confirmBtn.textContent = "Ir a Mercado Pago";
    }
}

async function handleMercadoPagoReturn() {
    const params = getUrlSearchParams();
    const ordenId =
        params.get("orden_id") ||
        getMpPendingOrdenId();
    const tier = getMpPendingTier() || params.get("tier");
    const collectionStatus = params.get("collection_status");
    const pagoFlag = params.get("pago");
    const hasReturn =
        ordenId &&
        (pagoFlag ||
            collectionStatus ||
            params.get("payment_id") ||
            params.get("external_reference") ||
            params.get("status"));

    if (!hasReturn) return;

    activatePostPaymentFlow();
    state.activeOrderId = parseInt(ordenId, 10);
    if (tier) state.activeTier = tier;
    persistMpReturnContext(params);

    if (pagoFlag || collectionStatus || params.get("payment_id")) {
        window.history.replaceState({}, "", window.location.pathname);
    }

    document.getElementById("results-dashboard")?.classList.remove("hidden");

    const approved =
        pagoFlag === "ok" ||
        collectionStatus === "approved" ||
        params.get("status") === "approved";

    if (approved) {
        logger("Retorno de Mercado Pago aprobado.");
        state.checkoutLaunchInProgress = false;
        persistPaidOrderHint(tier);
        scrollToPostPaymentSection();

        if (googleSessionValid()) {
            showMpCheckoutBanner("¡Pago exitoso! Desbloqueando tu reporte…");
            await syncMercadoPagoPaymentFromReturn();
            const unlocked = await resumePaidReportUnlock();
            if (!unlocked) {
                await pollPaidReportAfterCheckout();
            }
        } else {
            showPaidReportUnlockPrompt(
                "¡Pago exitoso! Inicia sesión con Google para ver tu reporte completo."
            );
        }
        return;
    }

    if (pagoFlag === "pending" || collectionStatus === "pending") {
        showMpCheckoutBanner("Tu pago está pendiente de confirmación en Mercado Pago.");
        scrollToPostPaymentSection();
        startMercadoPagoCheckoutPolling();
        return;
    }

    if (pagoFlag === "error") {
        document.getElementById("results-dashboard")?.classList.remove("hidden");
        showMpPaymentNotAccredited();
        scrollToPostPaymentSection();
        return;
    }
}

function showMpCheckoutBanner(message) {
    const banner = document.getElementById("mp-checkout-banner");
    const text = document.getElementById("mp-checkout-banner-text");
    if (text) text.textContent = message;
    banner?.classList.remove("hidden");
}

function hideMpCheckoutBanner() {
    document.getElementById("mp-checkout-banner")?.classList.add("hidden");
    document.getElementById("mp-unlock-report-btn")?.classList.add("hidden");
    document.getElementById("mp-unlock-google-container")?.classList.add("hidden");
}

function persistMpReturnContext(params) {
    const paymentId = params.get("payment_id") || params.get("collection_id");
    const ctx = {
        orden_id: params.get("orden_id"),
        payment_id: paymentId,
        external_reference: params.get("external_reference"),
        status: params.get("status") || params.get("collection_status") || params.get("pago"),
    };
    if (ctx.orden_id) {
        sessionStorage.setItem(MP_RETURN_CONTEXT_KEY, JSON.stringify(ctx));
        if (ctx.payment_id) {
            localStorage.setItem("mp_return_payment_id", String(ctx.payment_id));
        }
        if (ctx.external_reference) {
            localStorage.setItem("mp_return_external_ref", ctx.external_reference);
        }
    }
}

async function syncMercadoPagoPaymentFromReturn() {
    let ctx = null;
    const raw = sessionStorage.getItem(MP_RETURN_CONTEXT_KEY);
    if (raw) {
        try {
            ctx = JSON.parse(raw);
        } catch (_err) {
            sessionStorage.removeItem(MP_RETURN_CONTEXT_KEY);
        }
    }
    if (!ctx) {
        const ordenId =
            state.activeOrderId ||
            parseInt(localStorage.getItem(PAID_ORDER_STORAGE_KEY) || "", 10);
        const paymentId = localStorage.getItem("mp_return_payment_id");
        const externalRef = localStorage.getItem("mp_return_external_ref");
        if (ordenId && paymentId) {
            ctx = {
                orden_id: String(ordenId),
                payment_id: paymentId,
                external_reference: externalRef,
            };
        }
    }
    if (!ctx || !googleSessionValid()) return false;

    const ordenId = parseInt(ctx.orden_id, 10);
    const paymentId = ctx.payment_id ? parseInt(ctx.payment_id, 10) : null;
    if (!ordenId || Number.isNaN(ordenId) || !paymentId) return false;

    state.activeOrderId = ordenId;

    try {
        const resp = await fetchWithGoogleAuth("/api/pagos/confirmar-retorno", {
            method: "POST",
            headers: { "Content-Type": "application/json", ...getAuthHeaders() },
            body: JSON.stringify({
                orden_id: ordenId,
                payment_id: paymentId,
                external_reference: ctx.external_reference || null,
            }),
            skipAuthModal: true,
        });
        if (!resp.ok) {
            const detail = await parseHttpErrorMessage(resp, "No se pudo confirmar el pago.");
            logger("Confirmación de retorno MP falló:", detail);
            return false;
        }
        const data = await resp.json();
        state.activeTier = data.tier_adquirido || state.activeTier;
        persistPaidOrderHint(data.tier_adquirido);
        sessionStorage.removeItem(MP_RETURN_CONTEXT_KEY);
        localStorage.removeItem("mp_return_payment_id");
        localStorage.removeItem("mp_return_external_ref");
        logger(`Pago confirmado en servidor para orden #${ordenId}`);
        return true;
    } catch (err) {
        logger("Error al confirmar retorno MP:", err);
        return false;
    }
}

function persistPaidOrderHint(tier) {
    if (!state.activeOrderId) return;
    localStorage.setItem(PAID_ORDER_STORAGE_KEY, String(state.activeOrderId));
    const tierToSave = tier || state.activeTier || "premium";
    localStorage.setItem(PAID_TIER_STORAGE_KEY, tierToSave);
    state.activeTier = tierToSave;
}

function clearPaidOrderHint() {
    localStorage.removeItem(PAID_ORDER_STORAGE_KEY);
    localStorage.removeItem(PAID_TIER_STORAGE_KEY);
    clearMpPendingSession();
}

function showPaidReportUnlockPrompt(message, options = {}) {
    const { allowUnlock = true } = options;
    const text = document.getElementById("mp-checkout-banner-text");
    const hint = document.getElementById("mp-checkout-banner-hint");
    if (text) {
        text.textContent =
            message ||
            "¡Pago confirmado! Inicia sesión con Google para ver tu reporte completo.";
    }
    if (hint) {
        hint.textContent =
            "Usa la misma cuenta de Google con la que compraste el reporte.";
    }
    document.getElementById("mp-checkout-banner")?.classList.remove("hidden");
    document.getElementById("results-dashboard")?.classList.remove("hidden");

    if (!allowUnlock) {
        document.getElementById("mp-unlock-report-btn")?.classList.add("hidden");
        document.getElementById("mp-unlock-google-container")?.classList.add("hidden");
        return;
    }

    if (state.googleAuthEnabled && !googleSessionValid()) {
        document.getElementById("mp-unlock-report-btn")?.classList.add("hidden");
        renderPaidUnlockGoogleButton();
    } else if (googleSessionValid()) {
        document.getElementById("mp-unlock-google-container")?.classList.add("hidden");
        const retryBtn = document.getElementById("mp-unlock-report-btn");
        if (retryBtn) {
            retryBtn.textContent = "Cargar mi reporte pagado";
            retryBtn.classList.remove("hidden");
        }
    } else {
        document.getElementById("mp-unlock-google-container")?.classList.add("hidden");
        document.getElementById("mp-unlock-report-btn")?.classList.remove("hidden");
    }
}

function showMpPaymentNotAccredited() {
    clearMpPendingSession();
    clearPaidOrderHint();
    state.postPaymentFlow = false;
    state.checkoutLaunchInProgress = false;

    const text = document.getElementById("mp-checkout-banner-text");
    const hint = document.getElementById("mp-checkout-banner-hint");
    if (text) {
        text.textContent =
            "No recibimos la confirmación de tu pago en Mercado Pago. Si no completaste el pago, puedes volver a intentarlo desde el reporte.";
    }
    if (hint) {
        hint.textContent =
            "Si ya pagaste y no ves tu reporte, espera unos minutos o contacta a soporte con tu comprobante.";
    }
    document.getElementById("mp-checkout-banner")?.classList.remove("hidden");
    document.getElementById("mp-unlock-report-btn")?.classList.add("hidden");
    document.getElementById("mp-unlock-google-container")?.classList.add("hidden");
}

function handleCheckoutPollingTimeout(lastSnapshot) {
    const estado = lastSnapshot?.estado_pago;

    if (estado === "approved") {
        persistPaidOrderHint(lastSnapshot.tier_adquirido);
        if (lastSnapshot.reporte_listo) {
            showPaidReportUnlockPrompt(
                "Tu pago fue acreditado. Inicia sesión con Google para desbloquear el reporte."
            );
        } else {
            showPaidReportUnlockPrompt(
                "Tu pago fue acreditado. El reporte sigue generándose; inicia sesión para cargarlo cuando esté listo."
            );
        }
        return;
    }

    if (estado === "rejected") {
        clearPaidOrderHint();
        hideMpCheckoutBanner();
        alert("El pago fue rechazado. Puedes intentar de nuevo.");
        return;
    }

    showMpPaymentNotAccredited();
}

async function renderPaidUnlockGoogleButton() {
    if (!state.googleAuthEnabled) return;
    const container = document.getElementById("mp-unlock-google-container");
    if (!container) return;

    container.classList.remove("hidden");
    try {
        await waitForGoogleGsi();
        ensureGoogleIdentityInitialized();
        container.innerHTML = "";
        google.accounts.id.renderButton(container, {
            theme: "filled_blue",
            size: "large",
            width: 320,
            text: "continue_with",
            locale: "es",
        });
    } catch (err) {
        logger("No se pudo renderizar botón Google en banner de desbloqueo:", err);
        document.getElementById("mp-unlock-report-btn")?.classList.remove("hidden");
    }
}

function ensureGoogleIdentityInitialized() {
    if (googleSignInInitialized) return;
    google.accounts.id.initialize({
        client_id: state.googleClientId,
        callback: handleGoogleCredentialResponse,
        auto_select: false,
        cancel_on_tap_outside: false,
    });
    googleSignInInitialized = true;
}

function ensureMapReady() {
    if (!state.map) {
        initMap();
    }
}

async function resolveActivePaidOrderFromServer() {
    const localOrderId =
        state.activeOrderId ||
        parseInt(localStorage.getItem(PAID_ORDER_STORAGE_KEY) || "", 10);
    if (localOrderId && !Number.isNaN(localOrderId)) {
        state.activeOrderId = localOrderId;
        return null;
    }

    try {
        const resp = await fetchWithGoogleAuth("/api/pagos/mi-ultima-aprobada", {
            method: "GET",
            skipAuthModal: true,
        });
        if (!resp.ok) {
            logger("No se encontró orden aprobada en servidor:", resp.status);
            return null;
        }
        const data = await resp.json();
        state.activeOrderId = data.orden_id;
        state.activeTier = data.tier_adquirido || state.activeTier;
        persistPaidOrderHint(data.tier_adquirido);
        logger(`Orden pagada resuelta desde servidor: #${data.orden_id}`);
        return data;
    } catch (err) {
        logger("Error al resolver orden pagada en servidor:", err);
        return null;
    }
}

async function resumePaidReportUnlock(options = {}) {
    const { silent = false, syncFromServer = false } = options;

    if (syncFromServer && state.googleAuthEnabled && googleSessionValid()) {
        await resolveActivePaidOrderFromServer();
    }

    if (!state.activeOrderId) {
        const stored = localStorage.getItem(PAID_ORDER_STORAGE_KEY);
        if (stored) state.activeOrderId = parseInt(stored, 10);
    }
    if (!state.activeOrderId && googleSessionValid()) {
        await resolveActivePaidOrderFromServer();
    }
    if (!state.activeOrderId) return false;

    if (!state.activeTier) {
        state.activeTier =
            localStorage.getItem(PAID_TIER_STORAGE_KEY) ||
            getMpPendingTier() ||
            "premium";
    }

    if (state.googleAuthEnabled && !googleSessionValid()) {
        showPaidReportUnlockPrompt();
        return false;
    }

    try {
        ensureMapReady();
        await syncMercadoPagoPaymentFromReturn();

        const statusResp = await fetchWithGoogleAuth(
            `/api/pagos/orden/${state.activeOrderId}/estado`,
            { method: "GET", skipAuthModal: true }
        );
        if (!statusResp.ok) {
            const detail = await parseHttpErrorMessage(
                statusResp,
                "No se pudo verificar tu compra."
            );
            logger("Estado de orden falló:", statusResp.status, detail);
            showPaidReportUnlockPrompt(
                statusResp.status === 403
                    ? "Esta compra pertenece a otra cuenta de Google. Usa la misma cuenta con la que pagaste."
                    : "Inicia sesión con la misma cuenta de Google con la que compraste."
            );
            return false;
        }

        const statusData = await statusResp.json();
        state.activeTier = statusData.tier_adquirido || state.activeTier;
        persistPaidOrderHint(statusData.tier_adquirido);

        if (statusData.estado_pago === "pending") {
            showMpCheckoutBanner("Esperando confirmación del pago en Mercado Pago…");
            startMercadoPagoCheckoutPolling();
            return false;
        }
        if (statusData.estado_pago === "rejected") {
            clearPaidOrderHint();
            hideMpCheckoutBanner();
            if (!silent) alert("El pago fue rechazado. Puedes intentar de nuevo.");
            return false;
        }
        if (statusData.estado_pago !== "approved") return false;

        if (!statusData.reporte_listo) {
            showMpCheckoutBanner("Pago acreditado. Generando tu reporte…");
            startMercadoPagoCheckoutPolling();
            return false;
        }

        showMpCheckoutBanner("Cargando tu reporte completo…");
        const unlocked = await unlockPaidReport();
        if (unlocked) {
            hideMpCheckoutBanner();
            clearPaidOrderHint();
            state.postPaymentFlow = false;
            if (!silent) {
                logger("Reporte pagado desbloqueado correctamente.");
            }
            return true;
        }

        if (googleSessionValid()) {
            showMpCheckoutBanner("Tu pago está confirmado. Reintentando cargar el reporte…");
            startMercadoPagoCheckoutPolling();
        } else {
            showPaidReportUnlockPrompt(
                "No pudimos cargar el reporte. Inicia sesión de nuevo con Google."
            );
        }
        return false;
    } catch (err) {
        logger("Error al reanudar desbloqueo del reporte:", err);
        const detail = err?.message ? ` (${err.message})` : "";
        showPaidReportUnlockPrompt(
            `Ocurrió un error al desbloquear${detail}. Intenta otra vez.`
        );
        return false;
    }
}

async function tryRestorePaidReport() {
    const pendingOrdenId = getMpPendingOrdenId();
    const storedPaidOrdenId = localStorage.getItem(PAID_ORDER_STORAGE_KEY);
    const ordenId = pendingOrdenId || storedPaidOrdenId;
    if (!ordenId) return;

    activatePostPaymentFlow();
    state.activeOrderId = parseInt(ordenId, 10);
    state.activeTier =
        getMpPendingTier() ||
        localStorage.getItem(PAID_TIER_STORAGE_KEY) ||
        state.activeTier;

    document.getElementById("results-dashboard")?.classList.remove("hidden");

    if (state.googleAuthEnabled && !googleSessionValid()) {
        const message = storedPaidOrdenId && !pendingOrdenId
            ? "Tienes un reporte pagado pendiente de desbloquear. Inicia sesión con Google."
            : "Si completaste tu pago en Mercado Pago, inicia sesión con Google para ver tu reporte.";
        showPaidReportUnlockPrompt(message);
        scrollToPostPaymentSection();
        return;
    }

    await resumePaidReportUnlock();
}

function clearMpPendingSession() {
    sessionStorage.removeItem("mp_pending_orden_id");
    sessionStorage.removeItem("mp_pending_tier");
    sessionStorage.removeItem("mp_pending_checkout_id");
    localStorage.removeItem("mp_pending_orden_id");
    localStorage.removeItem("mp_pending_tier");
    localStorage.removeItem("mp_pending_checkout_id");
}

function persistMpPendingSession(ordenId, tier, checkoutId) {
    sessionStorage.setItem("mp_pending_orden_id", String(ordenId));
    sessionStorage.setItem("mp_pending_tier", tier);
    sessionStorage.setItem("mp_pending_checkout_id", checkoutId || "");
    localStorage.setItem("mp_pending_orden_id", String(ordenId));
    localStorage.setItem("mp_pending_tier", tier);
    localStorage.setItem("mp_pending_checkout_id", checkoutId || "");
}

function getMpPendingOrdenId() {
    return (
        sessionStorage.getItem("mp_pending_orden_id") ||
        localStorage.getItem("mp_pending_orden_id")
    );
}

function getMpPendingTier() {
    return (
        sessionStorage.getItem("mp_pending_tier") ||
        localStorage.getItem("mp_pending_tier")
    );
}

function launchMercadoPagoCheckout(initPoint, ordenId, tier) {
    if (state.checkoutLaunchInProgress) {
        logger("Checkout de Mercado Pago ya en curso; se omite apertura duplicada.");
        return;
    }
    state.checkoutLaunchInProgress = true;

    persistMpPendingSession(ordenId, tier, state.activeCheckoutId);
    state.activeOrderId = ordenId;
    state.activeTier = tier;
    activatePostPaymentFlow();
    closePaymentModal();

    logger("Redirigiendo a Mercado Pago…");
    window.location.assign(initPoint);
}

async function resumePendingMercadoPagoCheckout() {
    const ordenId = getMpPendingOrdenId();
    if (!ordenId || state.checkoutPollActive) return;

    const params = new URLSearchParams(window.location.search);
    if (params.get("pago") || params.get("collection_status")) return;

    state.activeOrderId = parseInt(ordenId, 10);
    const tier = getMpPendingTier();
    if (tier) state.activeTier = tier;

    if (state.googleAuthEnabled && !googleSessionValid()) {
        showPaidReportUnlockPrompt(
            "Si completaste tu pago en Mercado Pago, inicia sesión con Google para ver tu reporte."
        );
        scrollToPostPaymentSection();
        return;
    }

    try {
        const response = await fetchWithGoogleAuth(
            `/api/pagos/orden/${state.activeOrderId}/estado`,
            { method: "GET", skipAuthModal: true }
        );
        if (!response.ok) return;
        const data = await response.json();
        if (data.estado_pago === "approved" && data.reporte_listo) {
            document.getElementById("results-dashboard")?.classList.remove("hidden");
            persistPaidOrderHint(data.tier_adquirido);
            await resumePaidReportUnlock();
            return;
        }
        if (data.estado_pago === "approved" || data.estado_pago === "pending") {
            document.getElementById("results-dashboard")?.classList.remove("hidden");
            showMpCheckoutBanner(
                data.estado_pago === "approved"
                    ? "Pago acreditado. Generando tu reporte…"
                    : "Esperando confirmación de pago en Mercado Pago…"
            );
            startMercadoPagoCheckoutPolling();
        } else if (data.estado_pago === "rejected") {
            document.getElementById("results-dashboard")?.classList.remove("hidden");
            clearPaidOrderHint();
            hideMpCheckoutBanner();
            alert("El pago fue rechazado. Puedes intentar de nuevo.");
        }
    } catch (err) {
        logger("No se pudo reanudar checkout pendiente:", err);
    }
}

function startMercadoPagoCheckoutPolling() {
    if (state.checkoutPollActive) return;
    state.checkoutPollActive = true;
    pollPaidReportAfterCheckout().finally(() => {
        state.checkoutPollActive = false;
    });
}

/** Recupera un reporte ya pagado si la URL trae ?orden_id= (p. ej. retorno desde MP). */
async function tryUnlockOrderFromUrl() {
    const params = getUrlSearchParams();
    const ordenParam = params.get("orden_id");
    if (!ordenParam) return;
    if (getMpPendingOrdenId()) return;
    if (params.get("pago") || params.get("collection_status")) return;

    activatePostPaymentFlow();
    state.activeOrderId = parseInt(ordenParam, 10);
    if (params.get("pago") === "error") return;

    document.getElementById("results-dashboard")?.classList.remove("hidden");
    await resumePaidReportUnlock();
}

async function pollPaidReportAfterCheckout(maxAttempts = 60, delayMs = 3000) {
    let lastSnapshot = null;

    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
        try {
            if (state.googleAuthEnabled && !googleSessionValid()) {
                showPaidReportUnlockPrompt(
                    "Pago en proceso. Inicia sesión con Google para desbloquear tu reporte cuando esté listo."
                );
                return;
            }

            const statusResponse = await fetchWithGoogleAuth(
                `/api/pagos/orden/${state.activeOrderId}/estado`,
                { method: "GET", skipAuthModal: true }
            );
            if (statusResponse.ok) {
                const statusData = await statusResponse.json();
                lastSnapshot = {
                    estado_pago: statusData.estado_pago,
                    reporte_listo: statusData.reporte_listo,
                    tier_adquirido: statusData.tier_adquirido,
                };
                state.activeTier = statusData.tier_adquirido || state.activeTier;

                if (statusData.estado_pago === "approved" && statusData.reporte_listo) {
                    persistPaidOrderHint(statusData.tier_adquirido);
                    const unlocked = await resumePaidReportUnlock({ silent: true });
                    if (unlocked) return;
                }
                if (statusData.estado_pago === "approved") {
                    persistPaidOrderHint(statusData.tier_adquirido);
                    showMpCheckoutBanner(
                        `Pago acreditado. Generando reporte… (${attempt}/${maxAttempts})`
                    );
                } else if (statusData.estado_pago === "pending") {
                    showMpCheckoutBanner(
                        `Esperando confirmación en Mercado Pago… (${attempt}/${maxAttempts})`
                    );
                } else if (statusData.estado_pago === "rejected") {
                    hideMpCheckoutBanner();
                    clearPaidOrderHint();
                    alert("El pago fue rechazado. Puedes intentar de nuevo.");
                    return;
                }
            } else if (statusResponse.status === 401 || statusResponse.status === 403) {
                showPaidReportUnlockPrompt();
                return;
            }
        } catch (err) {
            logger("Polling post-pago error de red:", err);
        }
        await new Promise((resolve) => setTimeout(resolve, delayMs));
    }
    handleCheckoutPollingTimeout(lastSnapshot);
}

async function initGoogleAuthConfig() {
    try {
        const response = await fetch("/api/auth/config");
        if (!response.ok) return;
        const data = await response.json();
        state.googleClientId = data.client_id || null;
        state.googleAuthEnabled = Boolean(data.enabled && data.client_id);
        logger(`Google Sign-In ${state.googleAuthEnabled ? "habilitado" : "no configurado"}.`);
    } catch (err) {
        logger("No se pudo cargar configuración de Google Auth:", err);
    }
}

function updateUserChip(user) {
    const chip = document.getElementById("google-user-chip");
    const nameEl = document.getElementById("google-user-name");
    const avatarEl = document.getElementById("google-user-avatar");
    if (!chip || !nameEl || !avatarEl) return;

    if (!user?.email) {
        chip.classList.add("hidden");
        nameEl.textContent = "";
        avatarEl.style.backgroundImage = "";
        return;
    }

    const label = user.nombre || user.email.split("@")[0];
    nameEl.textContent = label;
    if (user.avatar_url) {
        avatarEl.style.backgroundImage = `url('${user.avatar_url}')`;
    } else {
        avatarEl.style.backgroundImage = "";
    }
    chip.classList.remove("hidden");
}

function persistGoogleSession(data) {
    const session = {
        token: data.token,
        email: data.user.email,
        nombre: data.user.nombre,
        google_sub: data.user.google_sub,
        avatar_url: data.user.avatar_url,
        user: data.user,
    };
    sessionStorage.setItem(GOOGLE_AUTH_STORAGE_KEY, JSON.stringify(session));
    localStorage.setItem(GOOGLE_AUTH_STORAGE_KEY, JSON.stringify(session));
    state.googleAuthenticated = true;
    state.googleUser = session;
    state.currentUserRole = "user";
    updateUserChip(data.user);
}

function waitForGoogleGsi(timeoutMs = 8000) {
    return new Promise((resolve, reject) => {
        if (window.google?.accounts?.id) {
            resolve();
            return;
        }
        const started = Date.now();
        const timer = setInterval(() => {
            if (window.google?.accounts?.id) {
                clearInterval(timer);
                resolve();
                return;
            }
            if (Date.now() - started >= timeoutMs) {
                clearInterval(timer);
                reject(new Error("Google Identity Services no cargó a tiempo."));
            }
        }, 100);
    });
}

let googleSignInInitialized = false;

function prepareGoogleSignInUi(options = {}) {
    const modal = document.getElementById("google-login-modal");
    const modalTitle = modal?.querySelector(".modal-header h3");
    const modalDesc = modal?.querySelector(".billing-desc");
    const hint = document.getElementById("google-login-hint");
    const progressContainer = document.getElementById("login-progress-container");

    if (options.showModal || options.analyzeFlow) {
        modal?.classList.remove("hidden");
    }
    progressContainer?.classList.add("hidden");

    if (options.analyzeFlow && modalTitle) {
        modalTitle.textContent = "🌐 Autenticando para analizar";
    }
    if (options.analyzeFlow && modalDesc) {
        modalDesc.textContent =
            "Vinculamos tu cuenta de Google mientras preparamos el análisis de viabilidad de tu ubicación.";
    }
    if (options.unlockFlow && modalTitle) {
        modalTitle.textContent = "🔓 Desbloquear reporte pagado";
    }
    if (options.unlockFlow && modalDesc) {
        modalDesc.textContent =
            "Inicia sesión con la misma cuenta de Google que usaste al comprar para ver tu reporte completo.";
    }
    if (hint) {
        const originActual = window.location.origin;
        const baseHint = options.analyzeFlow
            ? "Elige tu cuenta de Google para continuar con el análisis."
            : "Selecciona tu cuenta de Google para continuar.";
        hint.innerHTML =
            `${baseHint}<br><br>` +
            `<strong>Origen actual:</strong> <code style="font-size:11px;">${originActual}</code><br>` +
            `Si ves <em>origin_mismatch</em>, agrega exactamente esa URL en Google Cloud → Credenciales → Orígenes JavaScript autorizados.`;
    }

    if (!googleSignInInitialized) {
        ensureGoogleIdentityInitialized();
    }

    const container = document.getElementById("google-signin-button-container");
    if (container) {
        container.innerHTML = "";
        google.accounts.id.renderButton(container, {
            theme: "outline",
            size: "large",
            width: 320,
            text: "continue_with",
            locale: "es",
        });
    }

    if (options.analyzeFlow) {
        google.accounts.id.prompt((notification) => {
            if (notification.isNotDisplayed() || notification.isSkippedMoment()) {
                logger("One Tap no disponible; usa el botón de Google.", notification);
            }
        });
    }
}

async function handleGoogleCredentialResponse(response) {
    const pending = state.googleAuthPending;
    try {
        const authResponse = await fetch("/api/auth/google", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ credential: response.credential }),
        });
        if (!authResponse.ok) {
            const errData = await authResponse.json().catch(() => ({}));
            throw new Error(errData.detail || "No se pudo validar la sesión de Google.");
        }
        const data = await authResponse.json();
        persistGoogleSession(data);
        document.getElementById("google-login-modal")?.classList.add("hidden");
        document.getElementById("mp-unlock-google-container")?.classList.add("hidden");
        logger(`Sesión Google iniciada: ${data.user.email}`);

        if (state.postPaymentFlow || hasPaidOrderPendingUnlock()) {
            activatePostPaymentFlow();
            document.getElementById("results-dashboard")?.classList.remove("hidden");
            showMpCheckoutBanner("Sesión confirmada. Cargando tu reporte…");
            ensureMapReady();
            await syncMercadoPagoPaymentFromReturn();
            await resumePaidReportUnlock();
        }

        if (pending?.options?.showAlert) {
            alert(`Autenticación exitosa. Bienvenido, ${data.user.nombre || data.user.email}.`);
        }
        pending?.resolve?.();
    } catch (err) {
        logger("Error en autenticación Google:", err);
        alert(err.message || "No se pudo completar el inicio de sesión con Google.");
        pending?.reject?.(err);
    }
}

// --- LOGGER INTERNO ---
function logger(message, data = null) {
    const timestamp = new Date().toLocaleTimeString();
    if (data) {
        console.log(`[${timestamp}] 📍 ${message}`, data);
    } else {
        console.log(`[${timestamp}] 📍 ${message}`);
    }
}

function formatTierPrice(tier) {
    const amount = TIER_PRICING[tier]?.amount ?? 0;
    return `${priceFormatter.format(amount)} MXN`;
}

function initUIFeatures() {
    const intencionesSection = document.getElementById("intenciones-section");
    if (intencionesSection) {
        intencionesSection.classList.toggle("hidden", !UI_FEATURES.intencionesNegocio);
    }

    const copy = UI_FEATURES.intencionesNegocio
        ? INTRO_COPY.conIntenciones
        : INTRO_COPY.sinIntenciones;

    const introStep = document.getElementById("intro-step-config");
    if (introStep) {
        introStep.innerHTML = `<strong>Configura variables:</strong> ${copy.step}`;
    }

    const panelDesc = document.getElementById("panel-config-desc");
    if (panelDesc) {
        panelDesc.textContent = copy.panel;
    }
}

function initTierPricingLabels() {
    Object.entries(TIER_PRICING).forEach(([tier, config]) => {
        const btn = document.getElementById(`buy-${tier}-btn`);
        if (btn) {
            btn.textContent = `🔒 COMPRAR ${config.label} (${formatTierPrice(tier)})`;
        }
    });
}

function startInlineProgress(containerId, {
    messages = ["Procesando..."],
    stepMs = 150,
    stepPercent = 4,
    maxWhileWaiting = 88,
} = {}) {
    const container = document.getElementById(containerId);
    if (!container) return null;

    const statusEl = container.querySelector("[data-progress-status]");
    const fillEl = container.querySelector("[data-progress-fill]");
    if (!statusEl || !fillEl) return null;

    if (progressTimers[containerId]) {
        clearInterval(progressTimers[containerId]);
    }

    container.classList.remove("hidden");
    let progress = 0;
    let messageIndex = 0;
    statusEl.textContent = messages[0];
    fillEl.style.width = "0%";

    progressTimers[containerId] = setInterval(() => {
        if (progress < maxWhileWaiting) {
            progress = Math.min(progress + stepPercent, maxWhileWaiting);
            fillEl.style.width = `${progress}%`;
        }

        const nextMsgIdx = Math.min(
            messages.length - 1,
            Math.floor((progress / maxWhileWaiting) * messages.length)
        );
        if (nextMsgIdx !== messageIndex && messages[nextMsgIdx]) {
            messageIndex = nextMsgIdx;
            statusEl.textContent = messages[messageIndex];
        }
    }, stepMs);

    return { container, statusEl, fillEl };
}

function finishInlineProgress(containerId, message = "Listo") {
    const container = document.getElementById(containerId);
    if (!container) return;

    const statusEl = container.querySelector("[data-progress-status]");
    const fillEl = container.querySelector("[data-progress-fill]");

    if (progressTimers[containerId]) {
        clearInterval(progressTimers[containerId]);
        delete progressTimers[containerId];
    }

    if (statusEl) statusEl.textContent = message;
    if (fillEl) fillEl.style.width = "100%";
}

function resetInlineProgress(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (progressTimers[containerId]) {
        clearInterval(progressTimers[containerId]);
        delete progressTimers[containerId];
    }

    container.classList.add("hidden");
    const fillEl = container.querySelector("[data-progress-fill]");
    if (fillEl) fillEl.style.width = "0%";
}

function setButtonLoading(btn, isLoading, loadingLabel = "Procesando...") {
    if (!btn) return;

    if (isLoading) {
        if (!btn.dataset.originalHtml) {
            btn.dataset.originalHtml = btn.innerHTML;
        }
        btn.classList.add("is-loading");
        btn.setAttribute("disabled", "true");
        btn.innerHTML = `<span class="btn-spinner" aria-hidden="true"></span> ${loadingLabel}`;
        return;
    }

    btn.classList.remove("is-loading");
    btn.innerHTML = btn.dataset.originalHtml || btn.innerHTML;
    delete btn.dataset.originalHtml;
}

function restoreAnalyzeButton(btn) {
    setButtonLoading(btn, false);
    checkFormValidity();
}

function setKpisLoading(loading) {
    KPI_VALUE_IDS.forEach((id) => {
        const el = document.getElementById(id);
        const card = el?.closest(".kpi-card");
        if (!el || !card) return;

        if (loading) {
            card.classList.add("kpi-loading");
            el.textContent = "\u00a0";
        } else {
            card.classList.remove("kpi-loading");
        }
    });
}

// --- CONFIGURACIÓN E INICIALIZACIÓN DEL MAPA ---
function initMap() {
    if (state.map) return;

    const mapEl = document.getElementById("map");
    if (!mapEl) {
        logger("Contenedor #map no disponible aún.");
        return;
    }

    // Coordenadas iniciales: Zócalo de la Ciudad de México
    const cdmxCoords = [19.432608, -99.133208];
    
    // Instanciar mapa Leaflet
    state.map = L.map(mapEl, {
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
    document.getElementById("mp-unlock-report-btn")?.addEventListener("click", async () => {
        if (googleSessionValid()) {
            showMpCheckoutBanner("Cargando tu reporte pagado…");
            await syncMercadoPagoPaymentFromReturn();
            await resumePaidReportUnlock();
            return;
        }
        showPaidReportUnlockPrompt();
        scrollToPostPaymentSection();
        renderPaidUnlockGoogleButton();
    });

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
    
    // D. Perfil simulado (selector oculto; rol gestionado por autenticación Google)
    
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
        if (state.googleAuthPending) {
            state.googleAuthPending.reject(new Error("Autenticación cancelada."));
            state.googleAuthPending = null;
            state.googleAuthPromise = null;
        }
    });
    
    // G2. Respaldo manual si GIS no renderiza botón
    document.getElementById("google-signin-btn").addEventListener("click", () => {
        ensureGoogleAuthenticated({ showModal: true, showAlert: true })
            .then(() => {
                if (state.pendingTier) {
                    openPaymentModal(state.pendingTier);
                    state.pendingTier = null;
                }
            })
            .catch((err) => logger("Google sign-in cancelado o fallido:", err));
    });
    
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
            const response = await fetch(
                `/api/analizar/buscar-direccion?direccion=${encodeURIComponent(query)}`,
                { method: "GET" }
            );
            
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
                const detail = await parseApiErrorMessage(response);
                logger("Error al buscar dirección:", detail);
                searchResults.innerHTML =
                    '<p style="cursor: default; text-align: center; color: var(--text-secondary);">No se pudo buscar. Intenta de nuevo.</p>';
                searchResults.classList.remove("hidden");
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
        const response = await fetch(`/api/analizar/geocodificar?lat=${lat}&lng=${lng}`, {
            method: "GET",
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

// --- CABECERAS DE AUTENTICACIÓN (Google ID token o mock de pruebas) ---
function getAuthHeaders() {
    const headers = {};
    if (state.googleAuthEnabled) {
        if (googleSessionValid()) {
            headers.Authorization = `Bearer ${state.googleUser.token}`;
        }
        return headers;
    }
    if (state.googleUser?.token && !isGoogleTokenExpired(state.googleUser.token)) {
        headers.Authorization = `Bearer ${state.googleUser.token}`;
        return headers;
    }
    const token = state.currentUserRole === "admin" ? "mock-jwt-admin" : "mock-jwt-user";
    headers.Authorization = `Bearer ${token}`;
    return headers;
}

async function fetchWithGoogleAuth(url, options = {}) {
    const mergeHeaders = () => ({
        ...getAuthHeaders(),
        ...(options.headers || {}),
    });

    let response = await fetch(url, { ...options, headers: mergeHeaders() });

    const shouldSkipAuthModal =
        options.skipAuthModal || state.postPaymentFlow;

    if (
        state.googleAuthEnabled &&
        (response.status === 401 || response.status === 403) &&
        !shouldSkipAuthModal
    ) {
        const hadValidSession = googleSessionValid();
        if (!hadValidSession || response.status === 401) {
            try {
                clearGoogleSession();
                await ensureGoogleAuthenticated({ showModal: true, forceRefresh: true });
                response = await fetch(url, { ...options, headers: mergeHeaders() });
            } catch (authErr) {
                logger("Reautenticación Google fallida:", authErr);
            }
        }
    }

    return response;
}

async function parseHttpErrorMessage(response, fallback) {
    try {
        const data = await response.json();
        if (typeof data?.detail === "string") return data.detail;
    } catch (_err) {
        // sin JSON
    }
    return fallback;
}

function getJsonAuthHeaders() {
    const headers = getAuthHeaders();
    headers["Content-Type"] = "application/json";
    return headers;
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
        renderHeatmapSummaryTable(afluencia);
        logger("Mapa de calor visible: tier pagado y telemetría BestTime disponible.");
    } else {
        section.classList.add("hidden");
        if (grid) grid.innerHTML = "";
        if (legend) legend.style.display = "none";
        const summaryWrap = document.getElementById("heatmap-summary-wrap");
        const refEl = document.getElementById("heatmap-establecimiento-ref");
        const notaEl = document.getElementById("heatmap-nota-establecimiento");
        if (summaryWrap) summaryWrap.classList.add("hidden");
        if (refEl) refEl.classList.add("hidden");
        if (notaEl) notaEl.classList.add("hidden");
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
            descEl.textContent = "Indicador del poder adquisitivo promedio en la zona. Desbloquéalo al comprar cualquier reporte (Básico, Pro o Premium).";
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

    const aliadosPayload = collectAliadosPayload();
    if (aliadosPayload.invalid) {
        setGuiadoError("Completa el cuestionario guiado: perfil, horarios y al menos 2 tipos de lugares.");
        return;
    }

    const btn = document.getElementById("analyze-btn");
    const progressId = "analyze-progress-container";
    setButtonLoading(btn, true, "ANALIZANDO ZONA...");
    startInlineProgress(progressId, {
        messages: [
            "Autenticando con Google...",
            "Consultando datos demográficos (INEGI)...",
            "Mapeando competencia en la zona...",
            "Calculando score de viabilidad...",
        ],
    });

    try {
        await ensureGoogleAuthenticated({ showModal: true, analyzeFlow: true });

        document.getElementById("results-dashboard").classList.remove("hidden");
        setKpisLoading(true);

        document.getElementById("tier-badge").textContent = "VISTA PREVIA GRATUITA";
        document.getElementById("tier-badge").className = "badge";
        document.getElementById("dashboard-subtitle").textContent = "Estás viendo información real del INEGI y conteos de competencia en la zona de estudio.";

        const kpiCard = document.getElementById("kpi-sva-card");
        if (kpiCard) kpiCard.style.borderLeft = "4px solid var(--text-secondary)";

        lockAdvancedFeatures();
        clearMapPins();

        const headers = getAuthHeaders();
        headers["Content-Type"] = "application/json";
        const queryParams = `lat=${state.selectedLat}&lng=${state.selectedLng}&radio_metros=${state.selectedRadio}&rubro=${encodeURIComponent(state.selectedGiro)}`;

        const compCheckboxes = document.querySelectorAll("#competidores-checkboxes input[type='checkbox']:checked");
        const competidoresSel = Array.from(compCheckboxes).map(cb => cb.value);

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

        const response = await fetchWithGoogleAuth(`/api/analizar/previa?${queryParams}`, {
            method: "POST",
            headers,
            body: JSON.stringify(previewBody),
        });

        if (response.ok) {
            const data = await response.json();
            logger("Datos de vista previa recibidos del backend:", data);

            document.getElementById("kpi-sva").textContent = `${data.score_viabilidad_sva}/100`;
            document.getElementById("kpi-poblacion").textContent = data.poblacion_estimada.toLocaleString();
            document.getElementById("kpi-competidores").textContent = data.competidores_conteo;
            setKpisLoading(false);

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

            if (kpiCard) {
                if (sva >= 80) {
                    kpiCard.style.borderLeft = "4px solid var(--success-color)";
                } else if (sva >= 50) {
                    kpiCard.style.borderLeft = "4px solid var(--warning-color)";
                } else {
                    kpiCard.style.borderLeft = "4px solid var(--danger-color)";
                }
            }

            renderCompetitorsChart(data.competidores_listado);
            renderTopCompetitorsTable(data);
            renderCompetitorReviews(data);
            renderAliadosDetalleTable(data, "gratuito");
            renderPOITable(data);
            syncHeatmapSection("gratuito", data.afluencia_peatonal);
            applyBlurRules("gratuito");

            finishInlineProgress(progressId, "Vista previa lista.");
            setTimeout(() => resetInlineProgress(progressId), 1200);

            document.getElementById("results-dashboard").scrollIntoView({ behavior: "smooth" });
        } else {
            setKpisLoading(false);
            resetInlineProgress(progressId);
            logger("Error al calcular la vista previa gratuita en el servidor.", response.status);
            if (response.status === 401) {
                alert("Tu sesión de Google expiró o no es válida. Vuelve a iniciar sesión e intenta analizar de nuevo.");
            } else {
                const detail = await parseApiErrorMessage(response);
                alert(`No se pudo completar la vista previa: ${detail}`);
            }
        }

    } catch (err) {
        setKpisLoading(false);
        resetInlineProgress(progressId);
        logger("Error en la vista previa:", err);
        if (err?.message?.includes("Google") || err?.message?.includes("sesión")) {
            alert(err.message);
        } else {
            alert("Error de red al analizar la ubicación. Verifica tu conexión e intenta de nuevo.");
        }
    } finally {
        restoreAnalyzeButton(btn);
    }
}

// --- LIMPIAR PINS DE COMPETIDORES Y POIs ---
function clearMapPins() {
    if (!state.map) return;
    state.competitorMarkers.forEach(m => state.map.removeLayer(m));
    state.competitorMarkers = [];
    state.poiMarkers.forEach(m => state.map.removeLayer(m));
    state.poiMarkers = [];
}

// --- BLOQUEAR CAMPOS DEL TIER GRATUITO ---
function unlockAdvancedFeaturesForTier(tier) {
    if (!tier || tier === "gratuito") return;

    document.getElementById("sva-composition-card")?.classList.remove("hidden");

    if (tier === "pro" || tier === "premium") {
        document.getElementById("lectura-estrategica-section")?.classList.remove("hidden");
        document.getElementById("competitor-reviews-block")?.classList.remove("hidden");
        document.getElementById("competitor-top-table-wrap")?.classList.remove("hidden");
    }
}

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

function collectAliadosPayloadForTier(tier) {
    if (tier !== "premium" && isAliadosGuiadoActivo()) {
        const aliadosCheckboxes = document.querySelectorAll("#aliados-checkboxes input[type='checkbox']:checked");
        const aliadosSel = Array.from(aliadosCheckboxes).map(cb => cb.value);
        return {
            modo_analisis_aliados: "automatico",
            config_aliados_guiados: null,
            aliados_seleccionados: aliadosSel.length > 0 ? aliadosSel : null,
        };
    }
    return collectAliadosPayload();
}

function sliceSelection(arr, max) {
    return Array.isArray(arr) && arr.length > 0 ? arr.slice(0, max) : null;
}

function formatPremiumAliadosResumen(aliadosSeleccionados, aliadosAdicionales, aliadosPayload, categoryMap) {
    if (aliadosPayload.modo_analisis_aliados === "guiado") {
        const tipos = aliadosPayload.config_aliados_guiados?.atractores_confirmados
            || aliadosPayload.aliados_seleccionados
            || [];
        return tipos
            .map((a) => {
                const sug = (state.aliadosGuiadoSugerencias || []).find((s) => s.tipo === a);
                return sug?.etiqueta || categoryMap[a] || a;
            })
            .join(", ");
    }
    if (Array.isArray(aliadosSeleccionados) && aliadosSeleccionados.length > 0) {
        const base = aliadosSeleccionados
            .map((a) => {
                if (a === "ia_auto") return categoryMap.ia_auto_aliado;
                return categoryMap[a] || a;
            })
            .join(", ");
        return aliadosAdicionales ? `${base} (+ "${aliadosAdicionales}")` : base;
    }
    if (aliadosAdicionales) {
        return `Franquicias o marcas específicas: ${aliadosAdicionales}`;
    }
    return "Bancos, Escuelas y Transporte por defecto";
}

async function parseApiErrorMessage(response) {
    try {
        const data = await response.json();
        if (Array.isArray(data?.detail)) {
            return data.detail
                .map((item) => item?.msg || JSON.stringify(item))
                .join(" ");
        }
        if (typeof data?.detail === "string") {
            return data.detail;
        }
        if (data?.friendly_message) {
            return data.friendly_message;
        }
    } catch (_err) {
        // Sin cuerpo JSON legible
    }
    return `Error del servidor (${response.status}).`;
}

// --- ABRIR MODAL DE PASARELA DE PAGOS ---
async function openPaymentModal(tier) {
    if (state.checkoutLaunchInProgress) {
        logger("Ya hay un checkout en curso.");
        return;
    }
    state.activeTier = tier;

    const rubro = getRubroActual();
    if (!rubro) {
        alert("Selecciona el giro o rubro de tu negocio antes de comprar un reporte.");
        return;
    }
    if (state.selectedLat === null || state.selectedLng === null) {
        alert("Ubica un punto en el mapa antes de comprar un reporte.");
        return;
    }

    logger(`Solicitando orden de cobro para Tier: ${tier.toUpperCase()}`);

    await ensurePaymentsConfig();
    if (!state.paymentsConfigLoaded) {
        alert("No pudimos verificar el sistema de pagos. Recarga la página e intenta de nuevo.");
        return;
    }

    const billingTitle = document.getElementById("billing-title");
    const billingPrice = document.getElementById("billing-price");
    const tierConfig = TIER_PRICING[tier];

    if (tierConfig && billingTitle && billingPrice) {
        billingTitle.textContent = tierConfig.title;
        billingPrice.textContent = formatTierPrice(tier);
    }

    document.getElementById("compilation-progress-container")?.classList.add("hidden");
    document.getElementById("confirm-payment-btn")?.removeAttribute("disabled");

    try {
        const headers = getJsonAuthHeaders();

        const compCheckboxes = document.querySelectorAll("#competidores-checkboxes input[type='checkbox']:checked");
        let competidores_seleccionados = Array.from(compCheckboxes).map(cb => cb.value);

        const aliadosPayload = collectAliadosPayloadForTier(tier);
        if (aliadosPayload.invalid) {
            alert("Completa el cuestionario guiado de aliados: perfil, horarios y al menos 2 tipos de lugares.");
            return;
        }
        let aliados_seleccionados = aliadosPayload.aliados_seleccionados;

        const compAdicionales = document.getElementById("competidores-adicionales-input")?.value?.trim() || "";
        const aliadosAdicionales = document.getElementById("aliados-adicionales-input")?.value?.trim() || "";

        const categoryMap = {
            "ia_auto": "Detectar competidores con base en el giro/rubro del negocio",
            "ia_auto_aliado": "Detectar aliados de manera automática",
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
            competidores_seleccionados = sliceSelection(competidores_seleccionados, 1);
            aliados_seleccionados = null;
        } else if (tier === "pro") {
            competidores_seleccionados = sliceSelection(competidores_seleccionados, 3);
            aliados_seleccionados = null;
        } else if (tier === "premium") {
            competidores_seleccionados = sliceSelection(competidores_seleccionados, 5);
            if (aliadosPayload.modo_analisis_aliados === "guiado") {
                aliados_seleccionados = aliadosPayload.aliados_seleccionados || null;
            } else {
                aliados_seleccionados = sliceSelection(aliados_seleccionados, 5);
            }
        }

        // Configurar textos del resumen visual en el modal
        if (summaryContainer && summaryComps && summaryAllies) {
        if (tier === "basico") {
            summaryContainer.classList.remove("hidden");
            const compLabel = competidores_seleccionados ? categoryMap[competidores_seleccionados[0]] : "Giro principal (Cafetería por defecto)";
            let compText = `🏪 <b>Competidor a analizar:</b> ${compLabel}`;
            if (compAdicionales) {
                compText += ` (+ "${compAdicionales}")`;
            }
            summaryComps.innerHTML = compText;
            summaryAllies.innerHTML = `🌱 <b>Aliados incluidos:</b> Ninguno (no incluido en reporte Básico)`;
        } else if (tier === "pro") {
            summaryContainer.classList.remove("hidden");
            const compLabels = competidores_seleccionados ? competidores_seleccionados.map(c => categoryMap[c] || c).join(", ") : "Giro principal por defecto";
            let compText = `🏪 <b>Competidores a analizar (Máx 3):</b> ${compLabels}`;
            if (compAdicionales) {
                compText += ` (+ "${compAdicionales}")`;
            }
            summaryComps.innerHTML = compText;
            summaryAllies.innerHTML = `🌱 <b>Aliados incluidos:</b> Ninguno (no incluido en reporte Pro)`;
        } else if (tier === "premium") {
            summaryContainer.classList.remove("hidden");
            const compLabels = competidores_seleccionados
                ? competidores_seleccionados.map(c => categoryMap[c] || c).join(", ")
                : "Giro principal por defecto";
            const allyLabels = formatPremiumAliadosResumen(
                aliados_seleccionados,
                aliadosAdicionales,
                aliadosPayload,
                categoryMap
            );
            let compText = `🏪 <b>Competidores a analizar (Máx 5):</b> ${compLabels}`;
            if (compAdicionales) {
                compText += ` (+ "${compAdicionales}")`;
            }
            const allyText = aliadosPayload.modo_analisis_aliados === "guiado"
                ? `🧭 <b>Aliados (modo guiado):</b> ${allyLabels}`
                : `🌱 <b>Aliados a analizar:</b> ${allyLabels}`;
            summaryComps.innerHTML = compText;
            summaryAllies.innerHTML = allyText;
        } else {
            summaryContainer.classList.add("hidden");
        }
        }

        const payload = {
            tier_adquirido: tier,
            latitud: state.selectedLat,
            longitud: state.selectedLng,
            radio_metros: state.selectedRadio,
            rubro,
            intenciones: document.getElementById("intenciones-textarea")?.value?.trim() || null,
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
            body: JSON.stringify(payload),
        });

        if (response.ok) {
            const data = await response.json();
            state.activeOrderId = data.orden_id;
            state.activeCheckoutId = data.checkout_id;
            logger(`Orden registrada. Orden ID: ${data.orden_id} | Checkout: ${data.checkout_id}`);

            if (!state.paymentsMock) {
                if (!data.init_point) {
                    alert("Mercado Pago no devolvió un enlace de pago. Intenta de nuevo.");
                    return;
                }
                if (state.mercadoPagoSandbox) {
                    const returnNote = state.publicReturnUrlConfigured
                        ? "\n\n• Tras aprobar el pago, Mercado Pago te regresará automáticamente a GeoViabilidad."
                        : "\n\n• Configura PUBLIC_APP_URL con tu URL ngrok HTTPS para retorno automático tras el pago.";
                    const proceed = confirm(
                        "Pago de PRUEBA (Mercado Pago sandbox — México):\n\n" +
                        "1. Usa la URL ngrok (no localhost) para comprar reportes.\n" +
                        "2. En Mercado Pago elige **Tarjeta de crédito o débito** (no «Dinero en cuenta»).\n" +
                        "3. Puedes pagar como invitado (sin iniciar sesión en Mercado Pago).\n" +
                        "4. NO uses tarjetas guardadas → «Pagar con otro medio» → tarjeta NUEVA.\n" +
                        "5. Datos de la tarjeta nueva:\n" +
                        "   • Número: 5474 9254 3267 0366\n" +
                        "   • CVV: 123  |  Vence: 11/30\n" +
                        "   • Titular: APRO  (obligatorio)\n" +
                        "6. Tras pulsar Continuar, si pide documento del titular:\n" +
                        "   • Tipo: IFE (o INE)  |  Número: aaaaaa11111111a111" +
                        returnNote +
                        "\n\n¿Continuar al checkout de Mercado Pago?"
                    );
                    if (!proceed) return;
                }
                launchMercadoPagoCheckout(data.init_point, data.orden_id, tier);
                return;
            }

            document.getElementById("payment-modal")?.classList.remove("hidden");
        } else {
            const detail = await parseApiErrorMessage(response);
            logger("Falla al crear preferencia:", detail);
            alert(`No se pudo registrar la orden de cobro: ${detail}`);
        }
    } catch (err) {
        logger("Falla al abrir modal de pago:", err);
        alert(`No se pudo iniciar el flujo de pago. ${err?.message || "Revisa tu conexión e intenta de nuevo."}`);
    }
}

// --- CERRAR MODAL ---
function closePaymentModal() {
    document.getElementById("payment-modal").classList.add("hidden");
}

// --- PROCESAR PAGO SIMULADO (WEBHOOK MOCK & POLLING) ---
async function processSimulatedPayment() {
    await ensurePaymentsConfig();
    if (!state.paymentsMock) {
        alert(
            "El pago se completa en Mercado Pago. Cierra este cuadro y vuelve a hacer clic en comprar el reporte."
        );
        closePaymentModal();
        return;
    }

    const activeOption = document.querySelector(".pay-option-btn.active");
    const paymentStatus = activeOption.getAttribute("data-status");
    
    logger(`Confirmando pago simulado. Estatus elegido: ${paymentStatus.toUpperCase()}`);
    
    // 1. Bloquear controles del modal
    document.getElementById("confirm-payment-btn").setAttribute("disabled", "true");
    const progressContainer = document.getElementById("compilation-progress-container");
    const progressFill = document.getElementById("progress-bar-fill");
    const statusText = document.getElementById("compilation-status-text");
    
    progressContainer.classList.remove("hidden");
    statusText.textContent = "Acreditando pago simulado...";
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
            const detail = await parseApiErrorMessage(response);
            logger("Webhook mock rechazado:", detail);
            const hint =
                response.status === 403
                    ? "El modo simulado está desactivado. Vuelve a comprar: serás redirigido a Mercado Pago."
                    : detail;
            alert(`No se pudo confirmar el pago: ${hint}`);
            document.getElementById("confirm-payment-btn")?.removeAttribute("disabled");
            progressContainer?.classList.add("hidden");
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
    const tierLabel = (state.activeTier || "premium").toUpperCase();
    logger(`Desbloqueando resultados del reporte. Orden ID: ${state.activeOrderId} | Tier: ${tierLabel}`);

    if (!state.activeOrderId) {
        logger("unlockPaidReport abortado: sin orden activa.");
        return false;
    }

    if (state.googleAuthEnabled && !googleSessionValid()) {
        showPaidReportUnlockPrompt(
            "Inicia sesión con Google para ver tu reporte pagado."
        );
        scrollToPostPaymentSection();
        return false;
    }

    ensureMapReady();

    try {
        const response = await fetchWithGoogleAuth(
            `/api/analizar/resultado/${state.activeOrderId}`,
            { method: "GET", skipAuthModal: true }
        );
        
        if (response.ok) {
            const data = await response.json();
            logger("Datos completos del reporte comercial recibidos:", data);

            if (!state.activeTier) {
                state.activeTier =
                    data.orden?.tier_adquirido ||
                    data.metricas?.tier_adquirido ||
                    "premium";
            }
            
            const metricas = data.metricas;
            const iaAnalisis = data.analisis_estrategico_ia;

            unlockAdvancedFeaturesForTier(state.activeTier);
            
            // 1. Actualizar Badge y cabecera
            const tierBadge = document.getElementById("tier-badge");
            tierBadge.textContent = `REPORTE ${state.activeTier.toUpperCase()}`;
            tierBadge.className = `badge ${state.activeTier}`;
            
            // Actualizar KPIs de la interfaz con los datos reales del reporte pagado
            document.getElementById("kpi-sva").textContent = `${metricas.sva ?? 0}/100`;
            document.getElementById("kpi-poblacion").textContent = (
                metricas.poblacion_ponderada ?? metricas.poblacion_estimada ?? 0
            ).toLocaleString();
            document.getElementById("kpi-competidores").textContent =
                metricas.competidores_conteo ?? 0;

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
            preparePdfDownloadButton();
            
            // Pintar pines de competidores y aliados en el mapa (solo si Pro o Premium para el mapa físico)
            if (state.activeTier === "pro" || state.activeTier === "premium") {
                renderCompetitorPins(
                    metricas.competidores_listado,
                    metricas.aliados_destacados || metricas.aliados_listado
                );
            } else {
                clearMapPins();
            }
            
            // Generar Gráficos Avanzados siempre (el blur controla su visualización)
            renderCompetitorsChart(metricas.competidores_listado);
            renderTopCompetitorsTable(metricas);
            renderCompetitorReviews(metricas);
            renderAliadosDetalleTable(metricas, state.activeTier);
            renderPOITable(metricas);
            syncHeatmapSection(state.activeTier, metricas.afluencia_peatonal);

            // Aplicar las reglas de blur según el Tier activo
            applyBlurRules(state.activeTier);
            
            document.getElementById("results-dashboard")?.classList.remove("hidden");
            document.getElementById("advanced-charts-section")?.scrollIntoView({ behavior: "smooth" });
            return true;
            
        } else if (response.status === 401 || response.status === 403) {
            const detail = await parseHttpErrorMessage(
                response,
                "Sesión inválida o sin permiso para este reporte."
            );
            logger("Acceso al reporte denegado:", detail);
            showPaidReportUnlockPrompt(
                `${detail} Usa la misma cuenta de Google con la que realizaste la compra.`
            );
            return false;
        } else {
            const detail = await parseApiErrorMessage(response);
            logger("Error al cargar reporte pagado:", detail);
            alert(`No pudimos recuperar los datos completos del reporte: ${detail}`);
            return false;
        }
    } catch (err) {
        logger("Falla al recuperar resultados pagados:", err);
        alert("Error de red al consultar el endpoint de resultados.");
        return false;
    }
}

// --- RENDERIZAR PINS DE LA COMPETENCIA Y POIs ---
function renderCompetitorPins(competidores, aliados) {
    if (!state.map) {
        logger("Mapa no listo; se omiten pins de competencia hasta que cargue.");
        return;
    }
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
const NOTA_ESTABLECIMIENTO_REFERENCIA =
    "La afluencia refleja el paso de personas en el establecimiento comercial de referencia " +
    "utilizado para la medición (BestTime), no necesariamente el tránsito peatonal general de la calle. " +
    "Las horas sin dato reportado (0 %) no se incluyen en el promedio nocturno.";

const LABEL_NOCHE_PROMEDIO = "Noche — promedio de horas con dato (20:00–23:00)";
const HORAS_NOCHE = [20, 21, 22, 23];

function _promedioRango(curva, inicio, fin) {
    const segmento = curva.slice(inicio, fin);
    if (!segmento.length) return 0;
    return Math.round(segmento.reduce((a, b) => a + b, 0) / segmento.length);
}

function _formatoIntensidad(valor) {
    return valor > 0 ? `${valor}%` : "Sin dato";
}

function calcularDesgloseNoche(curva) {
    const porHora = {};
    HORAS_NOCHE.forEach((h) => {
        porHora[h] = curva[h] !== undefined ? Number(curva[h]) : 0;
    });
    const conDato = HORAS_NOCHE.map((h) => porHora[h]).filter((v) => v > 0);
    const promedioConDato = conDato.length
        ? Math.round(conDato.reduce((a, b) => a + b, 0) / conDato.length)
        : 0;
    return { porHora, promedioConDato, horasConDato: conDato.length };
}

function construirFilasTablaAfluencia(curva) {
    if (!Array.isArray(curva) || curva.length < 24) return [];

    const filas = [
        { rango: "Mañana (08:00 - 12:00)", intensidad: `${_promedioRango(curva, 8, 12)}%`, tipo: "bloque" },
        { rango: "Mediodía (12:00 - 16:00)", intensidad: `${_promedioRango(curva, 12, 16)}%`, tipo: "bloque" },
        { rango: "Tarde (16:00 - 20:00)", intensidad: `${_promedioRango(curva, 16, 20)}%`, tipo: "bloque" },
        { rango: "Desglose nocturno (competidor de referencia)", intensidad: "", tipo: "section" },
    ];

    const noche = calcularDesgloseNoche(curva);
    HORAS_NOCHE.forEach((h) => {
        filas.push({
            rango: `${String(h).padStart(2, "0")}:00`,
            intensidad: _formatoIntensidad(noche.porHora[h]),
            tipo: "sub",
        });
    });
    filas.push({
        rango: LABEL_NOCHE_PROMEDIO,
        intensidad: noche.horasConDato > 0 ? `${noche.promedioConDato}%` : "Sin dato",
        tipo: "bloque",
    });
    return filas;
}

function textoEstablecimientoReferencia(nombre) {
    if (nombre) {
        return `Competidor de referencia para la medición: ${nombre}.`;
    }
    return "Medición basada en el competidor identificado en la zona con telemetría BestTime disponible.";
}

function renderHeatmapSummaryTable(afluencia) {
    const wrap = document.getElementById("heatmap-summary-wrap");
    const tbody = document.getElementById("heatmap-summary-body");
    const refEl = document.getElementById("heatmap-establecimiento-ref");
    const notaEl = document.getElementById("heatmap-nota-establecimiento");
    if (!wrap || !tbody) return;

    const curva = afluencia?.afluencia_horaria;
    const filas = construirFilasTablaAfluencia(curva);
    if (!filas.length) {
        wrap.classList.add("hidden");
        if (refEl) refEl.classList.add("hidden");
        if (notaEl) notaEl.classList.add("hidden");
        return;
    }

    if (refEl) {
        refEl.textContent = textoEstablecimientoReferencia(afluencia?.venue_name);
        refEl.classList.remove("hidden");
    }
    if (notaEl) {
        notaEl.textContent = NOTA_ESTABLECIMIENTO_REFERENCIA;
        notaEl.classList.remove("hidden");
    }

    tbody.innerHTML = filas
        .map(({ rango, intensidad, tipo }) => {
            const rowClass =
                tipo === "section" ? "section-row" : tipo === "sub" ? "sub-row" : "";
            const cellClass = intensidad === "Sin dato" ? "sin-dato" : "";
            return `<tr class="${rowClass}"><td>${_escapeHtml(rango)}</td><td class="${cellClass}">${_escapeHtml(intensidad)}</td></tr>`;
        })
        .join("");
    wrap.classList.remove("hidden");
}

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

const VIGENCIA_DISCLAIMER =
    "La vigencia operativa se infiere de Google Maps (estado del negocio y fecha de reseñas recientes). " +
    "Un alto rating histórico no garantiza que el local siga abierto; valida en sitio antes de invertir.";

function _vigenciaBadgeClass(nivel) {
    const map = {
        alta: "vigencia-alta",
        media: "vigencia-media",
        baja: "vigencia-baja",
        inactivo: "vigencia-inactivo",
        sin_verificar: "vigencia-sin_verificar",
    };
    return map[nivel] || "vigencia-sin_verificar";
}

function _renderVigenciaCell(item) {
    const vig = item?.vigencia || {};
    const etiqueta = vig.etiqueta || "Sin verificar";
    const lectura = vig.lectura || "";
    const badge = `<span class="badge ${_vigenciaBadgeClass(vig.nivel)}">${_escapeHtml(etiqueta)}</span>`;
    const nota = lectura ? `<span class="vigencia-lectura">${_escapeHtml(lectura)}</span>` : "";
    return `${badge}${nota}`;
}

function _setVigenciaDisclaimers(metricas) {
    const compDisc = document.getElementById("competitor-vigencia-disclaimer");
    if (compDisc) {
        const total = metricas.competidores_conteo ?? (metricas.competidores_listado || []).length;
        const activos = metricas.competidores_activos_conteo ?? total;
        compDisc.textContent =
            `${VIGENCIA_DISCLAIMER} Detectados: ${total}; activos según Google: ${activos}.`;
    }
    const allyDisc = document.getElementById("aliados-vigencia-disclaimer");
    if (allyDisc) {
        allyDisc.textContent = VIGENCIA_DISCLAIMER;
    }
}

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
            <td>${_renderVigenciaCell(comp)}</td>
            <td>${_escapeHtml(_formatDistanceMeters(comp.distancia_metros) || "—")}</td>
        </tr>
    `).join("");
    _setVigenciaDisclaimers(metricas);
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

function renderAliadosDetalleTable(metricas, tier = "gratuito") {
    const card = document.getElementById("aliados-detalle-card");
    const tbody = document.getElementById("aliados-detalle-body");
    if (!card || !tbody) return;

    if (tier !== "premium") {
        card.classList.add("hidden");
        tbody.innerHTML = "";
        return;
    }

    const aliados = metricas.aliados_destacados || metricas.aliados_listado || [];
    const seleccion = metricas.atractores_seleccion || {};
    if (aliados.length === 0) {
        card.classList.add("hidden");
        tbody.innerHTML = "";
        return;
    }

    const hint = document.getElementById("aliados-detalle-hint");
    if (hint && seleccion.regla) {
        hint.textContent = seleccion.regla;
        hint.classList.remove("hidden");
    } else if (hint) {
        hint.classList.add("hidden");
    }

    tbody.innerHTML = aliados.map(aliado => `
        <tr>
            <td>${_escapeHtml(aliado.nombre || "Establecimiento")}</td>
            <td>${_escapeHtml(aliado.tipo || "—")}</td>
            <td>${aliado.rating > 0 ? `⭐ ${Number(aliado.rating).toFixed(1)} (${Number(aliado.user_ratings_total || 0).toLocaleString()})` : "Sin calificación"}</td>
            <td>${_formatDistanceMeters(aliado.distancia_metros) || "—"}</td>
            <td>${_renderVigenciaCell(aliado)}</td>
        </tr>
    `).join("");
    _setVigenciaDisclaimers(metricas);
    card.classList.remove("hidden");
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

async function savePdfFromUrl(downloadUrl, fallbackFilename = "Reporte_Viabilidad.pdf") {
    // Rutas relativas → origen actual (HTTPS ngrok). URLs absolutas del mismo host
    // se reescriben al origen de la página para evitar Mixed Content (API detrás de proxy HTTP).
    let absoluteUrl;
    if (downloadUrl.startsWith("http://") || downloadUrl.startsWith("https://")) {
        try {
            const parsed = new URL(downloadUrl);
            const page = new URL(window.location.origin);
            absoluteUrl =
                parsed.hostname === page.hostname
                    ? `${page.origin}${parsed.pathname}${parsed.search}`
                    : downloadUrl;
        } catch {
            absoluteUrl = downloadUrl;
        }
    } else {
        absoluteUrl = `${window.location.origin}${downloadUrl.startsWith("/") ? downloadUrl : `/${downloadUrl}`}`;
    }

    const fileResponse = await fetch(absoluteUrl);
    if (!fileResponse.ok) {
        throw new Error(await parseApiErrorMessage(fileResponse));
    }

    let filename = fallbackFilename;
    const disposition = fileResponse.headers.get("Content-Disposition");
    if (disposition) {
        const match = /filename=\"?([^\";]+)/i.exec(disposition);
        if (match?.[1]) {
            filename = decodeURIComponent(match[1].replace(/\"/g, ""));
        }
    }

    const blob = await fileResponse.blob();
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename;
    link.rel = "noopener";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 1500);
}

// --- DESCARGA DE REPORTE PDF (GET /api/reportes/pdf/{orden_id}) ---
async function fetchPdfDownloadUrl(ordenId, { retries = 20, delayMs = 2000, onWaiting = null } = {}) {
    const headers = getAuthHeaders();
    let lastDetail = "No se pudo obtener el enlace de descarga.";

    for (let attempt = 1; attempt <= retries; attempt++) {
        const response = await fetch(`/api/reportes/pdf/${ordenId}`, {
            method: "GET",
            headers,
        });

        if (response.ok) {
            const data = await response.json();
            if (data?.url_descarga) {
                return data.url_descarga;
            }
            lastDetail = "El servidor no devolvió una URL de descarga válida.";
            break;
        }

        lastDetail = await parseApiErrorMessage(response);

        // 422 = PDF aún compilándose en segundo plano
        if (response.status === 422 && attempt < retries) {
            if (typeof onWaiting === "function") {
                onWaiting(attempt, retries, lastDetail);
            }
            await new Promise((resolve) => setTimeout(resolve, delayMs));
            continue;
        }

        throw new Error(lastDetail);
    }

    throw new Error(lastDetail || "El PDF aún se está compilando. Intenta de nuevo en unos segundos.");
}

function setPdfDownloadReadyUi(isReady, message) {
    const btn = document.getElementById("download-pdf-btn");
    const desc = document.getElementById("download-p-desc");
    if (desc && message) {
        desc.textContent = message;
    }
    if (!btn) return;
    btn.disabled = !isReady;
    btn.textContent = isReady
        ? "⬇️ DESCARGAR REPORTE EN PDF"
        : "⏳ PREPARANDO PDF...";
}

async function preparePdfDownloadButton() {
    if (!state.activeOrderId) return;

    setPdfDownloadReadyUi(
        false,
        "Estamos compilando tu reporte en PDF. Este paso puede tardar unos segundos."
    );

    try {
        await fetchPdfDownloadUrl(state.activeOrderId, {
            onWaiting: (_attempt, _max, detail) => {
                setPdfDownloadReadyUi(false, detail || "Compilando reporte PDF...");
            },
        });
        setPdfDownloadReadyUi(
            true,
            "Tu reporte está listo. Haz clic para descargar la versión en PDF."
        );
    } catch (err) {
        logger("PDF aún no disponible:", err);
        setPdfDownloadReadyUi(
            true,
            `${err?.message || "El PDF puede tardar un poco más."} Puedes intentar descargar con el botón.`
        );
    }
}

async function triggerPDFDownload() {
    if (!state.activeOrderId) {
        alert("No hay una orden activa asociada. Completa el pago del reporte primero.");
        return;
    }

    logger(`Solicitando descarga de PDF para Orden ID: ${state.activeOrderId}...`);

    const btn = document.getElementById("download-pdf-btn");
    const progressId = "download-progress-container";
    setButtonLoading(btn, true, "PREPARANDO DESCARGA...");
    startInlineProgress(progressId, {
        messages: [
            "Verificando acceso al reporte...",
            "Esperando compilación del PDF...",
            "Generando enlace seguro de descarga...",
            "Preparando archivo PDF...",
        ],
        maxWhileWaiting: 92,
    });

    try {
        const downloadUrl = await fetchPdfDownloadUrl(state.activeOrderId, {
            onWaiting: (attempt, max) => {
                const statusEl = document.querySelector(`#${progressId} [data-progress-status]`);
                if (statusEl) {
                    statusEl.textContent = `Compilando PDF (${attempt}/${max})...`;
                }
            },
        });

        logger(`URL de descarga resuelta. Descargando desde: ${downloadUrl}`);
        finishInlineProgress(progressId, "Descarga lista. Guardando archivo...");
        await savePdfFromUrl(downloadUrl, `Reporte_Viabilidad_${state.activeOrderId}.pdf`);
        finishInlineProgress(progressId, "PDF descargado correctamente.");
        setPdfDownloadReadyUi(true, "Tu reporte está listo. Haz clic para descargar la versión en PDF.");
    } catch (err) {
        resetInlineProgress(progressId);
        logger("Falla al descargar PDF:", err);
        alert(err?.message || "No se pudo descargar el PDF. Intenta de nuevo en unos segundos.");
    } finally {
        setButtonLoading(btn, false);
        setTimeout(() => resetInlineProgress(progressId), 1500);
    }
}

// --- INTERCEPCIÓN DE COMPRA Y AUTENTICACIÓN GOOGLE ---
function checkAuthAndBuy(tier) {
    if (!state.googleAuthenticated) {
        state.pendingTier = tier;
        ensureGoogleAuthenticated({ showModal: true, showAlert: true })
            .then(() => {
                state.pendingTier = null;
                openPaymentModal(tier);
            })
            .catch(() => logger(`Compra ${tier.toUpperCase()} cancelada: falta autenticación Google.`));
        return;
    }
    openPaymentModal(tier);
}

function ensureGoogleAuthenticated(options = {}) {
    const { forceRefresh = false } = options;
    if (!forceRefresh && googleSessionValid()) {
        return Promise.resolve();
    }
    if (forceRefresh || isGoogleTokenExpired(state.googleUser?.token)) {
        clearGoogleSession();
    }
    if (state.googleAuthPromise) {
        return state.googleAuthPromise;
    }

    if (!state.googleAuthEnabled) {
        state.googleAuthPromise = runGoogleSigninMock(options)
            .then(() => {
                state.googleAuthenticated = true;
                state.currentUserRole = "user";
                sessionStorage.setItem(GOOGLE_AUTH_STORAGE_KEY, "1");
            })
            .finally(() => {
                state.googleAuthPromise = null;
            });
        return state.googleAuthPromise;
    }

    state.googleAuthPromise = new Promise((resolve, reject) => {
        state.googleAuthPending = { resolve, reject, options };
        waitForGoogleGsi()
            .then(() => prepareGoogleSignInUi(options))
            .catch((err) => {
                reject(err);
            });
    }).finally(() => {
        state.googleAuthPromise = null;
        state.googleAuthPending = null;
    });

    return state.googleAuthPromise;
}

function runGoogleSigninMock(options = {}) {
    const { showModal = false, showAlert = false, analyzeFlow = false } = options;

    if (state.googleAuthenticated) {
        return Promise.resolve();
    }

    return new Promise((resolve) => {
        const modal = document.getElementById("google-login-modal");
        const signinBtn = document.getElementById("google-signin-btn");
        const progressContainer = document.getElementById("login-progress-container");
        const progressFill = document.getElementById("login-progress-bar-fill");
        const statusText = document.getElementById("login-status-text");
        const modalTitle = modal?.querySelector(".modal-header h3");
        const modalDesc = modal?.querySelector(".billing-desc");

        if (showModal && modal) {
            modal.classList.remove("hidden");
            if (analyzeFlow && modalTitle) {
                modalTitle.textContent = "🌐 Autenticando para analizar";
            }
            if (analyzeFlow && modalDesc) {
                modalDesc.textContent =
                    "Vinculamos tu cuenta de Google mientras preparamos el análisis de viabilidad de tu ubicación.";
            }
        }

        if (signinBtn) {
            signinBtn.classList.toggle("hidden", analyzeFlow);
            signinBtn.setAttribute("disabled", "true");
        }
        if (progressContainer) progressContainer.classList.remove("hidden");
        if (statusText) {
            statusText.textContent = analyzeFlow
                ? "Conectando con Google para iniciar el análisis..."
                : "Conectando con Google Accounts...";
        }
        if (progressFill) progressFill.style.width = "0%";

        let progress = 0;
        const interval = setInterval(() => {
            progress += 10;
            if (progressFill) progressFill.style.width = `${progress}%`;

            if (statusText) {
                if (progress === 30) {
                    statusText.textContent = "Autenticando sesión y validando credenciales...";
                } else if (progress === 60) {
                    statusText.textContent = "Verificando perfil de usuario...";
                } else if (progress === 90) {
                    statusText.textContent = analyzeFlow
                        ? "Listo. Continuando con el análisis de la zona..."
                        : "Generando accesos seguros...";
                }
            }

            if (progress >= 100) {
                clearInterval(interval);
                if (signinBtn) {
                    signinBtn.removeAttribute("disabled");
                    signinBtn.classList.remove("hidden");
                }
                if (progressContainer) progressContainer.classList.add("hidden");
                if (modal) modal.classList.add("hidden");
                if (modalTitle) modalTitle.textContent = "🌐 Continuar con Google";
                if (modalDesc) {
                    modalDesc.textContent =
                        "Necesitamos autenticarte con Google para guardar tu análisis y habilitar la compra del reporte.";
                }
                if (showAlert) {
                    alert("Autenticación con Google exitosa. Bienvenido, demo_google@geoviabilidad.com.");
                }
                logger("Autenticación Google completada.");
                resolve();
            }
        }, 150);
    });
}
