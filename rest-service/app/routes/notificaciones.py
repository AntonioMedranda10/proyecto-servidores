from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from ..database import get_db
from ..schemas.notificacion import NotificacionCreate, NotificacionResponse
from ..services.notification_service import create_notification, emit_webhook
from .. import models
from ..utils.dependencies import get_current_user

router = APIRouter(prefix="/api/notificaciones", tags=["notificaciones"])


@router.post("", response_model=dict)
def post_notificacion(payload: NotificacionCreate, db: Session = Depends(get_db), current_user: models.usuario.Usuario = Depends(get_current_user)):
    """Crear una notificación en la BD y emitir webhook al servicio WebSocket.

    Sólo el propio usuario o un administrador pueden crear notificaciones para un usuario.
    """
    # permiso: si el payload.usuario_id no es el del current_user, sólo admins (nivel_prioridad == 1) pueden hacerlo
    if payload.usuario_id is not None and payload.usuario_id != current_user.id:
        if getattr(current_user.tipo_usuario, 'nivel_prioridad', None) != 1:
            raise HTTPException(status_code=403, detail='No tienes permiso para crear notificaciones para otro usuario')

    # si no se envió usuario_id, asumir current_user
    if payload.usuario_id is None:
        payload.usuario_id = current_user.id

    n = create_notification(db, payload.dict())
    # emitir al WebSocket para entrega en tiempo real
    emit_webhook('notificacion', {
        'usuario_id': n.usuario_id,
        'titulo': n.titulo,
        'mensaje': n.mensaje,
        'notificacion_id': n.id,
    })
    return {'success': True, 'id': n.id}


@router.get("", response_model=List[NotificacionResponse])
def list_notificaciones(usuario_id: int, limit: Optional[int] = 100, db: Session = Depends(get_db), current_user: models.usuario.Usuario = Depends(get_current_user)):
    """Listar notificaciones para un usuario usando ORM (autorizado).

    Sólo devuelve notificaciones si el `usuario_id` solicitado es igual al current_user o si el current_user es admin.
    """
    if usuario_id != current_user.id and getattr(current_user.tipo_usuario, 'nivel_prioridad', None) != 1:
        raise HTTPException(status_code=403, detail='No tienes permiso para ver notificaciones de otro usuario')

    q = db.query(models.notificacion.Notificacion).filter(models.notificacion.Notificacion.usuario_id == usuario_id)
    rows = q.order_by(models.notificacion.Notificacion.creado_en.desc()).limit(limit).all()
    out = []
    for r in rows:
        out.append(NotificacionResponse(
            id=r.id,
            usuario_id=r.usuario_id,
            titulo=r.titulo,
            mensaje=r.mensaje,
            leida=bool(r.leida),
            reserva_id=r.reserva_id,
            espacio_id=r.espacio_id,
            metadata=r.metadata_info or {},
            leida_at=r.leida_at,
            creado_en=r.creado_en,
        ))
    return out
