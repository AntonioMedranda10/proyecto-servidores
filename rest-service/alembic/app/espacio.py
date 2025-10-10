from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP, func
from sqlalchemy.orm import relationship
from ..database import Base

class Espacio(Base):
    __tablename__ = "espacio"
    
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(50), unique=True, nullable=False, index=True)
    nombre = Column(String(200), nullable=False)
    categoria_id = Column(Integer, ForeignKey("categoria_espacio.id"), nullable=False)
    capacidad_maxima = Column(Integer, nullable=False)
    imagen_url = Column(String(500))
    estado = Column(String(20), nullable=False, default="activo")
    # referencia_id referenced a table 'referencia' which is not present in this service.
    # If 'referencia' belongs to another microservice, don't enforce a DB-level foreign key here.
    referencia_id = Column(Integer, nullable=True)
    creado_en = Column(TIMESTAMP, server_default=func.current_timestamp())
    actualizado_en = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    categoria = relationship("CategoriaEspacio", back_populates="espacios")
    caracteristicas = relationship("CaracteristicaEspacio", back_populates="espacio", cascade="all, delete-orphan")
