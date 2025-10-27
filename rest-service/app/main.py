from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, EmailStr
from datetime import timedelta, date, time as time_cls
from pathlib import Path
import secrets
import time

from .database import get_db, engine, Base, SessionLocal
from .models import tipo_usuario, usuario, categoria_espacio, espacio, caracteristica_espacio, tipo_evento, reserva as reserva_model, estado_reserva as estado_reserva_model
from .routes import reservas as reservas_router, notificaciones as notificaciones_router
from .utils.password_handler import verify_password, get_password_hash
from .utils.jwt_handler import create_access_token
from .utils.dependencies import get_current_user, require_admin
from .services.reserva_service import calc_availability

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MEDIA_ROOT = PROJECT_ROOT / "attached_assets"
AVATAR_DIR = MEDIA_ROOT / "avatars"
SPACE_IMAGE_DIR = MEDIA_ROOT / "espacios"
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
VALID_USER_STATES = {"activo", "inactivo", "suspendido"}

for directory in (MEDIA_ROOT, AVATAR_DIR, SPACE_IMAGE_DIR):
    directory.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="ULEAM Reservas - REST API",
    description="API REST para gestión de reservas de espacios universitarios",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware: strip Authorization header for auth endpoints
# Rationale: some clients (Postman collections, browsers, or frontends) may
# attach an expired/global Authorization header to all requests. If an
# expired token is present it can cause dependencies that use HTTPBearer to
# fail early even for endpoints that should be public (like /api/auth/login
# and /api/auth/register). We remove the header for any path under
# /api/auth/ so login/register always work regardless of a stale header.
AUTH_PUBLIC_PATHS = {"/api/auth/login", "/api/auth/register"}

@app.middleware("http")
async def _strip_auth_header_for_auth_paths(request, call_next):
    try:
        path = request.url.path or ""
        if path in AUTH_PUBLIC_PATHS:
            headers = [
                (k, v)
                for (k, v) in request.scope.get("headers", [])
                if k != b"authorization"
            ]
            request.scope["headers"] = headers
    except Exception:
        pass
    return await call_next(request)

# registrar routers modulares
app.include_router(reservas_router.router)
app.include_router(notificaciones_router.router)


# --- Small inline Pydantic schemas (for simple endpoints) ---
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    nombre: str
    apellido: str
    telefono: Optional[str] = None
    tipo_usuario_id: int = 3

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict

class TipoUsuarioCreate(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    nivel_prioridad: int = 1
    permisos: dict = {}

class CategoriaEspacioCreate(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    requiere_aprobacion: bool = False
    capacidad_maxima: Optional[int] = None

class EspacioCreate(BaseModel):
    codigo: str
    nombre: str
    categoria_id: int
    capacidad_maxima: int
    imagen_url: Optional[str] = None
    estado: str = "activo"

class CaracteristicaCreate(BaseModel):
    nombre: str
    disponible: bool = True
    descripcion: Optional[str] = None

class TipoEventoCreate(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    requiere_aprobacion: bool = False
    color_hex: str = "#3B82F6"

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class UserUpdateRequest(BaseModel):
    nombre: Optional[str] = None
    apellido: Optional[str] = None
    telefono: Optional[str] = None
    tipo_usuario_id: Optional[int] = None

class UserStateUpdate(BaseModel):
    estado: str

class EspacioEstadoUpdate(BaseModel):
    estado: str

class TipoUsuarioUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    nivel_prioridad: Optional[int] = None
    permisos: Optional[dict] = None

class CategoriaEspacioUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    requiere_aprobacion: Optional[bool] = None
    capacidad_maxima: Optional[int] = None

class EspacioUpdate(BaseModel):
    codigo: Optional[str] = None
    nombre: Optional[str] = None
    categoria_id: Optional[int] = None
    capacidad_maxima: Optional[int] = None
    imagen_url: Optional[str] = None
    estado: Optional[str] = None

class CaracteristicaUpdate(BaseModel):
    nombre: Optional[str] = None
    disponible: Optional[bool] = None
    descripcion: Optional[str] = None

class TipoEventoUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    requiere_aprobacion: Optional[bool] = None
    color_hex: Optional[str] = None


def _calc_availability(db: Session, espacio_id: int, fecha: date, incluir_pendientes: bool = True):
    """
    Calcula slots libres y ocupados entre 08:00-18:00 para un espacio/fecha.
    Usa reservas con estado Aprobada y opcionalmente Pendiente como bloqueantes.
    """
    jornada_ini = time_cls(8, 0)
    jornada_fin = time_cls(18, 0)

    estados_bloqueantes = db.query(estado_reserva_model.EstadoReserva).filter(
        estado_reserva_model.EstadoReserva.nombre.in_(
            ["Aprobada"] + (["Pendiente"] if incluir_pendientes else [])
        )
    ).all()
    blocking_ids = {e.id for e in estados_bloqueantes}

    reservas = (
        db.query(reserva_model.Reserva)
        .filter(
            reserva_model.Reserva.espacio_id == espacio_id,
            reserva_model.Reserva.fecha == fecha,
            reserva_model.Reserva.estado_id.in_(blocking_ids) if blocking_ids else True,
        )
        .order_by(reserva_model.Reserva.hora_inicio.asc())
        .all()
    )

    ocupados = []
    intervals = []
    for r in reservas:
        ocupados.append(
            {
                "id": r.id,
                "estado": getattr(r.estado, "nombre", None),
                "hora_inicio": r.hora_inicio.strftime("%H:%M"),
                "hora_fin": r.hora_fin.strftime("%H:%M"),
                "titulo": r.titulo,
                "usuario_id": r.usuario_id,
            }
        )
        intervals.append((r.hora_inicio, r.hora_fin))

    # Calcular libres a partir de intervalos ocupados
    libres = []
    cursor = jornada_ini
    for ini, fin in intervals:
        if ini > cursor:
            libres.append(
                {"hora_inicio": cursor.strftime("%H:%M"), "hora_fin": ini.strftime("%H:%M")}
            )
        if fin > cursor:
            cursor = fin
    if cursor < jornada_fin:
        libres.append({"hora_inicio": cursor.strftime("%H:%M"), "hora_fin": jornada_fin.strftime("%H:%M")})

    espacio_obj = db.query(espacio.Espacio).filter(espacio.Espacio.id == espacio_id).first()
    nombre_espacio = espacio_obj.nombre if espacio_obj else None

    return {
        "espacio_id": espacio_id,
        "espacio_nombre": nombre_espacio,
        "fecha": fecha.isoformat(),
        "dia_semana": fecha.strftime("%A"),
        "ocupados": ocupados,
        "libres": libres,
    }


async def _save_uploaded_file(upload: UploadFile, directory: Path, filename_prefix: str) -> str:
    if upload.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    suffix = Path(upload.filename or "").suffix or ".bin"
    filename = f"{filename_prefix}_{int(time.time())}_{secrets.token_hex(4)}{suffix}"
    directory.mkdir(parents=True, exist_ok=True)
    file_path = directory / filename

    contents = await upload.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    with open(file_path, "wb") as fh:
        fh.write(contents)

    # store path relative to project root to keep URLs portable
    return file_path.relative_to(PROJECT_ROOT).as_posix()


def _ensure_owner_or_admin(target_user_id: int, current_user: usuario.Usuario):
    if current_user.tipo_usuario.nivel_prioridad != 1 and current_user.id != target_user_id:
        raise HTTPException(status_code=403, detail="Operation allowed only for admins or resource owners")


@app.get("/")
def read_root():
    return {
        "message": "ULEAM Reservas - REST API",
        "version": "1.0.0",
        "service": "REST API (Python/FastAPI)",
        "status": "running"
    }

@app.post("/api/auth/register", response_model=TokenResponse)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    existing_user = db.query(usuario.Usuario).filter(usuario.Usuario.email == request.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = usuario.Usuario(
        email=request.email,
        password_hash=get_password_hash(request.password),
        nombre=request.nombre,
        apellido=request.apellido,
        telefono=request.telefono,
        tipo_usuario_id=request.tipo_usuario_id,
        estado="activo"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    access_token = create_access_token(data={"sub": new_user.id})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": new_user.id,
            "email": new_user.email,
            "nombre": new_user.nombre,
            "apellido": new_user.apellido
        }
    }


@app.post("/api/auth/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(usuario.Usuario).filter(usuario.Usuario.email == request.email).first()
    
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    if user.estado != "activo":
        raise HTTPException(status_code=403, detail="User account is not active")
    
    access_token = create_access_token(data={"sub": user.id})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "nombre": user.nombre,
            "apellido": user.apellido,
            "tipo_usuario_id": user.tipo_usuario_id
        }
    }


@app.post("/api/auth/logout")
def logout(current_user: usuario.Usuario = Depends(get_current_user)):
    # JWT es stateless; indicar al cliente que elimine el token
    return {
        "success": True,
        "message": "Sesión cerrada. Elimina el token en el cliente.",
        "user_id": current_user.id
    }


@app.get("/api/disponibilidad")
def get_disponibilidad(
    espacio_id: int,
    fecha: date,
    incluir_pendientes: bool = True,
    db: Session = Depends(get_db),
):
    if not espacio_id:
        raise HTTPException(status_code=400, detail="espacio_id es requerido")
    payload = _calc_availability(db, espacio_id, fecha, incluir_pendientes)
    return payload

@app.get("/api/auth/me")
def get_me(current_user: usuario.Usuario = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "nombre": current_user.nombre,
        "apellido": current_user.apellido,
        "telefono": current_user.telefono,
        "tipo_usuario_id": current_user.tipo_usuario_id,
        "estado": current_user.estado
    }


@app.put("/api/auth/change-password")
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: usuario.Usuario = Depends(get_current_user)
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="La contraseña actual no es válida")

    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe tener al menos 8 caracteres")
    if payload.new_password == payload.current_password:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe ser diferente a la actual")

    db_user = db.query(usuario.Usuario).filter(usuario.Usuario.id == current_user.id).first()
    db_user.password_hash = get_password_hash(payload.new_password)
    db.add(db_user)
    db.commit()
    return {"success": True}

@app.get("/api/usuarios")
def get_usuarios(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: usuario.Usuario = Depends(require_admin)
):
    users = db.query(usuario.Usuario).offset(skip).limit(limit).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "nombre": u.nombre,
            "apellido": u.apellido,
            "telefono": u.telefono,
            "tipo_usuario_id": u.tipo_usuario_id,
            "estado": u.estado
        }
        for u in users
    ]


@app.get("/api/usuarios/{user_id}")
def get_usuario_detail(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: usuario.Usuario = Depends(get_current_user)
):
    _ensure_owner_or_admin(user_id, current_user)
    user = db.query(usuario.Usuario).filter(usuario.Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {
        "id": user.id,
        "email": user.email,
        "nombre": user.nombre,
        "apellido": user.apellido,
        "telefono": user.telefono,
        "tipo_usuario_id": user.tipo_usuario_id,
        "estado": user.estado,
        "avatar_url": user.avatar_url,
    }


@app.put("/api/usuarios/{user_id}")
def update_usuario(
    user_id: int,
    data: UserUpdateRequest,
    db: Session = Depends(get_db),
    current_user: usuario.Usuario = Depends(get_current_user)
):
    _ensure_owner_or_admin(user_id, current_user)
    user = db.query(usuario.Usuario).filter(usuario.Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    payload = data.dict(exclude_unset=True)
    if "tipo_usuario_id" in payload and current_user.tipo_usuario.nivel_prioridad != 1:
        raise HTTPException(status_code=403, detail="Solo un administrador puede cambiar el rol")

    for field, value in payload.items():
        setattr(user, field, value)

    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "email": user.email,
        "nombre": user.nombre,
        "apellido": user.apellido,
        "telefono": user.telefono,
        "tipo_usuario_id": user.tipo_usuario_id,
        "estado": user.estado,
        "avatar_url": user.avatar_url,
    }


@app.delete("/api/usuarios/{user_id}")
def delete_usuario(
    user_id: int,
    db: Session = Depends(get_db),
    admin: usuario.Usuario = Depends(require_admin)
):
    user = db.query(usuario.Usuario).filter(usuario.Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propio usuario")

    db.delete(user)
    db.commit()
    return {"success": True}


@app.patch("/api/usuarios/{user_id}/estado")
def patch_usuario_estado(
    user_id: int,
    data: UserStateUpdate,
    db: Session = Depends(get_db),
    admin: usuario.Usuario = Depends(require_admin)
):
    if data.estado not in VALID_USER_STATES:
        raise HTTPException(status_code=400, detail=f"Estado inválido. Usa uno de: {', '.join(sorted(VALID_USER_STATES))}")
    user = db.query(usuario.Usuario).filter(usuario.Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    user.estado = data.estado
    db.add(user)
    db.commit()
    return {"success": True, "estado": user.estado}


@app.post("/api/usuarios/{user_id}/avatar")
async def upload_usuario_avatar(
    user_id: int,
    avatar: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: usuario.Usuario = Depends(get_current_user)
):
    _ensure_owner_or_admin(user_id, current_user)
    user = db.query(usuario.Usuario).filter(usuario.Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    stored_path = await _save_uploaded_file(avatar, AVATAR_DIR, f"user_{user_id}")
    user.avatar_url = f"/{stored_path}"
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"success": True, "avatar_url": user.avatar_url}

@app.get("/api/tipos-usuario")
def get_tipos_usuario(db: Session = Depends(get_db)):
    tipos = db.query(tipo_usuario.TipoUsuario).all()
    return [{
        "id": t.id,
        "nombre": t.nombre,
        "descripcion": t.descripcion,
        "nivel_prioridad": t.nivel_prioridad,
        "permisos": t.permisos
    } for t in tipos]

@app.post("/api/tipos-usuario")
def create_tipo_usuario(
    data: TipoUsuarioCreate,
    db: Session = Depends(get_db),
    admin: usuario.Usuario = Depends(require_admin)
):
    new_tipo = tipo_usuario.TipoUsuario(**data.dict())
    db.add(new_tipo)
    db.commit()
    db.refresh(new_tipo)
    return new_tipo


@app.put("/api/tipos-usuario/{tipo_id}")
def update_tipo_usuario(
    tipo_id: int,
    data: TipoUsuarioUpdate,
    db: Session = Depends(get_db),
    admin: usuario.Usuario = Depends(require_admin)
):
    tipo_obj = db.query(tipo_usuario.TipoUsuario).filter(tipo_usuario.TipoUsuario.id == tipo_id).first()
    if not tipo_obj:
        raise HTTPException(status_code=404, detail="Tipo de usuario no encontrado")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(tipo_obj, field, value)
    db.add(tipo_obj)
    db.commit()
    db.refresh(tipo_obj)
    return tipo_obj


@app.delete("/api/tipos-usuario/{tipo_id}")
def delete_tipo_usuario(
    tipo_id: int,
    db: Session = Depends(get_db),
    admin: usuario.Usuario = Depends(require_admin)
):
    tipo_obj = db.query(tipo_usuario.TipoUsuario).filter(tipo_usuario.TipoUsuario.id == tipo_id).first()
    if not tipo_obj:
        raise HTTPException(status_code=404, detail="Tipo de usuario no encontrado")
    users_count = db.query(usuario.Usuario).filter(usuario.Usuario.tipo_usuario_id == tipo_id).count()
    if users_count > 0:
        raise HTTPException(status_code=400, detail="No puedes eliminar un tipo con usuarios asignados")
    db.delete(tipo_obj)
    db.commit()
    return {"success": True}

@app.get("/api/categorias-espacio")
def get_categorias(db: Session = Depends(get_db)):
    cats = db.query(categoria_espacio.CategoriaEspacio).all()
    return [{
        "id": c.id,
        "nombre": c.nombre,
        "descripcion": c.descripcion,
        "requiere_aprobacion": c.requiere_aprobacion,
        "capacidad_maxima": c.capacidad_maxima
    } for c in cats]

@app.post("/api/categorias-espacio")
def create_categoria(
    data: CategoriaEspacioCreate,
    db: Session = Depends(get_db),
    admin: usuario.Usuario = Depends(require_admin)
):
    new_cat = categoria_espacio.CategoriaEspacio(**data.dict())
    db.add(new_cat)
    db.commit()
    db.refresh(new_cat)
    return new_cat


@app.put("/api/categorias-espacio/{categoria_id}")
def update_categoria(
    categoria_id: int,
    data: CategoriaEspacioUpdate,
    db: Session = Depends(get_db),
    admin: usuario.Usuario = Depends(require_admin)
):
    cat = db.query(categoria_espacio.CategoriaEspacio).filter(categoria_espacio.CategoriaEspacio.id == categoria_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(cat, field, value)
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@app.delete("/api/categorias-espacio/{categoria_id}")
def delete_categoria(
    categoria_id: int,
    db: Session = Depends(get_db),
    admin: usuario.Usuario = Depends(require_admin)
):
    cat = db.query(categoria_espacio.CategoriaEspacio).filter(categoria_espacio.CategoriaEspacio.id == categoria_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Categoría no encontrada")
    espacios_count = db.query(espacio.Espacio).filter(espacio.Espacio.categoria_id == categoria_id).count()
    if espacios_count:
        raise HTTPException(status_code=400, detail="No puedes eliminar una categoría con espacios asociados")
    db.delete(cat)
    db.commit()
    return {"success": True}

@app.get("/api/espacios")
def get_espacios(
    categoria_id: Optional[int] = None,
    estado: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(espacio.Espacio)
    if categoria_id:
        query = query.filter(espacio.Espacio.categoria_id == categoria_id)
    if estado:
        query = query.filter(espacio.Espacio.estado == estado)
    
    espacios_list = query.all()
    return [{
        "id": e.id,
        "codigo": e.codigo,
        "nombre": e.nombre,
        "categoria_id": e.categoria_id,
        "capacidad_maxima": e.capacidad_maxima,
        "imagen_url": e.imagen_url,
        "estado": e.estado
    } for e in espacios_list]

@app.get("/api/espacios/{espacio_id}")
def get_espacio(espacio_id: int, db: Session = Depends(get_db)):
    esp = db.query(espacio.Espacio).filter(espacio.Espacio.id == espacio_id).first()
    if not esp:
        raise HTTPException(status_code=404, detail="Espacio not found")
    
    return {
        "id": esp.id,
        "codigo": esp.codigo,
        "nombre": esp.nombre,
        "categoria_id": esp.categoria_id,
        "capacidad_maxima": esp.capacidad_maxima,
        "imagen_url": esp.imagen_url,
        "estado": esp.estado,
        "caracteristicas": [
            {
                "id": c.id,
                "nombre": c.nombre,
                "disponible": c.disponible,
                "descripcion": c.descripcion
            }
            for c in esp.caracteristicas
        ]
    }

@app.post("/api/espacios")
def create_espacio(
    data: EspacioCreate,
    db: Session = Depends(get_db),
    admin: usuario.Usuario = Depends(require_admin)
):
    new_espacio = espacio.Espacio(**data.dict())
    db.add(new_espacio)
    db.commit()
    db.refresh(new_espacio)
    return new_espacio

@app.post("/api/espacios/{espacio_id}/caracteristicas")
def create_caracteristica(
    espacio_id: int,
    data: CaracteristicaCreate,
    db: Session = Depends(get_db),
    admin: usuario.Usuario = Depends(require_admin)
):
    esp = db.query(espacio.Espacio).filter(espacio.Espacio.id == espacio_id).first()
    if not esp:
        raise HTTPException(status_code=404, detail="Espacio not found")
    
    new_car = caracteristica_espacio.CaracteristicaEspacio(
        espacio_id=espacio_id,
        **data.dict()
    )
    db.add(new_car)
    db.commit()
    db.refresh(new_car)
    return new_car


@app.put("/api/espacios/{espacio_id}")
def update_espacio(
    espacio_id: int,
    data: EspacioUpdate,
    db: Session = Depends(get_db),
    admin: usuario.Usuario = Depends(require_admin)
):
    esp = db.query(espacio.Espacio).filter(espacio.Espacio.id == espacio_id).first()
    if not esp:
        raise HTTPException(status_code=404, detail="Espacio no encontrado")

    payload = data.dict(exclude_unset=True)
    if "codigo" in payload:
        exists = (
            db.query(espacio.Espacio)
            .filter(espacio.Espacio.codigo == payload["codigo"], espacio.Espacio.id != espacio_id)
            .first()
        )
        if exists:
            raise HTTPException(status_code=400, detail="El código ya está en uso")

    for field, value in payload.items():
        setattr(esp, field, value)
    db.add(esp)
    db.commit()
    db.refresh(esp)
    return esp


@app.delete("/api/espacios/{espacio_id}")
def delete_espacio(
    espacio_id: int,
    db: Session = Depends(get_db),
    admin: usuario.Usuario = Depends(require_admin)
):
    esp = db.query(espacio.Espacio).filter(espacio.Espacio.id == espacio_id).first()
    if not esp:
        raise HTTPException(status_code=404, detail="Espacio no encontrado")
    db.delete(esp)
    db.commit()
    return {"success": True}


@app.patch("/api/espacios/{espacio_id}/estado")
def patch_espacio_estado(
    espacio_id: int,
    data: EspacioEstadoUpdate,
    db: Session = Depends(get_db),
    admin: usuario.Usuario = Depends(require_admin)
):
    esp = db.query(espacio.Espacio).filter(espacio.Espacio.id == espacio_id).first()
    if not esp:
        raise HTTPException(status_code=404, detail="Espacio no encontrado")
    if not data.estado:
        raise HTTPException(status_code=400, detail="Estado requerido")
    esp.estado = data.estado
    db.add(esp)
    db.commit()
    return {"success": True, "estado": esp.estado}


@app.post("/api/espacios/{espacio_id}/imagen")
async def upload_espacio_imagen(
    espacio_id: int,
    imagen: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: usuario.Usuario = Depends(require_admin)
):
    esp = db.query(espacio.Espacio).filter(espacio.Espacio.id == espacio_id).first()
    if not esp:
        raise HTTPException(status_code=404, detail="Espacio no encontrado")

    stored_path = await _save_uploaded_file(imagen, SPACE_IMAGE_DIR, f"espacio_{espacio_id}")
    esp.imagen_url = f"/{stored_path}"
    db.add(esp)
    db.commit()
    db.refresh(esp)
    return {"success": True, "imagen_url": esp.imagen_url}


@app.get("/api/espacios/{espacio_id}/caracteristicas")
def list_caracteristicas(
    espacio_id: int,
    db: Session = Depends(get_db),
    current_user: usuario.Usuario = Depends(get_current_user)
):
    esp = db.query(espacio.Espacio).filter(espacio.Espacio.id == espacio_id).first()
    if not esp:
        raise HTTPException(status_code=404, detail="Espacio no encontrado")
    return [
        {
            "id": car.id,
            "nombre": car.nombre,
            "descripcion": car.descripcion,
            "disponible": car.disponible,
        }
        for car in esp.caracteristicas
    ]


@app.put("/api/caracteristicas/{caracteristica_id}")
def update_caracteristica(
    caracteristica_id: int,
    data: CaracteristicaUpdate,
    db: Session = Depends(get_db),
    admin: usuario.Usuario = Depends(require_admin)
):
    car = (
        db.query(caracteristica_espacio.CaracteristicaEspacio)
        .filter(caracteristica_espacio.CaracteristicaEspacio.id == caracteristica_id)
        .first()
    )
    if not car:
        raise HTTPException(status_code=404, detail="Característica no encontrada")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(car, field, value)
    db.add(car)
    db.commit()
    db.refresh(car)
    return car


@app.delete("/api/caracteristicas/{caracteristica_id}")
def delete_caracteristica(
    caracteristica_id: int,
    db: Session = Depends(get_db),
    admin: usuario.Usuario = Depends(require_admin)
):
    car = (
        db.query(caracteristica_espacio.CaracteristicaEspacio)
        .filter(caracteristica_espacio.CaracteristicaEspacio.id == caracteristica_id)
        .first()
    )
    if not car:
        raise HTTPException(status_code=404, detail="Característica no encontrada")
    db.delete(car)
    db.commit()
    return {"success": True}

@app.get("/api/tipos-evento")
def get_tipos_evento(db: Session = Depends(get_db)):
    tipos = db.query(tipo_evento.TipoEvento).all()
    return [{
        "id": t.id,
        "nombre": t.nombre,
        "descripcion": t.descripcion,
        "requiere_aprobacion": t.requiere_aprobacion,
        "color_hex": t.color_hex
    } for t in tipos]

@app.post("/api/tipos-evento")
def create_tipo_evento(
    data: TipoEventoCreate,
    db: Session = Depends(get_db),
    admin: usuario.Usuario = Depends(require_admin)
):
    new_tipo = tipo_evento.TipoEvento(**data.dict())
    db.add(new_tipo)
    db.commit()
    db.refresh(new_tipo)
    return new_tipo


@app.put("/api/tipos-evento/{tipo_evento_id}")
def update_tipo_evento(
    tipo_evento_id: int,
    data: TipoEventoUpdate,
    db: Session = Depends(get_db),
    admin: usuario.Usuario = Depends(require_admin)
):
    tipo_obj = db.query(tipo_evento.TipoEvento).filter(tipo_evento.TipoEvento.id == tipo_evento_id).first()
    if not tipo_obj:
        raise HTTPException(status_code=404, detail="Tipo de evento no encontrado")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(tipo_obj, field, value)
    db.add(tipo_obj)
    db.commit()
    db.refresh(tipo_obj)
    return tipo_obj


@app.delete("/api/tipos-evento/{tipo_evento_id}")
def delete_tipo_evento(
    tipo_evento_id: int,
    db: Session = Depends(get_db),
    admin: usuario.Usuario = Depends(require_admin)
):
    tipo_obj = db.query(tipo_evento.TipoEvento).filter(tipo_evento.TipoEvento.id == tipo_evento_id).first()
    if not tipo_obj:
        raise HTTPException(status_code=404, detail="Tipo de evento no encontrado")
    reservas_count = db.query(reserva_model.Reserva).filter(reserva_model.Reserva.tipo_evento_id == tipo_evento_id).count()
    if reservas_count:
        raise HTTPException(status_code=400, detail="No puedes eliminar un tipo de evento con reservas asociadas")
    db.delete(tipo_obj)
    db.commit()
    return {"success": True}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


@app.on_event('startup')
def startup():
    # Optionally run alembic migrations (if ALEMBIC is configured to use DATABASE_URL)
    #try:
    #    from .utils.alembic_runner import run_migrations_if_needed
    #    run_migrations_if_needed()
    #except Exception:
    #    # don't fail startup if migrations fail; fallback to create_all
    #    pass

    # Ensure tables exist and seed default estados (fallback if migrations not run)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        defaults = [
            {"nombre": "Pendiente", "color_hex": "#F59E0B", "permite_edicion": True, "es_final": False, "orden": 1},
            {"nombre": "Aprobada", "color_hex": "#10B981", "permite_edicion": False, "es_final": False, "orden": 2},
            {"nombre": "Rechazada", "color_hex": "#EF4444", "permite_edicion": False, "es_final": True, "orden": 3},
            {"nombre": "Cancelada", "color_hex": "#6B7280", "permite_edicion": False, "es_final": True, "orden": 4},
        ]
        for s in defaults:
            exists = db.query(estado_reserva_model.EstadoReserva).filter(estado_reserva_model.EstadoReserva.nombre == s["nombre"]).first()
            if not exists:
                db.add(estado_reserva_model.EstadoReserva(**s))

        tipo_defaults = [
            {"id": 1, "nombre": "Administrador", "descripcion": "Rol con acceso completo", "nivel_prioridad": 1, "permisos": {"access_level": 5}},
            {"id": 2, "nombre": "Profesor", "descripcion": "Permisos para gestión académica", "nivel_prioridad": 2, "permisos": {"reservas": "gestionar"}},
            {"id": 3, "nombre": "Estudiante", "descripcion": "Puede solicitar reservas", "nivel_prioridad": 3, "permisos": {}},
        ]
        for td in tipo_defaults:
            exists = (
                db.query(tipo_usuario.TipoUsuario)
                .filter(
                    (tipo_usuario.TipoUsuario.id == td["id"])
                    | (tipo_usuario.TipoUsuario.nombre == td["nombre"])
                )
                .first()
            )
            if not exists:
                db.add(tipo_usuario.TipoUsuario(**td))

        db.commit()
    finally:
        db.close()
