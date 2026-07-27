"""Legacy bedrock client — re-exports from clients/v0/bedrock only.

No importa app.services. Para FODA orquestado (LLM + narrative), usar
``app.services.foda_service.generar_analisis_foda``.
"""

from app.clients.v0.bedrock.bedrock_client_processed import (  # noqa: F401
    determinar_categorias_ia,
    filtrar_y_validar_categorias,
    generar_consideraciones_apertura,
    invocar_foda_llm_raw,
    sanitizar_input_usuario,
    validar_schema_foda,
    verificar_guardrail_groq,
)

# Alias legacy usado por report_pdf_service
_generar_consideraciones_apertura = generar_consideraciones_apertura
