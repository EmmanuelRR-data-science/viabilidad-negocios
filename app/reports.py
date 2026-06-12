import datetime
import io
import logging
import math
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

logger = logging.getLogger("reports")

# Nombres legibles (con acentos) de los rubros del catálogo para textos del reporte
RUBRO_DISPLAY = {
    "cafeteria": "Cafetería",
    "restaurante_carta": "Restaurante a la Carta",
    "comida_rapida": "Comida Rápida",
    "gimnasio": "Gimnasio",
    "abarrotes": "Tienda de Abarrotes",
    "farmacia": "Farmacia",
    "estetica": "Estética / Salón de Belleza",
    "lavanderia": "Lavandería",
    "consultorio_medico": "Consultorio Médico",
    "escuela": "Escuela Privada",
}


def rubro_legible(rubro: str) -> str:
    """Devuelve el nombre legible del rubro; para giros libres conserva el texto del usuario."""
    if not rubro:
        return "Negocio"
    return RUBRO_DISPLAY.get(rubro.lower().strip(), rubro.replace("_", " ").strip().capitalize())


_TEXTOS_FODA_GENERICOS_OMITIR = frozenset(
    {
        "Análisis de viabilidad concluido con éxito.",
        "Población y segmento comercial cautivo detectados en el radio.",
        "Posicionamiento de precios acorde a la competencia y densidad demográfica local.",
        "Demanda residencial en el radio analizado.",
        "Espacio para diferenciación en el giro.",
        "Validar permisos, renta y operación con cifras reales.",
        "Monitorear retornos de inversión.",
    }
)


def _texto_si_es_real(valor: str | None) -> str | None:
    if not valor or not str(valor).strip():
        return None
    texto = str(valor).strip()
    if texto in _TEXTOS_FODA_GENERICOS_OMITIR:
        return None
    return texto


def _bullets_reales(items: list, *, max_items: int = 3) -> str | None:
    lista = [str(x).strip() for x in (items or []) if str(x).strip()][:max_items]
    return "<br/>".join(f"• {x}" for x in lista) if lista else None


def _tipo_comercial_legible(tipo: str | None, rubro: str) -> str:
    from app.aliados_deterministico import nombre_categoria_places

    if not tipo:
        return rubro_legible(rubro)
    clave = str(tipo).lower().replace(" ", "_").strip()
    return nombre_categoria_places(clave)


def _pct_poblacion(valor: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((valor / total) * 100, 1)


def _texto_entrada_demografica(dem: dict) -> str:
    if dem.get("log_densidad") is not None:
        return (
            f"{dem['poblacion']:,} hab. en radio {dem['radio_metros']:,} m "
            f"(area {dem['area_km2']:.2f} km2) -> {dem['densidad_hab_km2']:,.1f} hab/km2 "
            f"(log10 = {dem['log_densidad']:.4f})"
        )
    return (
        f"{dem['poblacion']:,} hab. en radio {dem['radio_metros']:,} m "
        f"-> {dem['densidad_hab_km2']:,.1f} hab/km2"
    )


def _texto_entrada_competencia(comp: dict) -> str:
    isc = float(comp["isc"])
    factor = comp.get("factor_log_isc")
    n = comp["competidores_conteo"]
    isc_txt = f"{isc:.6f}"
    if factor is not None:
        return f"{n} competidores -> ISC {isc_txt} -> log10(ISC) = {factor:.4f}"
    return f"{n} competidores → ISC {isc_txt}"


def _agregar_seccion_transparencia_sva(
    story,
    analisis: dict,
    *,
    tier: str,
    radio_metros: int,
    s_h2,
    s_body,
    s_table_header,
    s_table_cell,
) -> None:
    """Tablas paso a paso + mini simulador para la sección ¿Por qué este Score de Viabilidad?"""
    from app.sva_calculo import GLOSARIO_SVA_PDF, desglose_sva_completo, escenarios_simulacion_sva

    desglose = desglose_sva_completo(analisis, tier=tier, radio_metros=radio_metros)
    dem = desglose["demografico"]
    comp = desglose["competencia"]
    traf = desglose["trafico"]

    story.append(
        Paragraph(
            "El SVA no es una opinión de la IA: es una suma ponderada con fórmulas fijas. "
            "Cada pilar usa datos medidos en tu radio; abajo se muestran las entradas, la regla aplicada "
            "y el aporte al resultado final.",
            s_body,
        )
    )
    story.append(Spacer(1, 6))

    paso_a_paso = [
        [
            Paragraph("Pilar", s_table_header),
            Paragraph("Entrada medida", s_table_header),
            Paragraph("Fórmula aplicada", s_table_header),
            Paragraph("Score", s_table_header),
            Paragraph("× Peso", s_table_header),
            Paragraph("Aporte", s_table_header),
        ],
        [
            Paragraph("Demografía", s_table_cell),
            Paragraph(_texto_entrada_demografica(dem), s_table_cell),
            Paragraph(dem["regla"], s_table_cell),
            Paragraph(f"{dem['score']:.1f}", s_table_cell),
            Paragraph("40%", s_table_cell),
            Paragraph(f"{dem['aporte_ponderado']:.1f}", s_table_cell),
        ],
        [
            Paragraph("Competencia", s_table_cell),
            Paragraph(_texto_entrada_competencia(comp), s_table_cell),
            Paragraph(comp["regla"], s_table_cell),
            Paragraph(f"{comp['score']:.1f}", s_table_cell),
            Paragraph("30%", s_table_cell),
            Paragraph(f"{comp['aporte_ponderado']:.1f}", s_table_cell),
        ],
        [
            Paragraph("Tráfico", s_table_cell),
            Paragraph(traf["detalle"], s_table_cell),
            Paragraph(traf["regla"], s_table_cell),
            Paragraph(f"{traf['score']:.1f}", s_table_cell),
            Paragraph("30%", s_table_cell),
            Paragraph(f"{traf['aporte_ponderado']:.1f}", s_table_cell),
        ],
    ]
    tabla_pasos = Table(paso_a_paso, colWidths=[58, 118, 118, 42, 42, 46])
    tabla_pasos.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("PADDING", (0, 0), (-1, -1), 5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
            ]
        )
    )
    story.append(tabla_pasos)
    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>En palabras simples:</b>", s_body))
    story.append(Spacer(1, 4))
    for etiqueta, pilar in (
        ("Demografia", dem),
        ("Competencia", comp),
        ("Trafico", traf),
    ):
        story.append(
            Paragraph(
                f"<b>{etiqueta}:</b> {pilar.get('lectura_llana', '')}",
                s_body,
            )
        )
        story.append(Spacer(1, 3))
    story.append(Spacer(1, 4))
    story.append(Paragraph("<b>Glosario rapido:</b>", s_body))
    story.append(Spacer(1, 4))
    for termino, definicion in GLOSARIO_SVA_PDF:
        story.append(Paragraph(f"<b>{termino}:</b> {definicion}", s_body))
        story.append(Spacer(1, 2))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<i>{comp['nota']}</i>", s_body))
    story.append(Spacer(1, 4))
    story.append(
        Paragraph(
            f"<b>Resultado:</b> {desglose['formula_final']}. "
            f"El reporte muestra <b>{desglose['sva_reportado']}/100</b>.",
            s_body,
        )
    )
    story.append(Spacer(1, 4))
    story.append(
        Paragraph(
            f"<b>Fuente del pilar tráfico:</b> {traf['fuente']}.",
            s_body,
        )
    )

    escenarios = escenarios_simulacion_sva(analisis, tier=tier, radio_metros=radio_metros)
    if len(escenarios) > 1:
        story.append(Spacer(1, 10))
        story.append(Paragraph("<b>Mini simulador — ¿qué pasaría si cambia la competencia?</b>", s_h2))
        story.append(
            Paragraph(
                "Escenarios hipotéticos recalculados con las mismas fórmulas. "
                "Se conservan demografía y tráfico actuales; solo varía el ISC según cuántos "
                "competidores (y a qué distancia) permanecen en el radio. "
                "<b>No son metas comerciales ni recomendaciones de ubicación.</b>",
                s_body,
            )
        )
        story.append(Spacer(1, 6))

        sim_data = [
            [
                Paragraph("Escenario", s_table_header),
                Paragraph("Competidores", s_table_header),
                Paragraph("ISC", s_table_header),
                Paragraph("Score competencia", s_table_header),
                Paragraph("SVA estimado", s_table_header),
                Paragraph("Δ vs actual", s_table_header),
            ]
        ]
        for esc in escenarios:
            delta = esc["delta_vs_actual"]
            delta_txt = "—" if esc["escenario"].startswith("Situación actual") else f"{delta:+d}"
            sim_data.append(
                [
                    Paragraph(esc["escenario"], s_table_cell),
                    Paragraph(str(esc["competidores"]), s_table_cell),
                    Paragraph(f"{float(esc['isc']):.6f}", s_table_cell),
                    Paragraph(f"{esc['score_competencia']:.1f}", s_table_cell),
                    Paragraph(f"{esc['sva']}/100", s_table_cell),
                    Paragraph(delta_txt, s_table_cell),
                ]
            )

        sim_table = Table(sim_data, colWidths=[150, 58, 72, 78, 68, 58])
        sim_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("PADDING", (0, 0), (-1, -1), 4),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.append(sim_table)
        story.append(Spacer(1, 6))
        story.append(
            Paragraph(
                "<i>Un SVA alto con competencia real es posible cuando los rivales están lejos: "
                "el conteo por sí solo no define el score. La fila «sin rivales» solo muestra un "
                "contrafactual matemático, no una estrategia de negocio.</i>",
                s_body,
            )
        )


def _interpretacion_distribucion_poblacional(
    rubro: str,
    segmentacion: dict,
    pob_total: int,
    tier: str,
) -> str:
    """Interpreta las gráficas demográficas en función del giro del usuario."""
    rubro_txt = rubro_legible(rubro)
    rubro_l = (rubro or "").lower()

    pob0_14 = int(segmentacion.get("pob0_14", 0))
    pob15_64 = int(segmentacion.get("pob15_64", 0))
    pob65 = int(segmentacion.get("pob65_mas", 0))
    pea = int(segmentacion.get("pea", 0))
    pct_15_64 = _pct_poblacion(pob15_64, pob_total)
    pct_ninos = _pct_poblacion(pob0_14, pob_total)

    intro = (
        f"En el radio analizado viven <b>{pob_total:,}</b> personas; las gráficas muestran cómo se reparten por edad"
    )
    if tier == "premium":
        intro += ", actividad laboral y escolaridad"
    elif tier == "pro":
        intro += " y su pirámide por cohortes"
    intro += (
        f". Para <b>{rubro_txt}</b>, estos datos ayudan a estimar quién puede consumir tu giro, "
        f"en qué horarios y con qué frecuencia."
    )

    if "cafe" in rubro_l or "cafeter" in rubro_l:
        giro_txt = (
            f"El {pct_15_64}% en edad 15-64 años y una PEA de {pea:,} personas sugieren demanda en horarios "
            f"laborales y de estudio; prioriza desayunos, breaks y consumo de paso cerca de oficinas o escuelas."
        )
    elif "flor" in rubro_l:
        giro_txt = (
            f"El {pct_ninos}% menor de 15 años y el {pct_15_64}% en edad productiva indican hogares con celebraciones "
            f"recurrentes (escuela, aniversarios, condolencias); ubica campañas en fechas escolares y zonas con "
            f"tráfico de visitas a clínicas o centros comerciales."
        )
    elif "farma" in rubro_l:
        giro_txt = (
            f"Familias ({pct_ninos}% menores de 15) y adultos mayores en la pirámide definen demanda de medicamentos "
            f"de primera necesidad; un radio con PEA de {pea:,} personas también aporta compras de paso en jornada laboral."
        )
    elif "gym" in rubro_l or "gimnasio" in rubro_l:
        giro_txt = (
            f"La concentración de población 15-39 años en la pirámide y {pea:,} personas económicamente activas "
            f"orientan horarios pico antes y después del trabajo; valida si hay estudiantes o jóvenes suficientes "
            f"para sostener membresías."
        )
    elif "restaur" in rubro_l or "comida" in rubro_l:
        giro_txt = (
            f"El {pct_15_64}% en edad laboral y la PEA de {pea:,} personas respaldan comidas de jornada y fines de semana; "
            f"compara la franja joven vs. adulta para decidir menú, ticket promedio y horario de mayor afluencia."
        )
    else:
        giro_txt = (
            f"El {pct_15_64}% en edad 15-64 años concentra la demanda comercial principal; "
            f"la PEA de {pea:,} personas indica flujo cotidiano y el {pct_ninos}% menor de 15 años señala hogares "
            f"familiares que pueden ampliar el ticket con compras complementarias."
        )

    if tier == "basico":
        plan_txt = " En Básico ves tres franjas etarias; en Pro y Premium la pirámide y segmentos afinan el nicho."
    elif tier == "pro":
        plan_txt = " La pirámide detallada permite detectar si tu público objetivo es joven, familiar o mixto."
    else:
        plan_txt = (
            " Los perfiles laboral y escolar complementan la pirámide para ajustar horarios, "
            "personal y promociones al ritmo real del barrio."
        )

    return intro + " " + giro_txt + plan_txt


def _embed_chart_png(story, png_bytes: bytes | None, *, width: float = 468, height: float | None = None) -> None:
    """Incrusta una gráfica PNG generada server-side en el flujo del PDF."""
    if not png_bytes:
        return
    try:
        from reportlab.platypus import Image

        img = Image(io.BytesIO(png_bytes), width=width, height=height or width * 0.42)
        img.hAlign = "CENTER"
        story.append(Spacer(1, 6))
        story.append(img)
        story.append(Spacer(1, 6))
    except Exception as err:
        logger.error("Error incrustando gráfica en PDF: %s", err)


class NumberedCanvas(canvas.Canvas):
    """
    Canvas personalizado de ReportLab de dos pasadas para:
    1. Dibujar cabeceras y pies de página dinámicos ("Página X de Y") a partir de la página 2.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):  # noqa: N802
        # Guardar estado de la página para la segunda pasada
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        current_annotation_count = getattr(self, "_annotationCount", 0)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._annotationCount = current_annotation_count
            self.draw_page_decorations(num_pages)
            current_annotation_count = self._annotationCount
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()

        # --- PÁGINA 1: PORTADA (Manejada por onFirstPage) ---
        if self._pageNumber == 1:
            pass

        # --- PÁGINAS SUCESIVAS: CABECERA Y PIE DE PÁGINA ---
        else:
            logo_path = os.path.join(os.path.dirname(__file__), "assets", "phiqus_logo_positivo.png")
            has_logo = os.path.exists(logo_path)

            if has_logo:
                # Dibujar logo a la izquierda
                self.drawImage(logo_path, 54, 742, width=55, height=15, preserveAspectRatio=True, mask="auto")
                text_offset = 65
            else:
                text_offset = 0

            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(colors.HexColor("#0f172a"))  # Navy
            self.drawString(54 + text_offset, 746, "GEOVIABILIDAD HOOK — ESTUDIO DE LOCALIZACIÓN INTELIGENTE")

            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#64748b"))  # Slate
            self.drawRightString(612 - 54, 746, datetime.date.today().strftime("%d/%m/%Y"))

            # Línea de cabecera sutil
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(54, 736, 612 - 54, 736)

            # PIE DE PÁGINA
            self.line(54, 55, 612 - 54, 55)
            self.setFont("Helvetica-Bold", 7)
            self.setFillColor(colors.HexColor("#ef4444"))  # Rojo alerta confidencial
            self.drawString(54, 42, "CONFIDENCIAL")

            self.setFont("Helvetica", 7)
            self.setFillColor(colors.HexColor("#64748b"))
            self.drawString(130, 42, "— ESTE REPORTE TIENE VIGENCIA DE 30 DÍAS.")

            page_text = f"Página {self._pageNumber} de {page_count}"
            self.drawRightString(612 - 54, 42, page_text)

            # Disclaimer orientativo (sin enlace comercial)
            self.setFont("Helvetica", 6.5)
            self.setFillColor(colors.HexColor("#64748b"))
            self.drawString(
                54,
                32,
                "Este informe es orientativo y basado en datos públicos y estimaciones.",
            )
            self.drawString(
                54,
                24,
                "No garantiza rentabilidad ni sustituye visita al sitio, asesoría legal o financiera.",
            )

        self.restoreState()


def dibujar_portada_background(canvas_obj, doc):
    """
    Dibuja el fondo geométrico de la portada (diapositiva 14 de Phiqus)
    y el logo blanco antes de pintar los textos de flujo.
    """
    canvas_obj.saveState()

    # 1. Fondo base gris oscuro
    canvas_obj.setFillColor(colors.HexColor("#212121"))
    canvas_obj.rect(0, 0, 612, 792, fill=1, stroke=0)

    # 2. Dibujar la imagen de fondo con la espiral Fibonacci de Phiqus
    bg_path = os.path.join(os.path.dirname(__file__), "assets", "cover_bg.png")
    if os.path.exists(bg_path):
        canvas_obj.drawImage(bg_path, 0, 0, width=612, height=792, mask="auto")

    # 3. Dibujar el logotipo blanco en la esquina superior izquierda
    logo_path = os.path.join(os.path.dirname(__file__), "assets", "cover_logo.png")
    if os.path.exists(logo_path):
        canvas_obj.drawImage(logo_path, 54, 700, width=110, height=30, preserveAspectRatio=True, mask="auto")

    canvas_obj.restoreState()


class ReportLabGenerator:
    """
    Compila el reporte ejecutivo en PDF usando ReportLab.
    Secciona la información con PageBreaks estrictos de acuerdo al Tier:
    - Básico: 6 Páginas
    - Pro: 10 Páginas
    - Premium: 13 Páginas
    """

    @staticmethod
    def construir_reporte_pdf(orden, analisis: dict, foda: str) -> bytes:
        logger.info(
            f"ReportLab: Iniciando compilación de PDF para Orden ID: {orden.id} (Tier: {orden.tier_adquirido.upper()})"
        )

        # Flujo de bytes en memoria para recibir el PDF
        buffer = io.BytesIO()

        # Secciones diferidas: Diagnóstico (5) y Metodología (6) van al final del documento
        bloque_diagnostico: list = []
        bloque_metodologia: list = []

        # Si foda es un diccionario, lo extraemos y formateamos
        foda_dict = {}
        if isinstance(foda, dict):
            foda_dict = foda
        else:
            try:
                import json

                foda_dict = json.loads(foda)
            except Exception:
                foda_dict = {}
                if isinstance(foda, str) and foda.strip():
                    foda_dict = {"conclusion": foda.strip()}

        # Inicializar plantilla de documento (Márgenes de 54pt = 0.75 pulgadas)
        doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=54, rightMargin=54, topMargin=70, bottomMargin=75)

        # Paleta de colores Premium
        c_navy = colors.HexColor("#0f172a")
        c_blue = colors.HexColor("#2563eb")
        c_text = colors.HexColor("#334155")

        # Crear estilos personalizados
        s_title_cover = ParagraphStyle(
            "CoverTitle",
            fontName="Helvetica-Bold",
            fontSize=28,
            leading=34,
            textColor=colors.HexColor("#37F18A"),
            spaceAfter=15,
            alignment=TA_LEFT,
            rightIndent=180,
        )

        s_subtitle_cover = ParagraphStyle(
            "CoverSubtitle",
            fontName="Helvetica",
            fontSize=15,
            leading=20,
            textColor=colors.white,
            spaceAfter=25,
            alignment=TA_LEFT,
            rightIndent=180,
        )

        s_meta_cover = ParagraphStyle(
            "CoverMeta",
            fontName="Helvetica",
            fontSize=10,
            leading=16,
            textColor=colors.HexColor("#cbd5e1"),
            rightIndent=180,
        )

        s_h1 = ParagraphStyle(
            "Heading1_Custom",
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=c_navy,
            spaceBefore=10,
            spaceAfter=15,
            keepWithNext=True,
        )

        s_h2 = ParagraphStyle(
            "Heading2_Custom",
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=16,
            textColor=c_blue,
            spaceBefore=8,
            spaceAfter=10,
            keepWithNext=True,
        )

        s_body = ParagraphStyle(
            "Body_Custom",
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=c_text,
            spaceAfter=10,
            alignment=TA_JUSTIFY,
        )
        s_table_header = ParagraphStyle(
            "TableHeader",
            parent=s_body,
            fontName="Helvetica-Bold",
            textColor=colors.white,
            spaceAfter=0,
            alignment=TA_LEFT,
        )
        s_table_cell = ParagraphStyle("TableCell", parent=s_body, alignment=TA_LEFT, spaceAfter=0)

        s_bullet = ParagraphStyle(
            "Bullet_Custom",
            fontName="Helvetica",
            fontSize=9.5,
            leading=13.5,
            textColor=c_text,
            leftIndent=15,
            spaceAfter=6,
        )

        s_card_val = ParagraphStyle(
            "CardVal",
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#1e3a8a"),
            alignment=1,
        )

        s_card_lbl = ParagraphStyle(
            "CardLbl",
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#475569"),
            alignment=1,
        )

        story = []

        # =====================================================================
        # PÁGINA 1: PORTADA DARK PREMIUM (Todos los Tiers)
        # =====================================================================
        story.append(Spacer(1, 80))
        story.append(Paragraph("ESTUDIO DE<br/>VIABILIDAD COMERCIAL", s_title_cover))
        story.append(
            Paragraph("ANÁLISIS ESPACIAL Y DIAGNÓSTICO DE GEOMARKETING INTELIGENTE EN MÉXICO", s_subtitle_cover)
        )

        # Etiqueta de Tier destacada
        tier_map = {
            "basico": "BÁSICO",
            "pro": "PRO",
            "premium": "PREMIUM",
        }
        tier_label = tier_map.get(orden.tier_adquirido, orden.tier_adquirido.upper())
        story.append(Spacer(1, 50))

        meses_es = {
            1: "enero",
            2: "febrero",
            3: "marzo",
            4: "abril",
            5: "mayo",
            6: "junio",
            7: "julio",
            8: "agosto",
            9: "septiembre",
            10: "octubre",
            11: "noviembre",
            12: "diciembre",
        }
        today = datetime.date.today()
        fecha_es = f"{today.day:02d} de {meses_es[today.month]} de {today.year}"

        meta_html = (
            f"<b>GIRO COMERCIAL:</b> {rubro_legible(orden.rubro).upper()}<br/>"
            f"<b>COORDENADAS:</b> {orden.latitud}, {orden.longitud}<br/>"
            f"<b>RADIO DE INFLUENCIA:</b> {orden.radio_metros} metros<br/>"
            f"<b>CÓDIGO DE ORDEN:</b> {orden.checkout_id}<br/>"
            f"<b>NIVEL ADQUIRIDO:</b> <font color='#0675F1'><b>TIER {tier_label}</b></font><br/>"
            f"<b>FECHA DE EMISIÓN:</b> {fecha_es}<br/>"
        )
        story.append(Paragraph(meta_html, s_meta_cover))

        # Elementos adicionales de la diapositiva 14
        story.append(Spacer(1, 40))

        # Monospace Data Science
        s_data_science = ParagraphStyle(
            "CoverDataScience",
            fontName="Courier-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.white,
            spaceAfter=20,
            rightIndent=180,
        )
        story.append(Paragraph("&lt;Data Science&gt;", s_data_science))

        # Pie de página de la portada
        s_footer_cover = ParagraphStyle(
            "CoverFooter",
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#94a3b8"),  # slate-400
            rightIndent=180,
        )
        footer_text = (
            f"GeoViabilidad Hook | Estudio de Localización Inteligente | {datetime.date.today().strftime('%d/%m/%Y')}"
        )
        story.append(Paragraph(footer_text, s_footer_cover))

        story.append(PageBreak())

        # =====================================================================
        # PÁGINA 2: RESUMEN EJECUTIVO & METRICAS (Todos los Tiers)
        # =====================================================================
        localidad = analisis.get("localidad", "México")
        story.append(Paragraph("1. RESUMEN EJECUTIVO", s_h1))
        story.append(
            Paragraph(
                f"Este reporte ejecutivo proporciona un diagnóstico cuantitativo y estratégico de geomarketing "
                f"para evaluar la apertura o expansión de tu negocio en <b>{localidad}</b>. A continuación se presentan los indicadores clave "
                f"calculados a partir de los datos geodésicos del Censo de Población de INEGI y el motor analítico de la plataforma.",
                s_body,
            )
        )
        story.append(Spacer(1, 15))

        # Renderizar Tarjetas de KPIs usando una Tabla
        nse_info = analisis.get("nse") or {}
        nse_etiqueta_pdf = nse_info.get("nse_etiqueta", "No disponible")

        kpi_data = [
            [
                Paragraph("SCORE VIABILIDAD", s_card_lbl),
                Paragraph("POBLACIÓN RESIDENTE", s_card_lbl),
                Paragraph("COMPETIDORES", s_card_lbl),
                Paragraph("NIVEL SOCIOECONÓMICO", s_card_lbl),
            ],
            [
                Paragraph(f"{analisis['sva']}/100", s_card_val),
                Paragraph(f"{analisis['poblacion_ponderada']:,}", s_card_val),
                Paragraph(f"{analisis['competidores_conteo']}", s_card_val),
                Paragraph(nse_etiqueta_pdf, s_card_val),
            ],
        ]

        kpi_table = Table(kpi_data, colWidths=[126, 126, 126, 126])
        kpi_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("PADDING", (0, 0), (-1, -1), 12),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ]
            )
        )
        story.append(kpi_table)
        story.append(Spacer(1, 20))

        story.append(Paragraph("Resumen Diagnóstico de Apertura:", s_h2))
        sva_val = analisis["sva"]
        if sva_val >= 80:
            status_txt = "<font color='#16a34a'><b>EXCELENTE (VIABILIDAD ALTA)</b></font>"
        elif sva_val >= 50:
            status_txt = "<font color='#ca8a04'><b>MODERADA (REQUIERE DIFERENCIACIÓN)</b></font>"
        else:
            status_txt = "<font color='#dc2626'><b>RIESGOSA (VIABILIDAD BAJA)</b></font>"

        story.append(Paragraph(f"<b>Diagnóstico preliminar:</b> {status_txt}", s_body))

        from app.lectura_estrategica import generar_conclusion_detallada

        conclusion_ejecutiva = generar_conclusion_detallada(
            analisis,
            orden.rubro,
            tier=orden.tier_adquirido,
            radio_metros=int(orden.radio_metros),
            html=True,
        )
        story.append(Spacer(1, 10))
        story.append(Paragraph("<b>Conclusión general — por qué obtuviste este score:</b>", s_h2))
        story.append(Paragraph(conclusion_ejecutiva, s_body))

        story.append(Spacer(1, 15))
        story.append(Paragraph(f"<b>Ubicación física resuelta:</b><br/>{analisis['direccion']}", s_body))

        # Tabla Multi-Radio con población y densidad REALES (PostGIS por anillo de cobertura).
        # La competencia solo se reporta en el radio contratado — no se extrapola.
        multi_radio = analisis.get("multi_radio") or []
        if orden.tier_adquirido in ["pro", "premium"] and multi_radio:
            story.append(Spacer(1, 8))
            story.append(Paragraph("<b>Análisis Demográfico Multi-Radio:</b>", s_h2))

            comp_base = analisis.get("competidores_conteo", 0)

            mr_data = [
                [
                    Paragraph("Cobertura", s_table_header),
                    Paragraph("Población Residente", s_table_header),
                    Paragraph("Densidad Real", s_table_header),
                    Paragraph("Competencia Medida", s_table_header),
                ]
            ]
            for anillo in multi_radio:
                r_km = anillo.get("radio_km", 0)
                etiqueta = f"Radio {r_km:.1f} km"
                if anillo.get("es_radio_contratado"):
                    etiqueta += " (contratado)"
                    comp_txt = f"{comp_base} competidores directos"
                else:
                    comp_txt = "No medida en este anillo"
                mr_data.append(
                    [
                        Paragraph(etiqueta, s_table_cell),
                        Paragraph(f"{anillo.get('poblacion', 0):,} hab.", s_table_cell),
                        Paragraph(f"{anillo.get('densidad', 0):,} hab/km²", s_table_cell),
                        Paragraph(comp_txt, s_table_cell),
                    ]
                )

            mr_table = Table(mr_data, colWidths=[128, 128, 128, 128])
            mr_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#475569")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                        ("PADDING", (0, 0), (-1, -1), 4),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )
            story.append(mr_table)

        # Composición del SVA integrada al resumen (antes era sección independiente)
        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Composición del Score de Viabilidad (SVA):</b>", s_h2))
        from app.sva_calculo import DENSIDAD_MINIMA_HAB_KM2, DENSIDAD_OPTIMA_HAB_KM2

        story.append(
            Paragraph(
                "Métrica compuesta de 0 a 100 que pondera demografía (40%), competencia (30%) y atractores de tráfico (30%).",
                s_body,
            )
        )
        story.append(Spacer(1, 6))
        story.append(
            Paragraph(
                "<b>Nota metodológica — Pilar demográfico:</b> el score no compara la población absoluta del municipio "
                "contra ciudades grandes, sino la <b>densidad de habitantes dentro del radio contratado</b> (hab/km²). "
                f"Referencias calibradas para México: ≤{DENSIDAD_MINIMA_HAB_KM2:,.0f} hab/km² indica mercado disperso; "
                f"≥{DENSIDAD_OPTIMA_HAB_KM2:,.0f} hab/km² indica demanda local sólida. Entre ambos umbrales se aplica "
                "una escala logarítmica para que un pueblo compacto no quede penalizado frente a una metrópoli.",
                s_body,
            )
        )
        story.append(Spacer(1, 8))

        pob_tot_val = analisis.get("poblacion_ponderada", 0)
        score_dem = analisis.get("score_demog", 50.0)
        dens_dem = analisis.get("densidad_hab_km2", 0)
        comp_cont = analisis.get("competidores_conteo", 0)

        if score_dem >= 80:
            dem_est = f"Excelente densidad ({dens_dem:,.1f} hab/km² · {pob_tot_val:,} hab.)"
        elif score_dem >= 50:
            dem_est = f"Densidad aceptable ({dens_dem:,.1f} hab/km² · {pob_tot_val:,} hab.)"
        else:
            dem_est = f"Baja concentración ({dens_dem:,.1f} hab/km² · {pob_tot_val:,} hab.)"

        if comp_cont == 0:
            comp_est = "Sin competidores directos detectados"
        elif comp_cont <= 3:
            comp_est = f"Baja competencia ({comp_cont} competidores)"
        elif comp_cont <= 8:
            comp_est = f"Competencia intermedia ({comp_cont} competidores)"
        else:
            comp_est = f"Alta saturación ({comp_cont} competidores)"

        if orden.tier_adquirido == "premium":
            conteos_aliados = {
                k: v for k, v in (analisis.get("aliados_conteos") or {}).items() if k != "ia_auto"
            }
            total_atractores = sum(conteos_aliados.values())
            if total_atractores > 0:
                inf_est = f"Detectados {total_atractores} atractores/aliados en {len(conteos_aliados)} categorías"
            else:
                inf_est = (
                    f"Detectados {analisis.get('bancos_conteo', 0)} bancos, "
                    f"{analisis.get('escuelas_conteo', 0)} esc. y {analisis.get('transporte_conteo', 0)} transp."
                )
        else:
            inf_est = "Zonificación comercial estimada"

        score_comp = analisis.get("score_competencia", 50.0)
        score_traf = analisis.get("score_trafico", 50.0)

        pilares_data = [
            [
                Paragraph("Pilar Analítico", s_table_header),
                Paragraph("Peso", s_table_header),
                Paragraph("Score", s_table_header),
                Paragraph("Estatus en la Zona", s_table_header),
            ],
            [
                Paragraph("Pilar Demográfico", s_table_cell),
                Paragraph("40%", s_table_cell),
                Paragraph(f"{score_dem:.1f}/100", s_table_cell),
                Paragraph(dem_est, s_table_cell),
            ],
            [
                Paragraph("Pilar Competencia", s_table_cell),
                Paragraph("30%", s_table_cell),
                Paragraph(f"{score_comp:.1f}/100", s_table_cell),
                Paragraph(comp_est, s_table_cell),
            ],
            [
                Paragraph("Pilar Atractores e Inferencia", s_table_cell),
                Paragraph("30%", s_table_cell),
                Paragraph(f"{score_traf:.1f}/100", s_table_cell),
                Paragraph(inf_est, s_table_cell),
            ],
        ]
        pilares_table = Table(pilares_data, colWidths=[130, 55, 65, 254])
        pilares_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("PADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(pilares_table)
        story.append(Spacer(1, 8))
        story.append(Paragraph("<b>¿Por qué este Score de Viabilidad?</b>", s_h2))
        _agregar_seccion_transparencia_sva(
            story,
            analisis,
            tier=orden.tier_adquirido,
            radio_metros=int(orden.radio_metros),
            s_h2=s_h2,
            s_body=s_body,
            s_table_header=s_table_header,
            s_table_cell=s_table_cell,
        )

        story.append(PageBreak())

        # =====================================================================
        # SECCIÓN 2: PERFIL DEL CLIENTE Y DEMANDA (Todos los Tiers)
        # =====================================================================
        story.append(Paragraph("2. PERFIL DEL CLIENTE Y DEMANDA", s_h1))
        story.append(Paragraph("<b>Mercado Potencial — Datos Demográficos INEGI:</b>", s_h2))
        story.append(
            Paragraph(
                "El cálculo demográfico se realiza ponderando la intersección del radio de influencia seleccionado "
                "con cada una de las Áreas Geoestadísticas Básicas (AGEBs) urbanas registradas en "
                "nuestra base demográfica proveniente del Censo de Población y Vivienda 2020 de INEGI.",
                s_body,
            )
        )

        # Distribuciones demográficas — solo valores calculados desde datos reales de PostGIS
        pob_tot = analisis["poblacion_ponderada"]
        pob_mas = analisis.get("pobmas_ponderada", 0)
        pob_fem = analisis.get("pobfem_ponderada", 0)
        viv_tot = analisis.get("vivtot_ponderada", 0)

        # Si no hay datos de INEGI para esta zona, mostramos un aviso honesto
        if pob_tot == 0:
            story.append(
                Paragraph(
                    "<font color='#dc2626'><b>Aviso:</b></font> No se detectaron Áreas Geostadísticas Básicas (AGEBs) de INEGI "
                    "en el radio seleccionado. La zona consultada puede corresponder a un área rural no cartografiada, "
                    "zona de conservación o límite geográfico fuera del alcance del Censo Urbano 2020.",
                    s_body,
                )
            )
        else:
            # Calcular densidad real con el área geodésica del círculo (pi * r² en km²)
            area_km2 = math.pi * ((orden.radio_metros / 1000.0) ** 2)
            densidad_real = round(pob_tot / area_km2, 1) if area_km2 > 0 else 0

            # Calcular ocupantes por vivienda (ratio real)
            ocupantes_viv = round(pob_tot / viv_tot, 2) if viv_tot > 0 else 0

            # Calcular distribución de género desde datos reales
            pct_mas = round((pob_mas / pob_tot) * 100, 1) if pob_tot > 0 else 0
            pct_fem = round((pob_fem / pob_tot) * 100, 1) if pob_tot > 0 else 0

            demo_table_data = [
                [
                    Paragraph("Indicador Demográfico (Censo INEGI 2020)", s_table_header),
                    Paragraph("Valor Real", s_table_header),
                    Paragraph("Nota Metodológica", s_table_header),
                ],
                [
                    Paragraph("Población Total Residente", s_table_cell),
                    Paragraph(f"{pob_tot:,} hab.", s_table_cell),
                    Paragraph("Suma ponderada por intersección geodésica de AGEBs", s_table_cell),
                ],
                [
                    Paragraph("Viviendas Particulares Habitadas", s_table_cell),
                    Paragraph(f"{viv_tot:,} viv.", s_table_cell),
                    Paragraph("Censo INEGI 2020 — dato puro de base de datos", s_table_cell),
                ],
                [
                    Paragraph("Densidad Poblacional Real", s_table_cell),
                    Paragraph(f"{densidad_real:,} hab/km²", s_table_cell),
                    Paragraph(f"Calculada: {pob_tot:,} hab ÷ {area_km2:.2f} km²", s_table_cell),
                ],
                [
                    Paragraph("Promedio de Ocupantes por Vivienda", s_table_cell),
                    Paragraph(f"{ocupantes_viv} personas/viv.", s_table_cell),
                    Paragraph("Calculado: Población Total ÷ Viviendas", s_table_cell),
                ],
                [
                    Paragraph("Población Masculina", s_table_cell),
                    Paragraph(f"{pob_mas:,} hab. ({pct_mas}%)", s_table_cell),
                    Paragraph("Dato de registros oficiales", s_table_cell),
                ],
                [
                    Paragraph("Población Femenina", s_table_cell),
                    Paragraph(f"{pob_fem:,} hab. ({pct_fem}%)", s_table_cell),
                    Paragraph("Dato de registros oficiales", s_table_cell),
                ],
            ]

            nse_metricas = nse_info.get("metricas") or {}
            fuente_nse = "Censo INEGI 2020" if nse_metricas.get("fuente") == "censo_2020" else "Estimación determinista"
            demo_table_data.extend(
                [
                    [
                        Paragraph("Nivel Socioeconómico Predominante", s_table_cell),
                        Paragraph(nse_etiqueta_pdf, s_table_cell),
                        Paragraph(f"Estimación AMAI ({fuente_nse})", s_table_cell),
                    ],
                    [
                        Paragraph("Grado Promedio de Escolaridad", s_table_cell),
                        Paragraph(f"{nse_metricas.get('escolaridad_promedio', 0):.1f} años equiv.", s_table_cell),
                        Paragraph("Promedio ponderado en AGEBs del radio", s_table_cell),
                    ],
                    [
                        Paragraph("Conexión a Internet en Viviendas", s_table_cell),
                        Paragraph(f"{nse_metricas.get('internet_pct', 0):.1f}%", s_table_cell),
                        Paragraph("Viviendas con internet / total de viviendas", s_table_cell),
                    ],
                    [
                        Paragraph("Viviendas con Automóvil", s_table_cell),
                        Paragraph(f"{nse_metricas.get('autos_pct', 0):.1f}%", s_table_cell),
                        Paragraph("Indicador de equipamiento del hogar", s_table_cell),
                    ],
                ]
            )

            demo_table = Table(demo_table_data, colWidths=[200, 140, 164])
            demo_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
                        ("TOPPADDING", (0, 0), (-1, 0), 5),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                        ("PADDING", (0, 0), (-1, -1), 5),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )
            story.append(demo_table)

            segmentacion = analisis.get("segmentacion_demografica") or {}
            if segmentacion.get("fuente") == "censo_2020":
                from app.chart_images import (
                    generar_grafica_edades_amplias,
                    generar_grafica_escolaridad,
                    generar_grafica_laboral,
                    generar_piramide_poblacional,
                )
                from app.demografia_segmentos import segmentos_destacados_por_rubro

                story.append(Spacer(1, 10))
                story.append(Paragraph("<b>Distribución Poblacional en el Radio:</b>", s_h2))

                if orden.tier_adquirido == "basico":
                    png_edades = generar_grafica_edades_amplias(
                        segmentacion.get("pob0_14", 0),
                        segmentacion.get("pob15_64", 0),
                        segmentacion.get("pob65_mas", 0),
                        pob_total=pob_tot,
                    )
                    _embed_chart_png(story, png_edades, width=468, height=200)
                elif orden.tier_adquirido == "pro":
                    png_piramide = generar_piramide_poblacional(
                        segmentacion.get("piramide", []),
                        pob_total=pob_tot,
                    )
                    _embed_chart_png(story, png_piramide, width=468, height=280)
                else:
                    png_piramide = generar_piramide_poblacional(
                        segmentacion.get("piramide", []),
                        pob_total=pob_tot,
                    )
                    _embed_chart_png(story, png_piramide, width=468, height=260)

                    png_labor = generar_grafica_laboral(
                        segmentacion.get("pea", 0),
                        segmentacion.get("pocupada", 0),
                        segmentacion.get("pdesocup", 0),
                        segmentacion.get("pe_inac", 0),
                    )
                    _embed_chart_png(story, png_labor, width=468, height=180)

                    escolar_6_14 = sum(
                        g["mujeres"] + g["hombres"]
                        for g in segmentacion.get("piramide", [])
                        if g.get("etiqueta") in ("6-11 años", "12-14 años")
                    )
                    png_escolar = generar_grafica_escolaridad(
                        segmentacion.get("p15a17a", 0),
                        segmentacion.get("p18a24a", 0),
                        escolar_6_14,
                    )
                    _embed_chart_png(story, png_escolar, width=468, height=180)

                story.append(Spacer(1, 6))
                story.append(Paragraph("<b>Interpretación para tu giro:</b>", s_h2))
                story.append(
                    Paragraph(
                        _interpretacion_distribucion_poblacional(
                            orden.rubro,
                            segmentacion,
                            pob_tot,
                            orden.tier_adquirido,
                        ),
                        s_body,
                    )
                )

                if orden.tier_adquirido == "premium":
                    destacados = segmentos_destacados_por_rubro(orden.rubro, segmentacion, pob_tot)
                    if destacados:
                        story.append(Spacer(1, 8))
                        story.append(
                            Paragraph(
                                "<b>Segmentos Censales Relevantes para tu Rubro (datos INEGI):</b>",
                                s_h2,
                            )
                        )
                        seg_censo_data = [
                            [
                                Paragraph("Segmento", s_table_header),
                                Paragraph("Habitantes", s_table_header),
                                Paragraph("% del radio", s_table_header),
                                Paragraph("Relevancia", s_table_header),
                            ]
                        ]
                        for etiqueta, hab, pct, nota in destacados:
                            seg_censo_data.append(
                                [
                                    Paragraph(etiqueta, s_table_cell),
                                    Paragraph(f"{hab:,}", s_table_cell),
                                    Paragraph(f"{pct}%", s_table_cell),
                                    Paragraph(nota, s_table_cell),
                                ]
                            )
                        seg_censo_table = Table(seg_censo_data, colWidths=[150, 80, 70, 204])
                        seg_censo_table.setStyle(
                            TableStyle(
                                [
                                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                                    ("PADDING", (0, 0), (-1, -1), 6),
                                ]
                            )
                        )
                        story.append(seg_censo_table)

        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Nota de precisión en el análisis:</b>", s_h2))
        story.append(
            Paragraph(
                "Al intersectar el radio de influencia con los límites de las zonas habitacionales, "
                "se aplica una ponderación de superficie proporcional al área interceptada de cada polígono. "
                "Esto asegura que si una zona se encuentra parcialmente cruzada por el radio de influencia, únicamente se sume la fracción "
                "de población que reside físicamente en la sección interceptada, reduciendo estimaciones imprecisas.",
                s_body,
            )
        )
        # --- Premium: segmentación de nicho solo si el análisis aportó texto real ---
        if orden.tier_adquirido == "premium":
            seg_nicho = _texto_si_es_real(foda_dict.get("segmentacion_nicho"))
            if seg_nicho:
                story.append(Spacer(1, 12))
                story.append(Paragraph("<b>Segmentación de Nicho:</b>", s_h2))
                story.append(Paragraph(seg_nicho, s_body))

            estrategia = _texto_si_es_real(foda_dict.get("estrategia_precios"))
            if estrategia:
                story.append(Spacer(1, 8))
                story.append(Paragraph("<b>Estrategia de Posicionamiento Comercial:</b>", s_h2))
                story.append(Paragraph(estrategia, s_body))

        # =====================================================================
        # SECCIÓN 5 (DIFERIDA): LECTURA ESTRATÉGICA DEL PUNTO
        # =====================================================================
        from app.bedrock import _generar_consideraciones_apertura
        from app.lectura_estrategica import enriquecer_lista_lectura

        s_body_foda = ParagraphStyle("Body_Foda", parent=s_body, fontSize=8.2, leading=11, spaceAfter=3)
        s_h2_foda = ParagraphStyle("Heading2_Foda", parent=s_h2, fontSize=9.5, leading=12, spaceBefore=4, spaceAfter=2)

        if not foda_dict.get("consideraciones_apertura"):
            foda_dict["consideraciones_apertura"] = _generar_consideraciones_apertura(analisis)

        s_col_title = ParagraphStyle(
            "DiagColTitle",
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=10,
            textColor=colors.HexColor("#0f172a"),
        )
        s_col_body = ParagraphStyle(
            "DiagColBody",
            fontName="Helvetica",
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor("#334155"),
        )

        fort_list = enriquecer_lista_lectura(foda_dict.get("fortalezas", []), analisis)
        op_list = enriquecer_lista_lectura(foda_dict.get("oportunidades", []), analisis)
        cons_list = enriquecer_lista_lectura(foda_dict.get("consideraciones_apertura", []), analisis)
        dictamen_txt = _texto_si_es_real(foda_dict.get("dictamen_final"))

        bloque_foda: list = []
        columnas_foda: list[tuple[str, str, str]] = []
        if texto := _bullets_reales(fort_list):
            columnas_foda.append(("<b>FORTALEZAS DEL PUNTO</b>", texto, "#f0fdf4"))
        if texto := _bullets_reales(op_list):
            columnas_foda.append(("<b>OPORTUNIDADES</b>", texto, "#eff6ff"))
        if texto := _bullets_reales(cons_list):
            columnas_foda.append(("<b>CONSIDERACIONES PARA LA APERTURA</b>", texto, "#fffbeb"))

        if columnas_foda:
            ancho_col = 504 / len(columnas_foda)
            lectura_grid = [
                [Paragraph(titulo, s_col_title) for titulo, _, _ in columnas_foda],
                [Paragraph(cuerpo, s_col_body) for _, cuerpo, _ in columnas_foda],
            ]
            lectura_table = Table(lectura_grid, colWidths=[ancho_col] * len(columnas_foda))
            estilos_tabla = [
                ("PADDING", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ]
            for idx, (_, _, color_fondo) in enumerate(columnas_foda):
                estilos_tabla.append(("BACKGROUND", (idx, 0), (idx, 0), colors.HexColor(color_fondo)))
            lectura_table.setStyle(TableStyle(estilos_tabla))
            bloque_foda.append(lectura_table)
            bloque_foda.append(Spacer(1, 8))

        if dictamen_txt:
            bloque_foda.append(Spacer(1, 8))
            bloque_foda.append(Paragraph("<b>Dictamen Final del Consultor:</b>", s_h2_foda))
            bloque_foda.append(Paragraph(dictamen_txt, s_body_foda))

        if bloque_foda:
            bloque_diagnostico.append(Paragraph("5. LECTURA ESTRATÉGICA DEL PUNTO", s_h1))
            bloque_diagnostico.append(
                Paragraph(
                    "Lectura ampliada de fortalezas, oportunidades y consideraciones. "
                    "La síntesis del score y cómo mejorarlo está en el <b>Resumen Ejecutivo</b>.",
                    s_body_foda,
                )
            )
            if foda_dict.get("_fuente") == "respaldo_cuantitativo":
                bloque_diagnostico.append(
                    Paragraph(
                        "<i>Diagnóstico generado con métricas reales (modo sin LLM en la nube).</i>",
                        s_body_foda,
                    )
                )
            bloque_diagnostico.append(Spacer(1, 6))
            bloque_diagnostico.extend(bloque_foda)

        # =====================================================================
        # SECCIÓN 6 (DIFERIDA): METODOLOGÍA — siempre al final del documento
        # =====================================================================
        bloque_metodologia.append(Paragraph("6. METODOLOGÍA, FUENTES Y DESLINDE", s_h1))
        bloque_metodologia.append(
            Paragraph(
                "<b>Fuentes de Información Oficiales:</b><br/>"
                "Todos los datos demográficos provienen del Instituto Nacional de Estadística y Geografía "
                "<b>(INEGI)</b>, recopilados en el Censo de Población y Vivienda 2020. Las zonas comerciales son mapeadas en tiempo "
                "real y los flujos horarios se obtienen de servicios de analítica de tráfico.",
                s_body,
            )
        )

        bloque_metodologia.append(Spacer(1, 10))
        bloque_metodologia.append(Paragraph("<b>Resumen metodológico y glosario:</b>", s_h2))
        from app.lectura_estrategica import bloques_metodologia_resumen

        for titulo, cuerpo in bloques_metodologia_resumen(
            analisis,
            tier=orden.tier_adquirido,
            radio_metros=int(orden.radio_metros),
        ):
            bloque_metodologia.append(Paragraph(f"• <b>{titulo}:</b> {cuerpo}", s_bullet))

        bloque_metodologia.append(Spacer(1, 10))
        bloque_metodologia.append(Paragraph("<b>Conceptos Clave de Localización:</b>", s_h2))
        bloque_metodologia.append(
            Paragraph(
                "• <b>Zona Habitacional:</b> Agrupaciones geográficas definidas por el INEGI que agrupan conjuntos de manzanas con características demográficas homogéneas.",
                s_bullet,
            )
        )
        bloque_metodologia.append(
            Paragraph(
                "• <b>Radio de Influencia:</b> Área geográfica circular en torno a la ubicación seleccionada para estimar el mercado y sus características demográficas. La distancia se mide en metros lineales.",
                s_bullet,
            )
        )
        bloque_metodologia.append(
            Paragraph(
                "• <b>Modelo de Atracción Comercial:</b> Herramienta analítica que evalúa la probabilidad de éxito en función de la capacidad de captación del punto de venta y su cercanía geográfica.",
                s_bullet,
            )
        )

        bloque_metodologia.append(Spacer(1, 15))
        bloque_metodologia.append(Paragraph("<b>Deslinde de Responsabilidad:</b>", s_h2))
        bloque_metodologia.append(
            Paragraph(
                "GeoViabilidad Hook es una aplicación desarrollada por PhiQus que integra modelos de análisis avanzado "
                "basados en información estadística y fuentes oficiales gubernamentales en México. "
                "Los resultados presentados constituyen una herramienta de apoyo para la toma de decisiones y no representan una "
                "garantía de rentabilidad, éxito comercial o validación de uso de suelo. "
                "Parte de los análisis puede ser generada mediante modelos de Inteligencia Artificial (IA). En caso de requerir un análisis más profundo, "
                "recomendamos contactar directamente los servicios de consultoría de "
                "<font color='#2563eb'><u><a href=\"https://phiqus.com/\">PhiQus</a></u></font>, "
                "<font color='#2563eb'><u><a href=\"https://estudiosdemercado.phiqus.com/\">Estudios de Mercado</a></u></font>.",
                s_body,
            )
        )

        def _cerrar_reporte():
            if bloque_diagnostico:
                story.append(PageBreak())
                story.extend(bloque_diagnostico)
            story.append(PageBreak())
            story.extend(bloque_metodologia)
            doc.build(story, canvasmaker=NumberedCanvas, onFirstPage=dibujar_portada_background)
            pdf_bytes = buffer.getvalue()
            buffer.close()
            return pdf_bytes

        # TIER BÁSICO: Resumen + Perfil + Diagnóstico + Metodología
        if orden.tier_adquirido == "basico":
            logger.info("ReportLab: Compilación Básico exitosa.")
            return _cerrar_reporte()

        # =====================================================================
        # SECCIÓN 3: ANÁLISIS DE COMPETENCIA (Pro y Premium)
        # =====================================================================
        from app.chart_images import generar_grafica_competidores

        s_quadrant_title = ParagraphStyle(
            "QuadrantTitle",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=2,
        )

        story.append(PageBreak())
        story.append(Paragraph("3. ANÁLISIS DE COMPETENCIA", s_h1))
        map_bytes = analisis.get("map_bytes")
        if map_bytes:
            story.append(Paragraph("<b>Mapa de Ubicación y Competencia:</b>", s_h2))
            mapa_desc = (
                "Mapa del área comercial analizada (misma base cartográfica y convención de colores que el dashboard). "
                "La ubicación propuesta se marca con un pin <font color='#2563eb'><b>AZUL</b></font>, "
                "los competidores directos en <font color='#dc2626'><b>ROJO</b></font>"
            )
            if orden.tier_adquirido == "premium":
                mapa_desc += (
                    " y los atractores/aliados comerciales en <font color='#10b981'><b>VERDE</b></font>."
                )
            mapa_desc += " El círculo semitransparente delimita el radio de influencia contratado."
            story.append(Paragraph(mapa_desc, s_body))
            story.append(Spacer(1, 15))
            try:
                from reportlab.platypus import Image

                img_data = io.BytesIO(map_bytes)
                img = Image(img_data, width=504, height=315)
                img.hAlign = "CENTER"
                story.append(img)
            except Exception as img_err:
                logger.error(f"Error al renderizar mapa estático en PDF: {img_err}")
        else:
            logger.info("ReportLab: Sin mapa estático real; se omite la subsección de mapa en el PDF.")

        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Competencia Detallada en la Zona:</b>", s_h2))
        if getattr(orden, "competidores_adicionales", None):
            story.append(
                Paragraph(
                    f"<b>Competidores específicos o marcas a considerar:</b> {orden.competidores_adicionales}",
                    s_body,
                )
            )
            story.append(Spacer(1, 5))

        from app.analytics import (
            MIN_RESENAS_DESTACADO,
            asegurar_distancias_competidores,
            competidores_mas_cercanos,
            formatear_distancia_metros,
            lectura_competidor_cercano,
            resolver_competidores_destacados_para_reporte,
        )

        comp_list = list(analisis.get("competidores_listado", []))
        asegurar_distancias_competidores(
            comp_list,
            float(orden.latitud),
            float(orden.longitud),
        )
        total_comp_detectados = int(analisis.get("competidores_conteo") or len(comp_list))
        story.append(
            Paragraph(
                f"Listado completo de los <b>{total_comp_detectados}</b> establecimientos competidores detectados "
                f"en el radio (misma lista que el dashboard). Los datos provienen de Google Places según el giro "
                f"y las categorías analizadas.",
                s_body,
            )
        )
        enriquecer_reseñas = orden.tier_adquirido in ["pro", "premium"]
        mejor_valorados = resolver_competidores_destacados_para_reporte(
            comp_list,
            orden.rubro,
            top_n=5,
            enriquecer_reseñas=enriquecer_reseñas,
        )

        def _etiqueta_rating_competidor(item: dict) -> str:
            total = int(item.get("user_ratings_total") or 0)
            rating = float(item.get("rating") or 0)
            texto = f"⭐ {rating} / 5.0 ({total} reseñas)"
            if 0 < total < MIN_RESENAS_DESTACADO:
                texto += " · muestra pequeña"
            return texto

        comp_table_data = [
            [
                Paragraph("Nombre del Establecimiento", s_table_header),
                Paragraph("Giro / Tipo Comercial", s_table_header),
                Paragraph("Calificación Google", s_table_header),
                Paragraph("Distancia al punto", s_table_header),
            ],
        ]

        if not comp_list:
            comp_table_data.append(
                [
                    Paragraph(
                        "<font color='#64748b'><i>0 competidores directos detectados en el radio</i></font>",
                        s_table_cell,
                    ),
                    Paragraph("—", s_table_cell),
                    Paragraph("—", s_table_cell),
                    Paragraph("—", s_table_cell),
                ]
            )
        else:
            for item in comp_list:
                comp_table_data.append(
                    [
                        Paragraph(item.get("nombre", "—"), s_table_cell),
                        Paragraph(_tipo_comercial_legible(item.get("tipo"), orden.rubro), s_table_cell),
                        Paragraph(_etiqueta_rating_competidor(item), s_table_cell),
                        Paragraph(formatear_distancia_metros(item.get("distancia_metros")), s_table_cell),
                    ]
                )

        comp_table = Table(comp_table_data, colWidths=[130, 110, 130, 134])
        comp_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("PADDING", (0, 0), (-1, -1), 5),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )

        story.append(comp_table)

        aliados_reales = analisis.get("aliados_listado", [])
        if orden.tier_adquirido == "premium" and aliados_reales:
            story.append(Spacer(1, 10))
            story.append(
                Paragraph("<b>Establecimientos Complementarios (Atractores de Tráfico):</b>", s_h2)
            )
            aliados_table_data = [
                [
                    Paragraph("Nombre", s_table_header),
                    Paragraph("Categoría", s_table_header),
                    Paragraph("Calificación Google", s_table_header),
                ]
            ]
            for aliado in aliados_reales:
                rating_str = f"⭐ {aliado['rating']} / 5.0" if aliado["rating"] > 0 else "Sin calificación"
                reviews_str = (
                    f"({aliado['user_ratings_total']} reseñas)" if aliado["user_ratings_total"] > 0 else ""
                )
                aliados_table_data.append(
                    [
                        Paragraph(aliado["nombre"], s_table_cell),
                        Paragraph(_tipo_comercial_legible(aliado.get("tipo"), orden.rubro), s_table_cell),
                        Paragraph(f"{rating_str} {reviews_str}".strip(), s_table_cell),
                    ]
                )
            aliados_table = Table(aliados_table_data, colWidths=[200, 170, 134])
            aliados_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                        ("PADDING", (0, 0), (-1, -1), 5),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )
            story.append(aliados_table)
        story.append(
            Paragraph(
                "<font size='7' color='#64748b'><i>Nota: en la lista de cercanía pueden aparecer "
                "calificaciones altas con pocas reseñas (etiquetadas como «muestra pequeña»); "
                "no son estadísticamente representativas. El ranking de valoraciones y los comentarios "
                "siguientes exigen mínimo 5 reseñas en Google.</i></font>",
                s_body,
            )
        )

        if mejor_valorados:
            story.append(Spacer(1, 10))
            story.append(Paragraph("<b>Competidores mejor valorados y distancia desde tu punto:</b>", s_h2))
            story.append(
                Paragraph(
                    "Solo establecimientos con al menos 5 reseñas en Google Maps (misma lista que los comentarios "
                    "siguientes). Distancia geodésica desde tu ubicación; no equivale a tiempo de recorrido.",
                    s_body,
                )
            )
            story.append(Spacer(1, 6))
            top_data = [
                [
                    Paragraph("Establecimiento", s_table_header),
                    Paragraph("Calificación", s_table_header),
                    Paragraph("Reseñas", s_table_header),
                    Paragraph("Distancia al punto", s_table_header),
                ]
            ]
            for item in mejor_valorados:
                top_data.append(
                    [
                        Paragraph(item.get("nombre", "Comercio Local"), s_table_cell),
                        Paragraph(f"⭐ {item.get('rating', 0.0)} / 5.0", s_table_cell),
                        Paragraph(f"{int(item.get('user_ratings_total') or 0):,}", s_table_cell),
                        Paragraph(formatear_distancia_metros(item.get("distancia_metros")), s_table_cell),
                    ]
                )
            top_table = Table(top_data, colWidths=[180, 90, 80, 154])
            top_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                        ("PADDING", (0, 0), (-1, -1), 5),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )
            story.append(top_table)

        mas_cercanos = competidores_mas_cercanos(comp_list, top_n=8) if comp_list else []
        if mas_cercanos:
            story.append(Spacer(1, 10))
            story.append(
                Paragraph(
                    "<b>Competidores mas cercanos (por distancia, sin filtro de calificacion):</b>",
                    s_h2,
                )
            )
            story.append(
                Paragraph(
                    "Mismos datos de Google Places que el listado completo, ordenados por proximidad. "
                    "Incluye locales mal valorados o con pocas reseñas que no aparecen en «mejor valorados». "
                    "La cercania afecta la saturacion del punto aunque el rival no sea referente en Google.",
                    s_body,
                )
            )
            story.append(Spacer(1, 6))
            cercanos_data = [
                [
                    Paragraph("Establecimiento", s_table_header),
                    Paragraph("Distancia", s_table_header),
                    Paragraph("Calificacion", s_table_header),
                    Paragraph("Resenas", s_table_header),
                    Paragraph("Lectura", s_table_header),
                ]
            ]
            for item in mas_cercanos:
                rating = float(item.get("rating") or 0)
                resenas = int(item.get("user_ratings_total") or 0)
                rating_txt = f"{rating:.1f} / 5.0" if rating > 0 else "Sin rating"
                cercanos_data.append(
                    [
                        Paragraph(item.get("nombre", "—"), s_table_cell),
                        Paragraph(formatear_distancia_metros(item.get("distancia_metros")), s_table_cell),
                        Paragraph(rating_txt, s_table_cell),
                        Paragraph(str(resenas) if resenas > 0 else "—", s_table_cell),
                        Paragraph(lectura_competidor_cercano(item), s_table_cell),
                    ]
                )
            cercanos_table = Table(cercanos_data, colWidths=[115, 62, 68, 48, 211])
            cercanos_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#475569")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                        ("PADDING", (0, 0), (-1, -1), 4),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ]
                )
            )
            story.append(cercanos_table)
            story.append(Spacer(1, 4))
            story.append(
                Paragraph(
                    "<font size='7' color='#64748b'><i>Esta lista no sustituye el listado completo ni "
                    "la seccion «mejor valorados» (minimo 5 reseñas). Si un local no aparece aqui, "
                    "no fue detectado por Google Places en el radio analizado.</i></font>",
                    s_body,
                )
            )

        from xml.sax.saxutils import escape as xml_escape

        reseñas_rows: list = []
        for item in mejor_valorados:
            nombre = item.get("nombre", "Competidor local")
            for rev in item.get("reseñas_google") or []:
                texto = rev.get("texto", "").strip()
                if not texto:
                    continue
                meta_parts = []
                if rev.get("rating"):
                    meta_parts.append(f"⭐ {rev['rating']}/5")
                if rev.get("fecha_relativa"):
                    meta_parts.append(str(rev["fecha_relativa"]))
                if rev.get("autor"):
                    meta_parts.append(str(rev["autor"]))
                meta = " · ".join(meta_parts)
                dist_txt = formatear_distancia_metros(item.get("distancia_metros"))
                reseñas_rows.append(
                    [
                        Paragraph(f"<b>{xml_escape(nombre)}</b>", s_table_cell),
                        Paragraph(
                            f"“{xml_escape(texto)}”"
                            + (f"<br/><font size='6' color='#64748b'>{xml_escape(meta)}</font>" if meta else ""),
                            s_table_cell,
                        ),
                        Paragraph(dist_txt, s_table_cell),
                    ]
                )

        if reseñas_rows:
            story.append(Spacer(1, 10))
            story.append(Paragraph("<b>Comentarios de Google sobre competidores:</b>", s_h2))
            story.append(
                Paragraph(
                    "Extractos de reseñas públicas de Google Maps (mínimo 5 reseñas en Google), "
                    "con distancia lineal desde tu punto. Son opiniones de usuarios y no representan "
                    "la postura de GeoViabilidad Hook.",
                    s_body,
                )
            )
            story.append(Spacer(1, 6))
            reseñas_table = Table(
                [
                    [
                        Paragraph("Competidor", s_table_header),
                        Paragraph("Comentario de Google", s_table_header),
                        Paragraph("Distancia", s_table_header),
                    ],
                    *reseñas_rows,
                ],
                colWidths=[120, 290, 94],
            )
            reseñas_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                        ("PADDING", (0, 0), (-1, -1), 5),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )
            story.append(reseñas_table)

        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Análisis de Saturación Comercial:</b>", s_h2))
        story.append(
            Paragraph(
                "El Índice de Saturación Comercial (ISC) estima el nivel de fricción en la zona de influencia. "
                "Se computa penalizando a competidores "
                "que comparten vecindario inmediato con tu punto.",
                s_body,
            )
        )
        story.append(Spacer(1, 15))

        # Calcular bandas de distancia en tiempo real a partir del listado de competidores
        comp_list = analisis.get("competidores_listado", [])
        inmediatos = 0
        cercanos = 0
        perifericos = 0
        for comp in comp_list:
            dist = comp.get("distancia_metros", 9999)
            if dist < 250:
                inmediatos += 1
            elif dist < 500:
                cercanos += 1
            else:
                perifericos += 1

        distancia_cercana = analisis.get("distancia_competidor_cercano", -1)
        dist_txt = f"{distancia_cercana} metros lineales" if distancia_cercana != -1 else "No detectados"

        isc_val = float(analisis.get("isc", 0.0))
        isc_formato = f"{isc_val:.6f}"

        saturacion_table_data = [
            [
                Paragraph("Métrica de Fricción Espacial", s_table_header),
                Paragraph("Valor Analítico Real", s_table_header),
            ],
            [
                Paragraph("Competidores Cercanos (< 250m)", s_table_cell),
                Paragraph(f"{inmediatos} establecimientos", s_table_cell),
            ],
            [
                Paragraph("Competidores Intermedios (250m - 500m)", s_table_cell),
                Paragraph(f"{cercanos} establecimientos", s_table_cell),
            ],
            [
                Paragraph("Competidores Periféricos (> 500m)", s_table_cell),
                Paragraph(f"{perifericos} establecimientos", s_table_cell),
            ],
            [
                Paragraph("Distancia al Competidor Cercano", s_table_cell),
                Paragraph(dist_txt, s_table_cell),
            ],
            [
                Paragraph("Índice de Saturación Comercial (ISC)", s_table_cell),
                Paragraph(isc_formato, s_table_cell),
            ],
        ]

        saturacion_table = Table(saturacion_table_data, colWidths=[280, 224])
        saturacion_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("PADDING", (0, 0), (-1, -1), 5),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(saturacion_table)

        # Calidad percibida de la competencia — calculada con ratings y reseñas reales de Places
        if comp_list:
            story.append(Spacer(1, 10))
            story.append(Paragraph("<b>Calidad Percibida de la Competencia (Reseñas Reales de Clientes):</b>", s_h2))

            total_c = len(comp_list)
            rangos_def = [
                ("Mal valorados (< 3.0 o sin rating)", 0.0, 3.0),
                ("Aceptables (3.0 - 3.9)", 3.0, 4.0),
                ("Bien valorados (4.0 - 4.4)", 4.0, 4.5),
                ("Excelentes (4.5 - 5.0)", 4.5, 5.1),
            ]

            calidad_data = [
                [
                    Paragraph("Rango de Calificación", s_table_header),
                    Paragraph("Competidores", s_table_header),
                    Paragraph("% del Total", s_table_header),
                ]
            ]
            for etiqueta, lim_inf, lim_sup in rangos_def:
                cnt = sum(1 for c in comp_list if lim_inf <= float(c.get("rating", 0) or 0) < lim_sup)
                pct = round(cnt / total_c * 100) if total_c else 0
                calidad_data.append(
                    [
                        Paragraph(etiqueta, s_table_cell),
                        Paragraph(f"{cnt}", s_table_cell),
                        Paragraph(f"{pct}%", s_table_cell),
                    ]
                )

            ratings_validos = [float(c.get("rating", 0) or 0) for c in comp_list if c.get("rating")]
            rating_prom = round(sum(ratings_validos) / len(ratings_validos), 2) if ratings_validos else 0
            resenas_tot = sum(int(c.get("user_ratings_total", 0) or 0) for c in comp_list)
            calidad_data.append(
                [
                    Paragraph("<b>Promedio de la zona</b>", s_table_cell),
                    Paragraph(f"<b>{rating_prom} / 5.0</b>", s_table_cell),
                    Paragraph(f"<b>{resenas_tot:,} reseñas</b>", s_table_cell),
                ]
            )

            calidad_table = Table(calidad_data, colWidths=[220, 120, 164])
            calidad_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#475569")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                        ("PADDING", (0, 0), (-1, -1), 4),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )
            story.append(calidad_table)
            story.append(Spacer(1, 6))
            story.append(Paragraph("<b>Gráfica — Distribución de Competidores por Rating:</b>", s_h2))
            _embed_chart_png(story, generar_grafica_competidores(comp_list), width=468, height=200)
            story.append(Spacer(1, 6))

        story.append(PageBreak())

        # SECCIÓN 4: TRÁFICO, ATRACTORES Y AFLUENCIA (Pro y Premium)
        from app.chart_images import generar_grafica_atractores, generar_heatmap_afluencia

        story.append(Paragraph("4. TRÁFICO, ATRACTORES Y AFLUENCIA", s_h1))
        story.append(Paragraph("<b>Índice de Atracción de Tráfico (IAT) y Puntos de Interés:</b>", s_h2))
        story.append(
            Paragraph(
                "El Índice de Atracción de Tráfico (IAT) mapea los puntos de interés que actúan como "
                "magnetos de flujo de personas en la zona (ej. estaciones de metro, paradas de autobús, bancos y escuelas).",
                s_body,
            )
        )
        if getattr(orden, "aliados_adicionales", None):
            story.append(
                Paragraph(
                    f"<b>Aliados específicos o marcas a considerar:</b> {orden.aliados_adicionales}",
                    s_body,
                )
            )
            story.append(Spacer(1, 5))

        modo_aliados = getattr(orden, "modo_analisis_aliados", None) or analisis.get(
            "modo_analisis_aliados", "automatico"
        )
        config_guiada = analisis.get("config_aliados_guiados")
        if not config_guiada and getattr(orden, "config_aliados_guiados", None):
            import json as _json

            try:
                config_guiada = _json.loads(orden.config_aliados_guiados)
            except Exception:
                config_guiada = None

        if orden.tier_adquirido == "premium" and modo_aliados == "guiado" and config_guiada:
            from app.aliados_guiados import (
                etiquetas_atractores_legibles,
                etiquetas_horario_legibles,
                etiquetas_perfil_legibles,
            )

            story.append(
                Paragraph(
                    "<i>Atractores definidos por configuración guiada del solicitante "
                    "(sin inferencia automática de categorías).</i>",
                    s_body,
                )
            )
            story.append(Spacer(1, 6))
            cfg_rows = [
                ["Perfil de cliente", etiquetas_perfil_legibles(config_guiada.get("perfil_cliente"))],
                ["Horarios clave", etiquetas_horario_legibles(config_guiada.get("horarios_pico"))],
                [
                    "Tipos elegidos",
                    etiquetas_atractores_legibles(config_guiada.get("atractores_confirmados")),
                ],
                [
                    "Marcas adicionales",
                    getattr(orden, "aliados_adicionales", None) or "No especificadas",
                ],
            ]
            cfg_table_data = [
                [Paragraph("Tu configuración", s_table_header), Paragraph("Detalle", s_table_header)]
            ]
            for etiqueta, valor in cfg_rows:
                cfg_table_data.append(
                    [Paragraph(etiqueta, s_table_cell), Paragraph(str(valor), s_table_cell)]
                )
            cfg_table = Table(cfg_table_data, colWidths=[170, 334])
            cfg_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                        ("PADDING", (0, 0), (-1, -1), 6),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )
            story.append(cfg_table)
            story.append(Spacer(1, 8))

        aliados_conteos = analisis.get("aliados_conteos", {})

        poi_table_data = [
            [
                Paragraph("Categoría de Punto de Interés (Atractor)", s_table_header),
                Paragraph("Conteo en Radio", s_table_header),
            ],
        ]

        from app.aliados_deterministico import nombre_categoria_places

        conteos_reales = {k: v for k, v in aliados_conteos.items() if k != "ia_auto" and int(v or 0) > 0}
        if orden.tier_adquirido == "premium" and conteos_reales:
            for ally_type, cnt in conteos_reales.items():
                poi_table_data.append(
                    [
                        Paragraph(nombre_categoria_places(ally_type), s_table_cell),
                        Paragraph(f"{cnt} detectados", s_table_cell),
                    ]
                )
        else:
            filas_pro = [
                ("Bancos e Instituciones Financieras", int(analisis.get("bancos_conteo", 0))),
                ("Escuelas e Instituciones Educativas", int(analisis.get("escuelas_conteo", 0))),
                ("Paradas de Transporte Público", int(analisis.get("transporte_conteo", 0))),
            ]
            for etiqueta, cnt in filas_pro:
                if cnt > 0:
                    poi_table_data.append(
                        [
                            Paragraph(etiqueta, s_table_cell),
                            Paragraph(f"{cnt} detectados", s_table_cell),
                        ]
                    )

        if len(poi_table_data) > 1:
            poi_table = Table(poi_table_data, colWidths=[300, 204])
            poi_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                        ("PADDING", (0, 0), (-1, -1), 6),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )
            story.append(poi_table)
            story.append(Spacer(1, 8))

        total_atractores_zona = sum(conteos_reales.values()) if conteos_reales else (
            int(analisis.get("bancos_conteo", 0))
            + int(analisis.get("escuelas_conteo", 0))
            + int(analisis.get("transporte_conteo", 0))
        )
        if total_atractores_zona > 0:
            story.append(Paragraph("<b>Gráfica — Atractores de Tráfico por Categoría:</b>", s_h2))
            _embed_chart_png(
                story,
                generar_grafica_atractores(
                    aliados_conteos,
                    bancos=analisis.get("bancos_conteo", 0),
                    escuelas=analisis.get("escuelas_conteo", 0),
                    transporte=analisis.get("transporte_conteo", 0),
                ),
                width=468,
                height=220,
            )
            story.append(Spacer(1, 12))

        if orden.tier_adquirido == "pro":
            logger.info("ReportLab: Compilación Pro exitosa.")
            return _cerrar_reporte()

        # Premium: afluencia peatonal + extras de diagnóstico (fricciones del sector)
        # PÁGINA (CONDICIONAL): AFLUENCIA PEATONAL DINÁMICA (BestTime API) (Premium)
        # Se incluye SOLO si la API de BestTime retornó datos reales de telemetría.
        # Si la API falló o no tiene cobertura en la zona, esta sección se omite completamente.
        afl_data = analisis.get("afluencia_peatonal", {})
        besttime_tiene_datos = (
            afl_data.get("status") == "success"
            and afl_data.get("afluencia_horaria")
            and len(afl_data.get("afluencia_horaria", [])) >= 24
        )

        if besttime_tiene_datos:
            story.append(Spacer(1, 12))
            story.append(Paragraph("<b>Afluencia Peatonal Dinámica:</b>", s_h2))
            story.append(
                Paragraph(
                    "Mapeo de la afluencia peatonal por hora, construido a partir de registros históricos de "
                    "tráfico de visitantes en establecimientos representativos de la zona. "
                    "Este análisis permite programar de forma eficiente turnos del personal y picos de producción.",
                    s_body,
                )
            )
            story.append(Spacer(1, 8))
            _embed_chart_png(
                story,
                generar_heatmap_afluencia(afl_data),
                width=504,
                height=210,
            )
            story.append(Spacer(1, 8))

            afl_curva = afl_data.get("afluencia_horaria", [])
            int_manana = int(round(sum(afl_curva[8:12]) / 4.0))
            int_mediodia = int(round(sum(afl_curva[12:16]) / 4.0))
            int_tarde = int(round(sum(afl_curva[16:20]) / 4.0))
            int_noche = int(round(sum(afl_curva[20:24]) / 4.0))

            afluencia_table_data = [
                [
                    Paragraph("Rango Horario", s_table_header),
                    Paragraph("Intensidad Peatonal (%)", s_table_header),
                ],
                [
                    Paragraph("Mañana (08:00 - 12:00)", s_table_cell),
                    Paragraph(f"{int_manana}%", s_table_cell),
                ],
                [
                    Paragraph("Mediodía (12:00 - 16:00)", s_table_cell),
                    Paragraph(f"{int_mediodia}%", s_table_cell),
                ],
                [
                    Paragraph("Tarde (16:00 - 20:00)", s_table_cell),
                    Paragraph(f"{int_tarde}%", s_table_cell),
                ],
                [
                    Paragraph("Noche (20:00 - 24:00)", s_table_cell),
                    Paragraph(f"{int_noche}%", s_table_cell),
                ],
            ]
            afluencia_table = Table(afluencia_table_data, colWidths=[252, 252])
            afluencia_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                        ("PADDING", (0, 0), (-1, -1), 6),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )
            story.append(afluencia_table)

            from app.besttime import construir_filas_horas_pico

            filas_horas = construir_filas_horas_pico(afl_data)
            if filas_horas:
                story.append(Spacer(1, 10))
                story.append(Paragraph("<b>Horas Pico y Ventanas de Afluencia por Día:</b>", s_h2))
                story.append(
                    Paragraph(
                        "Ventanas calculadas a partir de la curva horaria semanal para esta coordenada.",
                        s_body,
                    )
                )
                story.append(Spacer(1, 6))

                horas_data = [
                    [
                        Paragraph("Día", s_table_header),
                        Paragraph("Horas Pico (Mayor Afluencia)", s_table_header),
                        Paragraph("Horas Tranquilas", s_table_header),
                    ]
                ]
                for dia, picos, tranquilas, _interp in filas_horas:
                    horas_data.append(
                        [
                            Paragraph(dia, s_table_cell),
                            Paragraph(picos, s_table_cell),
                            Paragraph(tranquilas, s_table_cell),
                        ]
                    )
                horas_table = Table(horas_data, colWidths=[100, 200, 204])
                horas_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#475569")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                            ("PADDING", (0, 0), (-1, -1), 4),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ]
                    )
                )
                story.append(horas_table)
        else:
            logger.info(
                "[PDF] BestTime no tiene datos reales de telemetría para esta coordenada. "
                "Se omite la sección de Afluencia Peatonal del reporte."
            )

        logger.info("ReportLab: Compilación Premium exitosa.")
        return _cerrar_reporte()
