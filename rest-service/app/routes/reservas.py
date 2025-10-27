from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas.reserva import ReservaCreate, ReservaResponse, ReservaEstadoUpdate
from ..services.reserva_service import create_reserva, calc_availability
from ..models import reserva as reserva_model
from ..utils.dependencies import get_current_user
from .. import models
from ..services.notification_service import schedule_emit_webhook

router = APIRouter(prefix="/api/reservas", tags=["reservas"])

@router.post("", response_model=ReservaResponse)
def post_reserva(data: ReservaCreate, db: Session = Depends(get_db), current_user: models.usuario.Usuario = Depends(get_current_user), background_tasks: BackgroundTasks = None):
    try:
        new_res = create_reserva(db, current_user.id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # schedule webhook emission (non-blocking)
    payload_out = {
        'reserva_id': new_res.id,
        'usuario_id': new_res.usuario_id,
        'espacio_id': new_res.espacio_id,
        'espacio_nombre': getattr(new_res.espacio, 'nombre', None),
        'fecha': new_res.fecha.isoformat(),
        'hora_inicio': new_res.hora_inicio.strftime('%H:%M'),
        'hora_fin': new_res.hora_fin.strftime('%H:%M'),
        'titulo': new_res.titulo,
        'estado': getattr(new_res.estado, 'nombre', None) or 'Pendiente'
    }
    if background_tasks is not None:
        schedule_emit_webhook(background_tasks, 'reserva_creada', payload_out)
        avail = calc_availability(db, new_res.espacio_id, new_res.fecha, True)
        schedule_emit_webhook(background_tasks, 'disponibilidad_actualizada', avail)
        # notificación al usuario: reserva registrada en estado pendiente/aprobada
        try:
            from ..services.notification_service import create_notification
            create_notification(db, {
                'usuario_id': new_res.usuario_id,
                'titulo': 'Reserva creada',
                'mensaje': f"Tu reserva '{new_res.titulo or new_res.codigo}' fue registrada en estado {payload_out['estado']}",
                'reserva_id': new_res.id,
                'espacio_id': new_res.espacio_id,
                'metadata': {'tipo': 'reserva_creada', 'estado': payload_out['estado']},
            })
            schedule_emit_webhook(background_tasks, 'notificacion', {
                'usuario_id': new_res.usuario_id,
                'titulo': 'Reserva creada',
                'mensaje': f"Tu reserva '{new_res.titulo or new_res.codigo}' fue registrada en estado {payload_out['estado']}",
                'notificacion_id': new_res.id,
            })
        except Exception:
            pass

    return ReservaResponse(
        id=new_res.id,
        codigo=new_res.codigo,
        usuario_id=new_res.usuario_id,
        espacio_id=new_res.espacio_id,
        tipo_evento_id=new_res.tipo_evento_id,
        estado_id=new_res.estado_id,
        fecha=new_res.fecha,
        hora_inicio=new_res.hora_inicio,
        hora_fin=new_res.hora_fin,
        titulo=new_res.titulo,
        descripcion=new_res.descripcion,
        es_bloqueo=new_res.es_bloqueo,
    )

@router.get("")
def list_reservas(usuario_id: int = None, espacio_id: int = None, estado_id: int = None, db: Session = Depends(get_db)):
    q = db.query(reserva_model.Reserva)
    if usuario_id:
        q = q.filter(reserva_model.Reserva.usuario_id == usuario_id)
    if espacio_id:
        q = q.filter(reserva_model.Reserva.espacio_id == espacio_id)
    if estado_id:
        q = q.filter(reserva_model.Reserva.estado_id == estado_id)
    rows = q.order_by(reserva_model.Reserva.fecha.desc()).all()
    out = []
    for r in rows:
        out.append({
            'id': r.id,
            'codigo': r.codigo,
            'usuario_id': r.usuario_id,
            'espacio_id': r.espacio_id,
            'tipo_evento_id': r.tipo_evento_id,
            'estado_id': r.estado_id,
            'fecha': r.fecha.isoformat(),
            'hora_inicio': r.hora_inicio.strftime('%H:%M'),
            'hora_fin': r.hora_fin.strftime('%H:%M'),
            'titulo': r.titulo,
            'descripcion': r.descripcion,
            'es_bloqueo': r.es_bloqueo,
        })
    return out

@router.get("/{reserva_id}")
def get_reserva(reserva_id: int, db: Session = Depends(get_db)):
    r = db.query(reserva_model.Reserva).filter(reserva_model.Reserva.id == reserva_id).first()
    if not r:
        raise HTTPException(status_code=404, detail='Reserva not found')
    return {
        'id': r.id,
        'codigo': r.codigo,
        'usuario': {
            'id': r.usuario.id,
            'nombre': r.usuario.nombre,
            'apellido': r.usuario.apellido,
            'email': r.usuario.email,
        } if r.usuario else None,
        'espacio': {
            'id': r.espacio.id,
            'nombre': r.espacio.nombre,
            'codigo': r.espacio.codigo,
        } if r.espacio else None,
        'tipo_evento_id': r.tipo_evento_id,
        'estado': getattr(r.estado, 'nombre', None),
        'fecha': r.fecha.isoformat(),
        'hora_inicio': r.hora_inicio.strftime('%H:%M'),
        'hora_fin': r.hora_fin.strftime('%H:%M'),
        'titulo': r.titulo,
        'descripcion': r.descripcion,
        'es_bloqueo': r.es_bloqueo,
        'motivo_bloqueo': r.motivo_bloqueo,
    }

@router.patch("/{reserva_id}/estado")
def update_reserva_estado(reserva_id: int, data: ReservaEstadoUpdate, db: Session = Depends(get_db), current_user: models.usuario.Usuario = Depends(get_current_user)):
    r = db.query(reserva_model.Reserva).filter(reserva_model.Reserva.id == reserva_id).first()
    if not r:
        raise HTTPException(status_code=404, detail='Reserva not found')
    if current_user.tipo_usuario.nivel_prioridad != 1 and current_user.id != r.usuario_id:
        raise HTTPException(status_code=403, detail='Permission denied')
    estado = db.query(models.estado_reserva.EstadoReserva).filter(models.estado_reserva.EstadoReserva.id == data.estado_id).first()
    if not estado:
        raise HTTPException(status_code=404, detail='Estado not found')

    # Si se aprueba, rechazar otras pendientes que choquen en el mismo espacio/fecha/horario
    pendientes_rechazadas = []
    if estado.nombre.lower() == 'aprobada':
        estado_pendiente = (
            db.query(models.estado_reserva.EstadoReserva)
            .filter(models.estado_reserva.EstadoReserva.nombre == 'Pendiente')
            .first()
        )
        estado_rechazada = (
            db.query(models.estado_reserva.EstadoReserva)
            .filter(models.estado_reserva.EstadoReserva.nombre == 'Rechazada')
            .first()
        )
        if estado_pendiente and estado_rechazada:
            solapadas = (
                db.query(reserva_model.Reserva)
                .join(models.estado_reserva.EstadoReserva, reserva_model.Reserva.estado_id == models.estado_reserva.EstadoReserva.id)
                .filter(
                    reserva_model.Reserva.id != r.id,
                    reserva_model.Reserva.espacio_id == r.espacio_id,
                    reserva_model.Reserva.fecha == r.fecha,
                    models.estado_reserva.EstadoReserva.id == estado_pendiente.id,
                    reserva_model.Reserva.hora_inicio < r.hora_fin,
                    reserva_model.Reserva.hora_fin > r.hora_inicio,
                )
                .all()
            )
            for other in solapadas:
                other.estado_id = estado_rechazada.id
                pendientes_rechazadas.append(other)
                db.add(other)

    r.estado_id = estado.id
    db.add(r)
    db.commit()
    db.refresh(r)

    from ..services.notification_service import schedule_emit_webhook
    from ..services.notification_service import create_notification
    payload = {
        'reserva_id': r.id,
        'usuario_id': r.usuario_id,
        'espacio_id': r.espacio_id,
        'nuevo_estado': estado.nombre,
    }
    # schedule webhook para la reserva actualizada
    schedule_emit_webhook(None, 'reserva_actualizada', payload)

    # Emitir webhook para las pendientes rechazadas automáticamente
    for other in pendientes_rechazadas:
        schedule_emit_webhook(
            None,
            'reserva_actualizada',
            {
                'reserva_id': other.id,
                'usuario_id': other.usuario_id,
                'espacio_id': other.espacio_id,
                'nuevo_estado': 'Rechazada',
            },
        )

    # Notificar disponibilidad del espacio/fecha tras cambio de estado
    avail = calc_availability(db, r.espacio_id, r.fecha, True)
    schedule_emit_webhook(None, 'disponibilidad_actualizada', avail)

    # Crear notificación para el usuario del cambio de estado
    try:
        create_notification(db, {
            'usuario_id': r.usuario_id,
            'titulo': 'Actualizar estado de reserva',
            'mensaje': f"Tu reserva '{r.titulo or r.codigo}' ahora está en estado {estado.nombre}",
            'reserva_id': r.id,
            'espacio_id': r.espacio_id,
            'metadata': {'tipo': 'reserva_estado', 'estado': estado.nombre},
        })
        schedule_emit_webhook(None, 'notificacion', {
            'usuario_id': r.usuario_id,
            'titulo': 'Actualizar estado de reserva',
            'mensaje': f"Tu reserva '{r.titulo or r.codigo}' ahora está en estado {estado.nombre}",
            'notificacion_id': r.id,
        })
    except Exception:
        pass

    return {'success': True, 'reserva_id': r.id, 'nuevo_estado': estado.nombre}

@router.delete("/{reserva_id}")
def delete_reserva(reserva_id: int, db: Session = Depends(get_db), current_user: models.usuario.Usuario = Depends(get_current_user)):
    r = db.query(reserva_model.Reserva).filter(reserva_model.Reserva.id == reserva_id).first()
    if not r:
        raise HTTPException(status_code=404, detail='Reserva not found')
    if current_user.tipo_usuario.nivel_prioridad != 1 and current_user.id != r.usuario_id:
        raise HTTPException(status_code=403, detail='Permission denied')
    db.delete(r)
    db.commit()
    from ..services.notification_service import schedule_emit_webhook
    payload = {
        'reserva_id': reserva_id,
        'espacio_id': r.espacio_id,
    }
    # schedule webhook (no BackgroundTasks available here)
    schedule_emit_webhook(None, 'reserva_cancelada', payload)
    avail = calc_availability(db, r.espacio_id, r.fecha, True)
    schedule_emit_webhook(None, 'disponibilidad_actualizada', avail)
    return {'success': True}
