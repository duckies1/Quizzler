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
        
        quiz = db.select("quizzes", "title,description", {"id": quiz_id})[0]
        
        questions = db.select("questions", "id,question_text,option_a,option_b,option_c,option_d,correct_option", {"quiz_id": quiz_id})
        
        question_details = {}
        for question in questions:
            question_details[str(question["id"])] = {
                "question_text": question["question_text"],
                "option_a": question["option_a"],
                "option_b": question["option_b"],
                "option_c": question["option_c"],
                "option_d": question["option_d"],
                "correct_option": question["correct_option"]
            }
        
        return {
            "quiz_title": quiz["title"],
            "score": response["score"],
            "answers": response["answers"],
            "correct_answers": response["correct_answers"],
            "questions": question_details,
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
        quizzes = db.select("quizzes", "*", {"id": quiz_id, "creator_id": current_user["id"]})
        if not quizzes:
            raise HTTPException(status_code=403, detail="Access denied. You are not the creator of this quiz.")
        
        quiz = quizzes[0]
        
        responses = db.select("responses", "*", {"quiz_id": quiz_id})
        
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
async def get_global_leaderboard(limit: int = 50):
    """Get global leaderboard for trivia quizzes"""
    try:
        responses = db.select("responses", "*", {})
        
        leaderboard_data = []
        user_ratings = {}  
        
        for response in responses:
            quiz = db.select("quizzes", "title,topic,is_trivia,difficulty", {"id": response["quiz_id"]})[0]
            if quiz["is_trivia"]:
                user = db.select("users", "name,email", {"id": response["user_id"]})[0]
                
                rating = 0
                try:
                    ratings = db.select("ratings", "rating", {"user_id": response["user_id"], "quiz_id": response["quiz_id"]})
                    if ratings:
                        rating = ratings[0]["rating"]
                except:
                    rating = response["score"] * 10  
                
                user_key = response["user_id"]
                if user_key not in user_ratings:
                    user_ratings[user_key] = {
                        "user_id": response["user_id"],
                        "user_name": user["name"],
                        "email": user["email"],
                        "total_rating": 0,
                        "quiz_count": 0,
                        "best_quiz": "",
                        "best_score": 0
                    }
                
                user_ratings[user_key]["total_rating"] += rating
                user_ratings[user_key]["quiz_count"] += 1
                
                if response["score"] > user_ratings[user_key]["best_score"]:
                    user_ratings[user_key]["best_score"] = response["score"]
                    user_ratings[user_key]["best_quiz"] = quiz["title"]
        
        for user_data in user_ratings.values():
            user_data["average_rating"] = user_data["total_rating"] / user_data["quiz_count"] if user_data["quiz_count"] > 0 else 0
            leaderboard_data.append(user_data)
        
        leaderboard_data.sort(key=lambda x: (x["average_rating"], x["quiz_count"]), reverse=True)
        
        return {
            "leaderboard": leaderboard_data[:limit],
            "total_entries": len(leaderboard_data)
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get leaderboard: {str(e)}")

@router.get("/leaderboards/quiz/{quiz_id}")
async def get_quiz_leaderboard(quiz_id: str, current_user: dict = Depends(get_current_user)):
    """Get leaderboard for a specific quiz"""
    try:
        quizzes = db.select("quizzes", "*", {"id": quiz_id})
        if not quizzes:
            raise HTTPException(status_code=404, detail="Quiz not found")
        
        quiz = quizzes[0]
        
        if not quiz["is_trivia"] and quiz["creator_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
        
        responses = db.select("responses", "*", {"quiz_id": quiz_id})
        
        leaderboard = []
        for response in responses:
            user = db.select("users", "name,email", {"id": response["user_id"]})[0]
            leaderboard.append({
                "user_name": user["name"],
                "email": user["email"],
                "score": response["score"],
                "submitted_at": response["submitted_at"]
            })
        
        leaderboard.sort(key=lambda x: (-x["score"], x["submitted_at"]))
        
        return {
            "quiz": {
                "id": quiz["id"],
                "title": quiz["title"],
                "is_trivia": quiz["is_trivia"]
            },
            "leaderboard": leaderboard,
            "total_participants": len(leaderboard)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get quiz leaderboard: {str(e)}")

@router.get("/stats/user")
async def get_user_stats(current_user: dict = Depends(get_current_user)):
    """Get user's quiz statistics"""
    try:
        responses = db.select("responses", "*", {"user_id": current_user["id"]})
        
        total_quizzes = len(responses)
        total_score = sum(response["score"] for response in responses)
        
        trivia_stats = {
            "quizzes_attempted": 0,
            "total_score": 0,
            "average_score": 0,
            "best_score": 0,
            "topics_attempted": set()
        }
        
        private_stats = {
            "quizzes_attempted": 0,
            "total_score": 0,
            "average_score": 0,
            "best_score": 0
        }
        
        has_perfect_score = False
        
        for response in responses:
            quiz = db.select("quizzes", "is_trivia,topic,title,positive_mark", {"id": response["quiz_id"]})[0]
            
            questions = db.select("questions", "id", {"quiz_id": response["quiz_id"]})
            max_possible_score = len(questions) * quiz["positive_mark"]
            
            if response["score"] == max_possible_score and max_possible_score > 0:
                has_perfect_score = True
            
            if quiz["is_trivia"]:
                trivia_stats["quizzes_attempted"] += 1
                trivia_stats["total_score"] += response["score"]
                trivia_stats["best_score"] = max(trivia_stats["best_score"], response["score"])
                if quiz["topic"]:
                    trivia_stats["topics_attempted"].add(quiz["topic"])
            else:
                private_stats["quizzes_attempted"] += 1
                private_stats["total_score"] += response["score"]
                private_stats["best_score"] = max(private_stats["best_score"], response["score"])
        
        if trivia_stats["quizzes_attempted"] > 0:
            trivia_stats["average_score"] = trivia_stats["total_score"] / trivia_stats["quizzes_attempted"]
        
        if private_stats["quizzes_attempted"] > 0:
            private_stats["average_score"] = private_stats["total_score"] / private_stats["quizzes_attempted"]
        
        trivia_stats["topics_attempted"] = list(trivia_stats["topics_attempted"])
        
        return {
            "total_quizzes_attempted": total_quizzes,
            "total_score": total_score,
            "trivia_stats": trivia_stats,
            "private_stats": private_stats,
            "has_perfect_score": has_perfect_score
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get user stats: {str(e)}")