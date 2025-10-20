import pytest
import asyncio
from httpx import AsyncClient
from app.main import app
from app.database import Database
from app.config import settings
import os

# Test configuration
TEST_DATABASE_URL = "test_database"  # Use separate test instance

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def client():
    """Create test client"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
async def test_user_token():
    """Create a test user and return auth token"""
    # This will be used for authenticated requests
    test_user_data = {
        "email": "test@example.com",
        "password": "testpassword123",
        "name": "Test User"
    }
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Create test user
        response = await ac.post("/auth/signup", json=test_user_data)
        if response.status_code in [200, 201]:
            data = response.json()
            return data.get("access_token")
        return None

@pytest.fixture
async def admin_user_token():
    """Create an admin user and return auth token"""
    admin_user_data = {
        "email": "admin@quizzler.com",  # Admin email pattern
        "password": "adminpassword123",
        "name": "Admin User"
    }
    
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/auth/signup", json=admin_user_data)
        if response.status_code in [200, 201]:
            data = response.json()
            return data.get("access_token")
        return None

@pytest.fixture
async def test_quiz_data():
    """Sample quiz data for testing"""
    return {
        "title": "Test Quiz",
        "description": "A test quiz for unit testing",
        "topic": "general",
        "duration": 30,
        "positive_mark": 2,
        "negative_mark": 1,
        "navigation_type": "omni",
        "tab_switch_exit": True,
        "difficulty": "medium",
        "is_trivia": False,
        "questions": [
            {
                "question_text": "What is 2+2?",
                "option_a": "3",
                "option_b": "4",
                "option_c": "5",
                "option_d": "6",
                "correct_option": "b",
                "mark": 2
            },
            {
                "question_text": "What is the capital of France?",
                "option_a": "London",
                "option_b": "Berlin",
                "option_c": "Paris",
                "option_d": "Madrid",
                "correct_option": "c",
                "mark": 2
            }
        ]
    }

@pytest.fixture
async def trivia_quiz_data():
    """Sample trivia quiz data for testing"""
    return {
        "title": "Sports Trivia",
        "description": "Test your sports knowledge",
        "topic": "sports",
        "duration": 15,
        "positive_mark": 1,
        "negative_mark": 0,
        "navigation_type": "omni",
        "tab_switch_exit": False,
        "difficulty": "easy",
        "is_trivia": True,
        "questions": [
            {
                "question_text": "How many players are there in a basketball team on court?",
                "option_a": "4",
                "option_b": "5",
                "option_c": "6",
                "option_d": "7",
                "correct_option": "b",
                "mark": 1
            }
        ]
    }

@pytest.fixture
def auth_headers():
    """Helper to create auth headers"""
    def _auth_headers(token: str):
        return {"Authorization": f"Bearer {token}"}
    return _auth_headers

# Test data cleanup
@pytest.fixture(autouse=True)
async def cleanup_test_data():
    """Cleanup test data after each test"""
    yield
    # Add cleanup logic if needed
    pass

class TestConfig:
    """Test configuration constants"""
    TEST_USER_EMAIL = "test@example.com"
    TEST_ADMIN_EMAIL = "admin@quizzler.com"
    TEST_PASSWORD = "testpassword123"
    BASE_URL = "http://test"
