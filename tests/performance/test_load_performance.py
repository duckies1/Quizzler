import pytest
import asyncio
import time
from httpx import AsyncClient
from app.main import app

class TestPerformance:
    """Performance tests for the API"""
    
    @pytest.mark.asyncio
    async def test_auth_endpoint_response_time(self, client: AsyncClient):
        """Test authentication endpoint response time"""
        user_data = {
            "email": "perf_test@example.com",
            "password": "testpassword123",
            "name": "Performance Test User"
        }
        
        # Measure signup time
        start_time = time.time()
        response = await client.post("/auth/signup", json=user_data)
        signup_time = time.time() - start_time
        
        assert response.status_code in [200, 201]
        assert signup_time < 2.0  # Should complete within 2 seconds
        
        # Measure signin time
        signin_data = {
            "email": user_data["email"],
            "password": user_data["password"]
        }
        start_time = time.time()
        signin_response = await client.post("/auth/signin", json=signin_data)
        signin_time = time.time() - start_time
        
        assert signin_response.status_code == 200
        assert signin_time < 1.5  # Should complete within 1.5 seconds
    
    @pytest.mark.asyncio
    async def test_quiz_creation_performance(self, client: AsyncClient):
        """Test quiz creation with large number of questions"""
        # Create user first
        user_data = {
            "email": "quiz_perf@test.com",
            "password": "test123",
            "name": "Quiz Performance Tester"
        }
        
        await client.post("/auth/signup", json=user_data)
        signin_response = await client.post("/auth/signin", json={
            "email": user_data["email"],
            "password": user_data["password"]
        })
        token = signin_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Create quiz with 50 questions
        questions = []
        for i in range(50):
            questions.append({
                "question_text": f"Question {i+1}: What is {i} + 1?",
                "option_a": str(i),
                "option_b": str(i+1),
                "option_c": str(i+2),
                "option_d": str(i+3),
                "correct_option": "b",
                "mark": 1
            })
        
        quiz_data = {
            "title": "Performance Test Quiz",
            "description": "Large quiz for performance testing",
            "duration": 60,
            "questions": questions,
            "is_trivia": False
        }
        
        start_time = time.time()
        response = await client.post("/quizzes/", json=quiz_data, headers=headers)
        creation_time = time.time() - start_time
        
        assert response.status_code in [200, 201]
        assert creation_time < 5.0  # Should complete within 5 seconds
    
    @pytest.mark.asyncio
    async def test_concurrent_quiz_starts(self, client: AsyncClient):
        """Test performance with multiple users starting quiz simultaneously"""
        # Create quiz
        creator_data = {
            "email": "concurrent_creator@test.com",
            "password": "test123",
            "name": "Concurrent Creator"
        }
        
        await client.post("/auth/signup", json=creator_data)
        signin_response = await client.post("/auth/signin", json={
            "email": creator_data["email"],
            "password": creator_data["password"]
        })
        creator_token = signin_response.json()["access_token"]
        creator_headers = {"Authorization": f"Bearer {creator_token}"}
        
        quiz_data = {
            "title": "Concurrent Access Quiz",
            "description": "Testing concurrent access",
            "duration": 30,
            "is_trivia": True,
            "questions": [
                {
                    "question_text": "Concurrent test question?",
                    "option_a": "A", "option_b": "B", "option_c": "C", "option_d": "D",
                    "correct_option": "a", "mark": 1
                }
            ]
        }
        
        create_response = await client.post("/quizzes/", json=quiz_data, headers=creator_headers)
        quiz_id = create_response.json()["quiz_id"]
        
        # Create 10 users
        user_tokens = []
        for i in range(10):
            user_data = {
                "email": f"concurrent_user_{i}@test.com",
                "password": "test123",
                "name": f"Concurrent User {i}"
            }
            await client.post("/auth/signup", json=user_data)
            signin_resp = await client.post("/auth/signin", json={
                "email": user_data["email"],
                "password": user_data["password"]
            })
            token = signin_resp.json()["access_token"]
            user_tokens.append(token)
        
        # All users start quiz simultaneously
        start_time = time.time()
        tasks = []
        for token in user_tokens:
            headers = {"Authorization": f"Bearer {token}"}
            tasks.append(client.post(f"/quizzes/{quiz_id}/start", headers=headers))
        
        responses = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        # All should succeed
        for response in responses:
            assert response.status_code == 200
        
        # Should handle 10 concurrent requests within 3 seconds
        assert total_time < 3.0
        assert len(responses) == 10
    
    @pytest.mark.asyncio
    async def test_leaderboard_performance(self, client: AsyncClient):
        """Test leaderboard performance with multiple users"""
        start_time = time.time()
        response = await client.get("/results/leaderboards/global?limit=100")
        response_time = time.time() - start_time
        
        assert response.status_code == 200
        assert response_time < 1.0  # Should load within 1 second
        
        leaderboard_data = response.json()
        assert isinstance(leaderboard_data, list)
    
    @pytest.mark.asyncio
    async def test_trivia_list_performance(self, client: AsyncClient):
        """Test trivia listing performance"""
        start_time = time.time()
        response = await client.get("/trivia?sort_by=popularity")
        response_time = time.time() - start_time
        
        assert response.status_code == 200
        assert response_time < 1.0  # Should load within 1 second
    
    @pytest.mark.asyncio
    async def test_memory_usage_during_quiz_submission(self, client: AsyncClient):
        """Test memory usage during quiz submission with large answer set"""
        # Create user and quiz
        user_data = {
            "email": "memory_test@test.com",
            "password": "test123",
            "name": "Memory Test User"
        }
        
        await client.post("/auth/signup", json=user_data)
        signin_response = await client.post("/auth/signin", json={
            "email": user_data["email"],
            "password": user_data["password"]
        })
        token = signin_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Create quiz with many questions
        questions = []
        for i in range(100):
            questions.append({
                "question_text": f"Memory test question {i}?",
                "option_a": f"Option A {i}", "option_b": f"Option B {i}",
                "option_c": f"Option C {i}", "option_d": f"Option D {i}",
                "correct_option": "a", "mark": 1
            })
        
        quiz_data = {
            "title": "Memory Test Quiz",
            "description": "Testing memory usage",
            "duration": 120,
            "questions": questions,
            "is_trivia": False
        }
        
        create_response = await client.post("/quizzes/", json=quiz_data, headers=headers)
        quiz_id = create_response.json()["quiz_id"]
        
        # Start quiz
        await client.post(f"/quizzes/{quiz_id}/start", headers=headers)
        
        # Submit large answer set
        answers = {str(i): "a" for i in range(1, 101)}  # 100 answers
        
        start_time = time.time()
        submit_response = await client.post(
            f"/quizzes/{quiz_id}/submit",
            json={"answers": answers},
            headers=headers
        )
        submit_time = time.time() - start_time
        
        assert submit_response.status_code == 200
        assert submit_time < 3.0  # Should process within 3 seconds
