import pytest
from httpx import AsyncClient
from app.main import app
import asyncio

class TestCompleteUserJourney:
    """End-to-end tests simulating complete user journeys"""
    
    @pytest.mark.asyncio
    async def test_educator_creates_and_manages_quiz(self, client: AsyncClient):
        """Complete educator journey: signup -> create quiz -> invite users -> view results"""
        
        # 1. Educator signs up
        educator_data = {
            "email": "educator@university.edu",
            "password": "educator123",
            "name": "Dr. Smith"
        }
        
        signup_response = await client.post("/auth/signup", json=educator_data)
        assert signup_response.status_code in [200, 201]
        
        # 2. Educator signs in
        signin_response = await client.post("/auth/signin", json={
            "email": educator_data["email"],
            "password": educator_data["password"]
        })
        educator_token = signin_response.json()["access_token"]
        educator_headers = {"Authorization": f"Bearer {educator_token}"}
        
        # 3. Create a private quiz
        quiz_data = {
            "title": "Database Systems Final Exam",
            "description": "Final examination for CS 432",
            "topic": "computer_science",
            "duration": 120,
            "positive_mark": 2,
            "negative_mark": 1,
            "navigation_type": "restricted",
            "tab_switch_exit": True,
            "difficulty": "hard",
            "is_trivia": False,
            "questions": [
                {
                    "question_text": "What is normalization in databases?",
                    "option_a": "Data compression",
                    "option_b": "Organizing data to reduce redundancy",
                    "option_c": "Data encryption",
                    "option_d": "Data backup",
                    "correct_option": "b",
                    "mark": 2
                },
                {
                    "question_text": "What does ACID stand for?",
                    "option_a": "Atomicity, Consistency, Isolation, Durability",
                    "option_b": "Association, Consistency, Integration, Data",
                    "option_c": "Automatic, Consistent, Independent, Durable",
                    "option_d": "None of the above",
                    "correct_option": "a",
                    "mark": 2
                }
            ]
        }
        
        create_response = await client.post("/quizzes/", json=quiz_data, headers=educator_headers)
        assert create_response.status_code in [200, 201]
        quiz_id = create_response.json()["quiz_id"]
        
        # 4. Invite students
        invite_data = {
            "emails": ["student1@university.edu", "student2@university.edu"]
        }
        invite_response = await client.post(
            f"/quizzes/{quiz_id}/invite",
            json=invite_data,
            headers=educator_headers
        )
        assert invite_response.status_code == 200
        
        # 5. View quiz details
        details_response = await client.get(f"/quizzes/{quiz_id}", headers=educator_headers)
        assert details_response.status_code == 200
        quiz_details = details_response.json()
        assert quiz_details["title"] == quiz_data["title"]
        
        return quiz_id, educator_token
    
    @pytest.mark.asyncio
    async def test_student_takes_quiz_journey(self, client: AsyncClient):
        """Complete student journey: signup -> find quiz -> attempt -> view results"""
        
        # 1. Student signs up
        student_data = {
            "email": "student@university.edu",
            "password": "student123",
            "name": "Alice Johnson"
        }
        
        signup_response = await client.post("/auth/signup", json=student_data)
        assert signup_response.status_code in [200, 201]
        
        # 2. Student signs in
        signin_response = await client.post("/auth/signin", json={
            "email": student_data["email"],
            "password": student_data["password"]
        })
        student_token = signin_response.json()["access_token"]
        student_headers = {"Authorization": f"Bearer {student_token}"}
        
        # 3. Create a test quiz for the student to attempt
        quiz_data = {
            "title": "Sample Quiz",
            "description": "A quiz for testing",
            "duration": 30,
            "positive_mark": 1,
            "negative_mark": 0,
            "navigation_type": "omni",
            "tab_switch_exit": False,
            "is_trivia": False,
            "questions": [
                {
                    "question_text": "What is 2+2?",
                    "option_a": "3",
                    "option_b": "4",
                    "option_c": "5",
                    "option_d": "6",
                    "correct_option": "b",
                    "mark": 1
                }
            ]
        }
        
        create_response = await client.post("/quizzes/", json=quiz_data, headers=student_headers)
        quiz_id = create_response.json()["quiz_id"]
        
        # 4. Start the quiz
        start_response = await client.post(f"/quizzes/{quiz_id}/start", headers=student_headers)
        assert start_response.status_code == 200
        session_data = start_response.json()
        assert "questions" in session_data
        assert "started_at" in session_data
        
        # 5. Submit answers
        answers_data = {"answers": {"1": "b"}}  # Correct answer
        submit_response = await client.post(
            f"/quizzes/{quiz_id}/submit",
            json=answers_data,
            headers=student_headers
        )
        assert submit_response.status_code == 200
        result = submit_response.json()
        assert "score" in result
        
        # 6. View personal results
        my_result_response = await client.get(f"/results/{quiz_id}/my-result", headers=student_headers)
        assert my_result_response.status_code == 200
        my_result = my_result_response.json()
        assert "score" in my_result
        assert "answers" in my_result
        
        # 7. Check profile and statistics
        profile_response = await client.get("/users/me", headers=student_headers)
        assert profile_response.status_code == 200
        
        return student_token
    
    @pytest.mark.asyncio
    async def test_admin_manages_trivia_journey(self, client: AsyncClient):
        """Complete admin journey: create trivia -> manage platform"""
        
        # 1. Admin signs up
        admin_data = {
            "email": "admin@quizzler.com",
            "password": "admin123",
            "name": "System Admin"
        }
        
        signup_response = await client.post("/auth/signup", json=admin_data)
        assert signup_response.status_code in [200, 201]
        
        # 2. Admin signs in
        signin_response = await client.post("/auth/signin", json={
            "email": admin_data["email"],
            "password": admin_data["password"]
        })
        admin_token = signin_response.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        
        # 3. Create trivia quiz
        trivia_data = {
            "title": "Sports Trivia Challenge",
            "description": "Test your sports knowledge",
            "topic": "sports",
            "duration": 15,
            "positive_mark": 1,
            "negative_mark": 0,
            "navigation_type": "omni",
            "tab_switch_exit": False,
            "difficulty": "medium",
            "is_trivia": True,
            "questions": [
                {
                    "question_text": "How many players are on a basketball team?",
                    "option_a": "4",
                    "option_b": "5",
                    "option_c": "6",
                    "option_d": "7",
                    "correct_option": "b",
                    "mark": 1
                }
            ]
        }
        
        create_response = await client.post("/quizzes/", json=trivia_data, headers=admin_headers)
        assert create_response.status_code in [200, 201]
        
        # 4. Check public trivia access
        trivia_response = await client.get("/trivia")
        assert trivia_response.status_code == 200
        trivia_list = trivia_response.json()
        assert isinstance(trivia_list, list)
        
        # 5. View platform statistics
        stats_response = await client.get("/admin/platform-stats", headers=admin_headers)
        assert stats_response.status_code == 200
        
        return admin_token
    
    @pytest.mark.asyncio
    async def test_concurrent_users_taking_quiz(self, client: AsyncClient):
        """Test multiple users taking the same quiz concurrently"""
        
        # Create a quiz first
        creator_data = {
            "email": "creator@test.com",
            "password": "creator123",
            "name": "Quiz Creator"
        }
        
        signup_response = await client.post("/auth/signup", json=creator_data)
        signin_response = await client.post("/auth/signin", json={
            "email": creator_data["email"],
            "password": creator_data["password"]
        })
        creator_token = signin_response.json()["access_token"]
        creator_headers = {"Authorization": f"Bearer {creator_token}"}
        
        quiz_data = {
            "title": "Concurrent Test Quiz",
            "description": "Testing concurrent access",
            "duration": 30,
            "is_trivia": True,
            "questions": [{"question_text": "Test?", "option_a": "A", "option_b": "B", "option_c": "C", "option_d": "D", "correct_option": "a", "mark": 1}]
        }
        
        create_response = await client.post("/quizzes/", json=quiz_data, headers=creator_headers)
        quiz_id = create_response.json()["quiz_id"]
        
        # Create multiple users
        users = []
        for i in range(3):
            user_data = {
                "email": f"user{i}@test.com",
                "password": "test123",
                "name": f"User {i}"
            }
            await client.post("/auth/signup", json=user_data)
            signin_resp = await client.post("/auth/signin", json={
                "email": user_data["email"],
                "password": user_data["password"]
            })
            token = signin_resp.json()["access_token"]
            users.append({"token": token, "headers": {"Authorization": f"Bearer {token}"}})
        
        # All users start quiz simultaneously
        start_tasks = []
        for user in users:
            start_tasks.append(client.post(f"/quizzes/{quiz_id}/start", headers=user["headers"]))
        
        start_responses = await asyncio.gather(*start_tasks)
        
        # All should be able to start
        for response in start_responses:
            assert response.status_code == 200
        
        # All users submit answers
        submit_tasks = []
        for user in users:
            submit_tasks.append(
                client.post(
                    f"/quizzes/{quiz_id}/submit",
                    json={"answers": {"1": "a"}},
                    headers=user["headers"]
                )
            )
        
        submit_responses = await asyncio.gather(*submit_tasks)
        
        # All should be able to submit
        for response in submit_responses:
            assert response.status_code == 200
