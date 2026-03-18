from datetime import datetime, timedelta
from passlib.context import CryptContext
from jose import jwt, JWTError
from backend.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

ACCESS_TOKEN_EXPIRE_HOURS = 8

class AuthService:
    @staticmethod
    def create_access_token(data: dict) -> str:
        payload = data.copy()
        payload["exp"] = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
        return jwt.encode(payload, settings.secret_key, algorithm="HS256")

    @staticmethod
    def decode_token(token: str) -> dict:
        try:
            return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        except JWTError:
            raise ValueError("Invalid token")
