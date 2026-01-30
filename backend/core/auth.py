"""Authentication core utilities."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt
from passlib.context import CryptContext

from backend.core.settings import get_settings
from backend.core.passwords import verify_password as verify_legacy_pbkdf2

# Setup Passlib context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against hash.
    Supports both legacy custom PBKDF2 and new Passlib (bcrypt) hashes.
    """
    if hashed_password.startswith("pbkdf2$"):
        return verify_legacy_pbkdf2(plain_password, hashed_password)
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash using bcrypt (via Passlib)."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token.
    
    Args:
        data: Payload data (must include 'sub' for username)
        expires_delta: Optional expiration time delta
    """
    to_encode = data.copy()
    settings = get_settings()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # Default expiration if not provided (e.g. 30 mins)
        expire = datetime.now(timezone.utc) + timedelta(minutes=30)
        
    to_encode.update({"exp": expire})
    
    # Use session_secret as JWT secret key (should be secure in prod)
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.session_secret, 
        algorithm="HS256"
    )
    return encoded_jwt
