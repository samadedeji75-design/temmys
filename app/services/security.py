import base64
import hashlib
from cryptography.fernet import Fernet
from flask import current_app


def _get_fernet():
    # Derive a valid 32-byte urlsafe-base64 Fernet key from the app's
    # existing SECRET_KEY so no separate key needs to be provisioned or
    # stored anywhere new. If SECRET_KEY ever changes, previously encrypted
    # passwords become undecryptable — this is the same operational
    # constraint the session cookie already has, nothing new to manage.
    secret = current_app.config["SECRET_KEY"].encode("utf-8")
    derived = hashlib.sha256(secret).digest()
    key = base64.urlsafe_b64encode(derived)
    return Fernet(key)


def encrypt_password(raw_password):
    return _get_fernet().encrypt(raw_password.encode("utf-8")).decode("utf-8")


def decrypt_password(encrypted_value):
    if not encrypted_value:
        return None
    return _get_fernet().decrypt(encrypted_value.encode("utf-8")).decode("utf-8")
