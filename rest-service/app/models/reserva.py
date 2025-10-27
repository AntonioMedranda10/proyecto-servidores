from sqlalchemy import Column, Integer, String, ForeignKey, Date, Time, Boolean, Text, TIMESTAMP, func
from sqlalchemy.orm import relationship
from ..database import Base

class Reserva(Base):
    __tablename__ = "reserva"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(100), unique=True, nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuario.id"), nullable=False)
    espacio_id = Column(Integer, ForeignKey("espacio.id"), nullable=False)
    tipo_evento_id = Column(Integer, ForeignKey("tipo_evento.id"))
    estado_id = Column(Integer, ForeignKey("estado_reserva.id"))
    fecha = Column(Date, nullable=False)
    hora_inicio = Column(Time, nullable=False)
    hora_fin = Column(Time, nullable=False)
    titulo = Column(String(250))
    descripcion = Column(Text)
    es_bloqueo = Column(Boolean, default=False)
    motivo_bloqueo = Column(String(500))
    asistentes_estimada = Column(Integer, nullable=True)
    creado_en = Column(TIMESTAMP, server_default=func.current_timestamp())
    actualizado_en = Column(TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp())

    usuario = relationship("Usuario")
    espacio = relationship("Espacio")
    tipo_evento = relationship("TipoEvento")
    estado = relationship("EstadoReserva")

    //