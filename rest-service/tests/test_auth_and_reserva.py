import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine, SessionLocal
from app.models.tipo_usuario import TipoUsuario
from app.models.estado_reserva import EstadoReserva
import app.routes.reservas as reservas_routes

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        seeds_tu = [
            {"id": 1, "nombre": "Administrador", "nivel_prioridad": 1},
            {"id": 2, "nombre": "Profesor", "nivel_prioridad": 2},
            {"id": 3, "nombre": "Estudiante", "nivel_prioridad": 3},
        ]
        for payload in seeds_tu:
            session.merge(TipoUsuario(**payload))

        seeds_estado = [
            {"id": 1, "nombre": "Pendiente"},
            {"id": 2, "nombre": "Aprobada"},
            {"id": 3, "nombre": "Rechazada"},
            {"id": 4, "nombre": "Cancelada"},
        ]
        for payload in seeds_estado:
            session.merge(EstadoReserva(**payload))
        session.commit()
    finally:
        session.close()
    yield
    Base.metadata.drop_all(bind=engine)


def _register_user(email, password, tipo=3, nombre="Test", apellido="User"):
    resp = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
            "nombre": nombre,
            "apellido": apellido,
            "tipo_usuario_id": tipo,
        },
    )
    assert resp.status_code == 200
    return resp.json()


def _login(email, password):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_register_and_login():
    data = _register_user("testuser@example.com", "password123", 3)
    assert "access_token" in data
    token = _login("testuser@example.com", "password123")
    assert token


def _setup_space(admin_headers):
    client.post("/api/categorias-espacio", json={"nombre": "Auditorio Test"}, headers=admin_headers)
    cats = client.get("/api/categorias-espacio").json()
    cat_id = cats[0]["id"]
    client.post(
        "/api/espacios",
        json={"codigo": "A1", "nombre": "Auditorio 1", "categoria_id": cat_id, "capacidad_maxima": 100},
        headers=admin_headers,
    )
    espacios = client.get("/api/espacios").json()
    return espacios[0]["id"]


def test_create_reserva_happy_path(monkeypatch):
    _register_user("admin.reserva@example.com", "adminpass123", 1, "Admin", "Reserva")
    admin_token = _login("admin.reserva@example.com", "adminpass123")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    _register_user("resuser@example.com", "pass1234", 3, "Res", "User")
    token = _login("resuser@example.com", "pass1234")
    headers = {"Authorization": f"Bearer {token}"}

    esp_id = _setup_space(admin_headers)

    emitted = []
    monkeypatch.setattr(
        reservas_routes,
        "schedule_emit_webhook",
        lambda bt, event, data: emitted.append((event, data)),
    )

    payload = {
        "espacio_id": esp_id,
        "fecha": "2025-10-28",
        "hora_inicio": "09:00:00",
        "hora_fin": "10:00:00",
        "titulo": "Prueba Reserva",
    }
    resp = client.post("/api/reservas", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"]
    assert data["espacio_id"] == esp_id
    events = [e for e, _ in emitted]
    assert "reserva_creada" in events
    assert "disponibilidad_actualizada" in events


def test_pending_queue_then_approve_rejects_others(monkeypatch):
    _register_user("admin.queue@example.com", "adminpass123", 1, "Admin", "Queue")
    admin_token = _login("admin.queue@example.com", "adminpass123")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    _register_user("u1@example.com", "pass1234", 3, "U1", "User")
    _register_user("u2@example.com", "pass1234", 3, "U2", "User")
    t1 = _login("u1@example.com", "pass1234")
    t2 = _login("u2@example.com", "pass1234")
    h1 = {"Authorization": f"Bearer {t1}"}
    h2 = {"Authorization": f"Bearer {t2}"}

    esp_id = _setup_space(admin_headers)
    payload = {
        "espacio_id": esp_id,
        "fecha": "2025-11-01",
        "hora_inicio": "10:00:00",
        "hora_fin": "11:00:00",
        "titulo": "Req",
    }

    emitted = []
    monkeypatch.setattr(
        reservas_routes,
        "schedule_emit_webhook",
        lambda bt, event, data: emitted.append((event, data)),
    )

    r1 = client.post("/api/reservas", json=payload, headers=h1)
    r2 = client.post("/api/reservas", json=payload, headers=h2)
    assert r1.status_code == 200 and r2.status_code == 200
    id1 = r1.json()["id"]
    id2 = r2.json()["id"]

    approve = client.patch(f"/api/reservas/{id1}/estado", json={"estado_id": 2}, headers=admin_headers)
    assert approve.status_code == 200

    detail2 = client.get(f"/api/reservas/{id2}", headers=h2)
    assert detail2.status_code == 200
    assert detail2.json()["estado"].lower() == "rechazada"

    events = [e for e, _ in emitted]
    assert "reserva_actualizada" in events
    assert events.count("reserva_actualizada") >= 2  # aprobada + rechazada
    assert "disponibilidad_actualizada" in events


def test_disponibilidad_endpoint_reflects_slots():
    _register_user("admin.disp@example.com", "adminpass123", 1, "Admin", "Disp")
    admin_token = _login("admin.disp@example.com", "adminpass123")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    _register_user("dispuser@example.com", "pass1234", 3, "Disp", "User")
    t = _login("dispuser@example.com", "pass1234")
    h = {"Authorization": f"Bearer {t}"}

    esp_id = _setup_space(admin_headers)
    fecha = "2025-12-01"

    client.post(
        "/api/reservas",
        json={"espacio_id": esp_id, "fecha": fecha, "hora_inicio": "09:00:00", "hora_fin": "10:00:00", "titulo": "Slot"},
        headers=h,
    )

    disp = client.get(f"/api/disponibilidad?espacio_id={esp_id}&fecha={fecha}&incluir_pendientes=true", headers=h)
    assert disp.status_code == 200
    body = disp.json()
    assert any(o["hora_inicio"] == "09:00" for o in body["ocupados"])
    assert body["libres"]


def test_create_and_list_notifications():
    resp = client.post(
        "/api/auth/register",
        json={
            "email": "notifuser@example.com",
            "password": "notifpass",
            "nombre": "Notif",
            "apellido": "User",
            "tipo_usuario_id": 3,
        },
    )
    assert resp.status_code == 200
    user = resp.json()["user"]
    uid = user["id"]

    login = client.post("/api/auth/login", json={"email": "notifuser@example.com", "password": "notifpass"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {"usuario_id": uid, "titulo": "Prueba Notif", "mensaje": "Mensaje de prueba", "metadata": {"test": True}}
    r = client.post("/api/notificaciones", json=payload, headers=headers)
    assert r.status_code == 200
    nid = r.json().get("id")
    assert nid

    l = client.get(f"/api/notificaciones?usuario_id={uid}", headers=headers)
    assert l.status_code == 200
    data = l.json()
    assert isinstance(data, list)
    assert any(n["id"] == nid for n in data)
