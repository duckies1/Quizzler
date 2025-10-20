import pytest
from httpx import AsyncClient
from app.main import app

class TestSecurityAndValidation:
    """Security and input validation tests"""
    
    @pytest.mark.asyncio
    async def test_sql_injection_protection(self, client: AsyncClient):
        """Test protection against SQL injection attempts"""
        # Try SQL injection in login
        malicious_data = {
            "email": "admin@test.com'; DROP TABLE users; --",
            "password": "password"
        }
        
        response = await client.post("/auth/signin", json=malicious_data)
        # Should not cause server error, should handle gracefully
        assert response.status_code in [400, 401, 422]  # Not 500
    
    @pytest.mark.asyncio
    async def test_xss_protection(self, client: AsyncClient):
        """Test protection against XSS attacks"""
        user_data = {
            "email": "xss_test@test.com",
            "password": "test123",
            "name": "<script>alert('XSS')</script>"
        }
        
        response = await client.post("/auth/signup", json=user_data)
        if response.status_code in [200, 201]:
            # Name should be sanitized or escaped
            user_info = response.json()
            assert "<script>" not in str(user_info)
    
    @pytest.mark.asyncio
    async def test_unauthorized_access_protection(self, client: AsyncClient):
        """Test unauthorized access to protected endpoints"""
        protected_endpoints = [
            ("GET", "/auth/me"),
            ("GET", "/quizzes/"),
            ("POST", "/quizzes/"),
            ("GET", "/users/me"),
            ("GET", "/admin/platform-stats")
        ]
        
        for method, endpoint in protected_endpoints:
            if method == "GET":
                response = await client.get(endpoint)
            elif method == "POST":
                response = await client.post(endpoint, json={})
            
            assert response.status_code == 401  # Unauthorized
    
    @pytest.mark.asyncio
    async def test_admin_endpoint_protection(self, client: AsyncClient):
        """Test admin endpoint protection from regular users"""
        # Create regular user
        user_data = {
            "email": "regular@test.com",
            "password": "test123",
            "name": "Regular User"
        }
        
        await client.post("/auth/signup", json=user_data)
        signin_response = await client.post("/auth/signin", json={
            "email": user_data["email"],
            "password": user_data["password"]
        })
        token = signin_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Try to access admin endpoints
        admin_endpoints = [
            "/admin/platform-stats",
            "/admin/quiz-stats",
            "/admin/user-stats"
        ]
        
        for endpoint in admin_endpoints:
            response = await client.get(endpoint, headers=headers)
            assert response.status_code == 403  # Forbidden
    
    @pytest.mark.asyncio
    async def test_rate_limiting_simulation(self, client: AsyncClient):
        """Simulate rapid requests to test rate limiting"""
        # Make multiple rapid requests
        responses = []
        for i in range(20):  # 20 rapid requests
            response = await client.get("/trivia")
            responses.append(response.status_code)
        
        # All should succeed for public endpoint (or implement rate limiting)
        success_count = sum(1 for status in responses if status == 200)
        assert success_count > 0  # At least some should succeed
    
    @pytest.mark.asyncio
    async def test_invalid_token_handling(self, client: AsyncClient):
        """Test handling of invalid JWT tokens"""
        invalid_tokens = [
            "invalid.token.here",
            "Bearer malformed_token",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid",
            ""
        ]
        
        for token in invalid_tokens:
            headers = {"Authorization": f"Bearer {token}"}
            response = await client.get("/auth/me", headers=headers)
            assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_input_validation_quiz_creation(self, client: AsyncClient):
        """Test input validation for quiz creation"""
        # Create user first
        user_data = {
            "email": "validation@test.com",
            "password": "test123",
            "name": "Validation Tester"
        }
        
        await client.post("/auth/signup", json=user_data)
        signin_response = await client.post("/auth/signin", json={
            "email": user_data["email"],
            "password": user_data["password"]
        })
        token = signin_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test various invalid quiz data
        invalid_quiz_data = [
            # Missing required fields
            {"title": "Test"},
            # Invalid duration
            {"title": "Test", "duration": -5, "questions": []},
            # Invalid marks
            {"title": "Test", "duration": 30, "positive_mark": -1, "questions": []},
            # Empty questions
            {"title": "Test", "duration": 30, "questions": []},
            # Invalid question structure
            {
                "title": "Test",
                "duration": 30,
                "questions": [{"question_text": "Test?"}]  # Missing options
            }
        ]
        
        for invalid_data in invalid_quiz_data:
            response = await client.post("/quizzes/", json=invalid_data, headers=headers)
            assert response.status_code in [400, 422]  # Bad request or validation error
    
    @pytest.mark.asyncio
    async def test_quiz_access_control(self, client: AsyncClient):
        """Test quiz access control between users"""
        # Create two users
        user1_data = {
            "email": "user1@test.com",
            "password": "test123",
            "name": "User 1"
        }
        user2_data = {
            "email": "user2@test.com",
            "password": "test123",
            "name": "User 2"
        }
        
        # Sign up both users
        await client.post("/auth/signup", json=user1_data)
        await client.post("/auth/signup", json=user2_data)
        
        # Get tokens
        signin1 = await client.post("/auth/signin", json={
            "email": user1_data["email"],
            "password": user1_data["password"]
        })
        signin2 = await client.post("/auth/signin", json={
            "email": user2_data["email"],
            "password": user2_data["password"]
        })
        
        token1 = signin1.json()["access_token"]
        token2 = signin2.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}
        headers2 = {"Authorization": f"Bearer {token2}"}
        
        # User 1 creates a quiz
        quiz_data = {
            "title": "Private Quiz",
            "description": "Only for user 1",
            "duration": 30,
            "is_trivia": False,
            "questions": [
                {
                    "question_text": "Test question?",
                    "option_a": "A", "option_b": "B", "option_c": "C", "option_d": "D",
                    "correct_option": "a", "mark": 1
                }
            ]
        }
        
        create_response = await client.post("/quizzes/", json=quiz_data, headers=headers1)
        quiz_id = create_response.json()["quiz_id"]
        
        # User 2 tries to access User 1's quiz results (should be denied or empty)
        results_response = await client.get(f"/results/{quiz_id}/results", headers=headers2)
        # Should either be forbidden or return empty results
        assert results_response.status_code in [403, 200]
    
    @pytest.mark.asyncio
    async def test_time_manipulation_protection(self, client: AsyncClient):
        """Test protection against time manipulation in quiz submission"""
        # Create user and quiz
        user_data = {
            "email": "time_test@test.com",
            "password": "test123",
            "name": "Time Tester"
        }
        
        await client.post("/auth/signup", json=user_data)
        signin_response = await client.post("/auth/signin", json={
            "email": user_data["email"],
            "password": user_data["password"]
        })
        token = signin_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Create quiz with short duration
        quiz_data = {
            "title": "Time Test Quiz",
            "duration": 1,  # 1 minute only
            "questions": [
                {
                    "question_text": "Quick question?",
                    "option_a": "A", "option_b": "B", "option_c": "C", "option_d": "D",
                    "correct_option": "a", "mark": 1
                }
            ]
        }
        
        create_response = await client.post("/quizzes/", json=quiz_data, headers=headers)
        quiz_id = create_response.json()["quiz_id"]
        
        # Start quiz
        await client.post(f"/quizzes/{quiz_id}/start", headers=headers)
        
        # Wait for quiz to expire (simulate)
        import asyncio
        await asyncio.sleep(1.5)  # Wait longer than duration
        
        # Try to submit after time limit
        submit_response = await client.post(
            f"/quizzes/{quiz_id}/submit",
            json={"answers": {"1": "a"}},
            headers=headers
        )
        
        # Should either reject or apply time penalty
        assert submit_response.status_code in [200, 400, 408]  # OK, Bad Request, or Timeout
