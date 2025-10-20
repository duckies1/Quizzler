import pytest
from httpx import AsyncClient
from app.main import app

class TestAuthIntegration:
    """Integration tests for authentication flow"""
    
    @pytest.mark.asyncio
    async def test_signup_signin_flow(self, client: AsyncClient):
        """Test complete signup and signin flow"""
        # Test data
        user_data = {
            "email": "integration@test.com",
            "password": "testpassword123",
            "name": "Integration Test User"
        }
        
        # Signup
        signup_response = await client.post("/auth/signup", json=user_data)
        assert signup_response.status_code in [200, 201]
        signup_data = signup_response.json()
        assert "access_token" in signup_data
        
        # Signin
        signin_data = {
            "email": user_data["email"],
            "password": user_data["password"]
        }
        signin_response = await client.post("/auth/signin", json=signin_data)
        assert signin_response.status_code == 200
        signin_result = signin_response.json()
        assert "access_token" in signin_result
    
    @pytest.mark.asyncio
    async def test_protected_route_without_token(self, client: AsyncClient):
        """Test accessing protected route without token"""
        response = await client.get("/auth/me")
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_protected_route_with_token(self, client: AsyncClient, test_user_token):
        """Test accessing protected route with valid token"""
        if test_user_token:
            headers = {"Authorization": f"Bearer {test_user_token}"}
            response = await client.get("/auth/me", headers=headers)
            assert response.status_code == 200
            user_data = response.json()
            assert "email" in user_data

class TestQuizIntegration:
    """Integration tests for quiz operations"""
    
    @pytest.mark.asyncio
    async def test_create_quiz_flow(self, client: AsyncClient, test_user_token, test_quiz_data):
        """Test quiz creation flow"""
        if test_user_token:
            headers = {"Authorization": f"Bearer {test_user_token}"}
            
            # Create quiz
            response = await client.post("/quizzes/", json=test_quiz_data, headers=headers)
            assert response.status_code in [200, 201]
            quiz_data = response.json()
            assert "quiz_id" in quiz_data
            
            return quiz_data["quiz_id"]
    
    @pytest.mark.asyncio
    async def test_quiz_session_flow(self, client: AsyncClient, test_user_token, test_quiz_data):
        """Test complete quiz session flow: create -> start -> submit"""
        if test_user_token:
            headers = {"Authorization": f"Bearer {test_user_token}"}
            
            # 1. Create quiz
            create_response = await client.post("/quizzes/", json=test_quiz_data, headers=headers)
            assert create_response.status_code in [200, 201]
            quiz_id = create_response.json()["quiz_id"]
            
            # 2. Start quiz
            start_response = await client.post(f"/quizzes/{quiz_id}/start", headers=headers)
            assert start_response.status_code == 200
            session_data = start_response.json()
            assert "questions" in session_data
            assert "started_at" in session_data
            
            # 3. Submit answers
            answers = {"1": "b", "2": "c"}  # Assuming question IDs
            submit_response = await client.post(
                f"/quizzes/{quiz_id}/submit",
                json={"answers": answers},
                headers=headers
            )
            assert submit_response.status_code == 200
            result_data = submit_response.json()
            assert "score" in result_data
    
    @pytest.mark.asyncio
    async def test_trivia_quiz_workflow(self, client: AsyncClient, admin_user_token, trivia_quiz_data):
        """Test trivia quiz creation and access"""
        if admin_user_token:
            admin_headers = {"Authorization": f"Bearer {admin_user_token}"}
            
            # Create trivia quiz (admin only)
            response = await client.post("/quizzes/", json=trivia_quiz_data, headers=admin_headers)
            assert response.status_code in [200, 201]
            quiz_data = response.json()
            quiz_id = quiz_data["quiz_id"]
            
            # Check trivia list (public access)
            trivia_response = await client.get("/trivia")
            assert trivia_response.status_code == 200
            trivia_list = trivia_response.json()
            assert isinstance(trivia_list, list)

class TestResultsIntegration:
    """Integration tests for results and leaderboards"""
    
    @pytest.mark.asyncio
    async def test_results_after_quiz_submission(self, client: AsyncClient, test_user_token, test_quiz_data):
        """Test getting results after quiz submission"""
        if test_user_token:
            headers = {"Authorization": f"Bearer {test_user_token}"}
            
            # Create and complete a quiz first
            create_response = await client.post("/quizzes/", json=test_quiz_data, headers=headers)
            quiz_id = create_response.json()["quiz_id"]
            
            # Start quiz
            await client.post(f"/quizzes/{quiz_id}/start", headers=headers)
            
            # Submit quiz
            answers = {"1": "b", "2": "c"}
            await client.post(f"/quizzes/{quiz_id}/submit", json={"answers": answers}, headers=headers)
            
            # Get results
            results_response = await client.get(f"/results/{quiz_id}/my-result", headers=headers)
            assert results_response.status_code == 200
            results_data = results_response.json()
            assert "score" in results_data
            assert "answers" in results_data
    
    @pytest.mark.asyncio
    async def test_global_leaderboard(self, client: AsyncClient):
        """Test global leaderboard access"""
        response = await client.get("/results/leaderboards/global")
        assert response.status_code == 200
        leaderboard_data = response.json()
        assert isinstance(leaderboard_data, list)
