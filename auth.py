import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv

from database import get_db

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "junaidi-builders-secret-key-change-in-production-2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24 * 7  # 7 days

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    db = get_db()
    user = await db.users.find_one({"email": email})
    if user is None:
        raise credentials_exception

    user["id"] = str(user["_id"])
    return user


def require_admin(user: dict = Depends(get_current_user)):
    """Only admin can perform this action."""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can perform this action"
        )
    return user


def require_contractor(user: dict = Depends(get_current_user)):
    """Admin or contractor can perform this action."""
    if user.get("role") not in ("admin", "contractor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and contractors can perform this action"
        )
    return user


def require_financial_access(user: dict = Depends(get_current_user)):
    """Admin, contractor, or subcontractor can perform this action."""
    if user.get("role") not in ("admin", "contractor", "subcontractor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins, contractors and subcontractors can perform this action"
        )
    return user


def require_worker_management_access(user: dict = Depends(get_current_user)):
    """Admin, contractor, or subcontractor can manage workers."""
    if user.get("role") not in ("admin", "contractor", "subcontractor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins, contractors and subcontractors can manage workers"
        )
    return user


async def seed_admin():
    """Create the default admin account if no admin exists."""
    db = get_db()
    existing_admin = await db.users.find_one({"role": "admin"})
    if not existing_admin:
        admin_doc = {
            "name": "Admin",
            "email": "admin@junaidi.com",
            "password": hash_password("admin123"),
            "role": "admin",
            "created_by": None,
        }
        await db.users.insert_one(admin_doc)
        print("🔑 Default admin seeded: admin@junaidi.com / admin123")
    else:
        print("✅ Admin account exists")
