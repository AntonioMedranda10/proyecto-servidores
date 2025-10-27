# REST API Feature Coverage (DEC1)

This document resume the endpoints implemented in the Python/FastAPI service so the team can contrast them against the rubric for DEC1.

## Autenticación

- `POST /api/auth/register` – Registro de usuarios.
- `POST /api/auth/login` – Inicio de sesión con retorno de JWT.
- `POST /api/auth/logout` – Cierra la sesión a nivel lógico (el cliente invalida el JWT).
- `GET /api/auth/me` – Perfil del usuario autenticado.
- `PUT /api/auth/change-password` – Cambia la contraseña verificando la anterior.

## Gestión de Usuarios

- `GET /api/usuarios` – Listado (solo administradores).
- `GET /api/usuarios/{id}` – Perfil individual (propietario o admin).
- `PUT /api/usuarios/{id}` – Actualización de datos; solo admin puede cambiar rol.
- `DELETE /api/usuarios/{id}` – Solo administradores.
- `PATCH /api/usuarios/{id}/estado` – Cambia estado (`activo`, `inactivo`, `suspendido`).
- `POST /api/usuarios/{id}/avatar` – Subida de avatar (archivo) para el usuario o admin.

## Tipo de Usuario

- `GET /api/tipos-usuario`
- `POST /api/tipos-usuario` – Crear (admin).
- `PUT /api/tipos-usuario/{id}` – Actualizar (admin).
- `DELETE /api/tipos-usuario/{id}` – Eliminar si no tiene usuarios asociados.

## Categorías de Espacio

- `GET /api/categorias-espacio`
- `POST /api/categorias-espacio` – Crear (admin).
- `PUT /api/categorias-espacio/{id}` – Actualizar (admin).
- `DELETE /api/categorias-espacio/{id}` – Eliminar (admin) solo si no hay espacios ligados.

## Espacios

- `GET /api/espacios` – Listado con filtros por categoría y estado.
- `GET /api/espacios/{id}` – Detalle.
- `POST /api/espacios` – Crear (admin).
- `PUT /api/espacios/{id}` – Actualizar (admin).
- `DELETE /api/espacios/{id}` – Eliminar (admin).
- `PATCH /api/espacios/{id}/estado` – Cambio rápido de estado (admin).
- `POST /api/espacios/{id}/imagen` – Subida de imagen del espacio (admin).

## Características de Espacio

- `GET /api/espacios/{id}/caracteristicas` – Listar.
- `POST /api/espacios/{id}/caracteristicas` – Crear (admin).
- `PUT /api/caracteristicas/{id}` – Actualizar (admin).
- `DELETE /api/caracteristicas/{id}` – Eliminar (admin).

## Tipos de Evento

- `GET /api/tipos-evento`
- `POST /api/tipos-evento` – Crear (admin).
- `PUT /api/tipos-evento/{id}` – Actualizar (admin).
- `DELETE /api/tipos-evento/{id}` – Eliminar (admin) si no existen reservas vinculadas.

## Reservas y Notificaciones

Los endpoints especializados para reservas y notificaciones permanecen en `app/routes/reservas.py` y `app/routes/notificaciones.py`. Allí se manejan:

- CRUD de reservas con validaciones de horario, conflictos y estado inicial.
- Cambios de estado (`PATCH /api/reservas/{id}/estado`) y cancelaciones.
- Creación/listado de notificaciones con webhooks hacia el servicio WebSocket.
- `GET /api/disponibilidad` – Calcula slots libres/ocupados para un espacio/fecha. Parámetros: `espacio_id` (int, requerido), `fecha` (YYYY-MM-DD, requerido), `incluir_pendientes` (bool, default true). Considera como bloqueantes las reservas Aprobadas y, opcionalmente, Pendientes.
- **Lógica de fila de espera:** se permiten múltiples reservas Pendientes en el mismo rango; al aprobar una, las demás Pendientes solapadas se marcan automáticamente como Rechazada y se emiten webhooks de actualización.

> **Nota:** Todos los endpoints sensibles utilizan `get_current_user` o `require_admin` para garantizar autenticación JWT y control por roles, cumpliendo con el criterio de RBAC solicitado en la rúbrica.
