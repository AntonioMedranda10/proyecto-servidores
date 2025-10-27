from app.config import settings
import hashlib
s = settings.SECRET_KEY or ""
print("len:", len(s))
print("sha256:", hashlib.sha256(s.encode("utf-8")).hexdigest())
