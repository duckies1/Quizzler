from fastapi import APIRouter, Depends, HTTPException
from app.database import db
from app.utils.auth_utils import get_current_user
from datetime import datetime
from pydantic import BaseModel
from typing import Dict, Any
import pytz

router = APIRouter()
IST = pytz.timezone('Asia/Kolkata')

class SubmitAnswersRequest(BaseModel):
    answers: Dict[str, str]  # {question_id: selected_option}

@router.post("/{quiz_id}/start")
async def start_quiz(quiz_id: str, current_user: dict = Depends(get_current_user)):
    """Start a quiz session"""
    try:
        # Check if quiz exists and is active
        quizzes = db.select("quizzes", "*", {"id": quiz_id, "is_active": True})
        if not quizzes:
            raise HTTPException(status_code=404, detail="Quiz not found or not active")
        
        quiz = quizzes[0]
        
        # Check if user already has a session for this quiz
        existing_sessions = db.select("quiz_sessions", "*", {"quiz_id": quiz_id, "user_id": current_user["id"]})
        if existing_sessions:
            raise HTTPException(status_code=400, detail="You have already attempted this quiz")
        
        # Create new session
        session_data = {
            "quiz_id": quiz_id,
            "user_id": current_user["id"],
            "started_at": datetime.now(IST).isoformat()
        }
        
        session = db.insert("quiz_sessions", session_data)
        
        # Get quiz questions (without correct answers)
        questions = db.select("questions", "id,question_text,option_a,option_b,option_c,option_d,mark", {"quiz_id": quiz_id})
        
        return {
            "session_id": session["id"],
            "started_at": session["started_at"],
            "quiz": {
                "id": quiz["id"],
                "title": quiz["title"],
                "description": quiz["description"],
                "duration": quiz["duration"],
                "navigation_type": quiz["navigation_type"],
                "tab_switch_exit": quiz["tab_switch_exit"]
            },
            "questions": questions
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to start quiz: {str(e)}")

@router.post("/{quiz_id}/submit")
async def submit_quiz(quiz_id: str, answers_data: SubmitAnswersRequest, current_user: dict = Depends(get_current_user)):
    """Submit quiz answers"""
    try:
        # Get the quiz session
        sessions = db.select("quiz_sessions", "*", {"quiz_id": quiz_id, "user_id": current_user["id"]})
        if not sessions:
            raise HTTPException(status_code=404, detail="Quiz session not found")
        
        session = sessions[0]
        if session.get("ended"):
            raise HTTPException(status_code=400, detail="Quiz already submitted")
        
        # Get quiz and questions with correct answers
        quiz = db.select("quizzes", "*", {"id": quiz_id})[0]
        questions = db.select("questions", "*", {"quiz_id": quiz_id})
        
        # Calculate score
        correct_answers = {str(q["id"]): q["correct_option"] for q in questions}
        score = 0
        
        for question_id, correct_option in correct_answers.items():
            user_answer = answers_data.answers.get(question_id)
            if user_answer == correct_option:
                # Find question to get its marks
                question = next((q for q in questions if str(q["id"]) == question_id), None)
                if question:
                    score += question.get("mark", quiz["positive_mark"])
            elif user_answer is not None:  # Wrong answer (not unattempted)
                score -= quiz["negative_mark"]
        
        # Create response record
        response_data = {
            "quiz_id": quiz_id,
            "user_id": current_user["id"],
            "answers": answers_data.answers,
            "correct_answers": correct_answers,
            "score": score,
            "submitted_at": datetime.now(IST).isoformat()
        }
        
        response = db.insert("responses", response_data)
        
        # Update session as ended
        db.update("quiz_sessions", {"ended": True, "ended_at": datetime.now(IST).isoformat()}, {"id": session["id"]})
        
        return {
            "score": score,
            "total_questions": len(questions),
            "submitted_at": response["submitted_at"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to submit quiz: {str(e)}")