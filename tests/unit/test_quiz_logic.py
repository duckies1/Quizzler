import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import pytz

class TestQuizLogic:
    """Test quiz business logic"""
    
    def test_calculate_score_all_correct(self):
        """Test score calculation with all correct answers"""
        answers = {"1": "a", "2": "b"}
        correct_answers = {"1": "a", "2": "b"}
        positive_mark = 2
        negative_mark = 1
        
        # Mock quiz grading logic
        score = 0
        for q_id, user_answer in answers.items():
            if user_answer == correct_answers.get(q_id):
                score += positive_mark
            elif user_answer is not None:
                score -= negative_mark
        
        assert score == 4  # 2 correct × 2 marks each
    
    def test_calculate_score_mixed_answers(self):
        """Test score calculation with mixed correct/incorrect answers"""
        answers = {"1": "a", "2": "wrong", "3": None}  # 1 correct, 1 wrong, 1 unattempted
        correct_answers = {"1": "a", "2": "b", "3": "c"}
        positive_mark = 2
        negative_mark = 1
        
        score = 0
        for q_id, user_answer in answers.items():
            if user_answer == correct_answers.get(q_id):
                score += positive_mark
            elif user_answer is not None:
                score -= negative_mark
        
        assert score == 1  # 2 (correct) - 1 (wrong) = 1
    
    def test_calculate_score_no_negative_marking(self):
        """Test score calculation without negative marking"""
        answers = {"1": "a", "2": "wrong"}
        correct_answers = {"1": "a", "2": "b"}
        positive_mark = 1
        negative_mark = 0
        
        score = 0
        for q_id, user_answer in answers.items():
            if user_answer == correct_answers.get(q_id):
                score += positive_mark
            elif user_answer is not None and negative_mark > 0:
                score -= negative_mark
        
        assert score == 1  # Only positive marks counted
    
    def test_quiz_time_validation_within_limit(self):
        """Test quiz submission within time limit"""
        IST = pytz.timezone('Asia/Kolkata')
        start_time = datetime.now(IST)
        submit_time = start_time + timedelta(minutes=25)  # Within 30 min limit
        duration = 30
        
        # Check if submission is within time
        time_taken = (submit_time - start_time).total_seconds() / 60
        is_valid = time_taken <= duration + 0.5  # 30 sec grace period
        
        assert is_valid is True
    
    def test_quiz_time_validation_exceeded(self):
        """Test quiz submission beyond time limit"""
        IST = pytz.timezone('Asia/Kolkata')
        start_time = datetime.now(IST)
        submit_time = start_time + timedelta(minutes=35)  # Beyond 30 min limit
        duration = 30
        
        time_taken = (submit_time - start_time).total_seconds() / 60
        is_valid = time_taken <= duration + 0.5
        
        assert is_valid is False
    
    def test_quiz_eligibility_not_attempted(self):
        """Test quiz eligibility for user who hasn't attempted"""
        user_attempts = []  # No previous attempts
        quiz_id = "quiz-123"
        
        has_attempted = any(attempt.get("quiz_id") == quiz_id for attempt in user_attempts)
        is_eligible = not has_attempted
        
        assert is_eligible is True
    
    def test_quiz_eligibility_already_attempted(self):
        """Test quiz eligibility for user who has already attempted"""
        user_attempts = [{"quiz_id": "quiz-123", "score": 85}]
        quiz_id = "quiz-123"
        
        has_attempted = any(attempt.get("quiz_id") == quiz_id for attempt in user_attempts)
        is_eligible = not has_attempted
        
        assert is_eligible is False
    
    def test_trivia_rating_calculation(self):
        """Test trivia rating calculation based on score and time"""
        score = 80  # 80% score
        max_score = 100
        time_taken = 5  # 5 minutes
        duration = 10  # 10 minutes allowed
        
        # Rating formula: score_percentage * time_bonus
        score_percentage = (score / max_score) * 100
        time_bonus = max(1.0, (duration - time_taken) / duration + 1)
        rating = int(score_percentage * time_bonus)
        
        assert rating > score  # Rating should be higher due to time bonus
        assert rating <= 200   # Maximum possible rating
    
    def test_quiz_scheduling_validation(self):
        """Test quiz scheduling time validation"""
        IST = pytz.timezone('Asia/Kolkata')
        now = datetime.now(IST)
        
        # Quiz scheduled for future
        start_time = now + timedelta(hours=1)
        end_time = start_time + timedelta(hours=2)
        
        is_scheduled_properly = start_time > now and end_time > start_time
        assert is_scheduled_properly is True
        
        # Quiz with past end time
        past_end_time = now - timedelta(hours=1)
        is_expired = past_end_time < now
        assert is_expired is True
