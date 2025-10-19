from fastapi import APIRouter, Depends, HTTPException
from app.database import db
from app.utils.auth_utils import get_current_user
from uuid import uuid4
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()

class QuizCreate(BaseModel):
    title: str
    description: str
    is_trivia: bool = False
    topic: Optional[str] = None
    duration: int = 60  # minutes
    positive_mark: int = 1
    negative_mark: int = 0
    navigation_type: str = "omni"
    tab_switch_exit: bool = True
    difficulty: Optional[str] = None

@router.post("/")
async def create_quiz(quiz_data: QuizCreate, current_user: dict = Depends(get_current_user)):
    """Create a new quiz"""
    try:
        quiz = {
            "id": str(uuid4()),
            "title": quiz_data.title,
            "description": quiz_data.description,
            "creator_id": current_user["id"],
            "is_trivia": quiz_data.is_trivia,
            "topic": quiz_data.topic,
            "duration": quiz_data.duration,
            "positive_mark": quiz_data.positive_mark,
            "negative_mark": quiz_data.negative_mark,
            "navigation_type": quiz_data.navigation_type,
            "tab_switch_exit": quiz_data.tab_switch_exit,
            "difficulty": quiz_data.difficulty,
            "is_active": True
        }
        
        created_quiz = db.insert("quizzes", quiz)
        return {"quiz_id": created_quiz["id"], "title": created_quiz["title"]}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create quiz: {str(e)}")

@router.get("/")
async def get_my_quizzes(current_user: dict = Depends(get_current_user)):
    """Get current user's quizzes"""
    try:
        quizzes = db.select("quizzes", "*", {"creator_id": current_user["id"]})
        return quizzes
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch quizzes: {str(e)}")

@router.get("/trivia")
async def get_trivia_quizzes(topic: Optional[str] = None, difficulty: Optional[str] = None):
    """Get public trivia quizzes"""
    try:
        filters = {"is_trivia": True, "is_active": True}
        if topic:
            filters["topic"] = topic
        if difficulty:
            filters["difficulty"] = difficulty
            
        quizzes = db.select("quizzes", "*", filters)
        return quizzes
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch trivia quizzes: {str(e)}")