# REST API (Python/FastAPI)

Servicio principal (DEC1) para autenticación, CRUD de entidades y gestión completa de reservas.

## Puesta en marcha
```bash
cd rest-service
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Variables de entorno
- `DATABASE_URL` (PostgreSQL)
- `SECRET_KEY` (clave JWT compartida con GraphQL/WS)
- `ACCESS_TOKEN_EXPIRE_MINUTES` (opcional, default 30)
- `WEBSOCKET_SERVICE_URL` (default `http://localhost:3001` para webhooks)
- `ALLOWED_ORIGINS` (opcional, CORS)

### Endpoints clave
- Autenticación: `POST /api/auth/login`, `POST /api/auth/register`, `GET /api/auth/me`, `PUT /api/auth/change-password`
- Usuarios/Roles: `GET /api/usuarios`, `PATCH /api/usuarios/{id}/estado`, `POST /api/usuarios/{id}/avatar`, `GET /api/tipos-usuario`
- Catálogos: `GET/POST/PUT/DELETE /api/categorias-espacio`, `/api/espacios`, `/api/tipos-evento`, `/api/espacios/{id}/caracteristicas`
- Reservas: `POST /api/reservas` (crea en estado Pendiente), `GET /api/reservas`, `PATCH /api/reservas/{id}/estado`, `DELETE /api/reservas/{id}`
- Disponibilidad: `GET /api/disponibilidad?espacio_id=1&fecha=2025-11-16&incluir_pendientes=true`
- Notificaciones: `GET /api/notificaciones?usuario_id={id}` y webhooks automáticos hacia el servicio WebSocket

Documentación interactiva: `http://localhost:8000/docs` y `http://localhost:8000/redoc`.

### Flujos implementados
- Las reservas se crean en **estado 1 = Pendiente** y disparan un webhook `reserva_creada` al servicio WebSocket.
- Al aprobar/rechazar (`PATCH /api/reservas/{id}/estado`), se actualizan solapes pendientes y se envían webhooks `reserva_aprobada`/`reserva_rechazada`.
- Notificaciones se persisten y se emiten al WS vía `POST /api/webhooks/notificacion`.

### Tests
`pytest` dentro de `rest-service` (se ignoran `__pycache__` y `.pytest_cache`).
