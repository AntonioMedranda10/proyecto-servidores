from datetime import datetime, timedelta
from typing import Optional
import logging
from jose import JWTError, jwt
from ..config import settings

# Log via the uvicorn.error logger so messages appear in the uvicorn stdout/stderr
logger = logging.getLogger("uvicorn.error")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create a JWT access token with an expiration."""
    to_encode = data.copy()
    # ensure 'sub' is a string (some JWT libraries expect subject as string)
    if "sub" in to_encode and to_encode["sub"] is not None:
        try:
            to_encode["sub"] = str(to_encode["sub"])
        except Exception:
            # fallback: remove sub if it can't be cast
            to_encode.pop("sub", None)
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str):
    """Decode a JWT token and return the payload or None on failure.

    This function logs decode errors so the server operator can see why a token
    is rejected (invalid signature, expired, wrong algorithm, etc.).
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError as e:
        # Log at WARNING so it is visible in the server output. Avoid logging
        # the token itself; include the error message only.
        logger.warning("JWT decode error: %s", str(e))
        return None
