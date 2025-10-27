from sqlalchemy import Column, Integer, String, Text, Boolean, TIMESTAMP, func
from ..database import Base

class TipoEvento(Base):
    __tablename__ = "tipo_evento"
    
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), unique=True, nullable=False)
    descripcion = Column(Text)
    requiere_aprobacion = Column(Boolean, default=False)
    color_hex = Column(String(7), default="#3B82F6")
    creado_en = Column(TIMESTAMP, server_default=func.current_timestamp())
    actualizado_en = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
