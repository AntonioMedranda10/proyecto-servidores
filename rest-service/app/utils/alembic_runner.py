import os
import logging
from alembic.config import Config
from alembic import command

logger = logging.getLogger("alembic_runner")


def run_migrations_if_needed(alembic_ini_path: str = None):
    """Run `alembic upgrade head` using the provided alembic.ini path or the package default.

    This function is safe to call on startup; it will attempt to run migrations and log errors
    but won't raise exceptions to break application startup.
    """
    try:
        base_dir = os.path.dirname(os.path.dirname(__file__))
        if alembic_ini_path is None:
            alembic_ini_path = os.path.join(base_dir, '..', 'alembic.ini')
            # try alternative location
            if not os.path.exists(alembic_ini_path):
                alembic_ini_path = os.path.join(base_dir, 'alembic.ini')

        if not os.path.exists(alembic_ini_path):
            logger.info(f"alembic.ini not found at {alembic_ini_path}; skipping automatic migrations")
            return

        cfg = Config(alembic_ini_path)
        # allow env var override of sqlalchemy.url (env handled in env.py)
        logger.info("Running alembic upgrade head...")
        command.upgrade(cfg, 'head')
        logger.info("Alembic upgrade head finished")
    except Exception as e:
        logger.exception(f"Failed to run alembic migrations automatically: {e}")
        # don't raise; just log
        return
