import logging
import os
import sys
from decimal import Decimal

# Set PYTHONPATH to current directory to resolve imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal
from app.models import OrdenPago
from app.tasks import generar_informe_task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_pdf")


def run_tier_test(tier: str, radio: int):
    logger.info("=========================================================")
    logger.info(f"🧪 INICIANDO PRUEBA DE GENERACIÓN PARA TIER: {tier.upper()} 🧪")
    logger.info("=========================================================")

    db = SessionLocal()
    try:
        # 1. Crear una orden de prueba en estado 'pending'
        checkout_id = f"chk_test_{tier}_{os.urandom(3).hex()}"
        monto = Decimal("99.00") if tier == "basico" else (Decimal("249.00") if tier == "pro" else Decimal("499.00"))

        orden = OrdenPago(
            cognito_user_id="usr_test_999",
            email="cliente_test@geoviabilidad.com",
            checkout_id=checkout_id,
            monto=monto,
            estado_pago="pending",
            tier_adquirido=tier,
            latitud=Decimal("19.432608"),  # Zócalo CDMX
            longitud=Decimal("-99.133208"),
            radio_metros=radio,
            rubro="cafeteria",
            intenciones="Quiero abrir una cafetería gourmet especializada en café de especialidad veracruzano, con ambiente minimalista y opciones para coworking.",
        )

        db.add(orden)
        db.commit()
        db.refresh(orden)

        logger.info(f"Orden de prueba guardada con ID: {orden.id}, checkout_id: {checkout_id}")

        # 2. Detonar la tarea en segundo plano asíncrona (se ejecutará síncronamente en el test)
        logger.info(f"Ejecutando tarea asíncrona generar_informe_task para ID {orden.id}...")
        generar_informe_task(orden.id)

        # 3. Refrescar orden y verificar resultados
        db.refresh(orden)
        logger.info(f"Estado de pago de la orden después de la tarea: {orden.estado_pago}")
        logger.info(f"Ruta de reporte guardada: {orden.s3_key_reporte}")

        assert orden.estado_pago == "approved", "Falla: La orden no fue aprobada por la tarea."
        assert orden.s3_key_reporte is not None, "Falla: s3_key_reporte no fue guardado en base de datos."

        # 4. Validar existencia física del PDF local (por estar en DEV_MODE)
        pdf_path = f"scratch/reports/{checkout_id}_reporte.pdf"
        assert os.path.exists(pdf_path), f"Falla: El archivo PDF no se guardó localmente en: {pdf_path}"
        pdf_size = os.path.getsize(pdf_path)
        logger.info(f"PDF generado correctamente en: {pdf_path} ({pdf_size:,} bytes)")
        assert pdf_size > 0, "Falla: El archivo PDF está vacío (0 bytes)."

        # 5. Validar existencia física del correo HTML local
        email_path = f"scratch/emails/email_orden_{orden.id}.html"
        assert os.path.exists(email_path), f"Falla: El archivo HTML de correo no se guardó localmente en: {email_path}"
        email_size = os.path.getsize(email_path)
        logger.info(f"HTML de correo de SES generado en: {email_path} ({email_size:,} bytes)")
        assert email_size > 0, "Falla: El archivo de correo está vacío (0 bytes)."

        logger.info(f"✅ ¡PRUEBA EXITOSA PARA TIER {tier.upper()}! ✅\n")

    except Exception as e:
        logger.error(f"❌ ERROR EN PRUEBA DE TIER {tier.upper()}: {e}")
        db.rollback()
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Iniciando bateria de pruebas de generación de informes...")
    try:
        run_tier_test("basico", 1000)
        run_tier_test("pro", 1000)
        run_tier_test("premium", 1000)
        logger.info("=========================================================")
        logger.info("🎉 ¡TODAS LAS PRUEBAS DE TIER SE COMPLETARON CON ÉXITO! 🎉")
        logger.info("=========================================================")
    except Exception:
        sys.exit(1)
