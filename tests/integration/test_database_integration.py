import pytest
from httpx import AsyncClient
from app.main import app

class TestDatabaseIntegration:
    """Integration tests for database operations"""
    
    @pytest.mark.asyncio
    async def test_user_crud_operations(self, client: AsyncClient):
        """Test user CRUD through API"""
        # Create user via signup
        user_data = {
            "email": "crud@test.com",
            "password": "testpassword123",
            "name": "CRUD Test User"
        }
        
        signup_response = await client.post("/auth/signup", json=user_data)
        assert signup_response.status_code in [200, 201]
        
        # Get user token
        signin_response = await client.post("/auth/signin", json={
            "email": user_data["email"],
            "password": user_data["password"]
        })
        token_data = signin_response.json()
        headers = {"Authorization": f"Bearer {token_data['access_token']}"}
        
        # Read user profile
        profile_response = await client.get("/users/me", headers=headers)
        assert profile_response.status_code == 200
        
        # Update user profile
        update_data = {"name": "Updated CRUD User"}
        update_response = await client.patch("/users/me", json=update_data, headers=headers)
        assert update_response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_quiz_persistence(self, client: AsyncClient, test_user_token, test_quiz_data):
        """Test quiz data persistence"""
        if test_user_token:
            headers = {"Authorization": f"Bearer {test_user_token}"}
            
            # Create quiz
            create_response = await client.post("/quizzes/", json=test_quiz_data, headers=headers)
            quiz_id = create_response.json()["quiz_id"]
            
            # Verify quiz exists
            get_response = await client.get(f"/quizzes/{quiz_id}", headers=headers)
            assert get_response.status_code == 200
            
            # Verify quiz in user's list
            list_response = await client.get("/quizzes/", headers=headers)
            assert list_response.status_code == 200
            quizzes = list_response.json()
            quiz_ids = [q["id"] for q in quizzes]
            assert quiz_id in quiz_ids
    
    @pytest.mark.asyncio
    async def test_session_constraints(self, client: AsyncClient, test_user_token, test_quiz_data):
        """Test database constraints (one attempt per user)"""
        if test_user_token:
            headers = {"Authorization": f"Bearer {test_user_token}"}
            
            # Create quiz
            create_response = await client.post("/quizzes/", json=test_quiz_data, headers=headers)
            quiz_id = create_response.json()["quiz_id"]
            
            # First attempt
            start_response1 = await client.post(f"/quizzes/{quiz_id}/start", headers=headers)
            assert start_response1.status_code == 200
            
            # Submit first attempt
            answers = {"1": "b"}
            submit_response = await client.post(
                f"/quizzes/{quiz_id}/submit",
                json={"answers": answers},
                headers=headers
            )
            assert submit_response.status_code == 200
            
            # Second attempt should fail
            start_response2 = await client.post(f"/quizzes/{quiz_id}/start", headers=headers)
            assert start_response2.status_code == 400  # Already attempted
