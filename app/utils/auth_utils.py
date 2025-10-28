from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import supabase
from typing import Optional
import logging

security = HTTPBearer()

def verify_supabase_token(token: str):
    """Verify Supabase JWT token"""
    try:
        user = supabase.auth.get_user(token)
        if user and user.user:
            return user.user
        return None
    except Exception as e:
        logging.error(f"Supabase token verification failed: {e}")
        return None

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from Supabase JWT token"""
    token = credentials.credentials
    
    user = verify_supabase_token(token)
    if user:
        return {
            "id": user.id,
            "email": user.email,
            "metadata": user.user_metadata
        }

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
    admin_emails = ["admin@quizzler.com", "adityatorgal581@gmail.com"] 
    return user.get("email") in admin_emails

async def require_admin(current_user: dict = Depends(get_current_user)):
    """Require admin privileges"""
    if not is_admin_user(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user

async def get_current_user_from_token(token: str) -> Optional[dict]:
    """Get current user from a raw JWT token string"""
    try:
        user = verify_supabase_token(token)
        if user:
            return {
                "id": user.id,
                "email": user.email,
                "metadata": user.user_metadata
            }
        return None
    except Exception as e:
        logging.error(f"Error getting user from token: {e}")
        return None
