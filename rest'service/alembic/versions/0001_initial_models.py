"""initial models

Revision ID: 0001_initial_models
Revises: 
Create Date: 2025-10-28 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0001_initial_models'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # --- tipo_usuario ---
    op.create_table(
        'tipo_usuario',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nombre', sa.String(length=100), nullable=False, unique=True),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('nivel_prioridad', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('permisos', postgresql.JSONB(), nullable=True),
        sa.Column('creado_en', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('actualizado_en', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # --- categoria_espacio ---
    op.create_table(
        'categoria_espacio',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nombre', sa.String(length=100), nullable=False, unique=True),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('requiere_aprobacion', sa.Boolean(), nullable=True),
        sa.Column('capacidad_maxima', sa.Integer(), nullable=True),
        sa.Column('creado_en', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('actualizado_en', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # --- tipo_evento ---
    op.create_table(
        'tipo_evento',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nombre', sa.String(length=100), nullable=False, unique=True),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('requiere_aprobacion', sa.Boolean(), nullable=True),
        sa.Column('color_hex', sa.String(length=7), nullable=True),
        sa.Column('creado_en', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('actualizado_en', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # --- estado_reserva ---
    op.create_table(
        'estado_reserva',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nombre', sa.String(length=100), nullable=False, unique=True),
        sa.Column('color_hex', sa.String(length=7), nullable=True),
        sa.Column('permite_edicion', sa.Boolean(), nullable=True),
        sa.Column('es_final', sa.Boolean(), nullable=True),
        sa.Column('orden', sa.Integer(), nullable=True),
        sa.Column('creado_en', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('actualizado_en', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # --- usuario (depends on tipo_usuario) ---
    op.create_table(
        'usuario',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(length=255), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column('apellido', sa.String(length=100), nullable=False),
        sa.Column('telefono', sa.String(length=20), nullable=True),
        sa.Column('tipo_usuario_id', sa.Integer(), sa.ForeignKey('tipo_usuario.id'), nullable=False),
        sa.Column('estado', sa.String(length=20), nullable=False, server_default='activo'),
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
        sa.Column('creado_en', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('actualizado_en', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # --- espacio (depends on categoria_espacio) ---
    op.create_table(
        'espacio',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('codigo', sa.String(length=50), nullable=False, unique=True),
        sa.Column('nombre', sa.String(length=200), nullable=False),
        sa.Column('categoria_id', sa.Integer(), sa.ForeignKey('categoria_espacio.id'), nullable=False),
        sa.Column('capacidad_maxima', sa.Integer(), nullable=False),
        sa.Column('imagen_url', sa.String(length=500), nullable=True),
        sa.Column('estado', sa.String(length=20), nullable=False, server_default='activo'),
        sa.Column('referencia_id', sa.Integer(), nullable=True),
        sa.Column('creado_en', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('actualizado_en', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # --- caracteristica_espacio (depends on espacio) ---
    op.create_table(
        'caracteristica_espacio',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('espacio_id', sa.Integer(), sa.ForeignKey('espacio.id'), nullable=False),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column('disponible', sa.Boolean(), nullable=True),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('creado_en', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('actualizado_en', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # --- reserva (depends on usuario, espacio, tipo_evento, estado_reserva) ---
    op.create_table(
        'reserva',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('codigo', sa.String(length=100), nullable=False, unique=True),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuario.id'), nullable=False),
        sa.Column('espacio_id', sa.Integer(), sa.ForeignKey('espacio.id'), nullable=False),
        sa.Column('tipo_evento_id', sa.Integer(), sa.ForeignKey('tipo_evento.id'), nullable=True),
        sa.Column('estado_id', sa.Integer(), sa.ForeignKey('estado_reserva.id'), nullable=True),
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('hora_inicio', sa.Time(), nullable=False),
        sa.Column('hora_fin', sa.Time(), nullable=False),
        sa.Column('titulo', sa.String(length=250), nullable=True),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('es_bloqueo', sa.Boolean(), nullable=True),
        sa.Column('motivo_bloqueo', sa.String(length=500), nullable=True),
        sa.Column('asistentes_estimada', sa.Integer(), nullable=True),
        sa.Column('creado_en', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('actualizado_en', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # --- notificacion (depends on usuario) ---
    op.create_table(
        'notificacion',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuario.id'), nullable=False),
        sa.Column('titulo', sa.String(length=250), nullable=True),
        sa.Column('mensaje', sa.Text(), nullable=True),
        sa.Column('leida', sa.Boolean(), nullable=True, server_default=sa.text('false')),
        sa.Column('reserva_id', sa.Integer(), nullable=True),
        sa.Column('espacio_id', sa.Integer(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('leida_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('creado_en', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # --- disponibilidad_espacio (depends on espacio) ---
    op.create_table(
        "disponibilidad_espacio",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("espacio_id", sa.Integer, sa.ForeignKey("espacio.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dia_semana", sa.String(10), nullable=False),
        sa.Column("hora_inicio", sa.Time, nullable=False),
        sa.Column("hora_fin", sa.Time, nullable=False),
        sa.Column("activo", sa.Boolean, nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_disp_espacio", "disponibilidad_espacio", ["espacio_id"])

    # indexes
    op.create_index('ix_usuario_email', 'usuario', ['email'], unique=True)
    op.create_index('ix_usuario_id', 'usuario', ['id'])
    op.create_index('ix_tipo_usuario_id', 'tipo_usuario', ['id'])
    op.create_index('ix_espacio_codigo', 'espacio', ['codigo'], unique=True)
    op.create_index('ix_reserva_codigo', 'reserva', ['codigo'], unique=True)


def downgrade():
    # 1) índices sueltos
    op.drop_index('ix_reserva_codigo', table_name='reserva')
    op.drop_index('ix_espacio_codigo', table_name='espacio')
    op.drop_index('ix_tipo_usuario_id', table_name='tipo_usuario')
    op.drop_index('ix_usuario_id', table_name='usuario')
    op.drop_index('ix_usuario_email', table_name='usuario')

    # 2) estructuras con FK (hijos antes que padres)
    # disponibilidad_espacio depende de espacio
    op.drop_index("ix_disp_espacio")
    op.drop_table("disponibilidad_espacio")

    # caracteristica_espacio depende de espacio
    op.drop_table('caracteristica_espacio')

    # reserva depende de usuario, espacio, tipo_evento, estado_reserva
    op.drop_table('reserva')

    # notificacion depende de usuario
    op.drop_table('notificacion')

    # padres
    op.drop_table('espacio')
    op.drop_table('usuario')
    op.drop_table('estado_reserva')
    op.drop_table('tipo_evento')
    op.drop_table('categoria_espacio')
    op.drop_table('tipo_usuario')