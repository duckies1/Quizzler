from fastapi import APIRouter, Depends, HTTPException, Query
from app.database import db
from app.utils.auth_utils import get_current_user, require_admin, is_admin_user
from uuid import uuid4
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import pytz

router = APIRouter()
IST = pytz.timezone('Asia/Kolkata')

class QuestionCreate(BaseModel):
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    correct_option: str  # 'a', 'b', 'c', 'd'
    mark: Optional[int] = None

class QuizCreate(BaseModel):
    title: str
    description: str
    is_trivia: bool = False
    topic: Optional[str] = None
    start_time: Optional[str] = None  # ISO format datetime string
    end_time: Optional[str] = None    # ISO format datetime string
    duration: int = 60  # minutes
    positive_mark: int = 1
    negative_mark: int = 0
    navigation_type: str = "omni"
    tab_switch_exit: bool = True
    difficulty: Optional[str] = None
    questions: List[QuestionCreate] = []

class InviteUsers(BaseModel):
    emails: List[str]

@router.post("/")
async def create_quiz(quiz_data: QuizCreate, current_user: dict = Depends(get_current_user)):
    """Create a new quiz"""
    try:
        # If it's a trivia quiz, check admin privileges
        if quiz_data.is_trivia:
            if not is_admin_user(current_user):
                raise HTTPException(status_code=403, detail="Only admins can create trivia quizzes")
        
        current_time = datetime.now(IST)
        
        # Convert datetime strings to IST if provided and validate scheduling
        start_time = None
        end_time = None
        
        if quiz_data.start_time:
            start_dt = datetime.fromisoformat(quiz_data.start_time.replace('Z', '+00:00')).astimezone(IST)
            
            # Validate that start_time is in the future for private quizzes
            if not quiz_data.is_trivia and start_dt <= current_time:
                raise HTTPException(
                    status_code=400, 
                    detail="Start time must be in the future for scheduled quizzes"
                )
            
            start_time = start_dt.isoformat()
            # Auto-calculate end_time = start_time + duration
            end_dt = start_dt + timedelta(minutes=quiz_data.duration)
            end_time = end_dt.isoformat()
            
        elif quiz_data.end_time:
            # If only end_time is provided, calculate start_time
            end_dt = datetime.fromisoformat(quiz_data.end_time.replace('Z', '+00:00')).astimezone(IST)
            start_dt = end_dt - timedelta(minutes=quiz_data.duration)
            
            # Validate that calculated start_time is in the future
            if not quiz_data.is_trivia and start_dt <= current_time:
                raise HTTPException(
                    status_code=400, 
                    detail="Quiz duration too long for the specified end time"
                )
            
            start_time = start_dt.isoformat()
            end_time = end_dt.isoformat()
            
        # For trivia quizzes, no scheduling required (always available)
        
        quiz = {
            "id": str(uuid4()),
            "title": quiz_data.title,
            "description": quiz_data.description,
            "creator_id": current_user["id"],
            "is_trivia": quiz_data.is_trivia,
            "topic": quiz_data.topic,
            "start_time": start_time,
            "end_time": end_time,
            "duration": quiz_data.duration,
            "positive_mark": quiz_data.positive_mark,
            "negative_mark": quiz_data.negative_mark,
            "navigation_type": quiz_data.navigation_type,
            "tab_switch_exit": quiz_data.tab_switch_exit,
            "difficulty": quiz_data.difficulty,
            "popularity": 0,
            "is_active": True,
            "created_at": datetime.now(IST).isoformat()
        }
        
        created_quiz = db.insert("quizzes", quiz)
        
        # Create questions if provided
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
                    "mark": question_data.mark or quiz_data.positive_mark
                }
                db.insert("questions", question)
        
        return {"quiz_id": created_quiz["id"], "title": created_quiz["title"]}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create quiz: {str(e)}")

@router.get("/")
async def get_my_quizzes(current_user: dict = Depends(get_current_user)):
    """Get current user's available private quizzes (invited or created)"""
    try:
        # Get quizzes created by the user
        created_quizzes = db.select("quizzes", "*", {"creator_id": current_user["id"], "is_trivia": False})
        
        # Get quizzes the user is invited to (check invites table)
        invited_quizzes = []
        try:
            invites = db.select("invites", "quiz_id", {"email": current_user["email"]})
            for invite in invites:
                quiz = db.select("quizzes", "*", {"id": invite["quiz_id"], "is_trivia": False, "is_active": True})
                if quiz:
                    invited_quizzes.extend(quiz)
        except:
            # Invites table might not exist yet, ignore
            pass
        
        # Combine and remove duplicates
        all_quizzes = created_quizzes + invited_quizzes
        unique_quizzes = {quiz["id"]: quiz for quiz in all_quizzes}.values()
        
        return list(unique_quizzes)
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
        
        # Sort quizzes based on sort_by parameter
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
    """Get quiz details (without questions/answers)"""
    try:
        quizzes = db.select("quizzes", "*", {"id": quiz_id, "is_active": True})
        if not quizzes:
            raise HTTPException(status_code=404, detail="Quiz not found")
        
        quiz = quizzes[0]
        
        # Check if user has access to this quiz
        if not quiz["is_trivia"]:
            # For private quiz, check if user is creator or invited
            if quiz["creator_id"] != current_user["id"]:
                try:
                    invites = db.select("invites", "*", {"quiz_id": quiz_id, "email": current_user["email"]})
                    if not invites:
                        raise HTTPException(status_code=403, detail="You don't have access to this quiz")
                except:
                    # If invites table doesn't exist, only creator can access
                    raise HTTPException(status_code=403, detail="You don't have access to this quiz")
        
        # Get question count
        questions = db.select("questions", "id", {"quiz_id": quiz_id})
        quiz["question_count"] = len(questions)
        
        return quiz
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get quiz details: {str(e)}")

@router.post("/{quiz_id}/invite")
async def invite_users(quiz_id: str, invite_data: InviteUsers, current_user: dict = Depends(get_current_user)):
    """Invite users to a private quiz"""
    try:
        # Check if quiz exists and user is the creator
        quizzes = db.select("quizzes", "*", {"id": quiz_id, "creator_id": current_user["id"]})
        if not quizzes:
            raise HTTPException(status_code=404, detail="Quiz not found or you're not the creator")
        
        quiz = quizzes[0]
        if quiz["is_trivia"]:
            raise HTTPException(status_code=400, detail="Cannot invite users to trivia quizzes")
        
        # Create invites table if it doesn't exist (handle via try-catch)
        invited_emails = []
        for email in invite_data.emails:
            try:
                invite = {
                    "quiz_id": quiz_id,
                    "email": email,
                    "invited_by": current_user["id"],
                    "invited_at": datetime.now(IST).isoformat()
                }
                db.insert("invites", invite)
                invited_emails.append(email)
            except Exception as e:
                # If insert fails, it might be duplicate or table issue
                continue
        
        return {
            "message": f"Invitations sent to {len(invited_emails)} users",
            "invited_emails": invited_emails,
            "quiz_title": quiz["title"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to send invitations: {str(e)}")

@router.get("/topics/list")
async def get_available_topics():
    """Get list of available topics for trivia quizzes"""
    try:
        quizzes = db.select("quizzes", "topic", {"is_trivia": True, "is_active": True})
        topics = list(set(quiz["topic"] for quiz in quizzes if quiz.get("topic")))
        return {"topics": topics}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get topics: {str(e)}")