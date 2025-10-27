import os, binascii
from app.config import settings

u = os.getenv("DATABASE_URL")
print("os.getenv('DATABASE_URL') repr:", repr(u))
print("settings.DATABASE_URL repr:  ", repr(settings.DATABASE_URL))
print("len(settings.DATABASE_URL):", len(settings.DATABASE_URL) if settings.DATABASE_URL else None)

if u:
    # muestra bytes tal cual (latin1 para mapear 1:1 bytes)
    print("bytes (hex):", binascii.hexlify(u.encode('latin1', errors='replace')).decode())
    # intenta codificar a utf-8
    try:
        print("utf8 bytes:", u.encode('utf-8'))
    except Exception as e:
        print("utf8 encode error:", repr(e))
