"""JWT token generation and validation."""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from app.core.config import get_settings

settings = get_settings()


def create_access_token(
    subject: int,
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Create JWT access token."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    
    if additional_claims:
        to_encode.update(additional_claims)

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm="HS256",
    )
    return encoded_jwt


def create_refresh_token(subject: int) -> str:
    """Create JWT refresh token."""
    expire = datetime.utcnow() + timedelta(
        days=settings.refresh_token_expire_days
    )
    
    to_encode = {
        "sub": str(subject),
        "type": "refresh",
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm="HS256",
    )
    return encoded_jwt


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify and decode JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=["HS256"],
        )
        return payload
    except JWTError:
        return None


def get_user_id_from_token(token: str) -> Optional[int]:
    """Extract user ID from token."""
    payload = verify_token(token)
    if payload and "sub" in payload:
        try:
            return int(payload["sub"])
        except (ValueError, TypeError):
            return None
    return None
