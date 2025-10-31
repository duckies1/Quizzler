from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
import requests
import json
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
import os
import app.utils.time_utils 
from google import genai
from dotenv import load_dotenv

def get_ist_time():
    """Get current time in IST"""
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.now(ist)

# IST = get_ist_time()
IST = timezone(timedelta(hours=5, minutes=30))

router = APIRouter()
client = genai.Client(api_key="API_KEY")

# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY1")
# GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"

GEMINI_PROMPT = f"""
You are a QuizBot integrated into a quiz creation platform. 
Your task is to generate multiple-choice questions for a given topic description.

Return ONLY raw JSON — do NOT include ```json``` or markdown fences.
Do not say "Here is your quiz". The response must begin with ( and end with ).


Inputs (ask the user if missing):
- description: str
- number_of_questions: int
- start_time: Optional[str]
- end_time: Optional[str]
- duration: int = 60
- positive_mark: int = 1
- negative_mark: int = 0
- navigation_type: str = "omni" 
- tab_switch_exit: bool = True

Rules for output:
1. Generate 5–10 high-quality MCQs relevant to the quiz description.
2. Each question must strictly follow this structure:

    {{
      "question_text": "string",
      "option_a": "string",
      "option_b": "string",
      "option_c": "string",
      "option_d": "string",
      "correct_option": "a" | "b" | "c" | "d"
    }}

3. The final output must be a valid JSON object matching this schema:

    {{
      "title": "<title derived from description>",
      "description": "<description>",
      "duration": <int>,
      "positive_mark": <int>,
      "negative_mark": <int>,
      "navigation_type": "<string>",
      "tab_switch_exit": <bool>,
      "start_time": "<optional>",
      "end_time": "<optional>",
      "is_trivia": false,
      "questions": [ ...list of questions... ]
    }}

4. Validate:
   - Question text ≤ 500 chars
   - Options ≤ 200 chars
   - Correct option ∈ [a,b,c,d]
5. Do NOT include explanations or commentary.
6. Respond only with valid JSON.
"""


class QuizPrompt(BaseModel):
    description: str
    start_time: str = None
    end_time: str = None
    duration: int = 60
    positive_mark: int = 1
    negative_mark: int = 0
    navigation_type: str = "omni"
    tab_switch_exit: bool = True

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
        
        # current_time = datetime.now(IST)
        
        # start_time = None
        # end_time = None
        
        # if quiz_data.start_time:
        #     start_dt = datetime.fromisoformat(quiz_data.start_time.replace('Z', '+00:00')).astimezone(IST)
            
        #     if not quiz_data.is_trivia and start_dt <= current_time:
        #         raise HTTPException(
        #             status_code=400, 
        #             detail="Start time must be in the future for scheduled quizzes"
        #         )
            
        #     start_time = start_dt.isoformat()
        #     end_dt = start_dt + timedelta(minutes=quiz_data.duration)
        #     end_time = end_dt.isoformat()
            
        # elif quiz_data.end_time:
        #     end_dt = datetime.fromisoformat(quiz_data.end_time.replace('Z', '+00:00')).astimezone(IST)
        #     start_dt = end_dt - timedelta(minutes=quiz_data.duration)
            
        #     if not quiz_data.is_trivia and start_dt <= current_time:
        #         raise HTTPException(
        #             status_code=400, 
        #             detail="Quiz duration too long for the specified end time"
        #         )
            
        #     start_time = start_dt.isoformat()
        #     end_time = end_dt.isoformat()

        current_time = datetime.now(IST)

        start_time = None
        end_time = None

        if quiz_data.start_time:
            start_dt = datetime.fromisoformat(
                quiz_data.start_time.replace('Z', '+00:00')
            ).astimezone(IST)

            if not quiz_data.is_trivia and start_dt <= current_time:
                raise HTTPException(
                    status_code=400,
                    detail="Start time must be in the future for scheduled quizzes"
                )

            start_time = start_dt.isoformat()
            end_dt = start_dt + timedelta(minutes=quiz_data.duration)
            end_time = end_dt.isoformat()

        elif quiz_data.end_time:
            end_dt = datetime.fromisoformat(
                quiz_data.end_time.replace('Z', '+00:00')
            ).astimezone(IST)
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
    


# @router.post("/auto-generate")
# async def auto_generate_quiz(prompt: QuizPrompt, current_user: dict = Depends(get_current_user)):
#     """Generate quiz questions automatically using Gemini"""
#     headers = {"Content-Type": "application/json"}
#     payload = {
#         "contents": [{"parts": [{"text": GEMINI_PROMPT + f"\n\nUser input:\n{prompt.model_dump_json()}"}]}]
#     }

#     res = requests.post(
#         f"{GEMINI_URL}?key={GEMINI_API_KEY}",
#         headers=headers,
#         data=json.dumps(payload)
#     )
    
#     if res.status_code != 200:
#         raise HTTPException(status_code=500, detail=f"Gemini API error: {res.text}")
    
#     data = res.json()
#     quiz_text = data["candidates"][0]["content"]["parts"][0]["text"]

#     try:
#         quiz_json = json.loads(quiz_text)
#     except json.JSONDecodeError:
#         raise HTTPException(status_code=400, detail="Invalid JSON returned by Gemini")

#     # Now call your existing create_quiz function
#     response = await create_quiz(quiz_data=quiz_json, current_user=current_user)
#     return response

import json, re
from fastapi import HTTPException

def clean_gemini_json(raw_text: str):
    """
    Cleans Gemini model output and extracts valid JSON.
    Handles markdown fences, parentheses, and extra text.
    """
    cleaned = raw_text.strip()

    # Remove markdown-style fences (```json ... ```)
    cleaned = re.sub(r"^```(?:json)?|```$", "", cleaned, flags=re.IGNORECASE | re.MULTILINE).strip()

    # Remove surrounding parentheses if present
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = cleaned[1:-1].strip()

    # Extract the first JSON object from the text
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        raise HTTPException(status_code=400, detail=f"Gemini returned no JSON block.\nOutput:\n{raw_text}")

    cleaned = match.group(0)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Gemini returned invalid JSON: {e}\nCleaned Output:\n{cleaned}")


@router.post("/auto-generate")
async def auto_generate_quiz(prompt: QuizPrompt, current_user: dict = Depends(get_current_user)):
    # if current_user is None:
        # Local dev fallback
        # current_user = {"id": "test_user", "email": "test@example.com"}
# async def auto_generate_quiz(prompt: QuizPrompt):
    # current_user = {"id": "3e925f22-4e0d-472f-88d0-ff6e07b8c4ff", "email": "adityatorgal581@gmail.com"}
    """Generate quiz questions automatically using Gemini (official SDK version)"""
    try:
        # Combine system prompt + user input
        full_prompt = GEMINI_PROMPT + f"\n\nUser input:\n{prompt.model_dump_json()}"

        # Call Gemini
        response = client.models.generate_content(
            model="gemini-2.0-flash",  # or "gemini-2.0-pro" for more accuracy
            contents=full_prompt
        )

        quiz_text = response.text.strip()

        # Remove Markdown-style code fences (```json ... ```)
        if quiz_text.startswith("```"):
            quiz_text = quiz_text.strip("`")
            # Remove optional json language tag
            quiz_text = quiz_text.replace("json", "", 1).strip()
            # Remove any remaining triple backticks
            quiz_text = quiz_text.replace("```", "").strip()


        # Try parsing JSON
        try:
            # quiz_json = json.loads(quiz_text)
            quiz_json = clean_gemini_json(response.text)
            quiz_obj = QuizCreate(**quiz_json)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Gemini returned invalid JSON: {str(e)}\nOutput:\n{quiz_text}")

        # ✅ Now reuse your existing create_quiz function
        response = await create_quiz(quiz_data=quiz_obj, current_user=current_user)
        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini quiz generation failed: {str(e)}")
