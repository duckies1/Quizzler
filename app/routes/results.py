from fastapi import APIRouter, Depends, HTTPException
from app.database import db
from app.utils.auth_utils import get_current_user, require_admin
from typing import List

router = APIRouter()

@router.get("/{quiz_id}/my-result")
async def get_my_result(quiz_id: str, current_user: dict = Depends(get_current_user)):
    """Get current user's result for a specific quiz"""
    try:
        responses = db.select("responses", "*", {"quiz_id": quiz_id, "user_id": current_user["id"]})
        if not responses:
            raise HTTPException(status_code=404, detail="Result not found")
        
        response = responses[0]
        
        # Get quiz info
        quiz = db.select("quizzes", "title,description", {"id": quiz_id})[0]
        
        return {
            "quiz_title": quiz["title"],
            "score": response["score"],
            "answers": response["answers"],
            "correct_answers": response["correct_answers"],
            "submitted_at": response["submitted_at"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get result: {str(e)}")

@router.get("/{quiz_id}/results")
async def get_quiz_results(quiz_id: str, current_user: dict = Depends(get_current_user)):
    """Get all results for a quiz (only for quiz creator)"""
    try:
        # Check if user is the creator of this quiz
        quizzes = db.select("quizzes", "*", {"id": quiz_id, "creator_id": current_user["id"]})
        if not quizzes:
            raise HTTPException(status_code=403, detail="Access denied. You are not the creator of this quiz.")
        
        quiz = quizzes[0]
        
        # Get all responses for this quiz
        responses = db.select("responses", "*", {"quiz_id": quiz_id})
        
        # Get user details for each response
        results = []
        for response in responses:
            user = db.select("users", "name,email", {"id": response["user_id"]})[0]
            results.append({
                "quiz_name": quiz["title"],
                "date": response["submitted_at"],
                "student_name": user["name"],
                "email": user["email"],
                "score": response["score"]
            })
        
        return {
            "quiz": {
                "id": quiz["id"],
                "title": quiz["title"],
                "description": quiz["description"]
            },
            "results": results,
            "total_participants": len(results)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get results: {str(e)}")

@router.get("/leaderboards/global")
async def get_global_leaderboard():
    """Get global leaderboard for trivia quizzes"""
    try:
        # Get all ratings with user details
        query = """
        SELECT r.rating, r.updated_at, u.name, u.email, q.title as quiz_title, q.topic
        FROM ratings r
        JOIN users u ON r.user_id = u.id
        JOIN quizzes q ON r.quiz_id = q.id
        WHERE q.is_trivia = true
        ORDER BY r.rating DESC
        LIMIT 50
        """
        
        # For now, let's use a simpler approach with responses
        responses = db.select("responses", "*", {})
        
        # Get trivia responses only
        trivia_responses = []
        for response in responses:
            quiz = db.select("quizzes", "title,topic,is_trivia", {"id": response["quiz_id"]})[0]
            if quiz["is_trivia"]:
                user = db.select("users", "name,email", {"id": response["user_id"]})[0]
                trivia_responses.append({
                    "user_name": user["name"],
                    "quiz_title": quiz["title"],
                    "topic": quiz["topic"],
                    "score": response["score"],
                    "submitted_at": response["submitted_at"]
                })
        
        # Sort by score
        trivia_responses.sort(key=lambda x: x["score"], reverse=True)
        
        return {
            "leaderboard": trivia_responses[:50],
            "total_entries": len(trivia_responses)
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get leaderboard: {str(e)}")