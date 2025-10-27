from pydantic import BaseModel
from datetime import date, time
from typing import Optional

class ReservaCreate(BaseModel):
    espacio_id: int
    tipo_evento_id: Optional[int] = None
    fecha: date
    hora_inicio: time
    hora_fin: time
    titulo: Optional[str] = None
    descripcion: Optional[str] = None
    es_bloqueo: bool = False
    motivo_bloqueo: Optional[str] = None
    asistentes_estimada: Optional[int] = None

class ReservaResponse(BaseModel):
    id: int
    codigo: str
    usuario_id: int
    espacio_id: int
    tipo_evento_id: Optional[int]
    estado_id: Optional[int]
    fecha: date
    hora_inicio: time
    hora_fin: time
    titulo: Optional[str]
    descripcion: Optional[str]
    es_bloqueo: bool

class ReservaEstadoUpdate(BaseModel):
    estado_id: int
