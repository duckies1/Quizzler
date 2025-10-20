from fastapi import APIRouter, Depends, HTTPException
from app.database import db
from app.utils.auth_utils import require_admin
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import pytz

router = APIRouter()
IST = pytz.timezone('Asia/Kolkata')

class AddGenre(BaseModel):
    name: str
    description: Optional[str] = None

class QuizStats(BaseModel):
    quiz_id: str
    title: str
    total_attempts: int
    average_score: float
    difficulty: str

@router.post("/trivia-genres")
async def add_trivia_genre(genre_data: AddGenre, admin_user: dict = Depends(require_admin)):
    """Add new trivia genre/topic"""
    try:
        # Check if genre already exists
        existing_genres = db.select("trivia_genres", "*", {"name": genre_data.name})
        if existing_genres:
            raise HTTPException(status_code=400, detail="Genre already exists")
        
        genre = {
            "name": genre_data.name,
            "description": genre_data.description,
            "created_by": admin_user["id"],
            "created_at": datetime.now(IST).isoformat(),
            "is_active": True
        }
        
        try:
            created_genre = db.insert("trivia_genres", genre)
        except Exception:
            # Table might not exist, create a simple response
            return {
                "message": f"Genre '{genre_data.name}' noted. Use this topic when creating trivia quizzes.",
                "genre": genre_data.name
            }
        
        return {
            "message": "Genre added successfully",
            "genre": created_genre
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to add genre: {str(e)}")

@router.get("/trivia-genres")
async def get_trivia_genres(admin_user: dict = Depends(require_admin)):
    """Get all trivia genres"""
    try:
        try:
            genres = db.select("trivia_genres", "*", {"is_active": True})
            return {"genres": genres}
        except:
            # If table doesn't exist, get from existing quizzes
            quizzes = db.select("quizzes", "topic", {"is_trivia": True, "is_active": True})
            topics = list(set(quiz["topic"] for quiz in quizzes if quiz.get("topic")))
            return {
                "message": "Genres extracted from existing quizzes",
                "genres": [{"name": topic, "description": f"Topic: {topic}"} for topic in topics]
            }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get genres: {str(e)}")

@router.get("/quiz-stats")
async def get_quiz_statistics(admin_user: dict = Depends(require_admin)):
    """Get statistics for all quizzes"""
    try:
        # Get all quizzes
        quizzes = db.select("quizzes", "*", {})
        
        quiz_stats = []
        
        for quiz in quizzes:
            # Get responses for this quiz
            responses = db.select("responses", "score", {"quiz_id": quiz["id"]})
            
            total_attempts = len(responses)
            average_score = 0
            
            if total_attempts > 0:
                total_score = sum(response["score"] for response in responses)
                average_score = total_score / total_attempts
            
            quiz_stats.append({
                "quiz_id": quiz["id"],
                "title": quiz["title"],
                "creator_id": quiz["creator_id"],
                "is_trivia": quiz["is_trivia"],
                "topic": quiz.get("topic"),
                "difficulty": quiz.get("difficulty"),
                "total_attempts": total_attempts,
                "average_score": round(average_score, 2),
                "popularity": quiz.get("popularity", 0),
                "created_at": quiz.get("created_at")
            })
        
        # Sort by total attempts (most popular first)
        quiz_stats.sort(key=lambda x: x["total_attempts"], reverse=True)
        
        return {
            "total_quizzes": len(quiz_stats),
            "trivia_quizzes": len([q for q in quiz_stats if q["is_trivia"]]),
            "private_quizzes": len([q for q in quiz_stats if not q["is_trivia"]]),
            "quiz_statistics": quiz_stats
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get quiz statistics: {str(e)}")

@router.get("/user-stats")
async def get_user_statistics(admin_user: dict = Depends(require_admin)):
    """Get user statistics"""
    try:
        # Get all users
        users = db.select("users", "*", {})
        
        # Get all responses
        responses = db.select("responses", "*", {})
        
        user_stats = []
        
        for user in users:
            user_responses = [r for r in responses if r["user_id"] == user["id"]]
            
            total_quizzes = len(user_responses)
            total_score = sum(r["score"] for r in user_responses)
            average_score = total_score / total_quizzes if total_quizzes > 0 else 0
            
            # Count trivia vs private
            trivia_attempts = 0
            private_attempts = 0
            
            for response in user_responses:
                quiz = db.select("quizzes", "is_trivia", {"id": response["quiz_id"]})[0]
                if quiz["is_trivia"]:
                    trivia_attempts += 1
                else:
                    private_attempts += 1
            
            user_stats.append({
                "user_id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "total_quizzes": total_quizzes,
                "trivia_attempts": trivia_attempts,
                "private_attempts": private_attempts,
                "total_score": total_score,
                "average_score": round(average_score, 2),
                "created_at": user.get("created_at")
            })
        
        # Sort by total quizzes (most active first)
        user_stats.sort(key=lambda x: x["total_quizzes"], reverse=True)
        
        return {
            "total_users": len(user_stats),
            "active_users": len([u for u in user_stats if u["total_quizzes"] > 0]),
            "user_statistics": user_stats
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get user statistics: {str(e)}")

@router.delete("/quiz/{quiz_id}")
async def delete_quiz(quiz_id: str, admin_user: dict = Depends(require_admin)):
    """Delete a quiz (admin only)"""
    try:
        # Check if quiz exists
        quizzes = db.select("quizzes", "*", {"id": quiz_id})
        if not quizzes:
            raise HTTPException(status_code=404, detail="Quiz not found")
        
        quiz = quizzes[0]
        
        # Soft delete - just mark as inactive
        db.update("quizzes", {"is_active": False}, {"id": quiz_id})
        
        return {
            "message": f"Quiz '{quiz['title']}' has been deactivated",
            "quiz_id": quiz_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to delete quiz: {str(e)}")

@router.get("/platform-stats")
async def get_platform_statistics(admin_user: dict = Depends(require_admin)):
    """Get overall platform statistics"""
    try:
        # Count totals
        total_users = len(db.select("users", "id", {}))
        total_quizzes = len(db.select("quizzes", "id", {"is_active": True}))
        total_responses = len(db.select("responses", "id", {}))
        
        # Quiz breakdown
        trivia_quizzes = len(db.select("quizzes", "id", {"is_trivia": True, "is_active": True}))
        private_quizzes = len(db.select("quizzes", "id", {"is_trivia": False, "is_active": True}))
        
        # Recent activity (last 7 days)
        from datetime import timedelta
        week_ago = (datetime.now(IST) - timedelta(days=7)).isoformat()
        
        recent_users = 0
        recent_responses = 0
        recent_quizzes = 0
        
        try:
            all_users = db.select("users", "created_at", {})
            recent_users = len([u for u in all_users if u.get("created_at", "") > week_ago])
            
            all_responses = db.select("responses", "submitted_at", {})
            recent_responses = len([r for r in all_responses if r.get("submitted_at", "") > week_ago])
            
            all_quizzes = db.select("quizzes", "created_at", {"is_active": True})
            recent_quizzes = len([q for q in all_quizzes if q.get("created_at", "") > week_ago])
        except:
            pass
        
        return {
            "platform_overview": {
                "total_users": total_users,
                "total_active_quizzes": total_quizzes,
                "total_quiz_attempts": total_responses,
                "trivia_quizzes": trivia_quizzes,
                "private_quizzes": private_quizzes
            },
            "recent_activity_7_days": {
                "new_users": recent_users,
                "quiz_attempts": recent_responses,
                "new_quizzes": recent_quizzes
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get platform statistics: {str(e)}")
