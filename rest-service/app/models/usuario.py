from sqlalchemy import Column, Integer, String, ForeignKey, TIMESTAMP, func, Enum as SQLEnum
from sqlalchemy.orm import relationship
from ..database import Base
import enum

class EstadoUsuario(str, enum.Enum):
    activo = "activo"
    inactivo = "inactivo"
    bloqueado = "bloqueado"

class Usuario(Base):
    __tablename__ = "usuario"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100), nullable=False)
    telefono = Column(String(20))
    tipo_usuario_id = Column(Integer, ForeignKey("tipo_usuario.id"), nullable=False)
    estado = Column(String(20), nullable=False, default="activo")
    avatar_url = Column(String(500))
    creado_en = Column(TIMESTAMP, server_default=func.current_timestamp())
    actualizado_en = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Relaciones
    tipo_usuario = relationship("TipoUsuario", back_populates="usuarios")
    reservas = relationship("Reserva", back_populates="usuario")
    notificaciones = relationship("Notificacion", back_populates="usuario")