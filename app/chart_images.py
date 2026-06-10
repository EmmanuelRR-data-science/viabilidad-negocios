"""
Generación server-side de gráficas del dashboard para incrustar en el PDF.
Replica la lógica visual de frontend/app.js (Chart.js + heatmap térmico)
usando los mismos datos de analisis (Places, BestTime, INEGI).
"""

from __future__ import annotations

import io
import logging

logger = logging.getLogger("chart_images")

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    _CHARTS_DISPONIBLES = True
except ImportError:
    plt = None  # type: ignore[assignment]
    np = None  # type: ignore[assignment]
    _CHARTS_DISPONIBLES = False
    logger.warning("matplotlib no instalado: las gráficas del PDF se omitirán.")

# Paleta semántica idéntica al dashboard (app.js renderCompetitorsChart)
RATING_LABELS = ["< 3.0 o Sin Rating", "3.0 - 3.9", "4.0 - 4.4", "4.5 - 5.0"]
RATING_COLORS = ["#f43f5e", "#f97316", "#fbbf24", "#22c55e"]

DIAS_SEMANA = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
HORAS_HEATMAP = list(range(8, 23))  # 08:00 – 22:00, igual que el dashboard

CATEGORY_LABELS = {
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
    "park": "Parques",
}


def _fig_to_png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white", edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _clasificar_ratings(competidores: list) -> dict[str, int]:
    conteos = dict.fromkeys(RATING_LABELS, 0)
    for c in competidores:
        r = float(c.get("rating") or 0)
        if r >= 4.5:
            conteos["4.5 - 5.0"] += 1
        elif r >= 4.0:
            conteos["4.0 - 4.4"] += 1
        elif r >= 3.0:
            conteos["3.0 - 3.9"] += 1
        else:
            conteos["< 3.0 o Sin Rating"] += 1
    return conteos


def generar_grafica_competidores(competidores: list) -> bytes | None:
    """Barras de distribución por rating — equivalente a competitors-chart del dashboard."""
    if not _CHARTS_DISPONIBLES or not competidores:
        return None
    try:
        conteos = _clasificar_ratings(competidores)
        valores = [conteos[label] for label in RATING_LABELS]

        fig, ax = plt.subplots(figsize=(7.2, 3.4))
        ax.bar(
            RATING_LABELS,
            valores,
            color=RATING_COLORS,
            edgecolor=RATING_COLORS,
            linewidth=1.2,
            width=0.62,
            zorder=3,
        )
        ax.set_ylabel("Número de Comercios", fontsize=9, color="#64748b")
        ax.set_title(
            "Distribución de Competidores por Rating",
            fontsize=11,
            fontweight="bold",
            color="#0f172a",
            pad=10,
        )
        ax.tick_params(axis="x", labelsize=7.5, colors="#64748b")
        ax.tick_params(axis="y", labelsize=8, colors="#64748b")
        ax.set_ylim(0, max(valores) * 1.2 if max(valores) else 1)
        ax.grid(axis="y", linestyle="--", alpha=0.25, zorder=0)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        for bar, val in zip(ax.patches, valores, strict=True):
            if val > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.15,
                    str(val),
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    fontweight="bold",
                    color="#0f172a",
                )
        fig.tight_layout()
        return _fig_to_png(fig)
    except Exception as err:
        logger.error("Error generando gráfica de competidores: %s", err)
        return None


def generar_grafica_atractores(
    aliados_conteos: dict | None,
    *,
    bancos: int = 0,
    escuelas: int = 0,
    transporte: int = 0,
) -> bytes | None:
    """Barras horizontales de atractores — visualiza lo que el dashboard muestra como tabla POI."""
    conteos = {k: v for k, v in (aliados_conteos or {}).items() if k != "ia_auto" and v > 0}
    if not conteos and (bancos or escuelas or transporte):
        conteos = {
            "transit_station": transporte,
            "school": escuelas,
            "bank": bancos,
        }
        conteos = {k: v for k, v in conteos.items() if v > 0}
    if not _CHARTS_DISPONIBLES or not conteos:
        return None

    try:
        items = sorted(conteos.items(), key=lambda x: x[1], reverse=True)[:8]
        labels = [CATEGORY_LABELS.get(k, k.replace("_", " ").title()) for k, _ in items]
        valores = [v for _, v in items]

        fig, ax = plt.subplots(figsize=(7.2, max(2.8, len(items) * 0.45 + 1.2)))
        y_pos = np.arange(len(labels))
        ax.barh(y_pos, valores, color="#2563eb", alpha=0.85, height=0.55, zorder=3)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=8.5)
        ax.set_xlabel("Establecimientos detectados en el radio", fontsize=9, color="#64748b")
        ax.set_title(
            "Atractores de Tráfico por Categoría",
            fontsize=11,
            fontweight="bold",
            color="#0f172a",
            pad=10,
        )
        ax.tick_params(axis="x", labelsize=8, colors="#64748b")
        ax.grid(axis="x", linestyle="--", alpha=0.25, zorder=0)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        for i, val in enumerate(valores):
            ax.text(val + 0.3, i, str(val), va="center", fontsize=8, fontweight="bold", color="#0f172a")
        fig.tight_layout()
        return _fig_to_png(fig)
    except Exception as err:
        logger.error("Error generando gráfica de atractores: %s", err)
        return None


def _color_celda_heatmap(val: float) -> tuple[float, float, float, float]:
    """Replica heatColor() de frontend/app.js: dorado → rojo según intensidad."""
    intensity = max(0.0, min(100.0, val)) / 100.0
    if intensity == 0:
        return (0.58, 0.64, 0.72, 0.08)
    hue = (45.0 - intensity * 45.0) / 360.0
    sat = 0.95
    light = 0.55
    alpha = 0.18 + intensity * 0.82
    import colorsys

    r, g, b = colorsys.hls_to_rgb(hue, light, sat)
    return (r, g, b, alpha)


def generar_heatmap_afluencia(afl_data: dict) -> bytes | None:
    """Mapa de calor día × hora — equivalente al heatmap-grid del dashboard."""
    if not _CHARTS_DISPONIBLES or afl_data.get("status") != "success" or not afl_data.get("afluencia_semanal"):
        return None
    try:
        semanal = afl_data["afluencia_semanal"]
        matriz = []
        for dia in DIAS_SEMANA:
            curva = semanal.get(dia, [0] * 24)
            fila = [float(curva[h]) if h < len(curva) else 0.0 for h in HORAS_HEATMAP]
            matriz.append(fila)
        data = np.array(matriz)

        fig, ax = plt.subplots(figsize=(9.5, 3.8))
        rgba_grid = np.zeros((len(DIAS_SEMANA), len(HORAS_HEATMAP), 4))
        for i in range(len(DIAS_SEMANA)):
            for j in range(len(HORAS_HEATMAP)):
                rgba_grid[i, j] = _color_celda_heatmap(data[i, j])

        ax.imshow(rgba_grid, aspect="auto", origin="upper")
        ax.set_xticks(range(len(HORAS_HEATMAP)))
        ax.set_xticklabels([f"{h:02d}:00" for h in HORAS_HEATMAP], fontsize=7, rotation=45, ha="right")
        ax.set_yticks(range(len(DIAS_SEMANA)))
        ax.set_yticklabels(DIAS_SEMANA, fontsize=8)
        ax.set_title(
            "Mapa de Calor — Afluencia Peatonal por Día y Hora",
            fontsize=11,
            fontweight="bold",
            color="#0f172a",
            pad=10,
        )

        for i in range(len(DIAS_SEMANA)):
            for j in range(len(HORAS_HEATMAP)):
                val = int(data[i, j])
                if val > 0:
                    txt_color = "white" if val >= 60 else "#0f172a"
                    ax.text(j, i, f"{val}%", ha="center", va="center", fontsize=6, color=txt_color)

        # Leyenda térmica
        gradient = np.linspace(0, 100, 256).reshape(1, -1)
        cax = fig.add_axes([0.72, 0.02, 0.22, 0.03])
        from matplotlib.colors import LinearSegmentedColormap

        cmap = LinearSegmentedColormap.from_list("fire", ["#fbbf24", "#f97316", "#ef4444"])
        cax.imshow(gradient, aspect="auto", cmap=cmap)
        cax.set_yticks([])
        cax.set_xticks([0, 128, 255])
        cax.set_xticklabels(["Baja", "Media", "Alta"], fontsize=7)
        cax.set_xlabel("Intensidad peatonal", fontsize=7, color="#64748b")

        fig.tight_layout(rect=[0, 0.06, 1, 1])
        return _fig_to_png(fig)
    except Exception as err:
        logger.error("Error generando heatmap de afluencia: %s", err)
        return None
