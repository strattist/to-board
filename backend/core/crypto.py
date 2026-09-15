import base64
from cryptography.fernet import Fernet
from .config import get_settings

def _fernet() -> Fernet:
    key = get_settings().secret_key.encode()
    try:
        base64.urlsafe_b64decode(key)
    except Exception as exc:
        raise ValueError('SECRET_KEY must be a Fernet key') from exc
    return Fernet(key)

def encrypt_api_key(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()

def decrypt_api_key(value: str) -> str:
    return _fernet().decrypt(value.encode()).decode()
