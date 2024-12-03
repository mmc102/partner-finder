from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv
import os

load_dotenv()

# Fetch the database URL from the environment
JWT_SECRET = os.getenv("JWT_SECRET")

assert JWT_SECRET is not None

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  * 24 * 365 # 1 year yolo

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hash a password
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

# Verify a password
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# Create a JWT token
def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=ALGORITHM)

# Verify a JWT token
def decode_access_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
