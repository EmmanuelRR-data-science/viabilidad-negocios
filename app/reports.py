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

            # Invitación a agendar asesoría / videollamada
            self.setFont("Helvetica-Bold", 6.5)
            self.setFillColor(colors.HexColor("#2563eb"))  # Azul enlace
            self.drawString(
                54,
                30,
                "— ¿DESEAS AGENDAR UNA ENTREVISTA POR VIDEOLLAMADA CON EL EQUIPO DE ESTUDIOS DE MERCADO? HAZ CLIC AQUÍ.",
            )
            self.linkURL("https://estudiosdemercado.phiqus.com/agenda", rect=(54, 25, 520, 35))

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
                foda_dict = {
                    "fortalezas": ["Base demográfica favorable."],
                    "oportunidades": ["Diferenciación de nicho."],
                    "debilidades": ["Costos iniciales."],
                    "amenazas": ["Competencia preexistente."],
                    "conclusion": str(foda),
                    "recomendacion_roi": "Monitorear retornos de inversión.",
                }

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
        kpi_data = [
            [
                Paragraph("SCORE VIABILIDAD", s_card_lbl),
                Paragraph("POBLACIÓN RESIDENTE", s_card_lbl),
                Paragraph("COMPETIDORES", s_card_lbl),
            ],
            [
                Paragraph(f"{analisis['sva']}/100", s_card_val),
                Paragraph(f"{analisis['poblacion_ponderada']:,}", s_card_val),
                Paragraph(f"{analisis['competidores_conteo']}", s_card_val),
            ],
        ]

        kpi_table = Table(kpi_data, colWidths=[168, 168, 168])
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
            desc_txt = "La ubicación analizada presenta un potencial sobresaliente. La alta concentración de la demanda y el balance óptimo con los competidores locales sugieren un entorno propicio para capturar mercado rápidamente."
        elif sva_val >= 50:
            status_txt = "<font color='#ca8a04'><b>MODERADA (REQUIERE DIFERENCIACIÓN)</b></font>"
            desc_txt = "El punto tiene un atractivo comercial intermedio. Existen flujos de demanda importantes, pero la competencia o los límites de atracción peatonal exigen una propuesta de valor única y estrategias activas de atracción."
        else:
            status_txt = "<font color='#dc2626'><b>RIESGOSA (VIABILIDAD BAJA)</b></font>"
            desc_txt = "Se identifican retos estructurales críticos. La saturación de competidores consolidados en el radio de influencia o la baja densidad poblacional en la zona sugieren explorar ubicaciones alternativas."

        story.append(Paragraph(f"<b>Diagnóstico preliminar:</b> {status_txt}", s_body))
        story.append(Paragraph(desc_txt, s_body))

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
        story.append(
            Paragraph(
                "Métrica compuesta de 0 a 100 que pondera demografía (40%), competencia (30%) y atractores de tráfico (30%).",
                s_body,
            )
        )
        story.append(Spacer(1, 8))

        pob_tot_val = analisis.get("poblacion_ponderada", 0)
        score_dem = analisis.get("score_demog", 50.0)
        comp_cont = analisis.get("competidores_conteo", 0)

        if score_dem >= 80:
            dem_est = f"Excelente densidad ({pob_tot_val:,} hab.)"
        elif score_dem >= 50:
            dem_est = f"Densidad aceptable ({pob_tot_val:,} hab.)"
        else:
            dem_est = f"Baja concentración ({pob_tot_val:,} hab.)"

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

        pilares_data = [
            [
                Paragraph("Pilar Analítico", s_table_header),
                Paragraph("Peso", s_table_header),
                Paragraph("Estatus en la Zona", s_table_header),
            ],
            [
                Paragraph("Pilar Demográfico", s_table_cell),
                Paragraph("40%", s_table_cell),
                Paragraph(dem_est, s_table_cell),
            ],
            [
                Paragraph("Pilar Competencia", s_table_cell),
                Paragraph("30%", s_table_cell),
                Paragraph(comp_est, s_table_cell),
            ],
            [
                Paragraph("Pilar Atractores e Inferencia", s_table_cell),
                Paragraph("30%", s_table_cell),
                Paragraph(inf_est, s_table_cell),
            ],
        ]
        pilares_table = Table(pilares_data, colWidths=[150, 80, 274])
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
        # --- Premium: segmentación sectorial dentro del perfil del cliente ---
        if orden.tier_adquirido == "premium":
            story.append(Spacer(1, 12))
            story.append(Paragraph("<b>Segmentos de Población Identificados:</b>", s_h2))
            story.append(
                Paragraph(
                    foda_dict.get(
                        "segmentacion_nicho",
                        "Población y segmento comercial cautivo detectados en el radio.",
                    ),
                    s_body,
                )
            )
            story.append(Spacer(1, 8))

            rubro_lower_seg = orden.rubro.lower()
            if "cafe" in rubro_lower_seg:
                segmentos = [
                    ("Jóvenes Profesionistas y Freelancers", "Muy Alta", "Consumo diario, trabajo remoto, coworking"),
                    ("Familias y Residentes locales", "Alta", "Reuniones de fin de semana, desayunos de convivencia"),
                    ("Trabajadores y Oficinistas cercanos", "Muy Alta", "Consumo en horas pico matutinas y almuerzo"),
                ]
            elif "farma" in rubro_lower_seg:
                segmentos = [
                    ("Familias con hijos", "Muy Alta", "Consumo constante de fórmulas, pediatría y consulta"),
                    ("Adultos Mayores / Seniors", "Muy Alta", "Medicamentos crónicos, consultas generales recurrentes"),
                    ("Jóvenes y Adultos Solteros", "Media", "Compras estacionales, higiene y cuidado personal"),
                ]
            elif "gym" in rubro_lower_seg or "gimnasio" in rubro_lower_seg:
                segmentos = [
                    ("Jóvenes Profesionistas (22-35 años)", "Muy Alta", "Fitness, entrenamiento post-oficina"),
                    ("Estudiantes universitarios", "Alta", "Entrenamiento en horas de bajo tráfico, tarifas promo"),
                    ("Residentes de Edad Avanzada", "Baja", "Clases de bajo impacto y mantenimiento de salud"),
                ]
            else:
                segmentos = [
                    ("Residentes locales principales", "Alta", "Consumo recurrente, conveniencia y abasto inmediato"),
                    ("Público Flotante / Transeúntes", "Media", "Compra espontánea por impulso y accesibilidad vial"),
                    ("Comercios aliados colindantes", "Media", "Intercambio de suministros e insumos directos"),
                ]

            segmento_table_data = [
                [
                    Paragraph("Segmento de Consumidor", s_table_header),
                    Paragraph("Afinidad Sectorial (Referencia)", s_table_header),
                    Paragraph("Justificación y Hábito de Consumo", s_table_header),
                ]
            ]
            for seg, afin, just in segmentos:
                segmento_table_data.append(
                    [
                        Paragraph(seg, s_table_cell),
                        Paragraph(afin, s_table_cell),
                        Paragraph(just, s_table_cell),
                    ]
                )
            seg_table = Table(segmento_table_data, colWidths=[150, 120, 234])
            seg_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                        ("PADDING", (0, 0), (-1, -1), 8),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )
            story.append(seg_table)

            if foda_dict.get("estrategia_precios"):
                story.append(Spacer(1, 8))
                story.append(Paragraph("<b>Estrategia de Posicionamiento Comercial:</b>", s_h2))
                story.append(Paragraph(foda_dict["estrategia_precios"], s_body))

        # =====================================================================
        # SECCIÓN 5 (DIFERIDA): DIAGNÓSTICO ESTRATÉGICO IA — se inserta al final
        # =====================================================================
        s_body_foda = ParagraphStyle("Body_Foda", parent=s_body, fontSize=8.2, leading=10.5, spaceAfter=2.5)
        ParagraphStyle("Bullet_Foda", parent=s_bullet, fontSize=7.8, leading=10, spaceAfter=2)
        s_h2_foda = ParagraphStyle("Heading2_Foda", parent=s_h2, fontSize=9.5, leading=12, spaceBefore=4, spaceAfter=2)

        bloque_diagnostico.append(Paragraph("5. DIAGNÓSTICO ESTRATÉGICO IA", s_h1))
        if foda_dict.get("_fuente") == "respaldo_cuantitativo":
            bloque_diagnostico.append(
                Paragraph(
                    "Diagnóstico elaborado con <b>métricas reales</b> de INEGI, Google Places y afluencia peatonal "
                    "(modo pruebas: servicios de IA en la nube omitidos).",
                    s_body_foda,
                )
            )
        else:
            bloque_diagnostico.append(
                Paragraph(
                    "La Inteligencia Artificial genera una evaluación estratégica cruzada adaptada al giro "
                    "comercial y las intenciones específicas ingresadas.",
                    s_body_foda,
                )
            )
        bloque_diagnostico.append(Spacer(1, 5))

        # Estilo para los títulos de los cuadrantes FODA
        s_quadrant_title = ParagraphStyle(
            "QuadrantTitle",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=2,
        )

        s_quadrant_body = ParagraphStyle(
            "QuadrantBody",
            fontName="Helvetica",
            fontSize=7.5,
            leading=9.5,
            textColor=colors.HexColor("#334155"),
        )

        # Extraer y limitar listas de FODA para que quepan perfectamente
        fort_list = foda_dict.get("fortalezas", [])[:3]
        op_list = foda_dict.get("oportunidades", [])[:3]
        deb_list = foda_dict.get("debilidades", [])[:3]
        am_list = foda_dict.get("amenazas", [])[:3]

        fortalezas_html = (
            "<br/>".join([f"• {f}" for f in fort_list]) if fort_list else "• Operación demográfica adecuada."
        )
        oportunidades_html = (
            "<br/>".join([f"• {o}" for o in op_list]) if op_list else "• Captación de mercado desatendido."
        )
        debilidades_html = (
            "<br/>".join([f"• {d}" for d in deb_list]) if deb_list else "• Presupuesto de adecuación inicial."
        )
        amenazas_html = "<br/>".join([f"• {a}" for a in am_list]) if am_list else "• Presión de comercios informales."

        foda_grid = [
            [
                Paragraph("💪 <b>FORTALEZAS</b>", s_quadrant_title),
                Paragraph("🚀 <b>OPORTUNIDADES</b>", s_quadrant_title),
            ],
            [
                Paragraph(fortalezas_html, s_quadrant_body),
                Paragraph(oportunidades_html, s_quadrant_body),
            ],
            [
                Paragraph("⚠️ <b>DEBILIDADES</b>", s_quadrant_title),
                Paragraph("🔥 <b>AMENAZAS</b>", s_quadrant_title),
            ],
            [
                Paragraph(debilidades_html, s_quadrant_body),
                Paragraph(amenazas_html, s_quadrant_body),
            ],
        ]

        foda_table = Table(foda_grid, colWidths=[250, 254])
        foda_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#f0fdf4")),
                    ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#eff6ff")),
                    ("BACKGROUND", (0, 2), (0, 2), colors.HexColor("#fff7ed")),
                    ("BACKGROUND", (1, 2), (1, 2), colors.HexColor("#fef2f2")),
                    ("PADDING", (0, 0), (-1, -1), 6),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOX", (0, 0), (0, 1), 1, colors.HexColor("#bbf7d0")),
                    ("BOX", (1, 0), (1, 1), 1, colors.HexColor("#bfdbfe")),
                    ("BOX", (0, 2), (0, 3), 1, colors.HexColor("#fed7aa")),
                    ("BOX", (1, 2), (1, 3), 1, colors.HexColor("#fecaca")),
                ]
            )
        )
        bloque_diagnostico.append(foda_table)
        bloque_diagnostico.append(Spacer(1, 8))

        bloque_diagnostico.append(Paragraph("Conclusión General del Diagnóstico:", s_h2_foda))
        bloque_diagnostico.append(
            Paragraph(foda_dict.get("conclusion", "Análisis de viabilidad concluido con éxito."), s_body_foda)
        )

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

        story.append(PageBreak())
        story.append(Paragraph("3. ANÁLISIS DE COMPETENCIA", s_h1))
        story.append(Paragraph("<b>Mapa de Ubicación y Competencia:</b>", s_h2))
        story.append(
            Paragraph(
                "A continuación se presenta el croquis del área comercial analizada. "
                "La ubicación propuesta de tu negocio se muestra marcada con un pin <font color='#2563eb'><b>AZUL (O)</b></font>, "
                "y los establecimientos competidores directos detectados en el radio de influencia se muestran marcados en <font color='#dc2626'><b>ROJO</b></font>.",
                s_body,
            )
        )
        story.append(Spacer(1, 15))

        # Dibujar croquis estilizado de fallback si no hay mapa estático (DEV_MODE)
        map_grid_fallback = [
            ["", "", "NORTE", "", ""],
            ["", "Zona Residencial (Demanda)", "", "Corredor Comercial", ""],
            [
                "OESTE",
                "",
                f"[ PUNTO DE INTERÉS ]\n({orden.latitud}, {orden.longitud})\nRadio: {orden.radio_metros}m",
                "",
                "ESTE",
            ],
            ["", "Vías de Acceso Primario", "", "Competidor Cercano", ""],
            ["", "", "SUR", "", ""],
        ]
        map_table_fallback = Table(
            map_grid_fallback, colWidths=[100, 100, 104, 100, 100], rowHeights=[40, 60, 100, 60, 40]
        )
        map_table_fallback.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (2, 2), (2, 2), colors.HexColor("#dbeafe")),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                    ("BOX", (2, 2), (2, 2), 2, colors.HexColor("#2563eb")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ]
            )
        )

        map_bytes = analisis.get("map_bytes")
        if map_bytes:
            try:
                from reportlab.platypus import Image

                img_data = io.BytesIO(map_bytes)
                img = Image(img_data, width=450, height=300)
                img.hAlign = "CENTER"
                story.append(img)
            except Exception as img_err:
                logger.error(f"Error al renderizar mapa estático en PDF: {img_err}")
                story.append(map_table_fallback)
        else:
            logger.info(
                "ReportLab: No se detectaron bytes de mapa estático real. Renderizando croquis de fallback."
            )
            story.append(map_table_fallback)

        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Competencia Detallada en la Zona:</b>", s_h2))
        story.append(
            Paragraph(
                "Visualización detallada de los establecimientos competidores mapeados. "
                "Los datos se obtienen identificando tipos comerciales equivalentes según las clasificaciones oficiales de actividad económica.",
                s_body,
            )
        )
        if getattr(orden, "competidores_adicionales", None):
            story.append(
                Paragraph(
                    f"<b>Competidores específicos o marcas a considerar:</b> {orden.competidores_adicionales}",
                    s_body,
                )
            )
            story.append(Spacer(1, 5))

        comp_list = analisis.get("competidores_listado", [])

        comp_table_data = [
            [
                Paragraph("Nombre del Establecimiento", s_table_header),
                Paragraph("Giro / Tipo Comercial", s_table_header),
                Paragraph("Calificación / Atractor", s_table_header),
            ],
            [
                Paragraph("<b>🎯 COMPETIDORES DIRECTOS DETECTADOS</b>", s_quadrant_title),
                Paragraph("", s_table_cell),
                Paragraph("", s_table_cell),
            ],
        ]

        real_directs = comp_list[:4]
        if not real_directs:
            comp_table_data.append(
                [
                    Paragraph(
                        "<font color='#64748b'><i>Sin competidores directos detectados</i></font>", s_table_cell
                    ),
                    Paragraph("—", s_table_cell),
                    Paragraph("—", s_table_cell),
                ]
            )
        else:
            for item in real_directs:
                comp_table_data.append(
                    [
                        Paragraph(item.get("nombre", "Comercio Local"), s_table_cell),
                        Paragraph(item.get("tipo", orden.rubro.capitalize()), s_table_cell),
                        Paragraph(
                            f"⭐ {item.get('rating', 0.0)} / 5.0 ({item.get('user_ratings_total', 15)} reseñas)",
                            s_table_cell,
                        ),
                    ]
                )

        comp_table_data.append(
            [
                Paragraph(
                    "<b>🤝 ESTABLECIMIENTOS COMPLEMENTARIOS (ALIADOS REALES DETECTADOS)</b>", s_quadrant_title
                ),
                Paragraph("", s_table_cell),
                Paragraph("", s_table_cell),
            ],
        )

        # Usar aliados reales detectados por la API de Google Places
        aliados_reales = analisis.get("aliados_listado", [])

        if aliados_reales:
            for aliado in aliados_reales:
                rating_str = f"⭐ {aliado['rating']} / 5.0" if aliado["rating"] > 0 else "Sin calificación"
                reviews_str = (
                    f"({aliado['user_ratings_total']} reseñas)" if aliado["user_ratings_total"] > 0 else ""
                )
                comp_table_data.append(
                    [
                        Paragraph(aliado["nombre"], s_table_cell),
                        Paragraph(aliado["tipo"], s_table_cell),
                        Paragraph(f"{rating_str} {reviews_str}".strip(), s_table_cell),
                    ]
                )
        else:
            comp_table_data.append(
                [
                    Paragraph(
                        "<font color='#64748b'><i>No se detectaron establecimientos complementarios (bancos, "
                        "escuelas o transporte) en el radio analizado. Se recomienda un enfoque de "
                        "marketing autónomo para la captación de tráfico peatonal.</i></font>",
                        s_table_cell,
                    ),
                    Paragraph("", s_table_cell),
                    Paragraph("", s_table_cell),
                ]
            )

        num_direct_rows = len(real_directs) if real_directs else 1
        comp_table = Table(comp_table_data, colWidths=[180, 160, 174])
        comp_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("SPAN", (0, 1), (2, 1)),
                    ("SPAN", (0, num_direct_rows + 2), (2, num_direct_rows + 2)),
                    ("BACKGROUND", (0, 1), (2, 1), colors.HexColor("#f1f5f9")),
                    (
                        "BACKGROUND",
                        (0, num_direct_rows + 2),
                        (2, num_direct_rows + 2),
                        colors.HexColor("#f1f5f9"),
                    ),
                    ("PADDING", (0, 0), (-1, -1), 5),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )

        story.append(comp_table)
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

        total_comp = len(comp_list)
        if total_comp == 0:
            densidad_txt = "Excelente (Sin competencia detectada en el radio)"
        elif total_comp <= 3:
            densidad_txt = "Baja saturación (Baja fricción en el cuadrante)"
        elif total_comp <= 8:
            densidad_txt = "Saturación moderada (Fricción intermedia, requiere diferenciación)"
        else:
            densidad_txt = "Alta saturación (Competencia intensa en el cuadrante)"

        isc_val = analisis.get("isc", 0.0)
        isc_formato = f"{isc_val:.6f}" if isc_val > 0 else "0.000000"

        saturacion_table_data = [
            [
                Paragraph("Métrica de Fricción Espacial", s_table_header),
                Paragraph("Valor Analítico Real", s_table_header),
                Paragraph("Estatus de Competencia", s_table_header),
            ],
            [
                Paragraph("Competidores Cercanos (< 250m)", s_table_cell),
                Paragraph(f"{inmediatos} establecimientos", s_table_cell),
                Paragraph(
                    "Fricción inmediata alta" if inmediatos > 0 else "Entorno libre de fricción", s_table_cell
                ),
            ],
            [
                Paragraph("Competidores Intermedios (250m - 500m)", s_table_cell),
                Paragraph(f"{cercanos} establecimientos", s_table_cell),
                Paragraph("Fricción intermedia" if cercanos > 0 else "Entorno despejado", s_table_cell),
            ],
            [
                Paragraph("Competidores Periféricos (> 500m)", s_table_cell),
                Paragraph(f"{perifericos} establecimientos", s_table_cell),
                Paragraph("Fricción periférica" if perifericos > 0 else "Sin competidores lejanos", s_table_cell),
            ],
            [
                Paragraph("Distancia al Competidor Cercano", s_table_cell),
                Paragraph(dist_txt, s_table_cell),
                Paragraph(
                    "Excelente distancia"
                    if (distancia_cercana > 400 or distancia_cercana == -1)
                    else "Competidor inmediato",
                    s_table_cell,
                ),
            ],
            [
                Paragraph("Índice de Saturación Comercial (ISC)", s_table_cell),
                Paragraph(isc_formato, s_table_cell),
                Paragraph(densidad_txt, s_table_cell),
            ],
        ]

        saturacion_table = Table(saturacion_table_data, colWidths=[200, 150, 154])
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
                ("Mal valorados (< 3.0 o sin rating)", 0.0, 3.0, "Oportunidad de captar clientes insatisfechos"),
                ("Aceptables (3.0 - 3.9)", 3.0, 4.0, "Competencia vulnerable a diferenciación"),
                ("Bien valorados (4.0 - 4.4)", 4.0, 4.5, "Competencia consolidada"),
                ("Excelentes (4.5 - 5.0)", 4.5, 5.1, "Competencia de alto posicionamiento"),
            ]

            calidad_data = [
                [
                    Paragraph("Rango de Calificación", s_table_header),
                    Paragraph("Competidores", s_table_header),
                    Paragraph("% del Total", s_table_header),
                    Paragraph("Lectura Estratégica", s_table_header),
                ]
            ]
            for etiqueta, lim_inf, lim_sup, lectura in rangos_def:
                cnt = sum(1 for c in comp_list if lim_inf <= float(c.get("rating", 0) or 0) < lim_sup)
                pct = round(cnt / total_c * 100) if total_c else 0
                calidad_data.append(
                    [
                        Paragraph(etiqueta, s_table_cell),
                        Paragraph(f"{cnt}", s_table_cell),
                        Paragraph(f"{pct}%", s_table_cell),
                        Paragraph(lectura, s_table_cell),
                    ]
                )

            ratings_validos = [float(c.get("rating", 0) or 0) for c in comp_list if c.get("rating")]
            rating_prom = round(sum(ratings_validos) / len(ratings_validos), 2) if ratings_validos else 0
            resenas_tot = sum(int(c.get("user_ratings_total", 0) or 0) for c in comp_list)
            calidad_data.append(
                [
                    Paragraph("<b>Promedio de la zona</b>", s_table_cell),
                    Paragraph(f"<b>{rating_prom} / 5.0</b>", s_table_cell),
                    Paragraph(f"<b>{resenas_tot:,}</b>", s_table_cell),
                    Paragraph("Total de reseñas acumuladas en la zona", s_table_cell),
                ]
            )

            calidad_table = Table(calidad_data, colWidths=[160, 80, 70, 194])
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
        else:
            story.append(Spacer(1, 15))
            story.append(
                Paragraph(
                    "<font color='#16a34a'><b>Océano Azul Detectado:</b></font> No se detectaron competidores directos "
                    "en el radio de influencia. Este entorno libre de competencia representa una oportunidad "
                    "privilegiada para capturar mercado sin fricción directa.",
                    s_body,
                )
            )

        story.append(Paragraph("<b>Recomendación de Posicionamiento Estratégico:</b>", s_h2))
        story.append(
            Paragraph(
                "El modelo de atracción comercial evalúa la probabilidad de éxito basándose en la ubicación. "
                "En áreas de fricción media/alta, se recomienda un enfoque en valor agregado e "
                "identidad de marca para maximizar la tasa de conversión sin entrar en guerras de precios destructivas.",
                s_body,
            )
        )
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

        aliados_conteos = analisis.get("aliados_conteos", {})

        poi_table_data = [
            [
                Paragraph("Categoría de Punto de Interés (Atractor)", s_table_header),
                Paragraph("Conteo en Radio", s_table_header),
                Paragraph("Peso IAT", s_table_header),
            ],
        ]

        # Iterar las categorías de aliados REALMENTE detectadas (aliados_conteos contiene
        # las categorías ya resueltas por IA o seleccionadas), nunca el token interno 'ia_auto'.
        conteos_reales = {k: v for k, v in aliados_conteos.items() if k != "ia_auto"}
        if orden.tier_adquirido == "premium" and conteos_reales:
            for ally_type, cnt in conteos_reales.items():
                tipo_nombre = ally_type.replace("_", " ").title()
                # Determinar un peso de IAT semántico basado en el tipo
                peso_iat = "Alto (Tráfico comercial)"
                if any(x in ally_type for x in ["transit", "subway", "bus", "station"]):
                    peso_iat = "Muy Alto (Flujo continuo)"
                elif any(x in ally_type for x in ["bank", "finance"]):
                    peso_iat = "Alto (Tráfico transaccional)"
                elif any(x in ally_type for x in ["school", "university"]):
                    peso_iat = "Medio (Tráfico matutino/tarde)"

                poi_table_data.append(
                    [
                        Paragraph(tipo_nombre, s_table_cell),
                        Paragraph(f"{cnt} detectados", s_table_cell),
                        Paragraph(peso_iat, s_table_cell),
                    ]
                )
        else:
            real_bancos = analisis.get("bancos_conteo", 0)
            real_escuelas = analisis.get("escuelas_conteo", 0)
            real_transporte = analisis.get("transporte_conteo", 0)
            poi_table_data.extend(
                [
                    [
                        Paragraph("Bancos e Instituciones Financieras", s_table_cell),
                        Paragraph(f"{real_bancos} bancos detectados", s_table_cell),
                        Paragraph("Alto (Tráfico transaccional)", s_table_cell),
                    ],
                    [
                        Paragraph("Escuelas e Instituciones Educativas", s_table_cell),
                        Paragraph(f"{real_escuelas} escuelas detectadas", s_table_cell),
                        Paragraph("Medio (Tráfico matutino/tarde)", s_table_cell),
                    ],
                    [
                        Paragraph("Paradas de Transporte Público", s_table_cell),
                        Paragraph(f"{real_transporte} paradas detectadas", s_table_cell),
                        Paragraph("Muy Alto (Flujo continuo)", s_table_cell),
                    ],
                ]
            )

        poi_table = Table(poi_table_data, colWidths=[200, 120, 184])
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
        story.append(Paragraph("Conclusión del Forecast del Mercado:", s_h2))

        # Conclusión coherente con los atractores realmente detectados
        total_atractores_zona = sum(v for k, v in aliados_conteos.items() if k != "ia_auto") or (
            analisis.get("bancos_conteo", 0) + analisis.get("escuelas_conteo", 0) + analisis.get("transporte_conteo", 0)
        )
        if total_atractores_zona > 0:
            conclusion_forecast = (
                f"La confluencia de {total_atractores_zona} atractores detectados en el radio geográfico y el volumen "
                "de población residente sustentan un piso de ventas favorable. Se proyecta que el nicho comercial "
                "sea capturado de manera estable en un mediano plazo."
            )
        else:
            conclusion_forecast = (
                "No se detectaron atractores de tráfico consolidados en el radio analizado, por lo que el flujo de "
                "clientes dependerá principalmente de la población residente y de la capacidad propia del negocio "
                "para generar tracción (marketing local y diferenciación)."
            )
        story.append(Paragraph(conclusion_forecast, s_body))

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
                    Paragraph("Diagnóstico de Flujo", s_table_header),
                ],
                [
                    Paragraph("Mañana (08:00 - 12:00)", s_table_cell),
                    Paragraph(f"{int_manana}%", s_table_cell),
                    Paragraph("Flujo de tránsito y escuelas", s_table_cell),
                ],
                [
                    Paragraph("Mediodía (12:00 - 16:00)", s_table_cell),
                    Paragraph(f"{int_mediodia}%", s_table_cell),
                    Paragraph("Hora pico de almuerzo y comercio", s_table_cell),
                ],
                [
                    Paragraph("Tarde (16:00 - 20:00)", s_table_cell),
                    Paragraph(f"{int_tarde}%", s_table_cell),
                    Paragraph("Salida laboral, máxima afluencia", s_table_cell),
                ],
                [
                    Paragraph("Noche (20:00 - 24:00)", s_table_cell),
                    Paragraph(f"{int_noche}%", s_table_cell),
                    Paragraph("Descenso y cierre comercial", s_table_cell),
                ],
            ]
            afluencia_table = Table(afluencia_table_data, colWidths=[150, 150, 204])
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
                        Paragraph("Interpretación de Flujo", s_table_header),
                    ]
                ]
                for dia, picos, tranquilas, interp in filas_horas:
                    horas_data.append(
                        [
                            Paragraph(dia, s_table_cell),
                            Paragraph(picos, s_table_cell),
                            Paragraph(tranquilas, s_table_cell),
                            Paragraph(interp, s_table_cell),
                        ]
                    )
                horas_table = Table(horas_data, colWidths=[80, 160, 130, 134])
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

        # Extras Premium en sección 5 (Diagnóstico IA): fricciones del sector
        bloque_diagnostico.append(Spacer(1, 10))
        bloque_diagnostico.append(Paragraph("<b>Fricciones Frecuentes del Sector (Análisis Generado por IA):</b>", s_h2))
        bloque_diagnostico.append(
            Paragraph(
                "Síntesis generada por Inteligencia Artificial de las fricciones y quejas más comunes que los "
                "consumidores suelen reportar en este giro comercial. No corresponden a reseñas textuales de "
                "establecimientos específicos de la zona; utilízalas como referencia para diseñar tu propuesta "
                "de valor superando las debilidades típicas del sector.",
                s_body,
            )
        )
        quejas_list = foda_dict.get("top_quejas_competidores", []) or [
            "El servicio es extremadamente lento en las horas pico.",
            "Los precios no corresponden a la calidad de los productos.",
            "El espacio físico es demasiado reducido e incómodo.",
            "Falta de variedad en el menú y opciones de especialidad.",
            "No cuentan con estacionamiento ni facilidades de acceso.",
        ]
        quejas_data = [
            [
                Paragraph(f"<font color='#ef4444'><b>Fricción #{i + 1}:</b></font>", s_table_cell),
                Paragraph(f"<i>{queja}</i>", s_table_cell),
            ]
            for i, queja in enumerate(quejas_list)
        ]
        quejas_table = Table(quejas_data, colWidths=[90, 414])
        quejas_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff5f5")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#fecaca")),
                    ("PADDING", (0, 0), (-1, -1), 4),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        bloque_diagnostico.append(quejas_table)

        if foda_dict.get("dictamen_final"):
            bloque_diagnostico.append(Spacer(1, 8))
            bloque_diagnostico.append(Paragraph("<b>Dictamen Final del Consultor:</b>", s_h2))
            bloque_diagnostico.append(Paragraph(foda_dict["dictamen_final"], s_body))

        logger.info("ReportLab: Compilación Premium exitosa.")
        return _cerrar_reporte()
