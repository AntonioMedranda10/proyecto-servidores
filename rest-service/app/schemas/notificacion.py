# app/schemas/notificacion.py
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class NotificacionCreate(BaseModel):
    """Schema para crear una notificación"""
    usuario_id: Optional[int] = None
    titulo: str
    mensaje: str
    leida: Optional[bool] = False
    reserva_id: Optional[int] = None
    espacio_id: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = {}

class NotificacionResponse(BaseModel):
    """Schema de respuesta de notificación"""
    id: int
    usuario_id: int
    titulo: str
    mensaje: str
    leida: bool
    reserva_id: Optional[int] = None
    espacio_id: Optional[int] = None
    metadata: Dict[str, Any]
    leida_at: Optional[datetime] = None
    creado_en: datetime

    class Config:
        from_attributes = True