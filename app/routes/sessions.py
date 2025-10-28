from fastapi import APIRouter, Depends, HTTPException
from app.database import db
from app.utils.auth_utils import get_current_user
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import Dict, Any
import pytz

router = APIRouter()
IST = pytz.timezone('Asia/Kolkata')

class SubmitAnswersRequest(BaseModel):
    answers: Dict[str, str] 

@router.post("/{quiz_id}/start")
async def start_quiz(quiz_id: str, current_user: dict = Depends(get_current_user)):
    """Start a quiz session"""
    try:
        quizzes = db.select("quizzes", "*", {"id": quiz_id, "is_active": True})
        if not quizzes:
            raise HTTPException(status_code=404, detail="Quiz not found or not active")
        
        quiz = quizzes[0]
        current_time = datetime.now(IST)
        
        if not quiz["is_trivia"]:
            if quiz["start_time"]:
                start_time_naive = datetime.fromisoformat(quiz["start_time"])
                if start_time_naive.tzinfo is None:
                    start_time = IST.localize(start_time_naive)
                else:
                    start_time = start_time_naive.astimezone(IST)
                if current_time < start_time:
                    raise HTTPException(status_code=400, detail="Quiz has not started yet")
            
            if quiz["end_time"]:
                end_time_naive = datetime.fromisoformat(quiz["end_time"])
                if end_time_naive.tzinfo is None:
                    end_time = IST.localize(end_time_naive)
                else:
                    end_time = end_time_naive.astimezone(IST)
                if current_time > end_time:
                    raise HTTPException(status_code=400, detail="Quiz has ended")
        
        existing_sessions = db.select("quiz_sessions", "*", {"quiz_id": quiz_id, "user_id": current_user["id"]})
        if existing_sessions:
            raise HTTPException(status_code=400, detail="You have already attempted this quiz")
        
        existing_responses = db.select("responses", "*", {"quiz_id": quiz_id, "user_id": current_user["id"]})
        if existing_responses:
            raise HTTPException(status_code=400, detail="You have already completed this quiz")
        
        session_data = {
            "quiz_id": quiz_id,
            "user_id": current_user["id"],
            "started_at": current_time.isoformat(),
            "ended": False
        }
        
        session = db.insert("quiz_sessions", session_data)
        
        questions = db.select("questions", "id,question_text,option_a,option_b,option_c,option_d", {"quiz_id": quiz_id})
        
        if quiz["is_trivia"]:
            new_popularity = quiz.get("popularity", 0) + 1
            db.update("quizzes", {"popularity": new_popularity}, {"id": quiz_id})
        
        return {
            "session_id": session["id"],
            "started_at": session["started_at"],
            "quiz": {
                "id": quiz["id"],
                "title": quiz["title"],
                "description": quiz["description"],
                "duration": quiz["duration"],
                "positive_mark": quiz["positive_mark"],
                "negative_mark": quiz["negative_mark"],
                "navigation_type": quiz["navigation_type"],
                "tab_switch_exit": quiz["tab_switch_exit"]
            },
            "questions": questions,
            "total_questions": len(questions)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to start quiz: {str(e)}")

@router.post("/{quiz_id}/submit")
async def submit_quiz(quiz_id: str, answers_data: SubmitAnswersRequest, current_user: dict = Depends(get_current_user)):
    """Submit quiz answers"""
    try:
        sessions = db.select("quiz_sessions", "*", {"quiz_id": quiz_id, "user_id": current_user["id"]})
        if not sessions:
            raise HTTPException(status_code=404, detail="Quiz session not found")
        
        session = sessions[0]
        if session.get("ended"):
            raise HTTPException(status_code=400, detail="Quiz already submitted")
        
        quiz = db.select("quizzes", "*", {"id": quiz_id})[0]
        questions = db.select("questions", "*", {"quiz_id": quiz_id})
        
        current_time = datetime.now(IST)
        started_at_naive = datetime.fromisoformat(session["started_at"])
        if started_at_naive.tzinfo is None:
            started_at = IST.localize(started_at_naive)
        else:
            started_at = started_at_naive.astimezone(IST)
        max_allowed_time = started_at + timedelta(minutes=quiz["duration"], seconds=30)  
        
        if current_time > max_allowed_time:
            response_data = {
                "quiz_id": quiz_id,
                "user_id": current_user["id"],
                "answers": {},
                "correct_answers": {str(q["id"]): q["correct_option"] for q in questions},
                "score": 0,
                "submitted_at": current_time.isoformat(),
                "time_exceeded": True
            }
            
            response = db.insert("responses", response_data)
            db.update("quiz_sessions", {"ended": True, "ended_at": current_time.isoformat()}, {"id": session["id"]})
            
            raise HTTPException(status_code=400, detail="Time limit exceeded. Quiz submitted with 0 score.")
        
        correct_answers = {str(q["id"]): q["correct_option"] for q in questions}
        score = 0
        
        for question_id, correct_option in correct_answers.items():
            user_answer = answers_data.answers.get(question_id)
            if user_answer == correct_option:
                score += quiz["positive_mark"]
            elif user_answer is not None:  
                score -= quiz["negative_mark"]
        
        score = max(0, score)
        
        response_data = {
            "quiz_id": quiz_id,
            "user_id": current_user["id"],
            "answers": answers_data.answers,
            "correct_answers": correct_answers,
            "score": score,
            "submitted_at": current_time.isoformat()
        }
        
        response = db.insert("responses", response_data)
        
        db.update("quiz_sessions", {"ended": True, "ended_at": current_time.isoformat()}, {"id": session["id"]})
        
        if quiz["is_trivia"]:
            time_taken_minutes = (current_time - started_at).total_seconds() / 60
            max_score = len(questions) * quiz["positive_mark"]
            
            score_percentage = (score / max_score) * 100 if max_score > 0 else 0
            time_bonus = max(0, (quiz["duration"] - time_taken_minutes) / quiz["duration"] * 20)  
            rating = int(score_percentage + time_bonus)
            
            rating_data = {
                "user_id": current_user["id"],
                "quiz_id": quiz_id,
                "rating": rating,
                "updated_at": current_time.isoformat()
            }
            
            try:
                existing_rating = db.select("ratings", "*", {"user_id": current_user["id"], "quiz_id": quiz_id})
                if existing_rating:
                    db.update("ratings", {"rating": rating, "updated_at": current_time.isoformat()}, 
                             {"user_id": current_user["id"], "quiz_id": quiz_id})
                else:
                    db.insert("ratings", rating_data)
            except:
                db.insert("ratings", rating_data)
        
        return {
            "score": score,
            "total_questions": len(questions),
            "submitted_at": response["submitted_at"],
            "time_taken_minutes": round((current_time - started_at).total_seconds() / 60, 2)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to submit quiz: {str(e)}")