from passlib.context import CryptContext

# Use pbkdf2_sha256 for password hashing to avoid bcrypt native issues and the
# 72-byte limit. This will be used for new registrations and for verification.
# Existing bcrypt hashes (if any) will not be recognized after this change —
# recommend recreating test users if needed.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
