from sqlalchemy import Column, Integer, String, Text, Boolean, TIMESTAMP, func
from sqlalchemy.orm import relationship
from ..database import Base

class CategoriaEspacio(Base):
    __tablename__ = "categoria_espacio"
    
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), unique=True, nullable=False)
    descripcion = Column(Text)
    requiere_aprobacion = Column(Boolean, default=False)
    capacidad_maxima = Column(Integer)
    creado_en = Column(TIMESTAMP, server_default=func.current_timestamp())
    actualizado_en = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    espacios = relationship("Espacio", back_populates="categoria")
