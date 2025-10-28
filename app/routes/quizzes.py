from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from app.database import db
from app.utils.auth_utils import get_current_user, require_admin, is_admin_user
from uuid import uuid4
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import pytz
import csv
import io

router = APIRouter()
IST = pytz.timezone('Asia/Kolkata')

class QuestionCreate(BaseModel):
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str  # 'a', 'b', 'c', 'd'
    
    def validate_lengths(self):
        if len(self.question_text) > 500:
            raise ValueError("Question text cannot exceed 500 characters")
        if len(self.option_a) > 200:
            raise ValueError("Option A cannot exceed 200 characters")
        if len(self.option_b) > 200:
            raise ValueError("Option B cannot exceed 200 characters")
        if len(self.option_c) > 200:
            raise ValueError("Option C cannot exceed 200 characters")
        if len(self.option_d) > 200:
            raise ValueError("Option D cannot exceed 200 characters")
        if self.correct_option not in ['a', 'b', 'c', 'd']:
            raise ValueError("Correct option must be 'a', 'b', 'c', or 'd'")

class QuizCreate(BaseModel):
    title: str
    description: str
    is_trivia: bool = False
    topic: Optional[str] = None
    start_time: Optional[str] = None 
    end_time: Optional[str] = None   
    duration: int = 60  
    positive_mark: int = 1
    negative_mark: int = 0  
    navigation_type: str = "omni"
    tab_switch_exit: bool = True
    difficulty: Optional[str] = None
    questions: List[QuestionCreate] = []

@router.post("/")
async def create_quiz(quiz_data: QuizCreate, current_user: dict = Depends(get_current_user)):
    """Create a new quiz"""
    try:
        if len(quiz_data.questions) > 50:
            raise HTTPException(status_code=400, detail="Maximum 50 questions allowed per quiz")

        for i, question in enumerate(quiz_data.questions):
            try:
                question.validate_lengths()
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Question {i+1}: {str(e)}")
        
        if quiz_data.is_trivia:
            if not is_admin_user(current_user):
                raise HTTPException(status_code=403, detail="Only admins can create trivia quizzes")
        
        current_time = datetime.now(IST)
        
        start_time = None
        end_time = None
        
        if quiz_data.start_time:
            start_dt = datetime.fromisoformat(quiz_data.start_time.replace('Z', '+00:00')).astimezone(IST)
            
            if not quiz_data.is_trivia and start_dt <= current_time:
                raise HTTPException(
                    status_code=400, 
                    detail="Start time must be in the future for scheduled quizzes"
                )
            
            start_time = start_dt.isoformat()
            end_dt = start_dt + timedelta(minutes=quiz_data.duration)
            end_time = end_dt.isoformat()
            
        elif quiz_data.end_time:
            end_dt = datetime.fromisoformat(quiz_data.end_time.replace('Z', '+00:00')).astimezone(IST)
            start_dt = end_dt - timedelta(minutes=quiz_data.duration)
            
            if not quiz_data.is_trivia and start_dt <= current_time:
                raise HTTPException(
                    status_code=400, 
                    detail="Quiz duration too long for the specified end time"
                )
            
            start_time = start_dt.isoformat()
            end_time = end_dt.isoformat()
            
        
        quiz = {
            "id": str(uuid4()),
            "title": quiz_data.title,
            "description": quiz_data.description,
            "creator_id": current_user["id"],
            "is_trivia": quiz_data.is_trivia,
            "topic": quiz_data.topic if quiz_data.is_trivia else None, 
            "start_time": start_time,
            "end_time": end_time,
            "duration": quiz_data.duration,
            "positive_mark": quiz_data.positive_mark,
            "negative_mark": quiz_data.negative_mark,
            "navigation_type": quiz_data.navigation_type,
            "tab_switch_exit": quiz_data.tab_switch_exit,
            "difficulty": quiz_data.difficulty if quiz_data.is_trivia else None, 
            "popularity": 0,
            "is_active": True,
            "created_at": datetime.now(IST).isoformat()
        }
        
        created_quiz = db.insert("quizzes", quiz)
        
        if quiz_data.questions:
            for question_data in quiz_data.questions:
                question = {
                    "quiz_id": created_quiz["id"],
                    "question_text": question_data.question_text,
                    "option_a": question_data.option_a,
                    "option_b": question_data.option_b,
                    "option_c": question_data.option_c,
                    "option_d": question_data.option_d,
                    "correct_option": question_data.correct_option,
                    "mark": quiz_data.positive_mark
                }
                db.insert("questions", question)
        
        return {"quiz_id": created_quiz["id"], "title": created_quiz["title"]}
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "unique_trivia_title_topic" in error_msg or "duplicate key value" in error_msg:
            if quiz_data.is_trivia:
                raise HTTPException(
                    status_code=400, 
                    detail=f"A trivia quiz with the title '{quiz_data.title}' and topic '{quiz_data.topic}' already exists. Please choose a different title or topic."
                )
            else:
                raise HTTPException(
                    status_code=400, 
                    detail="A quiz with this title already exists. Please choose a different title."
                )
        raise HTTPException(status_code=400, detail=f"Failed to create quiz: {error_msg}")

@router.get("/")
async def get_my_quizzes(current_user: dict = Depends(get_current_user)):
    """Get current user's created private quizzes"""
    try:
        created_quizzes = db.select("quizzes", "*", {"creator_id": current_user["id"], "is_trivia": False})
        
        current_time = datetime.now(IST)
        for quiz in created_quizzes:
            if quiz.get("start_time") and quiz.get("end_time"):
                start_time = datetime.fromisoformat(quiz["start_time"])
                end_time = datetime.fromisoformat(quiz["end_time"])
                
                if current_time < start_time:
                    quiz["status"] = "assigned"
                elif start_time <= current_time <= end_time:
                    quiz["status"] = "active"
                else:
                    quiz["status"] = "ended"
            else:
                quiz["status"] = "active"
        
        return created_quizzes
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch quizzes: {str(e)}")

@router.get("/trivia")
async def get_trivia_quizzes(
    topic: Optional[str] = Query(None, description="Filter by topic"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty"),
    sort_by: str = Query("popularity", description="Sort by: popularity, difficulty, recent")
):
    """Get public trivia quizzes with sorting and filtering"""
    try:
        filters = {"is_trivia": True, "is_active": True}
        if topic:
            filters["topic"] = topic
        if difficulty:
            filters["difficulty"] = difficulty
            
        quizzes = db.select("quizzes", "*", filters)
        
        if sort_by == "popularity":
            quizzes.sort(key=lambda x: x.get("popularity", 0), reverse=True)
        elif sort_by == "recent":
            quizzes.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        elif sort_by == "difficulty":
            difficulty_order = {"easy": 1, "medium": 2, "hard": 3}
            quizzes.sort(key=lambda x: difficulty_order.get(x.get("difficulty", "medium"), 2))
        
        return quizzes
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch trivia quizzes: {str(e)}")

@router.get("/{quiz_id}")
async def get_quiz_details(quiz_id: str, current_user: dict = Depends(get_current_user)):
    """Get quiz details (without questions/answers) - anyone with quiz ID can access"""
    try:
        quizzes = db.select("quizzes", "*", {"id": quiz_id, "is_active": True})
        if not quizzes:
            raise HTTPException(status_code=404, detail="Quiz not found")
        
        quiz = quizzes[0]
        
        if not quiz["is_trivia"]:
            current_time = datetime.now(IST)
            
            if quiz.get("start_time") and quiz.get("end_time"):
                start_time = datetime.fromisoformat(quiz["start_time"])
                end_time = datetime.fromisoformat(quiz["end_time"])
                
                if current_time < start_time:
                    quiz["status"] = "assigned"  
                elif start_time <= current_time <= end_time:
                    quiz["status"] = "active"    
                else:
                    quiz["status"] = "ended"    
            else:
                quiz["status"] = "active"
        else:
            quiz["status"] = "active"
        
        questions = db.select("questions", "id", {"quiz_id": quiz_id})
        quiz["question_count"] = len(questions)
        
        return quiz
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get quiz details: {str(e)}")

@router.get("/topics/list")
async def get_available_topics():
    """Get list of available topics for trivia quizzes"""
    try:
        quizzes = db.select("quizzes", "topic", {"is_trivia": True, "is_active": True})
        topics = list(set(quiz["topic"] for quiz in quizzes if quiz.get("topic")))
        return {"topics": topics}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get topics: {str(e)}")

@router.post("/import-questions")
async def import_questions_from_csv(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Import questions from a CSV file"""
    try:
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="Only CSV files are allowed")
        
        content = await file.read()
        csv_content = content.decode('utf-8')
        
        csv_reader = csv.reader(io.StringIO(csv_content))
        headers = next(csv_reader)  
        
        expected_headers = ['question_text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_option']
        if headers != expected_headers:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid CSV format. Expected headers: {', '.join(expected_headers)}"
            )
        
        questions = []
        row_number = 1 
        
        for row in csv_reader:
            row_number += 1
            
            if len(row) != 6:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Row {row_number}: Invalid number of columns. Expected 6, got {len(row)}"
                )
            
            question_text, option_a, option_b, option_c, option_d, correct_option = row
            
            try:
                question = QuestionCreate(
                    question_text=question_text.strip(),
                    option_a=option_a.strip(),
                    option_b=option_b.strip(),
                    option_c=option_c.strip(),
                    option_d=option_d.strip(),
                    correct_option=correct_option.strip().lower()
                )
                question.validate_lengths()
                questions.append(question)
            except ValueError as e:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Row {row_number}: {str(e)}"
                )
            
            if len(questions) > 50:
                raise HTTPException(
                    status_code=400, 
                    detail="Maximum 50 questions allowed per quiz"
                )
        
        if not questions:
            raise HTTPException(status_code=400, detail="No valid questions found in the CSV file")
        
        questions_data = []
        for i, q in enumerate(questions):
            questions_data.append({
                "id": f"import_{i}",  
                "question_text": q.question_text,
                "option_a": q.option_a,
                "option_b": q.option_b,
                "option_c": q.option_c,
                "option_d": q.option_d,
                "correct_option": q.correct_option
            })
        
        return {
            "message": f"Successfully imported {len(questions)} questions",
            "questions": questions_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to import questions: {str(e)}")