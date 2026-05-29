from sqlalchemy import Column, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class OrdenPago(Base):
    """
    Modelo ORM para representar la tabla 'ordenes_pagos'.
    Registra el estado de cobro, el Tier contratado y las variables del punto analizado.
    """

    __tablename__ = "ordenes_pagos"

    id = Column(Integer, primary_key=True, index=True)
    cognito_user_id = Column(String(100), nullable=False, index=True)
    checkout_id = Column(String(100), unique=True, nullable=False)
    monto = Column(Numeric(10, 2), nullable=False)
    estado_pago = Column(String(20), nullable=False, default="pending")  # 'pending', 'approved', 'rejected'
    tier_adquirido = Column(String(20), nullable=False)  # 'basico', 'pro', 'premium'
    latitud = Column(Numeric(9, 6), nullable=False)
    longitud = Column(Numeric(9, 6), nullable=False)
    radio_metros = Column(Integer, nullable=False)
    rubro = Column(String(50), nullable=False)
    intenciones = Column(Text, nullable=True)
    email = Column(String(255), nullable=False, default="demo_sva@geoviabilidad.com")
    s3_key_reporte = Column(String(255), nullable=True)
    fecha_creacion = Column(DateTime, server_default=func.now())
    fecha_aprobacion = Column(DateTime, nullable=True)
