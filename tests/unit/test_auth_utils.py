import pytest
from unittest.mock import Mock, patch
from app.utils.auth_utils import get_current_user, require_admin
from app.database import Database
from fastapi import HTTPException
import jwt

class TestAuthUtils:
    """Test authentication utility functions"""
    
    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self, mock_auth_utils):
        """Test getting current user with valid token"""
        from fastapi.security import HTTPAuthorizationCredentials
        
        mock_auth_utils.return_value = {"id": "test-user-id", "email": "test@example.com"}
        
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-token")
        result = await get_current_user(credentials)
        
        assert result is not None
        assert result["id"] == "test-user-id"
        assert result["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, mock_auth_utils):
        """Test getting current user with invalid token"""
        from fastapi.security import HTTPAuthorizationCredentials
        
        mock_auth_utils.side_effect = HTTPException(status_code=401, detail="Invalid token")
        
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid-token")
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials)
        
        assert exc_info.value.status_code == 401
    
    @pytest.mark.asyncio
    async def test_require_admin_valid_admin(self):
        """Test require_admin with valid admin user"""
        admin_user = {
            "id": "admin-id",
            "email": "admin@quizzler.com",
            "name": "Admin User"
        }
        
        result = await require_admin(admin_user)
        assert result == admin_user
    
    @pytest.mark.asyncio
    async def test_require_admin_non_admin(self):
        """Test require_admin with non-admin user"""
        regular_user = {
            "id": "user-id",
            "email": "user@example.com",
            "name": "Regular User"
        }
        
        with pytest.raises(HTTPException) as exc_info:
            await require_admin(regular_user)
        
        assert exc_info.value.status_code == 403
