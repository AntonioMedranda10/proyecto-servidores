from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, TIMESTAMP, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from ..database import Base

class Notificacion(Base):
    __tablename__ = 'notificacion'

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey('usuario.id'), nullable=False)
    titulo = Column(String(250))
    mensaje = Column(Text)
    leida = Column(Boolean, default=False)
    reserva_id = Column(Integer, nullable=True)
    espacio_id = Column(Integer, nullable=True)
    # Renombrado: metadata es palabra reservada en SQLAlchemy
    metadata_info = Column("metadata", JSONB, default={})
    leida_at = Column(TIMESTAMP)
    creado_en = Column(TIMESTAMP, server_default=func.current_timestamp())

    usuario = relationship('Usuario', back_populates='notificaciones')