from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from ..database import Base

class TipoUsuario(Base):
    __tablename__ = "tipo_usuario"
    
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), unique=True, nullable=False)
    descripcion = Column(Text)
    nivel_prioridad = Column(Integer, nullable=False, default=1)
    permisos = Column(JSONB, default={})
    creado_en = Column(TIMESTAMP, server_default=func.current_timestamp())
    actualizado_en = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    usuarios = relationship("Usuario", back_populates="tipo_usuario")
