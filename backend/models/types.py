"""SQLAlchemy column types that apply transparent crypto at the ORM boundary."""
from sqlalchemy.types import TypeDecorator, Text
from backend.services.encryption import encrypt, decrypt


class EncryptedString(TypeDecorator):
    """Transparent encrypt-on-write, decrypt-on-read column type.

    Stored as Text under the hood (Fernet ciphertext is url-safe base64).
    decrypt() tolerates plaintext rows so existing data remains readable until
    Phase 3 cutover re-encrypts everything.
    """
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt(str(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return decrypt(value)
