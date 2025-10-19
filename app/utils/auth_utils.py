# JWT validation helper and Supabase Auth utilities
import jwt
from datetime import datetime, timedelta
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings
from app.database import supabase, supabase_admin
from typing import Optional
import logging

# Security scheme for JWT tokens
security = HTTPBearer()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=24)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt

def verify_token(token: str):
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

def verify_supabase_token(token: str):
    """Verify Supabase JWT token"""
    try:
        # Verify token with Supabase
        user = supabase.auth.get_user(token)
        if user and user.user:
            return user.user
        return None
    except Exception as e:
        logging.error(f"Supabase token verification failed: {e}")
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from JWT token"""
    token = credentials.credentials
    
    # First try to verify with Supabase
    user = verify_supabase_token(token)
    if user:
        return {
            "id": user.id,
            "email": user.email,
            "metadata": user.user_metadata
        }
    
    # Fallback to custom JWT verification
    try:
        payload = verify_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload"
            )
        return {"id": user_id, "email": payload.get("email")}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

async def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Get current user from JWT token (optional)"""
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None

def is_admin_user(user: dict) -> bool:
    """Check if user is admin (you can customize this logic)"""
    # For now, we'll use email-based admin check
    # You can modify this to use a database field or other logic
    admin_emails = ["admin@quizzler.com"]  # Add your admin emails here
    return user.get("email") in admin_emails

async def require_admin(current_user: dict = Depends(get_current_user)):
    """Require admin privileges"""
    if not is_admin_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user
