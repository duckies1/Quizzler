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
        current_time = datetime.now(IST)
        
        # Check quiz timing for private quizzes
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
            
            # Check if user is invited for private quiz
            if quiz["creator_id"] != current_user["id"]:
                try:
                    invites = db.select("invites", "*", {"quiz_id": quiz_id, "email": current_user["email"]})
                    if not invites:
                        raise HTTPException(status_code=403, detail="You are not invited to this quiz")
                except:
                    # If invites table doesn't exist, only creator can access
                    if quiz["creator_id"] != current_user["id"]:
                        raise HTTPException(status_code=403, detail="You are not invited to this quiz")
        
        # Check if user already has a session for this quiz
        existing_sessions = db.select("quiz_sessions", "*", {"quiz_id": quiz_id, "user_id": current_user["id"]})
        if existing_sessions:
            raise HTTPException(status_code=400, detail="You have already attempted this quiz")
        
        # Check if user already has a response (backup check)
        existing_responses = db.select("responses", "*", {"quiz_id": quiz_id, "user_id": current_user["id"]})
        if existing_responses:
            raise HTTPException(status_code=400, detail="You have already completed this quiz")
        
        # Create new session
        session_data = {
            "quiz_id": quiz_id,
            "user_id": current_user["id"],
            "started_at": current_time.isoformat(),
            "ended": False
        }
        
        session = db.insert("quiz_sessions", session_data)
        
        # Get quiz questions (without correct answers)
        questions = db.select("questions", "id,question_text,option_a,option_b,option_c,option_d,mark", {"quiz_id": quiz_id})
        
        # Update quiz popularity for trivia
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
        
        # Validate submission time (with grace period of 30 seconds)
        current_time = datetime.now(IST)
        started_at_naive = datetime.fromisoformat(session["started_at"])
        # Convert to IST if it's naive, otherwise use as is
        if started_at_naive.tzinfo is None:
            started_at = IST.localize(started_at_naive)
        else:
            started_at = started_at_naive.astimezone(IST)
        max_allowed_time = started_at + timedelta(minutes=quiz["duration"], seconds=30)  # 30 second grace period
        
        if current_time > max_allowed_time:
            # Time exceeded, submit with 0 score
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
        
        # Ensure score is not negative
        score = max(0, score)
        
        # Create response record
        response_data = {
            "quiz_id": quiz_id,
            "user_id": current_user["id"],
            "answers": answers_data.answers,
            "correct_answers": correct_answers,
            "score": score,
            "submitted_at": current_time.isoformat()
        }
        
        response = db.insert("responses", response_data)
        
        # Update session as ended
        db.update("quiz_sessions", {"ended": True, "ended_at": current_time.isoformat()}, {"id": session["id"]})
        
        # If it's a trivia quiz, create/update rating
        if quiz["is_trivia"]:
            # Calculate rating based on score and time taken
            time_taken_minutes = (current_time - started_at).total_seconds() / 60
            max_score = sum(q.get("mark", quiz["positive_mark"]) for q in questions)
            
            # Rating calculation: base score + time bonus (faster = better)
            score_percentage = (score / max_score) * 100 if max_score > 0 else 0
            time_bonus = max(0, (quiz["duration"] - time_taken_minutes) / quiz["duration"] * 20)  # Up to 20 bonus points
            rating = int(score_percentage + time_bonus)
            
            rating_data = {
                "user_id": current_user["id"],
                "quiz_id": quiz_id,
                "rating": rating,
                "updated_at": current_time.isoformat()
            }
            
            # Try to update existing rating, or create new one
            try:
                existing_rating = db.select("ratings", "*", {"user_id": current_user["id"], "quiz_id": quiz_id})
                if existing_rating:
                    db.update("ratings", {"rating": rating, "updated_at": current_time.isoformat()}, 
                             {"user_id": current_user["id"], "quiz_id": quiz_id})
                else:
                    db.insert("ratings", rating_data)
            except:
                # Rating table might not exist, create it
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