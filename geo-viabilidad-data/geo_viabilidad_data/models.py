from sqlalchemy import Column, DateTime, Integer, Numeric, String, Text, func

from geo_viabilidad_data.database import Base


class OrdenPago(Base):
    """Orden de cobro y reporte de viabilidad."""

    __tablename__ = "ordenes_pagos"

    id = Column(Integer, primary_key=True, index=True)
    cognito_user_id = Column(String(100), nullable=False, index=True)
    checkout_id = Column(String(100), unique=True, nullable=False)
    monto = Column(Numeric(10, 2), nullable=False)
    estado_pago = Column(String(20), nullable=False, default="pending")
    tier_adquirido = Column(String(20), nullable=False)
    latitud = Column(Numeric(9, 6), nullable=False)
    longitud = Column(Numeric(9, 6), nullable=False)
    radio_metros = Column(Integer, nullable=False)
    rubro = Column(String(50), nullable=False)
    intenciones = Column(Text, nullable=True)
    email = Column(String(255), nullable=False, default="demo_sva@geoviabilidad.com")
    s3_key_reporte = Column(String(255), nullable=True)
    competidores_seleccionados = Column(Text, nullable=True)
    aliados_seleccionados = Column(Text, nullable=True)
    competidores_adicionales = Column(Text, nullable=True)
    aliados_adicionales = Column(Text, nullable=True)
    modo_analisis_aliados = Column(String(20), nullable=False, default="automatico")
    config_aliados_guiados = Column(Text, nullable=True)
    resultado_json = Column(Text, nullable=True)
    foda_json = Column(Text, nullable=True)
    fecha_creacion = Column(DateTime, server_default=func.now())
    fecha_aprobacion = Column(DateTime, nullable=True)


class AppUsuario(Base):
    """Usuario autenticado con Google Sign-In."""

    __tablename__ = "app_usuarios"

    id = Column(Integer, primary_key=True, index=True)
    google_sub = Column(String(128), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    nombre = Column(String(255), nullable=True)
    avatar_url = Column(String(512), nullable=True)
    primera_sesion = Column(DateTime, server_default=func.now())
    ultima_sesion = Column(DateTime, server_default=func.now(), onupdate=func.now())
