from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, TIMESTAMP, func
from sqlalchemy.orm import relationship
from ..database import Base

class CaracteristicaEspacio(Base):
    __tablename__ = "caracteristica_espacio"
    
    id = Column(Integer, primary_key=True, index=True)
    espacio_id = Column(Integer, ForeignKey("espacio.id"), nullable=False)
    nombre = Column(String(100), nullable=False)
    disponible = Column(Boolean, default=True)
    descripcion = Column(Text)
    creado_en = Column(TIMESTAMP, server_default=func.current_timestamp())
    actualizado_en = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    espacio = relationship("Espacio", back_populates="caracteristicas")
