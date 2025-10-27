from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.usuario import Usuario
from .jwt_handler import decode_access_token
import logging

logger = logging.getLogger(__name__)

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Usuario:
    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        # Log minimal info to help debugging (do not log token value). Use WARNING
        # so the message appears in normal server logs.
        logger.warning(
            "Authentication failed while decoding token (scheme=%s, token_len=%d)",
            credentials.scheme,
            len(token) if token else 0,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_sub = payload.get("sub")
    if raw_sub is None:
        logger.warning("Token payload missing 'sub' claim: %s", payload)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

    # ensure we have an integer user id for DB lookup
    try:
        user_id = int(raw_sub)
    except Exception:
        logger.warning("Token 'sub' claim is not an integer: %s", raw_sub)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if user is None:
        logger.warning("User referenced in token not found (user_id=%s)", user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    return user

def require_admin(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    if current_user.tipo_usuario.nivel_prioridad != 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user
