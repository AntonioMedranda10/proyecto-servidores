from sqlalchemy import Column, Integer, String, Boolean, TIMESTAMP, func
from ..database import Base

class EstadoReserva(Base):
    __tablename__ = "estado_reserva"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), unique=True, nullable=False)
    color_hex = Column(String(7))
    permite_edicion = Column(Boolean, default=True)
    es_final = Column(Boolean, default=False)
    orden = Column(Integer, default=0)
    creado_en = Column(TIMESTAMP, server_default=func.current_timestamp())
    actualizado_en = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
