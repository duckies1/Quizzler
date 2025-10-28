from fastapi import APIRouter, Depends, HTTPException
from app.database import db
from app.utils.auth_utils import get_current_user
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import pytz

router = APIRouter()
IST = pytz.timezone('Asia/Kolkata')

class UpdateProfile(BaseModel):
    name: Optional[str] = None

@router.get("/me")
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    """Get current user's profile with quiz history and recommendations"""
    try:
        users = db.select("users", "*", {"id": current_user["id"]})
        if not users:
            raise HTTPException(status_code=404, detail="User not found")
        
        user = users[0]
        
        responses = db.select("responses", "*", {"user_id": current_user["id"]})
        
        quiz_history = []
        attempted_topics = set()
        
        for response in responses:
            quiz = db.select("quizzes", "id,title,topic,is_trivia,difficulty", {"id": response["quiz_id"]})[0]
            quiz_history.append({
                "quiz_id": quiz["id"],
                "quiz_title": quiz["title"],
                "topic": quiz.get("topic"),
                "is_trivia": quiz["is_trivia"],
                "difficulty": quiz.get("difficulty"),
                "score": response["score"],
                "submitted_at": response["submitted_at"]
            })
            
            if quiz.get("topic"):
                attempted_topics.add(quiz["topic"])
        
        quiz_history.sort(key=lambda x: x["submitted_at"], reverse=True)
        
        all_topics = set()
        all_trivia = db.select("quizzes", "topic", {"is_trivia": True, "is_active": True})
        for quiz in all_trivia:
            if quiz.get("topic"):
                all_topics.add(quiz["topic"])
        
        recommended_topics = list(all_topics - attempted_topics)
        
        recommendations = []
        for topic in recommended_topics[:3]:  
            topic_quizzes = db.select("quizzes", "id,title,topic,difficulty,popularity", 
                                    {"is_trivia": True, "topic": topic, "is_active": True})
            if topic_quizzes:
                topic_quizzes.sort(key=lambda x: x.get("popularity", 0), reverse=True)
                recommendations.append(topic_quizzes[0])
        
        trivia_ranking = None
        try:
            all_ratings = db.select("ratings", "*", {})
            user_total_rating = 0
            user_quiz_count = 0
            
            all_user_ratings = {}
            
            for rating in all_ratings:
                quiz = db.select("quizzes", "is_trivia", {"id": rating["quiz_id"]})[0]
                if quiz["is_trivia"]:
                    user_id = rating["user_id"]
                    if user_id not in all_user_ratings:
                        all_user_ratings[user_id] = {"total": 0, "count": 0}
                    
                    all_user_ratings[user_id]["total"] += rating["rating"]
                    all_user_ratings[user_id]["count"] += 1
                    
                    if user_id == current_user["id"]:
                        user_total_rating += rating["rating"]
                        user_quiz_count += 1
            
            if user_quiz_count > 0:
                user_avg_rating = user_total_rating / user_quiz_count
                
                better_users = 0
                for uid, data in all_user_ratings.items():
                    if uid != current_user["id"]:
                        other_avg = data["total"] / data["count"] if data["count"] > 0 else 0
                        if other_avg > user_avg_rating:
                            better_users += 1
                
                trivia_ranking = {
                    "rank": better_users + 1,
                    "total_users": len(all_user_ratings),
                    "average_rating": round(user_avg_rating, 2)
                }
        except:
            pass
        
        return {
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "created_at": user.get("created_at")
            },
            "quiz_history": quiz_history[:10],  
            "total_quizzes_attempted": len(quiz_history),
            "attempted_topics": list(attempted_topics),
            "recommendations": recommendations,
            "trivia_ranking": trivia_ranking
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get profile: {str(e)}")

@router.patch("/me")
async def update_user_profile(profile_data: UpdateProfile, current_user: dict = Depends(get_current_user)):
    """Update current user's profile"""
    try:
        update_data = {}
        
        if profile_data.name is not None:
            update_data["name"] = profile_data.name
            
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        updated_user = db.update("users", update_data, {"id": current_user["id"]})
        
        if not updated_user:
            users = db.select("users", "*", {"id": current_user["id"]})
            if users:
                updated_user = users[0]
        
        return {
            "message": "Profile updated successfully",
            "user": {
                "id": updated_user["id"] if updated_user else current_user["id"],
                "name": updated_user["name"] if updated_user else profile_data.name,
                "email": updated_user["email"] if updated_user else current_user["email"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update profile: {str(e)}")

@router.get("/leaderboard-position")
async def get_user_leaderboard_position(current_user: dict = Depends(get_current_user)):
    """Get user's position in global trivia leaderboard"""
    try:
        all_ratings = db.select("ratings", "*", {})
        
        user_ratings = {}
        
        for rating in all_ratings:
            quiz = db.select("quizzes", "is_trivia", {"id": rating["quiz_id"]})[0]
            if quiz["is_trivia"]:
                user_id = rating["user_id"]
                if user_id not in user_ratings:
                    user_ratings[user_id] = {"total": 0, "count": 0}
                
                user_ratings[user_id]["total"] += rating["rating"]
                user_ratings[user_id]["count"] += 1
        
        leaderboard = []
        for user_id, data in user_ratings.items():
            if data["count"] > 0:
                avg_rating = data["total"] / data["count"]
                leaderboard.append({
                    "user_id": user_id,
                    "average_rating": avg_rating,
                    "quiz_count": data["count"]
                })
        
        leaderboard.sort(key=lambda x: (x["average_rating"], x["quiz_count"]), reverse=True)
        
        user_position = None
        for i, entry in enumerate(leaderboard):
            if entry["user_id"] == current_user["id"]:
                user_position = {
                    "rank": i + 1,
                    "total_users": len(leaderboard),
                    "average_rating": round(entry["average_rating"], 2),
                    "quiz_count": entry["quiz_count"]
                }
                break
        
        return {
            "position": user_position,
            "message": "No trivia attempts yet" if not user_position else "Current leaderboard position"
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get leaderboard position: {str(e)}")
