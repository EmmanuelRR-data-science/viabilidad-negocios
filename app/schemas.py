from pydantic import BaseModel, Field, field_validator


class PreferenciaCreate(BaseModel):
    """
    Schema de validación de entrada para crear una preferencia de cobro para un punto.
    """

    latitud: float = Field(..., description="Latitud decimal del marcador", ge=-90, le=90)
    longitud: float = Field(..., description="Longitud decimal del marcador", ge=-180, le=180)
    radio_metros: int = Field(..., description="Radio de cobertura en metros", ge=100, le=5000)
    rubro: str = Field(..., description="Giro comercial o nicho del negocio (ej. Cafetería, Gimnasio)")
    tier_adquirido: str = Field(..., description="Tier de visualización y análisis ('basico', 'pro', 'premium')")
    intenciones: str | None = Field(None, description="Intenciones o ideas de negocio adicionales en lenguaje natural")

    @field_validator("tier_adquirido")
    @classmethod
    def validate_tier(cls, v: str) -> str:
        v_lower = v.lower().strip()
        if v_lower not in ["basico", "pro", "premium"]:
            raise ValueError("El tier_adquirido debe ser 'basico', 'pro' o 'premium'.")
        return v_lower


class PreferenciaResponse(BaseModel):
    """
    Schema de respuesta tras registrar exitosamente una orden de pago pendiente.
    """

    orden_id: int
    checkout_id: str
    monto: float
    estado_pago: str
    init_point: str = Field(..., description="Enlace dinámico de Mercado Pago para realizar el cobro")


class WebhookMockTrigger(BaseModel):
    """
    Schema para simular webhooks de pago aprobados de forma sencilla en desarrollo.
    """

    checkout_id: str
    estado_pago: str = Field("approved", description="Estado a inyectar ('approved', 'rejected')")
